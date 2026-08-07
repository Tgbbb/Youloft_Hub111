# -*- coding: utf-8 -*-
"""Midscene 风格移动端 AI 自动化引擎（aiAct 独立模块）。

与 midscene_runner 的逐行执行/录制/回放逻辑解耦，只复用其底层原语
（截图、ADB/iOS 动作执行、VLM 调用、pHash、截图保存）。
"""
from .engine import run_ai_act  # noqa: F401

__all__ = ['run_ai_act']
