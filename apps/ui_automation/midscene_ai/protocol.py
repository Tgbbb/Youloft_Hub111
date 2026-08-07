# -*- coding: utf-8 -*-
"""Midscene 风格 XML 规划协议（移动端精简版）解析。

规划模型每次输出以下标签（均为可选）：
  <planning>...</planning>
  <memory>...</memory>
  <update-plan-content><sub-goal index="1" status="pending|running|finished">描述</sub-goal>...</update-plan-content>
  <mark-sub-goal-done><sub-goal index="1" status="finished" /></mark-sub-goal-done>
  <complete success="true|false">总结消息</complete>
  <log>给用户的一句话进度</log>
  <action-type>tap|long_press|swipe|input|back|home|wait|assert|query</action-type>
  <action-param-json>{...}</action-param-json>
  <error>错误说明</error>
"""
import json
import re
from types import SimpleNamespace


def extract_tag(content, tag):
    """提取 <tag>...</tag> 内容，未找到返回 None。"""
    m = re.search(rf'<{tag}>([\s\S]*?)</{tag}>', content, re.IGNORECASE)
    return m.group(1).strip() if m else None


def extract_complete(content):
    """解析 <complete success="true|false">消息</complete>。"""
    m = re.search(
        r'<complete\s+success\s*=\s*"?(true|false)"?\s*>\s*([\s\S]*?)\s*</complete>',
        content, re.IGNORECASE,
    )
    if not m:
        return None
    return {'success': m.group(1).lower() == 'true', 'message': m.group(2).strip()}


_XML_TAGS = (
    'planning', 'memory', 'log', 'error', 'action-type', 'action-param-json',
    'update-plan-content', 'mark-sub-goal-done', 'complete',
)


def is_truncated(content):
    """检测 XML 输出是否被截断：末尾是不完整的 < 片段，或有开标签无闭标签。"""
    if not content:
        return False
    text = content.strip()
    if re.search(r'<(/?[a-zA-Z-]*)?\s*$', text):
        return True
    for tag in _XML_TAGS:
        opens = len(re.findall(rf'<{tag}[ >]', content, re.IGNORECASE))
        closes = len(re.findall(rf'</{tag}\s*>', content, re.IGNORECASE))
        if opens > closes:
            return True
    return False


def parse_sub_goals(content):
    """解析 <update-plan-content> 内的 <sub-goal> 列表。"""
    if not content:
        return []
    goals = []
    pattern = re.compile(
        r'<sub-goal\s+index\s*=\s*"(\d+)"(?:\s+status\s*=\s*"([^"]*)")?\s*(?:/>|>([\s\S]*?)</sub-goal>)',
        re.IGNORECASE,
    )
    for m in pattern.finditer(content):
        index = int(m.group(1))
        status = (m.group(2) or 'pending').lower()
        if status not in ('pending', 'running', 'finished'):
            status = 'pending'
        description = (m.group(3) or '').strip()
        goals.append({'index': index, 'status': status, 'description': description})
    return goals


def parse_mark_finished(content):
    """解析 <mark-sub-goal-done> 内被标记 finished 的 sub-goal index。"""
    if not content:
        return []
    indexes = []
    pattern = re.compile(
        r'<sub-goal\s+index\s*=\s*"(\d+)"(?:\s+status\s*=\s*"([^"]*)")?\s*/>',
        re.IGNORECASE,
    )
    for m in pattern.finditer(content):
        status = (m.group(2) or '').lower()
        if status == 'finished' or not status:
            indexes.append(int(m.group(1)))
    return indexes


def _parse_param_json(raw):
    """解析 action-param-json，带容错（常见 JSON 错误修复 + 正则兜底）。"""
    if not raw:
        return {}
    candidates = [raw]
    # 常见修复 1：未加引号的 key（locate: "x" / locate = "x"）→ "locate":"x"
    fixed = re.sub(r'(^|[,{]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*[:=]\s*', r'\1"\2":', raw)
    # 常见修复 2：单引号值 -> 双引号
    fixed = re.sub(r'"\s*:\s*\'([^\']*)\'', r'": "\1"', fixed)
    # 常见修复 3：尾逗号
    fixed = re.sub(r',\s*([}\]])', r'\1', fixed)
    candidates.append(fixed)
    candidates.append(f'{{{fixed}}}')
    for candidate in candidates:
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except Exception:
            continue
    # 正则兜底：带引号 key 的提取
    out = {}
    keys = ('text', 'duration', 'x', 'y', 'x1', 'y1', 'x2', 'y2',
            'x_pct', 'y_pct', 'x1_pct', 'y1_pct', 'x2_pct', 'y2_pct',
            'locate', 'locate_start', 'locate_end', 'description', 'passed')
    for key in keys:
        m = re.search(rf'"{key}"\s*:\s*("([^"]*)"|(-?\d+(?:\.\d+)?))', fixed)
        if m:
            if m.group(2) is not None:
                out[key] = m.group(2)
            else:
                num = m.group(3)
                out[key] = float(num) if '.' in num else int(num)
    return out


def parse_planning_response(content):
    """解析规划模型 XML 输出 → SimpleNamespace。

    truncated 字段：输出疑似被截断（末尾不完整或标签未闭合），供引擎做
    错误反馈重规划，避免把残缺动作照常执行。
    """
    action_type = extract_tag(content, 'action-type') or ''
    action_type = action_type.split('<')[0].strip().lower()
    update_goals = parse_sub_goals(extract_tag(content, 'update-plan-content') or '')
    mark_done = parse_mark_finished(extract_tag(content, 'mark-sub-goal-done') or '')
    return SimpleNamespace(
        planning=extract_tag(content, 'planning'),
        memory=extract_tag(content, 'memory'),
        log=extract_tag(content, 'log'),
        error=extract_tag(content, 'error'),
        complete=extract_complete(content),
        update_sub_goals=update_goals,
        mark_finished_indexes=mark_done,
        action_type=action_type,
        action_param=_parse_param_json(extract_tag(content, 'action-param-json')),
        truncated=is_truncated(content),
    )
