"""TestHub AI 协作者 —— 基于 OpenAI Agents SDK 的对话式 AI 协作者。

替代旧版 Qwen-Agent FnCallAgent：
- 模型不绑定，由 sdk_runtime 按 AgentConfig 构建（Responses 优先，失败降级 Chat Completions）；
- 上下文经 RunContext[TestHubContext] 注入工具，删除 thread-local；
- 流式事件直接映射 SDK 类型化事件，删除手工 delta 拼接与 XML 清洗。
"""
from __future__ import annotations

import json
import logging
import re
import asyncio
import queue as _queue
import threading
from typing import Any, Dict, Iterator, List, Optional

from agents import (
    MaxTurnsExceeded,
    RawResponsesStreamEvent,
    RunItemStreamEvent,
    Runner,
)

from apps.assistant import sdk_runtime
from apps.assistant import tools as toolkit
from apps.assistant.context import TestHubContext

logger = logging.getLogger(__name__)


class TestHubAgent:
    """
    TestHub AI 协作者

    使用 OpenAI Agents SDK 作为推理编排引擎，
    通过自定义 function tool 操作 TestHub 的业务数据。
    """

    # System Prompt 模板
    SYSTEM_PROMPT_TEMPLATE = """你是 TestHub 的 AI 测试协作者，帮助用户高效管理 API 接口测试和测试用例。

## ⚠️ 关键规则（必须严格遵守）

### 1. 禁止编造数据
- **绝对禁止**在没有调用 Tool 的情况下声称"已创建"、"已删除"、"已修改"、"已完成"
- **绝对禁止**编造任何 ID、名称、数量、状态、时间戳等具体数据
- **绝对禁止**美化或掩盖 Tool 返回的错误信息
- 如果 Tool 返回 success=false 或 error，必须**如实逐字报告**错误内容
- 不确定的参数值必须询问用户，**禁止猜测后直接调用**

### 2. 操作流程
- 创建/修改/删除操作：必须调用对应 Tool → 等待 Tool 返回结果 → 根据真实结果回复
- 查询操作：必须调用对应 Tool → 等待 Tool 返回数据 → 基于真实数据回复
- Tool 返回之前，只能说"正在执行..."，**不能说"已完成"**

### 3. 数据真实性
- 你回复中的每一个 ID、数字、名称、状态都必须来自 Tool 的实际返回
- 如果 Tool 返回空列表，你应该说"未找到相关数据"，而不是编造几条示例
- 不要描述"假设"或"示例"数据来冒充真实数据

## 你的能力
- 通过 MCP 加载的浏览器工具（如 Playwright）访问和操作网页（如果已启用）
- 搜索和查看项目的接口定义（支持按名称、URL、方法搜索）
- 获取接口的完整详情（参数、请求头、请求体、断言规则）
- 创建新的 API 接口测试（含断言配置）
- 创建接口集合（用于分组管理）
- 执行接口请求并查看响应结果
- 读取文档文件内容（支持 PDF/Word/Excel/TXT/HTML/CSV）
- 解析 Swagger/OpenAPI 或 YApi 文档，自动提取接口列表。如果用户上传了 JSON/YAML 文件，直接调 parse_swagger/file_path 或 parse_yapi/file_path，不要用 simple_doc_parser
- 搜索和创建测试用例
- 查看和修改 Midscene（AI智能模式）用例（AI Prompt 每行一个步骤，换行分隔，不使用 → 箭头）

## 当前项目上下文
{project_context}

## 输出格式
- 列表数据必须使用 **Markdown 管道表格**，格式如下（必须有表头分隔行）：
  ```
  | 列1 | 列2 | 列3 |
  |-----|-----|-----|
  | 值1 | 值2 | 值3 |
  ```
- 禁止使用空格/制表符对齐的纯文本表格
- 代码块使用 ``` 包裹

## 工作原则
1. 操作各模块数据前，先用 list_xxx 工具发现可用项目，不要依赖名字猜测
2. 每次操作前先向用户确认关键信息（如接口名称、参数等）
3. 创建接口测试时务必包含异常场景的断言
4. 回复简洁清晰，用中文
5. 批量操作时先告知用户影响范围
"""

    def __init__(
        self,
        user=None,
        project_id: Optional[int] = None,
        llm_config: Optional[Dict[str, Any]] = None,
        tools: Optional[List[str]] = None,
        session_id: str = "",
    ):
        """
        初始化 Agent

        Args:
            user: Django User 对象，用于权限控制和 created_by 字段
            project_id: 当前主项目 ID
            llm_config: LLM 配置字典；为 None 时从数据库 AgentConfig 读取
            tools: 要启用的工具名称列表；None 表示启用全部注册工具
            session_id: 当前会话 ID（文件工具按会话隔离）
        """
        self.user = user
        self.project_id = project_id
        self.llm_config = llm_config or sdk_runtime.load_llm_config()
        # 兼容 views.test_agent 的展示字段
        self.llm_config.setdefault(
            "model_server",
            self.llm_config.get("base_url") or self.llm_config.get("provider") or "",
        )
        self.tool_names = tools
        if self.tool_names is None:
            groups = self.llm_config.get("tool_groups") or []
            if groups:
                self.tool_names = toolkit.resolve_tool_names(groups)
        self.session_id = session_id or ""
        self.max_tool_calls = self.llm_config.get("max_tool_calls", 20)

    # ---------------------------------------------------------------
    # 上下文
    # ---------------------------------------------------------------

    @property
    def context(self) -> TestHubContext:
        return TestHubContext(
            user=self.user,
            user_id=self.user.id if self.user else 0,
            project_id=self.project_id,
            session_id=self.session_id,
        )

    # ---------------------------------------------------------------
    # System Prompt
    # ---------------------------------------------------------------

    def _load_skills_prompt(self) -> str:
        """Skills 摘要：仅返回名字列表，节省 token。"""
        try:
            from apps.assistant.skill_loader import build_skills_prompt

            return build_skills_prompt()
        except Exception as e:
            logger.warning(f"Failed to load skills: {e}")
            return ""

    @staticmethod
    def _load_skills_instructions(skill_names: list) -> str:
        """展开指定 Skill 的完整指令（/skill:name 触发时调用）。"""
        try:
            from apps.assistant.skill_loader import build_skills_prompt

            return build_skills_prompt(filter_names=skill_names)
        except Exception:
            return ""

    def _build_system_prompt(self) -> str:
        """根据项目上下文构建 system prompt。"""
        project_context = "未指定项目"

        if self.project_id:
            try:
                from apps.projects.models import Project
                from apps.testcases.models import TestCase
                from apps.api_testing.models import ApiProject, ApiRequest

                project = Project.objects.get(id=self.project_id)
                testcase_count = TestCase.objects.filter(project_id=self.project_id).count()

                api_projects = ApiProject.objects.filter(main_project=project)
                api_count = 0
                collection_count = 0
                for ap in api_projects[:5]:
                    api_count += ApiRequest.objects.filter(collection__project=ap).count()
                    collection_count += ap.collections.count()

                ui_count = 0
                ui_suite_count = 0
                try:
                    from apps.ui_automation.models import (
                        UiProject,
                        TestScript as UIScript,
                        TestSuite as UITestSuite,
                    )

                    for up in UiProject.objects.filter(main_project=project)[:5]:
                        ui_count += UIScript.objects.filter(project=up).count()
                        ui_suite_count += UITestSuite.objects.filter(project=up).count()
                except Exception:
                    pass

                midscene_count = 0
                midscene_device_count = 0
                try:
                    from apps.ui_automation.models import (
                        MidsceneProject,
                        MidsceneCase,
                        MidsceneDevice,
                    )

                    for m in MidsceneProject.objects.filter(main_project=project)[:5]:
                        midscene_count += MidsceneCase.objects.filter(project=m).count()
                    midscene_device_count = MidsceneDevice.objects.filter(status="online").count()
                except Exception:
                    pass

                project_context = f"""项目名称: {project.name} (project_id={project.id})
项目状态: {project.get_status_display()}
项目描述: {project.description or '无'}

模块概况:
- 测试用例: {testcase_count} 条
- 接口测试: {api_count} 个接口, {collection_count} 个集合
- UI自动化: {ui_count} 个脚本, {ui_suite_count} 个套件
- AI智能模式(Midscene): {midscene_count} 个用例, {midscene_device_count} 台在线设备
- 知识库: {'已配置' if project.knowledge_base else '未配置'}

你可以操作测试用例、接口测试、UI自动化、AI智能模式(Midscene)等所有模块的数据。"""
            except Exception as e:
                logger.warning(f"Failed to build project context: {e}")
                project_context = f"(project_id={self.project_id})"

        skills_prompt = self._load_skills_prompt()
        extra = self.llm_config.get("system_prompt_extra") or ""
        return self.SYSTEM_PROMPT_TEMPLATE.format(project_context=project_context) + skills_prompt + ("\n" + extra if extra else "")

    # ---------------------------------------------------------------
    # Agent 构建与运行
    # ---------------------------------------------------------------

    async def _create_agent(self):
        """构建 SDK Agent（工具来自声明式注册表）。"""
        if self.tool_names:
            tools = [toolkit.TOOL_REGISTRY[n] for n in self.tool_names if n in toolkit.TOOL_REGISTRY]
        else:
            tools = toolkit.get_registered_tools()
        return await sdk_runtime.build_agent(
            self.llm_config, self._build_system_prompt(), tools
        )

    async def _achat(
        self, message: str, history: Optional[List[Dict[str, str]]] = None
    ):
        """异步对话主流程：Runner.run_streamed + 事件适配。"""
        agent = await self._create_agent()

        messages: List[Dict[str, Any]] = list(history or [])
        messages.append({"role": "user", "content": message})

        logger.info(
            f'Agent chat: "{message[:100]}..." with {len(messages)} messages '
            f"(max_turns={self.max_tool_calls})"
        )

        result = Runner.run_streamed(
            agent,
            input=messages,
            context=self.context,
            max_turns=self.max_tool_calls,
        )

        full_text = ""
        tool_calls: List[str] = []
        exceeded = False

        try:
            async for event in result.stream_events():
                if isinstance(event, RunItemStreamEvent):
                    if event.name == "tool_called":
                        item = event.item
                        raw = getattr(item, "raw_item", None)
                        call_id = getattr(raw, "id", "") or ""
                        name = getattr(raw, "name", "") or ""
                        raw_args = getattr(raw, "arguments", "")
                        try:
                            args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                        except Exception:
                            args = raw_args
                        tool_calls.append(name)
                        logger.info(f"[Agent] TOOL CALL: {name}")
                        yield {"type": "tool_start", "id": call_id, "name": name, "args": args}

                    elif event.name == "tool_output":
                        item = event.item
                        raw = getattr(item, "raw_item", None)
                        output = getattr(raw, "output", "")
                        # Responses 模式下 output 可能是内容片段列表，统一展平为文本
                        if isinstance(output, list):
                            parts = []
                            for p in output:
                                if isinstance(p, dict):
                                    parts.append(str(p.get("text", "")))
                                else:
                                    parts.append(str(p))
                            output = "".join(parts)
                        output_str = str(output)[:800] if output is not None else ""
                        yield {
                            "type": "tool_output",
                            "id": getattr(raw, "id", "") or "",
                            "name": getattr(raw, "name", "") or "",
                            "output": output_str,
                        }

                elif isinstance(event, RawResponsesStreamEvent):
                    data = event.data
                    dtype = getattr(data, "type", "")
                    if dtype == "response.output_text.delta":
                        delta = getattr(data, "delta", "") or ""
                        if delta:
                            full_text += delta
                            yield {"type": "message_delta", "content": delta}

            final_output = getattr(result, "final_output", None)
            final_text = str(final_output) if final_output else full_text
            yield {
                "type": "run_done",
                "final_output": final_text,
                "tool_calls": tool_calls,
                "max_turns_exceeded": exceeded,
            }

        except MaxTurnsExceeded:
            exceeded = True
            logger.warning(f"Agent hit max_turns limit: {self.max_tool_calls}")
            yield {
                "type": "error",
                "content": f"已超过单轮最大轮数限制（{self.max_tool_calls}），任务较大可调整 Agent 配置中的最大调用次数，或分步执行。",
            }
            yield {
                "type": "run_done",
                "final_output": full_text,
                "tool_calls": tool_calls,
                "max_turns_exceeded": True,
            }

        except Exception as e:
            logger.error(f"Agent run failed: {e}", exc_info=True)
            yield {"type": "error", "content": f"Agent 处理出错: {e}"}
            yield {
                "type": "run_done",
                "final_output": full_text,
                "tool_calls": tool_calls,
                "error": True,
            }

    # ---------------------------------------------------------------
    # 对外对话接口（同步生成器，SSE 视图直接消费）
    # ---------------------------------------------------------------

    def chat(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Iterator[Dict[str, Any]]:
        """
        对话入口（同步流式生成器）。

        Yields:
            - {'type': 'message_delta', 'content': '...'}  文本增量
            - {'type': 'tool_start', 'id', 'name', 'args'} 工具调用开始
            - {'type': 'tool_output', 'id', 'name', 'output'} 工具返回
            - {'type': 'run_done', 'final_output', 'tool_calls'} 完成
            - {'type': 'error', 'content': '...'}          错误
        """
        # 检测 /skill:name 调用，展开完整指令拼到用户消息前
        skill_names = re.findall(r"/skill:(\S+)", message)
        if skill_names:
            skill_instructions = self._load_skills_instructions(skill_names)
            if skill_instructions:
                message = skill_instructions + "\n\n---\n用户消息:\n" + message
                logger.info(f"Skills expanded: {skill_names}")

        # 同步桥：把异步生成器放进独立线程的事件循环，事件经队列回传。
        # （asgiref.async_to_sync 不支持 async generator，故手动桥接）
        sentinel = object()
        events: _queue.Queue = _queue.Queue()

        def _run() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:

                async def _consume() -> None:
                    async for ev in self._achat(message, history):
                        events.put(ev)

                loop.run_until_complete(_consume())
            except Exception as e:
                logger.error(f"Agent bridge error: {e}", exc_info=True)
                events.put({"type": "error", "content": f"Agent 处理出错: {e}"})
                events.put({"type": "run_done", "final_output": "", "tool_calls": []})
            finally:
                events.put(sentinel)
                loop.close()

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        while True:
            ev = events.get()
            if ev is sentinel:
                break
            yield ev

    def chat_sync(self, message: str, history: Optional[List[Dict]] = None) -> str:
        """同步对话（非流式），返回完整回复文本。"""
        full_response = []
        for event in self.chat(message, history):
            if event["type"] == "message_delta":
                full_response.append(event["content"])
        return "".join(full_response)

    def set_project(self, project_id: int):
        """切换当前项目上下文（SDK Agent 无状态，无需清理缓存）。"""
        self.project_id = project_id
