"""OpenAI Agents SDK 运行时层。

替代旧版 qwen-agent 的 FnCallAgent 初始化逻辑，负责：
- 从 AgentConfig/AIModelConfig 读取模型配置；
- 构造 OpenAI 兼容异步客户端；
- 探测 Responses API 兼容性并自动降级 Chat Completions；
- 构建 SDK Agent（含外部 MCP server 加载）。
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List

from openai import AsyncOpenAI

from agents import (
    Agent,
    Model,
    ModelSettings,
    OpenAIChatCompletionsModel,
    OpenAIResponsesModel,
    set_tracing_disabled,
)

from apps.assistant.context import TestHubContext

logger = logging.getLogger(__name__)

# 内部数据不出网：默认关闭 SDK 的远端 tracing，需要时可另行开启。
set_tracing_disabled(True)

# 各提供商默认 OpenAI 兼容 base_url（AgentConfig.base_url 留空时使用）
PROVIDER_DEFAULT_BASE: Dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "siliconflow": "https://api.siliconflow.cn/v1",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "xiaomi": "",
    "xiaomi_coding_plan": "",
    "other": "",
}

# Responses 兼容性探测缓存：key=(base_url, model, api_key) -> (supports, checked_at)
_probe_cache: Dict[tuple, tuple] = {}
_probe_lock = threading.Lock()
_PROBE_TTL = 600


def load_llm_config() -> Dict[str, Any]:
    """从数据库读取模型配置（优先 AgentConfig，回退 AIModelConfig）。"""
    try:
        from apps.assistant.models import AgentConfig

        ac = AgentConfig.get_active_config()
        if ac:
            protocol = getattr(ac, 'api_protocol', 'auto') or 'auto'
            return {
                "provider": ac.provider,
                "model": ac.model_name,
                "base_url": ac.base_url or PROVIDER_DEFAULT_BASE.get(ac.provider, ""),
                "api_key": ac.api_key or "",
                "api_protocol": protocol,
                "max_tokens": ac.max_tokens,
                "temperature": ac.temperature,
                "max_tool_calls": ac.max_tool_calls,
                "tool_groups": list(getattr(ac, "tool_groups", []) or []),
                "system_prompt_extra": ac.system_prompt_extra or "",
            }
    except Exception as e:
        logger.debug(f"AgentConfig not available: {e}")

    try:
        from apps.requirement_analysis.models import AIModelConfig

        config = AIModelConfig.objects.filter(role="writer", is_active=True).first()
        if config:
            return {
                "provider": "other",
                "model": config.model_name,
                "base_url": config.base_url or "https://api.deepseek.com",
                "api_key": config.api_key or "",
                "api_protocol": "auto",
                "max_tokens": config.max_tokens,
                "temperature": config.temperature,
                "max_tool_calls": 20,
                "tool_groups": [],
                "system_prompt_extra": "",
            }
    except Exception as e:
        logger.warning(f"Failed to load LLM config from DB: {e}")

    return {
        "provider": "qwen",
        "model": "qwen-plus",
        "base_url": PROVIDER_DEFAULT_BASE["qwen"],
        "api_key": "",
        "api_protocol": "auto",
        "max_tokens": 8192,
        "temperature": 0.7,
        "max_tool_calls": 20,
        "tool_groups": [],
        "system_prompt_extra": "",
    }


def build_openai_client(cfg: Dict[str, Any]) -> AsyncOpenAI:
    """按配置构造 OpenAI 兼容异步客户端。"""
    base_url = (cfg.get("base_url") or "").rstrip("/") or None
    api_key = cfg.get("api_key") or os.getenv("OPENAI_API_KEY") or "EMPTY"
    return AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=120.0, max_retries=1)


async def _probe_responses(client: AsyncOpenAI, model: str) -> bool:
    """发送最小探测请求，判断 base_url 是否支持 Responses 端点。"""
    # 探测用短超时专用客户端，避免断网时等待过长
    client = AsyncOpenAI(
        api_key=client.api_key,
        base_url=client.base_url,
        timeout=10.0,
        max_retries=0,
    )
    try:
        await client.responses.create(
            model=model, input="ping", max_output_tokens=16, stream=False
        )
        return True
    except Exception as e:
        logger.warning(f"Responses API probe failed, fallback to chat completions: {e}")
        return False


async def supports_responses(cfg: Dict[str, Any]) -> bool:
    """带缓存的 Responses 兼容性判断。

    - cfg['api_protocol'] 为 'responses' / 'chat_completions' 时按用户显式选择，
      不做网络探测；
    - 'auto'（默认）时探测 Responses，失败降级 Chat Completions；
    - AGENT_FORCE_CHAT_COMPLETIONS=1 环境变量强制降级。
    """
    if os.getenv("AGENT_FORCE_CHAT_COMPLETIONS") == "1":
        return False
    protocol = (cfg.get("api_protocol") or "auto")
    if protocol == "responses":
        return True
    if protocol == "chat_completions":
        return False
    base_url = (cfg.get("base_url") or "").rstrip("/")
    model = cfg.get("model") or ""
    api_key = cfg.get("api_key") or ""
    key = (base_url, model, api_key)
    now = time.time()
    with _probe_lock:
        cached = _probe_cache.get(key)
        if cached and now - cached[1] < _PROBE_TTL:
            return cached[0]
    client = build_openai_client(cfg)
    ok = await _probe_responses(client, model)
    with _probe_lock:
        _probe_cache[key] = (ok, now)
    return ok


async def build_model(cfg: Dict[str, Any]) -> Model:
    """构建 SDK Model：默认 Responses，探测失败时降级 Chat Completions。"""
    client = build_openai_client(cfg)
    model_name = cfg.get("model") or "gpt-4.1"
    if await supports_responses(cfg):
        return OpenAIResponsesModel(model=model_name, openai_client=client)
    return OpenAIChatCompletionsModel(model=model_name, openai_client=client)


def build_model_settings(cfg: Dict[str, Any]) -> ModelSettings:
    return ModelSettings(
        temperature=cfg.get("temperature", 0.7),
        max_tokens=cfg.get("max_tokens") or None,
    )


def load_mcp_servers() -> List[Any]:
    """加载 mcp_servers/ 与 skill 内嵌配置中 enabled 的 stdio MCP server。"""
    from agents.mcp import MCPServerStdio, MCPServerStdioParams

    servers: List[Any] = []
    base_dir = Path(__file__).resolve().parents[2] / "mcp_servers"
    if base_dir.is_dir():
        for f in sorted(base_dir.glob("*.json")):
            try:
                cfg = json.loads(f.read_text(encoding="utf-8"))
                if not cfg.get("enabled", True):
                    continue
                if cfg.get("type", "stdio") != "stdio":
                    logger.warning(
                        f"MCP {f.stem}: 当前仅支持 stdio，跳过 type={cfg.get('type')}"
                    )
                    continue
                servers.append(
                    MCPServerStdio(
                        params=MCPServerStdioParams(
                            command=cfg["command"],
                            args=cfg.get("args", []),
                            env=cfg.get("env"),
                            cwd=cfg.get("cwd"),
                        ),
                        name=f.stem,
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to load MCP config {f.name}: {e}")

    try:
        from apps.assistant.skill_loader import get_enabled_skills

        for skill in get_enabled_skills():
            if not skill.mcp_config:
                continue
            for srv_name, srv_cfg in (skill.mcp_config.get("mcpServers") or {}).items():
                if srv_cfg.get("type", "stdio") != "stdio":
                    continue
                servers.append(
                    MCPServerStdio(
                        params=MCPServerStdioParams(
                            command=srv_cfg["command"],
                            args=srv_cfg.get("args", []),
                            env=srv_cfg.get("env"),
                            cwd=srv_cfg.get("cwd"),
                        ),
                        name=f"{skill.name}-{srv_name}",
                    )
                )
    except Exception as e:
        logger.warning(f"Failed to load skill MCP servers: {e}")

    return servers


async def build_agent(
    cfg: Dict[str, Any], instructions: str, tools: List[Any]
) -> Agent[TestHubContext]:
    """构建 SDK Agent。tools 为 SDK FunctionTool 列表。"""
    model = await build_model(cfg)
    return Agent[TestHubContext](
        name="TestHubAssistant",
        instructions=instructions,
        tools=list(tools),
        mcp_servers=load_mcp_servers(),
        model=model,
        model_settings=build_model_settings(cfg),
    )
