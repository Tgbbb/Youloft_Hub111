# -*- coding: utf-8 -*-
"""两阶段定位：规划模型描述目标元素 -> locate 模型返回中心坐标。

对齐 Midscene 的 TaskBuilder（createLocateTask）：规划模型只负责"描述元素"，
坐标由专门的 locate 提示词基于截图计算。移动端纯截图视觉识别，不引入
DOM/无障碍树。

容错策略：
  - locate 输出缺失/越界/解析失败 -> 重试 1 次；
  - 重试仍失败且规划输出带直接坐标 -> 降级用直接坐标；
  - 都没有 -> 抛 LocateError，由引擎反馈给规划模型重规划。
"""

import json
import re
import logging

from .actions import INTERACTIVE_ACTIONS, has_direct_coords, locate_fields_for
from .prompts import LOCATE_SYSTEM_PROMPT, build_locate_user_prompt

logger = logging.getLogger(__name__)


class LocateError(RuntimeError):
    pass


def _tolerant_json_fix(raw):
    fixed = raw
    # 未加引号的 key（locate: "x" / locate = "x"）-> "locate":"x"
    fixed = re.sub(r'(^|[,{]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*[:=]\s*', r'\1"\2":', fixed)
    # 单引号值 -> 双引号；尾逗号
    fixed = re.sub(r'"\s*:\s*\'([^\']*)\'', r'": "\1"', fixed)
    fixed = re.sub(r',\s*([}\]])', r'\1', fixed)
    return fixed


def _parse_locate_json(raw):
    """从 locate 模型输出里解析 {x_pct, y_pct}，0-100 百分比，容错返回 None。"""
    if not raw:
        return None
    candidates = re.findall(r'\{[^{}]*\}', raw) or [raw]
    for chunk in candidates:
        fixed = _tolerant_json_fix(chunk)
        variants = [chunk, fixed, f'{{{fixed}}}']
        for text in variants:
            try:
                data = json.loads(text)
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            x_pct = data.get('x_pct')
            y_pct = data.get('y_pct')
            try:
                x_pct = float(x_pct)
                y_pct = float(y_pct)
            except (TypeError, ValueError):
                continue
            if not (0 <= x_pct <= 100 and 0 <= y_pct <= 100):
                continue
            return {'x_pct': x_pct, 'y_pct': y_pct, 'reasoning': str(data.get('reasoning', ''))[:200]}
    return None


def _locate_once(target_desc, png, model_config, width, height, context, call_vlm_fn):
    """单次 locate 调用，返回 {'x_pct','y_pct','reasoning'} 或抛 LocateError。"""
    system_prompt = LOCATE_SYSTEM_PROMPT.replace('{width}', str(width)).replace('{height}', str(height))
    if context:
        system_prompt = system_prompt.replace('{context}', f'全局提示: {context}')
    else:
        system_prompt = system_prompt.replace('{context}', '')
    raw = call_vlm_fn(
        png,
        build_locate_user_prompt(target_desc),
        model_config,
        width=width,
        height=height,
        context=context,
        system_prompt=system_prompt,
        return_raw=True,
    )
    logger.info(f'[Locate] 目标={target_desc[:100]}, 响应={str(raw)[:300]}')
    result = _parse_locate_json(raw)
    if not result:
        raise LocateError(f'locate 模型输出无法解析: {str(raw)[:200]}')
    return result


def locate_element(target_desc, png, model_config, width, height, context='',
                   call_vlm_fn=None, retries=1):
    """带重试的 locate：失败自动重试 retries 次，仍失败抛 LocateError。"""
    call_vlm_fn = call_vlm_fn or _default_call_vlm()
    last_err = None
    for attempt in range(retries + 1):
        try:
            return _locate_once(target_desc, png, model_config, width, height, context, call_vlm_fn)
        except Exception as e:
            last_err = e
            if attempt < retries:
                logger.warning(f'[Locate] 第{attempt + 1}次失败，重试: {e}')
    raise LocateError(f'定位目标失败（已重试 {retries} 次）: {target_desc[:100]}，错误: {last_err}')


def _default_call_vlm():
    from ..midscene_runner import call_vlm
    return call_vlm


def resolve_action_coords(action, png, model_config, width, height, context='',
                          use_locate=True, call_vlm_fn=None):
    """为交互动作补齐像素坐标。

    返回 (ok, action, error_msg)：
      - use_locate 且动作带 locate 描述 -> 逐字段 locate 填充坐标；
      - locate 失败/无描述 -> 若已有直接坐标则使用；
      - 都没有 -> (False, action, error)。
    """
    call_vlm_fn = call_vlm_fn or _default_call_vlm()
    action = dict(action)
    if action.get('action') not in INTERACTIVE_ACTIONS:
        return True, action, ''

    fields = locate_fields_for(action)
    if use_locate and fields:
        try:
            for locate_key, coord_pair in fields:
                desc = str(action.get(locate_key, '')).strip()
                if not desc:
                    continue
                loc = locate_element(desc, png, model_config, width, height,
                                     context, call_vlm_fn=call_vlm_fn)
                x = int(round(loc['x_pct'] / 100.0 * width))
                y = int(round(loc['y_pct'] / 100.0 * height))
                action[coord_pair[0]] = max(0, min(width, x))
                action[coord_pair[1]] = max(0, min(height, y))
            if all(
                action.get(c) is not None
                for pair in _coord_pairs_for(action.get('action')) for c in pair
            ):
                return True, action, ''
        except LocateError as e:
            logger.warning(f'[Locate] locate 失败，检查是否可降级直接坐标: {e}')

    if has_direct_coords(action):
        return True, action, ''
    return False, action, '无法确定动作坐标：locate 失败且没有直接坐标，请让规划模型改用 x_pct/y_pct 或更准确的元素描述'


def _coord_pairs_for(action_type):
    from .actions import _COORD_PAIRS
    return _COORD_PAIRS.get(action_type, ())
