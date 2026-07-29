"""
TestHub Agent — 基于 Qwen-Agent 的对话式 AI 协作者

封装 Qwen-Agent 的 FnCallAgent，提供：
1. Agent 初始化（LLM 配置、Tool 注册、System Prompt）
2. 对话接口（支持流式输出）
3. 项目上下文注入
"""
import json
import logging
import re as _re
import threading
import time
from typing import Generator, List, Dict, Any, Optional
from django.conf import settings

logger = logging.getLogger(__name__)

# Thread-local 存储当前请求上下文（user、project_id）
# FnCallAgent 调用 tool.call(params) 时不传递 kwargs，
# 所以 Tool 需要通过此机制获取当前用户
_ctx = threading.local()

# Agent 实例缓存：避免每次请求都重新创建 FnCallAgent（含 MCP 连接、Skill 扫描）
# key: (user_id, project_id)  →  value: (FnCallAgent, created_at_timestamp)
_agent_cache: Dict[tuple, tuple] = {}
_AGENT_CACHE_TTL = 300  # 5 分钟过期，平衡新鲜度和性能

# nous 格式 XML 碎片过滤：nous fncall_prompt_type 下模型偶尔会输出不完整的
# <tool_call>...</tool_call> XML 片段混在普通文本中，需要清除
# 匹配 nous XML 碎片：<tool_call>, </tool_call>, <tool_call..., <tool<, <tool 等
_NOUS_XML_PATTERN = _re.compile(r'</?tool[_a-z]*\s*/?>?', _re.IGNORECASE)


def _strip_nous_xml(text: str) -> str:
    """清除 nous 格式泄漏的 XML 碎片（<tool_call> 等）"""
    cleaned = _NOUS_XML_PATTERN.sub('', text).strip()
    # 清理残留：< 后面紧跟中文字符（如 <tool<你好 → <你好 → 你好）
    cleaned = _re.sub(r'<(?=[一-鿿㐀-䶿])', '', cleaned)
    return cleaned


class TestHubAgent:
    """
    TestHub AI 协作者

    使用 Qwen-Agent FnCallAgent 作为推理引擎，
    通过自定义 Tool 操作 TestHub 的业务数据。
    """

    # 所有可用工具（tools.py 中通过 @register_tool 注册）
    # 按需加载，启动时只加载核心工具
    # Qwen-Agent 内置工具 + 我们的自定义工具
    DEFAULT_TOOLS = [
        # 内置工具
        'simple_doc_parser',        # 读取文件（PDF/Word/Excel/TXT/HTML/CSV）
        # 自定义工具
        'get_project_overview',
        'search_apis',
        'get_api_detail',
        'search_testcases',
        'create_api_test',
        'create_collection',
        'create_testcase',
        'execute_api',
        'parse_swagger',
        'parse_yapi',
        'read_knowledge_base',      # 读取项目知识库
        'list_api_projects',        # 列出API测试项目
        'list_midscene_projects',   # 列出Midscene项目
        'list_midscene_cases',      # 列出Midscene用例
        'update_midscene_case',     # 修改Midscene用例
        'get_testcase_detail',      # 查看用例详情
        'update_testcase',          # 修改用例
        'delete_testcase',          # 删除用例
        'update_knowledge_base',    # 更新知识库
        'bash',                     # 受限 shell 命令
    ]

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
- 通过 `navigate` / `snapshot` / `screenshot` 访问和操作网页（如果加载了 Playwright MCP）
- 搜索和查看项目的接口定义（支持按名称、URL、方法搜索）
- 获取接口的完整详情（参数、请求头、请求体、断言规则）
- 创建新的 API 接口测试（含断言配置）
- 创建接口集合（用于分组管理）
- 执行接口请求并查看响应结果
- 读取文档文件内容（支持 PDF/Word/Excel/TXT/HTML/CSV）
- 解析 Swagger/OpenAPI 文档，自动提取接口列表
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
    ):
        """
        初始化 Agent

        Args:
            user: Django User 对象，用于权限控制和 created_by 字段
            project_id: 当前项目 ID（API测试项目）
            llm_config: LLM 配置字典，格式:
                {
                    'model': 'qwen-plus',
                    'model_server': 'dashscope',
                    'api_key': 'sk-xxx',
                    'generate_cfg': {
                        'fncall_prompt_type': 'nous',
                    }
                }
                如果为 None，则从数据库 AIModelConfig 读取
            tools: 要启用的工具名称列表，默认使用 DEFAULT_TOOLS
        """
        self.user = user
        self.project_id = project_id
        self.llm_config = llm_config or self._get_llm_config_from_db()
        self.tool_names = tools or self.DEFAULT_TOOLS
        self._agent = None
        self.max_tool_calls = self.llm_config.pop('_max_tool_calls', 20)

        # 写入 thread-local，供 Tool 通过 get_current_user() 获取
        _ctx.user = user
        _ctx.project_id = project_id

    # Qwen-Agent model_server 名称映射
    # oai = OpenAI 兼容接口（DeepSeek/SiliconFlow/Qwen-Compatible 等都用这个）
    # qwen_dashscope = 千问原生 DashScope API
    # 当 base_url 包含 'dashscope' 时用 qwen_dashscope，否则用 oai
    MODEL_SERVER_MAP = {
        'deepseek': 'oai',
        'qwen': 'oai',        # 兼容模式
        'siliconflow': 'oai',
        'zhipu': 'oai',
        'xiaomi': 'oai',
        'xiaomi_coding_plan': 'oai',
        'other': 'oai',
    }

    def _get_llm_config_from_db(self) -> Dict[str, Any]:
        """从数据库读取 LLM 配置（优先 AgentConfig，其次 AIModelConfig）"""
        # 1. 优先用 AgentConfig（专为 Agent 设计）
        try:
            from apps.assistant.models import AgentConfig
            agent_config = AgentConfig.get_active_config()
            if agent_config:
                # Qwen 无 base_url → 走 DashScope 原生 API（nous 格式）
                # Qwen 有 base_url → 走兼容模式（OpenAI 格式）
                if agent_config.provider == 'qwen' and not agent_config.base_url:
                    model_server = 'qwen_dashscope'
                else:
                    model_server = agent_config.base_url or 'https://api.deepseek.com'

                return {
                    'model': agent_config.model_name,
                    'model_server': model_server,
                    'api_key': agent_config.api_key or '',
                    'generate_cfg': {
                        'max_tokens': agent_config.max_tokens,
                        'temperature': agent_config.temperature,
                        'fncall_prompt_type': 'nous',
                    },
                    '_max_tool_calls': agent_config.max_tool_calls,
                }
        except Exception as e:
            logger.debug(f'AgentConfig not available: {e}')

        # 2. 回退到 AIModelConfig
        try:
            from apps.requirement_analysis.models import AIModelConfig
            config = AIModelConfig.objects.filter(
                role='writer', is_active=True
            ).first()

            if config:
                return {
                    'model': config.model_name,
                    'model_server': config.base_url or 'https://api.deepseek.com',
                    'api_key': config.api_key or '',
                    'generate_cfg': {
                        'max_tokens': config.max_tokens,
                        'temperature': config.temperature,
                        'fncall_prompt_type': 'nous',
                    },
                    '_max_tool_calls': 20,
                }
        except Exception as e:
            logger.warning(f'Failed to load LLM config from DB: {e}')

        # Fallback: 使用 DashScope Qwen
        return {
            'model': 'qwen-plus',
            'model_server': 'qwen_dashscope',
            'generate_cfg': {
                'fncall_prompt_type': 'nous',
            }
        }

    def _load_skills_prompt(self) -> str:
        """Skills 摘要：仅返回名字列表，节省 token。具体指令在调用时展开。"""
        try:
            from apps.assistant.skill_loader import build_skills_prompt
            return build_skills_prompt()  # 不传参 = 摘要模式
        except Exception as e:
            logger.warning(f'Failed to load skills: {e}')
            return ''

    @staticmethod
    def _load_skills_instructions(skill_names: list) -> str:
        """展开指定 Skill 的完整指令（/skill:name 触发时调用）"""
        try:
            from apps.assistant.skill_loader import build_skills_prompt
            return build_skills_prompt(filter_names=skill_names)
        except Exception:
            return ''

    def _build_system_prompt(self) -> str:
        """根据项目上下文构建 system prompt（覆盖所有模块）"""
        project_context = '未指定项目'

        if self.project_id:
            try:
                from apps.projects.models import Project
                from apps.testcases.models import TestCase
                from apps.api_testing.models import ApiProject, ApiRequest

                project = Project.objects.get(id=self.project_id)

                # 测试用例统计
                testcase_count = TestCase.objects.filter(project_id=self.project_id).count()

                # 接口测试统计（查找同名或关联的 ApiProject）
                api_projects = ApiProject.objects.filter(
                    name__icontains=project.name
                ) | ApiProject.objects.filter(
                    owner=project.owner
                )
                api_count = 0
                collection_count = 0
                for ap in api_projects[:5]:
                    api_count += ApiRequest.objects.filter(collection__project=ap).count()
                    collection_count += ap.collections.count()

                # UI 自动化统计
                ui_count = 0
                ui_suite_count = 0
                try:
                    from apps.ui_automation.models import UiProject, TestScript as UIScript, TestSuite as UITestSuite
                    ui_projects = UiProject.objects.filter(
                        name__icontains=project.name
                    ) | UiProject.objects.filter(owner=project.owner)
                    for up in ui_projects[:5]:
                        ui_count += UIScript.objects.filter(project=up).count()
                        ui_suite_count += UITestSuite.objects.filter(project=up).count()
                except Exception:
                    pass

                # AI智能模式 (Midscene) 统计
                midscene_count = 0
                midscene_device_count = 0
                try:
                    from apps.ui_automation.models import MidsceneProject, MidsceneCase, MidsceneDevice
                    mp = MidsceneProject.objects.filter(
                        name__icontains=project.name
                    ) | MidsceneProject.objects.filter(owner=project.owner)
                    for m in mp[:5]:
                        midscene_count += MidsceneCase.objects.filter(project=m).count()
                    midscene_device_count = MidsceneDevice.objects.filter(status='online').count()
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
                logger.warning(f'Failed to build project context: {e}')
                project_context = f'(project_id={self.project_id})'

        skills_prompt = self._load_skills_prompt()
        return self.SYSTEM_PROMPT_TEMPLATE.format(project_context=project_context) + skills_prompt

    @property
    def agent(self):
        """延迟初始化 Agent（首次调用时创建）"""
        if self._agent is None:
            self._agent = self._create_agent()
        return self._agent

    @staticmethod
    def get_current_user():
        """获取当前请求的用户（从 thread-local 读取）。

        Tool 通过此方法获取用户，避免依赖 kwargs.get('user')（FnCallAgent 不传 kwargs）。
        """
        return getattr(_ctx, 'user', None)

    @staticmethod
    def get_current_project_id():
        """获取当前请求的项目 ID（从 thread-local 读取）。"""
        return getattr(_ctx, 'project_id', None)

    def _create_agent(self):
        """创建或复用 Qwen-Agent FnCallAgent 实例（含缓存）

        缓存策略：按 (user_id, project_id) 缓存 FnCallAgent 实例，
        TTL 5 分钟，避免每次 HTTP 请求都重新扫描 Skill、加载 MCP、建立连接。
        """
        from qwen_agent.agents import FnCallAgent

        # 构建缓存 key
        user_id = self.user.id if self.user else 0
        cache_key = (user_id, self.project_id or 0)

        # 检查缓存
        now = time.time()
        if cache_key in _agent_cache:
            cached_agent, created_at = _agent_cache[cache_key]
            if now - created_at < _AGENT_CACHE_TTL:
                logger.debug(f'Reusing cached agent for user={user_id} project={self.project_id}')
                # 更新 thread-local（可能已切换到不同请求）
                _ctx.user = self.user
                _ctx.project_id = self.project_id
                return cached_agent
            else:
                logger.debug(f'Agent cache expired for user={user_id} project={self.project_id}')
                del _agent_cache[cache_key]

        # 确保 tools 模块已导入（触发 @register_tool 注册）
        from apps.assistant import tools as _tools  # noqa: F401

        # 构建 LLM 配置
        llm_cfg = dict(self.llm_config)

        # 确保有默认的 generate_cfg
        if 'generate_cfg' not in llm_cfg:
            llm_cfg['generate_cfg'] = {}
        llm_cfg['generate_cfg'].setdefault('fncall_prompt_type', 'nous')

        # 收集所有 Tool（内置 + Skill MCP）
        all_tools = list(self.tool_names)

        # 扫描 Skill 中的 MCP 配置 + 独立 mcp_servers/ 目录
        try:
            import os as _os
            from apps.assistant.skill_loader import get_enabled_skills
            from qwen_agent.tools.mcp_manager import MCPManager

            mcp_configs = {}

            for skill in get_enabled_skills():
                if skill.mcp_config:
                    servers = skill.mcp_config.get('mcpServers', {})
                    for srv_name, srv_cfg in servers.items():
                        mcp_configs[f'{skill.name}-{srv_name}'] = srv_cfg

            # 加载独立 MCP 配置
            mcp_dir = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(
                _os.path.abspath(__file__)))), 'mcp_servers')
            if _os.path.isdir(mcp_dir):
                for fname in sorted(_os.listdir(mcp_dir)):
                    if fname.endswith('.json'):
                        try:
                            with open(_os.path.join(mcp_dir, fname), 'r', encoding='utf-8') as f:
                                cfg = json.load(f)
                            if cfg.get('enabled', True):
                                mcp_configs[fname.replace('.json', '')] = cfg
                        except Exception as e:
                            logger.warning(f'Failed to load MCP {fname}: {e}')

            if mcp_configs:
                logger.info(f'Loading MCP tools from {len(mcp_configs)} server(s)...')
                manager = MCPManager()
                mcp_tools = manager.initConfig({'mcpServers': mcp_configs})
                all_tools.extend(mcp_tools)
                logger.info(f'MCP tools loaded: {len(mcp_tools)}')
        except ImportError:
            logger.debug('MCP not available, skipping MCP tools')
        except Exception as e:
            logger.warning(f'Failed to load MCP tools: {e}')

        logger.info(f'Creating FnCallAgent with {len(all_tools)} tools '
                     f'(cache miss for user={user_id} project={self.project_id})')
        logger.info(f'LLM config: model={llm_cfg.get("model")}, server={llm_cfg.get("model_server")}')

        agent = FnCallAgent(
            llm=llm_cfg,
            function_list=all_tools,
            system_message=self._build_system_prompt(),
        )

        # 加入缓存
        _agent_cache[cache_key] = (agent, now)

        return agent

    # 历史摘要触发阈值
    SUMMARY_MIN_MESSAGES = 20       # 超过此数量触发摘要
    SUMMARY_KEEP_LAST = 15          # 保留最近 N 条消息不参与摘要
    SUMMARY_MAX_TOKENS = 300        # 摘要最大 token 数

    def _summarize_history(
        self, history: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """
        对过长历史消息做 LLM 摘要压缩。

        策略：
        1. 保留最近 SUMMARY_KEEP_LAST 条消息不变
        2. 用 LLM 将更早的消息压缩为一段摘要
        3. 摘要作为 system 消息插入历史开头
        """
        if len(history) <= self.SUMMARY_MIN_MESSAGES:
            return history

        old_msgs = history[:-self.SUMMARY_KEEP_LAST]
        recent_msgs = history[-self.SUMMARY_KEEP_LAST:]

        # 只对 user 和 assistant 消息做摘要
        dialogue = []
        for m in old_msgs:
            role = m.get('role', '')
            content = str(m.get('content', ''))[:500]  # 每条截断
            if role in ('user', 'assistant') and content.strip():
                dialogue.append(f"[{role}] {content}")

        if len(dialogue) < 5:
            return history  # 有效内容太少，不摘要

        dialogue_text = '\n'.join(dialogue)

        try:
            from qwen_agent.llm import get_chat_model
            llm = get_chat_model(self.llm_config)

            summary_prompt = f"""请用 2-3 句中文简洁概括以下对话的核心内容和关键决策点：

{dialogue_text}

摘要（仅输出摘要内容，不要加前缀）："""

            summary_msgs = [{'role': 'user', 'content': summary_prompt}]
            result = list(llm.chat(
                messages=summary_msgs,
                stream=False,
                delta_stream=False,
            ))
            summary = ''
            if result:
                summary = str(result[-1].get('content', '') if isinstance(result[-1], dict) else result[-1]).strip()

            # 清理常见的模型废话
            for prefix in ['摘要：', '摘要:', '总结：', '总结:', '核心内容：']:
                if summary.startswith(prefix):
                    summary = summary[len(prefix):].strip()

            if len(summary) > 1500:
                summary = summary[:1500] + '...'

            logger.info(f'History summarized: {len(old_msgs)} msgs → {len(summary)} chars')

            # 构建新的历史：摘要 + 最近消息
            compressed = [{
                'role': 'system',
                'content': f'[对话历史摘要] {summary}'
            }]
            compressed.extend(recent_msgs)
            return compressed

        except Exception as e:
            logger.warning(f'History summarization failed, keeping original: {e}')
            return history

    def chat(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
        stream: bool = True,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        对话入口

        Args:
            message: 用户消息
            history: 历史消息列表 [{'role': 'user/assistant', 'content': '...'}]
            stream: 是否流式输出

        Yields:
            事件字典:
            - {'type': 'text', 'content': '...'}       — 文本内容块
            - {'type': 'tool_call', 'name': '...', 'args': {...}}  — 工具调用
            - {'type': 'tool_result', 'name': '...', 'result': '...'}  — 工具结果
            - {'type': 'done'}                           — 完成信号
        """
        # 构建 messages（长历史自动摘要压缩）
        messages = []
        if history:
            # 超过阈值时对早期消息做摘要
            if len(history) > self.SUMMARY_MIN_MESSAGES:
                history = self._summarize_history(history)
            messages.extend(history)
        messages.append({'role': 'user', 'content': message})

        # 检测 /skill:name 调用，展开完整指令拼到用户消息前面
        import re as _re2
        skill_names = _re2.findall(r'/skill:(\S+)', message)
        if skill_names:
            skill_instructions = self._load_skills_instructions(skill_names)
            if skill_instructions:
                messages[-1]['content'] = skill_instructions + '\n\n---\n用户消息:\n' + messages[-1]['content']
                logger.info(f'Skills expanded: {skill_names}')

        max_calls = self.max_tool_calls  # 从 AgentConfig 读取，默认 20
        warn_at = max(3, max_calls - 3)  # 倒数第 3 次开始提醒

        logger.info(f'Agent chat: "{message[:100]}..." with {len(messages)} messages '
                     f'(max_tool_calls={max_calls})')

        try:
            response_generator = self.agent.run(messages=messages)

            tool_count = 0
            seen_calls = set()
            tool_calls_made = []  # 记录实际调用的工具名（用于幻觉检测）
            # 跟踪每条消息的已知内容长度，用于计算增量
            last_content_by_msg_idx = {}
            warned = False

            for response in response_generator:
                if not response:
                    continue

                msgs = response if isinstance(response, list) else [response]

                for i, msg in enumerate(msgs):
                    msg_dict = msg if isinstance(msg, dict) else {}
                    role = msg_dict.get('role', '')

                    # 检查是否有 function_call
                    if msg_dict.get('function_call'):
                        func_call = msg_dict['function_call']
                        name = func_call.get('name', '')
                        args = func_call.get('arguments', {})

                        # 跳过碎片参数（流式不完整的 JSON）
                        if isinstance(args, str) and not args.endswith('}'):
                            continue

                        # 去重
                        call_key = f'{name}:{json.dumps(args, sort_keys=True, ensure_ascii=False)}'
                        if call_key in seen_calls:
                            continue
                        seen_calls.add(call_key)

                        # 逼近上限时注入智能提醒（而非直接截断）
                        if tool_count >= warn_at and not warned:
                            warned = True
                            remaining = max_calls - tool_count
                            yield {
                                'type': 'text',
                                'content': (f'\n\n⚡ 已调用 {tool_count} 次工具，还剩 {remaining} 次。'
                                            f'请高效收尾，避免超限。'),
                            }

                        # 达到上限
                        if tool_count >= max_calls:
                            yield {
                                'type': 'text',
                                'content': (f'\n\n⚠️ 已达到单轮工具调用上限({max_calls}次)。'
                                            f'任务较大可调整 Agent 配置中的最大调用次数，或分步执行。'),
                            }
                            logger.warning(f'Agent hit tool call limit: {max_calls}')
                            break

                        tool_count += 1
                        logger.info(f'[Agent] #{tool_count}/{max_calls} CALL: {name}')
                        tool_calls_made.append(name)
                        yield {
                            'type': 'tool_call',
                            'name': name,
                            'args': args,
                        }

                    # Tool 返回结果（role=function 或 role=tool）
                    if role in ('function', 'tool') and msg_dict.get('content'):
                        tool_name = msg_dict.get('name', '')
                        result_content = str(msg_dict.get('content', ''))[:800]
                        # 去重：同一结果在流式块中反复出现
                        result_key = f'{tool_name}:{hash(result_content)}'
                        if result_key not in seen_calls:
                            seen_calls.add(result_key)
                            logger.debug(f'[Agent] RESULT: {tool_name} → {result_content[:100]}')
                        yield {
                            'type': 'tool_result',
                            'name': tool_name,
                            'result': result_content,
                        }

                    # 文本增量（跳过 role=function/tool）
                    content = msg_dict.get('content', '')
                    if content and role not in ('function', 'tool'):
                        prev_len = last_content_by_msg_idx.get(i, 0)
                        if len(content) > prev_len:
                            # 只取新增部分
                            delta = content[prev_len:]
                            last_content_by_msg_idx[i] = len(content)
                            if delta:
                                # 过滤 nous 格式泄漏的 XML 碎片
                                delta = _strip_nous_xml(delta)
                                if delta:
                                    yield {
                                        'type': 'text',
                                        'content': delta,
                                    }

                    if tool_count >= max_calls:
                        break

            # 幻觉风险提示：如果模型没有调用任何工具，但生成了看似操作完成的文本，
            # 由前端根据 tool_calls_made 来判断；这里传递元数据
            yield {
                'type': 'done',
                'tool_calls_count': len(tool_calls_made),
                'tool_calls_made': tool_calls_made,
            }

        except Exception as e:
            logger.error(f'Agent chat error: {e}', exc_info=True)
            yield {
                'type': 'error',
                'content': f'Agent 处理出错: {str(e)}',
            }
            yield {'type': 'done'}

    def chat_sync(self, message: str, history: Optional[List[Dict]] = None) -> str:
        """同步对话（非流式），返回完整回复"""
        full_response = []
        for event in self.chat(message, history, stream=False):
            if event['type'] == 'text':
                full_response.append(event['content'])
        return ''.join(full_response)

    def set_project(self, project_id: int):
        """切换当前项目上下文，同时清除旧缓存"""
        user_id = self.user.id if self.user else 0
        old_key = (user_id, self.project_id or 0)
        self.project_id = project_id
        self._agent = None
        _ctx.project_id = project_id
        # 清除旧 project 的缓存，确保新 project 用新的 system prompt
        _agent_cache.pop(old_key, None)
        logger.debug(f'Agent cache invalidated for user={user_id} after project switch')


def clear_agent_cache(user_id=None):
    """清除 Agent 缓存（配置变更、Skill 更新、MCP 变动时调用）。

    Args:
        user_id: 指定用户 ID 则只清除该用户的缓存；None 则清除全部
    """
    if user_id is not None:
        keys_to_del = [k for k in _agent_cache if k[0] == user_id]
        for k in keys_to_del:
            del _agent_cache[k]
        logger.info(f'Agent cache cleared for user={user_id} ({len(keys_to_del)} entries)')
    else:
        count = len(_agent_cache)
        _agent_cache.clear()
        logger.info(f'Agent cache cleared (all {count} entries)')
