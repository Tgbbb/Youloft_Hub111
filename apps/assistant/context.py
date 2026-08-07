"""TestHub Agent 单次运行上下文（替代旧版 thread-local 传参）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class TestHubContext:
    """通过 SDK 的 RunContextWrapper 注入到每个工具函数。"""

    user: Any = None  # Django User 实例（未登录时为 None）
    user_id: int = 0
    project_id: Optional[int] = None
    session_id: str = ""
    extra: dict = field(default_factory=dict)
