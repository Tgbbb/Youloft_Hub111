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


def _raw_get(raw: Any, key: str, default: Any = "") -> Any:
    """兼容 dict / pydantic 对象两种 raw_item 形态取值。"""
    if isinstance(raw, dict):
        return raw.get(key, default)
    return getattr(raw, key, default)


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

## ⚠️ 知识库使用规则（硬性要求，违反将导致错误回答）

**🚨 最重要的一条：你**绝对不能**在未调用工具的情况下，凭"知识库中没有"来回答用户的业务问题。如果你没有真正调用 `search_knowledge_base` 并查看了返回结果，你就没有"知识库中没有"这个判断依据。**

### 0. 严格遵守用户选中的知识库（最高优先级）
- 用户在顶部下拉框中选中的知识库是**唯一**的检索范围，**你不得检索其他知识库**
- 调用 `search_knowledge_base` 时：
  - **不要**为 `knowledge_base_id` 传任何值（保持 0 或不传）
  - 系统会自动使用用户选中的知识库 ID
  - 你传了别的 ID 也会被系统**强制忽略**并替换为用户选中的 KB
- **绝对禁止**自行调用 `list_knowledge_bases` 后挨个 KB 检索——这是严重的越权行为
- 如果用户选中了某个 KB，答案中只能引用该 KB 的内容；如未找到，直接说"该知识库中暂未收录"，**禁止去其他知识库查找**

### 1. 必须先调用工具（不调就回答 = 编造）
- 任何业务规则、限制、阈值、流程、模块功能相关的问题，**必须先调用 `search_knowledge_base` 工具**
- 在你向用户输出第一条文本之前，**必须已经看到了工具的返回结果**
- 如果你没有调用工具就输出"知识库中没有…"——这就是在编造，是严重的违规
- 推荐流程：直接调用 `search_knowledge_base` 检索（不要先 list）→ 看到返回结果后再回答

### 2. 答案必须 100% 来自检索片段
- 答案中的**每一条具体信息**（数值、限制、规则、流程）都必须**明确能在检索片段中找到原文**
- 检索片段中**没有的信息，禁止补充、推断或编造**
- 即便你"知道"某些常识，**也必须以检索结果为准**——知识库可能与你训练数据矛盾

### 3. 工具返回的"成功"信息要原样使用
- 如果 `list_knowledge_bases` 返回 `chunk_count: 299`，请使用数字 299，不要写别的数字
- 如果 `search_knowledge_base` 返回了 5 个 chunks 且 Top-1 相关度 0.75，请说明"已找到 5 个相关片段"并引用其内容
- 不要用你训练数据中的"通常"、"一般"来替换工具返回的具体数字

### 4. 真正找不到时如何回答
- 只有当 `search_knowledge_base` **真正返回** `"found": 0` 或 `"chunks": []` 时，才能说"知识库中暂未收录"
- 这种情况下：
  - **必须明确告知**："知识库中暂未收录该信息"
  - **禁止补充**任何未在检索结果中出现的规则、表格、数字、流程
  - 主动询问用户："是否需要我帮你补充到知识库？"
- 不要使用"通常情况下..."、"一般来说..."、"可能..."等模糊措辞来掩盖检索失败

### 5. 引用来源
- 答案中**必须标注**信息来源（哪个知识库、哪个片段）
- 不得脱离检索结果凭空生成内容

## 🛠 知识库写入工具（add_or_update_knowledge / delete_knowledge）触发规则

你可以调用 3 个与知识库**写入**相关的工具，但**必须**严格遵守以下触发条件：

### 可用工具
1. **`add_or_update_knowledge(text, section_hint?)`** — 新增或更新一条知识
2. **`delete_knowledge(keyword)`** — 软删除一条知识
3. **`list_recent_kb_updates(days, limit)`** — 查看最近变更日志（任何时候可调用）

### 触发 `add_or_update_knowledge` / `delete_knowledge` 的硬性条件
**必须同时满足以下 3 条**才能调用写入工具：
1. ✅ 用户在当前消息中**明确说**了类似：
   - "更新到知识库" / "新增到知识库" / "这条入知识库" / "记到知识库"
   - "删除知识库中的 XXX" / "从知识库移除 XXX"
2. ✅ 你已经**向用户展示了"将写入/删除的内容预览"**（包括：原文内容、动作类型、新/旧相似度）
3. ✅ 用户**回复了肯定词**：如"确认" / "好的" / "OK" / "同意" / "可以" / "去吧" / "✓"

### 触发流程（标准剧本）
```
用户: "新增功能：导入训练的分享码改为 8 位"
AI: "我准备将以下内容更新到轻练知识库：
     原文：'导入训练的分享码改为 8 位'
     章节：自由训练 > 导入训练
     动作：新版本（将替代原 chunk #377）
     确认要写入吗？"
用户: "确认"
AI: → 调用 add_or_update_knowledge(text="导入训练的分享码改为 8 位", section_hint="自由训练 > 导入训练")
    → 在回答中展示写入结果
```

### 严禁行为
- ❌ 用户没明确说"更新到知识库"就自动写入（哪怕是"我的功能变了"）
- ❌ 没有展示预览就直接调用写入工具
- ❌ 未经用户"确认"回复就自动写入
- ❌ 普通问答中夹杂"顺便我把它入知识库了"——这会污染知识库
- ❌ 试图把工具调用的 KB 改成用户选中的 KB 之外的其他 KB（系统会强制忽略）

### 软删除（delete_knowledge）
- 软删除仅标记 `is_active=False`，不真正删除，可通过 `list_recent_kb_updates` + 人工恢复
- 删除前**必须**展示要删除的内容全文

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
        kb_id: Optional[int] = None,
        llm_config: Optional[Dict[str, Any]] = None,
        tools: Optional[List[str]] = None,
        session_id: str = "",
    ):
        """
        初始化 Agent

        Args:
            user: Django User 对象，用于权限控制和 created_by 字段
            project_id: 当前主项目 ID
            kb_id: 当前选中的知识库 ID（用于限制 RAG 检索范围）
            llm_config: LLM 配置字典；为 None 时从数据库 AgentConfig 读取
            tools: 要启用的工具名称列表；None 表示启用全部注册工具
            session_id: 当前会话 ID（文件工具按会话隔离）
        """
        self.user = user
        self.project_id = project_id
        self.kb_id = kb_id
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
            kb_id=self.kb_id,
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

        # 注入用户选中的知识库信息，让 AI 明确知道检索范围
        kb_context = self._build_kb_context()
        if kb_context:
            project_context = project_context + "\n\n" + kb_context

        skills_prompt = self._load_skills_prompt()
        extra = self.llm_config.get("system_prompt_extra") or ""
        return self.SYSTEM_PROMPT_TEMPLATE.format(project_context=project_context) + skills_prompt + ("\n" + extra if extra else "")

    def _build_kb_context(self) -> str:
        """构建用户选中的知识库上下文。

        注意：此方法可能从 async 上下文中调用，因此只使用纯 Python 操作，
        不进行任何 ORM 查询（KB 的具体信息已在工具返回中可见）。
        """
        if not self.kb_id:
            return ""
        return (
            f"## 🔒 用户选中的知识库（严格限定检索范围）\n"
            f"- 用户在前端下拉框中选中的知识库 ID: {self.kb_id}\n"
            f"\n"
            f"**重要约束：**\n"
            f"1. 你**只能**在该知识库（ID={self.kb_id}）中检索内容，**禁止检索其他任何知识库**\n"
            f"2. 调用 `search_knowledge_base` 时**不要传 `knowledge_base_id` 参数**（保持 0 或不传）\n"
            f"   - 系统会自动使用用户选中的 KB ID={self.kb_id} 进行检索\n"
            f"   - 即使你错误地传了其他 ID，系统也会**强制忽略**并替换为该 ID\n"
            f"3. **绝对禁止**调用 `list_knowledge_bases` 后挨个 KB 检索\n"
            f"4. 如果该 KB 中没有相关内容，直接说『该知识库中暂未收录』，**禁止去其他 KB 查找**\n"
        )

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
        call_names: Dict[str, str] = {}
        exceeded = False

        try:
            async for event in result.stream_events():
                if isinstance(event, RunItemStreamEvent):
                    if event.name == "tool_called":
                        item = event.item
                        raw = getattr(item, "raw_item", None)
                        # ResponseFunctionToolCall：call_id 是函数调用 ID，
                        # 与 tool_output 输出项里的 call_id 对应。
                        call_id = str(_raw_get(raw, "call_id") or _raw_get(raw, "id") or "")
                        name = str(_raw_get(raw, "name") or "")
                        call_names[call_id] = name
                        raw_args = _raw_get(raw, "arguments") or ""
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
                        # SDK 0.19.x 输出项是 dict（call_id/output/type），不含 name/id，
                        # 需从 call_id 反查 tool_start 阶段记录的函数名。
                        call_id = str(_raw_get(raw, "call_id") or _raw_get(raw, "id") or "")
                        name = call_names.get(call_id) or str(_raw_get(raw, "name") or "")
                        output = _raw_get(raw, "output", None)
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
                            "id": call_id,
                            "name": name,
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

        except RuntimeError as e:
            # 进程/解释器正在退出（服务重启、Ctrl+C、部署收尾）时，
            # 事件循环已无法调度新任务，属于正常收尾，不再产出错误事件。
            if "interpreter shutdown" in str(e):
                logger.info(f"Agent run interrupted by interpreter shutdown: {e}")
                return
            logger.error(f"Agent run failed: {e}", exc_info=True)
            yield {"type": "error", "content": f"Agent 处理出错: {e}"}
            yield {
                "type": "run_done",
                "final_output": full_text,
                "tool_calls": tool_calls,
                "error": True,
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
        cancel_event = threading.Event()

        def _run() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:

                async def _consume() -> None:
                    async for ev in self._achat(message, history):
                        events.put(ev)

                task = loop.create_task(_consume())

                async def _watch_cancel() -> None:
                    # 消费端退出（客户端断开/生成器被关闭）时取消后台运行，
                    # 避免线程在服务重启/进程退出时仍在执行 Agent 回合。
                    while not cancel_event.is_set() and not task.done():
                        await asyncio.sleep(0.2)
                    if cancel_event.is_set() and not task.done():
                        task.cancel()

                watcher = loop.create_task(_watch_cancel())
                loop.run_until_complete(
                    asyncio.gather(task, watcher, return_exceptions=True)
                )
            except Exception as e:
                logger.error(f"Agent bridge error: {e}", exc_info=True)
                try:
                    events.put({"type": "error", "content": f"Agent 处理出错: {e}"})
                    events.put({"type": "run_done", "final_output": "", "tool_calls": []})
                except Exception:
                    pass
            finally:
                try:
                    events.put(sentinel)
                except Exception:
                    pass
                # 关闭事件循环前清理残留任务，避免 executor 在进程退出时仍被引用
                try:
                    pending = [
                        t for t in asyncio.all_tasks(loop) if not t.done()
                    ]
                    for t in pending:
                        t.cancel()
                    if pending:
                        loop.run_until_complete(
                            asyncio.gather(*pending, return_exceptions=True)
                        )
                except Exception:
                    pass
                loop.close()

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        try:
            while True:
                ev = events.get()
                if ev is sentinel:
                    break
                yield ev
        finally:
            # 生成器被提前关闭（客户端断开/SSE 中断）：通知后台线程取消，
            # 不要让它继续把整个 Agent 回合跑完。
            if thread.is_alive():
                cancel_event.set()
                thread.join(timeout=5)

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
