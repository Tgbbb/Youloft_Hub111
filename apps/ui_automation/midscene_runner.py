# -*- coding: utf-8 -*-
"""
Midscene AI 移动端自动化 - 纯 Python Runner
核心循环: 截图(ADB) → VLM 看图 → 返回动作 → ADB 执行 → 循环

智能规划模式 (aiAct):
  VLM 携带总目标，持续决策下一步 → 执行 → 截图 → 再决策 → 直到 done
  不是预拆解，而是每步实时决策。Midscene 文档证实了这一点。
"""
import os
import re
import json
import base64
import logging
import subprocess
import shutil
import time
import platform as sys_platform
from datetime import datetime
import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

_SUBPROCESS_KWARGS = {}
if sys_platform.system() == 'Windows':
    _SUBPROCESS_KWARGS['creationflags'] = subprocess.CREATE_NO_WINDOW


# ============================================================
# 步骤解析
# ============================================================

def parse_ai_prompt(ai_prompt):
    steps = []
    raw = []
    for line in ai_prompt.strip().split('\n'):
        stripped = line.strip()
        if not stripped:
            continue
        # 行首空白（空格/制表符均可）视为缩进，用于识别分支子步骤
        indent = len(line) - len(line.lstrip())
        raw.append({'text': stripped, 'indent': indent})

    def _clean(text):
        repeat = text.startswith('重复')
        if repeat:
            text = text[2:].strip()
        text = re.sub(r'^(\d+[\.\)、]\s*)', '', text)
        text = re.sub(r'^[-*•]\s*', '', text)
        return text, repeat

    i = 0
    while i < len(raw):
        ln = raw[i]
        instruction, repeat = _clean(ln['text'])
        if not instruction:
            i += 1
            continue
        # 分支头：以「如果/若」开头、列首无缩进、以冒号结尾
        is_branch = (
            ln['indent'] == 0
            and (instruction.startswith('如果') or instruction.startswith('若'))
            and (instruction.rstrip().endswith(':') or instruction.rstrip().endswith('：'))
        )
        if is_branch:
            children_raw = []
            j = i + 1
            while j < len(raw) and raw[j]['indent'] > 0:
                ctext, crepeat = _clean(raw[j]['text'])
                if ctext:
                    children_raw.append({'instruction': ctext, 'repeat': crepeat})
                j += 1
            if not children_raw:
                raise ValueError(f'分支 "{instruction}" 必须至少有一个缩进的子步骤')
            header_index = len(steps)
            condition = (
                instruction.rstrip('：:')
                .replace('如果', '', 1)
                .replace('若', '', 1)
                .strip()
            )
            node = {
                'instruction': instruction,
                'repeat': repeat,
                'type': 'branch',
                'condition': condition,
                'children': [],
            }
            steps.append(node)
            for ct in children_raw:
                child_index = len(steps)
                steps.append({'instruction': ct['instruction'], 'repeat': ct['repeat'],
                              'branch_parent': header_index})
                node['children'].append(child_index)
            i = j
        else:
            steps.append({'instruction': instruction, 'repeat': repeat})
            i += 1
    return steps


# ============================================================
# ADB
# ============================================================

def _adb(device_id, *args, timeout=15):
    cmd = ['adb', '-s', device_id] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          encoding='utf-8', errors='replace', **_SUBPROCESS_KWARGS)

def adb_input_text(device_id, text):
    """输入文本：非 ASCII/特殊字符走 yadb（支持中文），否则单引号全字符转义
    走 `input text`（对齐 Midscene shellEscapeArg，空格/&/;/$/` 等全部由
    单引号保护，不再逐字转义）。返回证据 dict {'ok','returncode','stderr',
    'latency','fallback_used'}。"""
    text = str(text or '')
    if not text:
        return {'ok': True, 'returncode': 0, 'stderr': '', 'latency': 0.0,
                'fallback_used': False}
    start = time.time()
    fallback_used = False
    if _needs_yadb(text):
        if _yadb_input(device_id, text):
            logger.info('[ADB] 使用 yadb 输入非 ASCII/特殊字符')
            return {'ok': True, 'returncode': 0, 'stderr': '', 'latency': round(time.time() - start, 3),
                    'fallback_used': False}
        logger.warning('[ADB] yadb 不可用，降级 input text（非 ASCII 文本可能无法输入）')
        fallback_used = True
    escaped = text.replace("'", "'\\''")
    r = _adb(device_id, 'shell', 'input', 'text', f"'{escaped}'")
    ev = _adb_evidence(r, start)
    ev['fallback_used'] = fallback_used
    return ev


_YADB_PUSHED_DEVICES = set()


def _yadb_bin_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'midscene_ai', 'bin', 'yadb')


def _download_yadb(dest):
    """尽力下载 yadb 二进制（Midscene 同款 GitHub Release v1.1.1），失败返回 False。"""
    url = 'https://github.com/ysbing/YADB/releases/download/v1.1.1/yadb'
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        r = httpx.get(url, timeout=60, follow_redirects=True)
        if r.status_code == 200 and r.content:
            with open(dest, 'wb') as f:
                f.write(r.content)
            logger.info(f'[ADB] yadb 已下载: {dest} ({len(r.content)} bytes)')
            return True
        logger.warning(f'[ADB] yadb 下载失败 HTTP {r.status_code}')
    except Exception as e:
        logger.warning(f'[ADB] yadb 下载失败: {e}')
    return False


def _ensure_yadb(device_id):
    """确保 yadb 二进制已推送到设备 /data/local/tmp（每设备一次）。"""
    if device_id in _YADB_PUSHED_DEVICES:
        return True
    dest = _yadb_bin_path()
    if not os.path.exists(dest):
        _download_yadb(dest)
    if os.path.exists(dest) and os.path.getsize(dest) > 1000:
        r = _adb(device_id, 'push', dest, '/data/local/tmp/yadb', timeout=120)
        if r.returncode == 0:
            _YADB_PUSHED_DEVICES.add(device_id)
            logger.info(f'[ADB] yadb 已推送: {device_id}')
            return True
        logger.warning(f'[ADB] yadb push 失败: {r.stderr[:200]}')
    return False


def _needs_yadb(text):
    """对齐 Midscene shouldUseYadbForText：非 ASCII / %x 格式符 / \\ ` $ /
    同时含双引号与单引号时走 yadb，input text 无法正确处理。"""
    return (
        any(ord(ch) >= 128 for ch in text)
        or re.search(r'%[a-zA-Z]', text) is not None
        or re.search(r'[\\`$]', text) is not None
        or ('"' in text and "'" in text)
    )


def _yadb_input(device_id, text):
    """通过 yadb (app_process) 输入文本，支持中文/特殊字符。"""
    if not _ensure_yadb(device_id):
        return False
    escaped = text.replace("'", "'\\''").replace('\n', '\\n')
    r = _adb(device_id, 'shell', 'app_process',
             '-Djava.class.path=/data/local/tmp/yadb', '/data/local/tmp',
             'com.ysbing.yadb.Main', '-keyboard', f"'{escaped}'", timeout=30)
    if r.returncode != 0:
        logger.warning(f'[ADB] yadb 执行失败: {r.stderr[:200]}')
    return r.returncode == 0

def adb_execute(device_id, action):
    """执行 VLM 动作，返回证据 dict {'ok','returncode','stderr','latency'}
    （input 额外带 fallback_used）。不抛异常。"""
    t = action.get('action', '')
    start = time.time()
    if t in ('tap', 'click'):
        r = _adb(device_id, 'shell', 'input', 'tap', str(int(float(action.get('x',0)))), str(int(float(action.get('y',0)))))
    elif t == 'swipe':
        r = _adb(device_id, 'shell', 'input', 'swipe', str(int(float(action.get('x1',0)))), str(int(float(action.get('y1',0)))),
                 str(int(float(action.get('x2',0)))), str(int(float(action.get('y2',0)))), str(action.get('duration',300)))
    elif t == 'input':
        return adb_input_text(device_id, action.get('text', ''))
    elif t == 'back':
        r = _adb(device_id, 'shell', 'input', 'keyevent', 'KEYCODE_BACK')
    elif t == 'home':
        r = _adb(device_id, 'shell', 'input', 'keyevent', 'KEYCODE_HOME')
    elif t == 'long_press':
        x, y, d = int(float(action.get('x',0))), int(float(action.get('y',0))), action.get('duration',2000)
        r = _adb(device_id, 'shell', 'input', 'swipe', str(x), str(y), str(x), str(y), str(d))
    elif t == 'launch':
        r = _adb(device_id, 'shell', 'monkey', '-p', action.get('package',''), '1')
    else:
        return {'ok': True, 'returncode': 0, 'stderr': '', 'latency': 0.0}
    return _adb_evidence(r, start)

def _normalize_pct(v):
    """把模型输出的百分比归一化为 0-100；>100 视为旧模型(qwen3-vl-plus)的 10x 格式。"""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v / 10.0 if v > 100 else v


def _build_action_rec(action, png):
    """把 VLM 动作 + 执行前截图转成录制条目（调用方已过滤 assert/query/done）。
    新增 before_hash（动作执行前页面指纹；纯色页 phash=0 时不加门控）与 conditional（障碍处理标记）。"""
    t = action.get('action', '')
    before = str(_phash(png))
    rec = {
        'action': t,
        # 只有模型真实返回百分比才存；缺失时存 0，回放退回像素值
        'x_pct': _normalize_pct(action.get('x_pct')) or 0,
        'y_pct': _normalize_pct(action.get('y_pct')) or 0,
        'x': action.get('x', 0),
        'y': action.get('y', 0),
        'text': action.get('text', ''),
        'before_hash': before if before != '0' else '',
        'conditional': action.get('step_status') == 'in_progress',
    }
    if t == 'swipe':
        rec['x1_pct'] = _normalize_pct(action.get('x1_pct', 0)) or 0
        rec['y1_pct'] = _normalize_pct(action.get('y1_pct', 0)) or 0
        rec['x2_pct'] = _normalize_pct(action.get('x2_pct', 0)) or 0
        rec['y2_pct'] = _normalize_pct(action.get('y2_pct', 0)) or 0
        rec['x1'] = action.get('x1', 0)
        rec['y1'] = action.get('y1', 0)
        rec['x2'] = action.get('x2', 0)
        rec['y2'] = action.get('y2', 0)
    if t == 'wait':
        rec['duration'] = _clamp_wait_duration(action)
    return rec


# 回放动作的默认等待（实测缺失时的兜底；实测值按动作执行到下一次截图的实际耗时记录）
_DEFAULT_WAIT_AFTER = {
    'tap': 2.0, 'click': 2.0, 'long_press': 0.5, 'back': 0.5,
    'home': 0.5, 'input': 0.2, 'swipe': 1.5, 'wait': 3.0,
}


# ============================================================
# 异常分层采集（anomaly 机制）
# 纠错点（tap 重试 / hash 降级 / 跳过 / 等待超时 / 重规划 / 卡死 /
# 定位重试 / ADB / WDA / 截图）统一产出结构化异常，随 steps_detail 落库。
# ============================================================

ANOMALY_TYPES = {
    'tap_retry': {'label': '点击重试', 'default_layer': 'unknown'},
    'hash_mismatch_fallback': {'label': '页面指纹不匹配', 'default_layer': 'unknown'},
    'action_skipped': {'label': '条件动作跳过', 'default_layer': 'app'},
    'stable_wait_timeout': {'label': '页面稳定等待超时', 'default_layer': 'unknown'},
    'replan': {'label': '重规划', 'default_layer': 'unknown'},
    'stuck_detected': {'label': '卡死检测', 'default_layer': 'unknown'},
    'tap_repeat_no_change': {'label': '重复动作无变化', 'default_layer': 'unknown'},
    'locate_retry': {'label': '定位重试', 'default_layer': 'unknown'},
    'adb_error': {'label': 'ADB 错误', 'default_layer': 'execution'},
    'wda_error': {'label': 'WDA 错误', 'default_layer': 'execution'},
    'screenshot_error': {'label': '截图错误', 'default_layer': 'execution'},
}


def _infer_anomaly_layer(atype, evidence):
    """按证据推断异常层级：
    - execution: 环境级硬证据（adb 非 0、WDA 非 200、请求异常/超时）
    - app:       调用成功但页面类间接证据（tap 重试、指纹不匹配、等待超时等）
    - unknown:   单次事件无旁证，不下结论
    """
    evidence = evidence or {}
    for key in ('returncode', 'status_code', 'first_status'):
        val = evidence.get(key)
        if val not in (None, 0, 200, ''):
            return 'execution'
    if evidence.get('error') or evidence.get('first_error'):
        return 'execution'
    if atype in ('tap_retry', 'hash_mismatch_fallback', 'stable_wait_timeout',
                 'stuck_detected', 'action_skipped', 'tap_repeat_no_change'):
        # 页面类事件：有旁证（环境正常 / 页面指纹比较）才归 app，
        # 单次事件无旁证一律 unknown，报告只列可能原因、不下结论
        return 'app' if evidence else 'unknown'
    return ANOMALY_TYPES.get(atype, {}).get('default_layer', 'unknown')


SEVERITY_LABEL = {
    'minor': '轻微抖动',
    'recovered': '纠错救回',
    'critical': '疑似根因',
}

# 页面类纠错类型：环境正常时表示靠纠错救回（recovered 级）
_SEVERITY_RECOVERED_TYPES = {
    'hash_mismatch_fallback', 'replan', 'stuck_detected',
    'stable_wait_timeout', 'locate_retry', 'tap_repeat_no_change',
}


def _infer_anomaly_severity(atype, evidence, layer=None, recovered=True):
    """按证据/层级/恢复状态推断影响度：
    - critical: 环境硬错误，或最终未恢复（疑似根因）
    - recovered: 靠纠错救回（重规划/降级/多次重试/等待超时）
    - minor: 轻微抖动（单次重试即恢复）
    """
    if layer == 'execution' or not recovered:
        return 'critical'
    if atype == 'tap_retry':
        try:
            return 'recovered' if int((evidence or {}).get('attempt', 1)) >= 2 else 'minor'
        except (TypeError, ValueError):
            return 'minor'
    if atype in _SEVERITY_RECOVERED_TYPES:
        return 'recovered'
    return 'minor'


def _build_anomaly(atype, message, evidence=None, layer=None, recovered=True, severity=None):
    """构建一条结构化异常（可 JSON 序列化）。

    layer 未显式指定时按证据推断：环境硬证据 -> execution，
    页面类间接证据 -> app，无旁证 -> unknown。
    severity 未显式指定时按层级/恢复状态/证据推断（minor/recovered/critical）。"""
    evidence = dict(evidence or {})
    meta = ANOMALY_TYPES.get(atype, {})
    layer = layer or _infer_anomaly_layer(atype, evidence)
    return {
        'type': atype,
        'label': meta.get('label', atype),
        'layer': layer,
        'severity': severity or _infer_anomaly_severity(atype, evidence, layer, recovered),
        'message': str(message or '')[:500],
        'evidence': evidence,
        'recovered': bool(recovered),
    }


# ============================================================
# 阈值告警配置（常量 + 环境变量覆盖，与 AIACT_* 同风格）
# 评估入口 evaluate_anomaly_alert(steps)，报告/前端共用。
# ============================================================

ANOMALY_ALERT_EXECUTION_ANY = 1   # execution 层异常达到该次数即 critical 告警（ANOMALY_ALERT_EXECUTION_ANY）
ANOMALY_ALERT_CRITICAL_ANY = 1    # critical 级异常达到该次数即 critical 告警（ANOMALY_ALERT_CRITICAL_ANY）
ANOMALY_ALERT_RETRY_COUNT = 3     # 同一类型页面类异常累计达到该次数即 warn 告警（ANOMALY_ALERT_RETRY_COUNT）
ANOMALY_ALERT_FALLBACK_RATIO = 0.3  # 带异常通过步骤占比达到该阈值即 warn 告警（ANOMALY_ALERT_FALLBACK_RATIO）


def _anomaly_env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _anomaly_env_float(name, default):
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def evaluate_anomaly_alert(steps):
    """按阈值评估一次执行的异常告警级别。

    返回 {'level': 'ok'|'warn'|'critical', 'reasons': [...]}：
    - critical: 环境硬错误或未恢复（疑似根因）达到阈值；
    - warn:     同类型页面类异常过多，或纠错救回步骤占比过高；
    - ok:       无异常或低于阈值。
    """
    ex_any = _anomaly_env_int('ANOMALY_ALERT_EXECUTION_ANY', ANOMALY_ALERT_EXECUTION_ANY)
    cr_any = _anomaly_env_int('ANOMALY_ALERT_CRITICAL_ANY', ANOMALY_ALERT_CRITICAL_ANY)
    retry_n = _anomaly_env_int('ANOMALY_ALERT_RETRY_COUNT', ANOMALY_ALERT_RETRY_COUNT)
    ratio = _anomaly_env_float('ANOMALY_ALERT_FALLBACK_RATIO', ANOMALY_ALERT_FALLBACK_RATIO)

    all_anomalies = [a for s in steps for a in (s.get('anomalies') or [])]
    if not all_anomalies:
        return {'level': 'ok', 'reasons': []}

    reasons = []
    level = 'ok'
    passed_steps = [s for s in steps if s.get('status') == 'passed']
    # 纠错救回步骤：通过但含 recovered/critical 级异常（轻微抖动不计入占比）
    warned_steps = [
        s for s in passed_steps
        if any(a.get('severity') in ('recovered', 'critical')
               for a in (s.get('anomalies') or []))
    ]

    # 1. execution 层（环境硬证据）达到阈值 -> critical
    exec_count = sum(1 for a in all_anomalies if a.get('layer') == 'execution')
    if exec_count >= ex_any:
        level = 'critical'
        reasons.append(f'执行环境异常 {exec_count} 次（ADB/WDA/截图）')

    # 2. critical 严重度（含未恢复）达到阈值 -> critical
    critical_count = sum(1 for a in all_anomalies if a.get('severity') == 'critical')
    if critical_count >= cr_any:
        level = 'critical'
        reasons.append(f'疑似根因异常 {critical_count} 次（含未恢复/环境错误）')

    # 3. 同一类型页面类异常过多 -> warn
    page_by_type = {}
    for a in all_anomalies:
        if a.get('layer') == 'execution':
            continue
        page_by_type[a.get('type', 'unknown')] = page_by_type.get(a.get('type', 'unknown'), 0) + 1
    top_type = max(page_by_type.items(), key=lambda kv: kv[1]) if page_by_type else ('', 0)
    if top_type[1] >= retry_n:
        type_label = ANOMALY_TYPES.get(top_type[0], {}).get('label', top_type[0])
        if level != 'critical':
            level = 'warn'
        reasons.append(f'同一类页面异常重复出现 {top_type[1]} 次（{type_label}）')

    # 4. 带异常通过步骤占比过高 -> warn
    if passed_steps and ratio > 0:
        fallback_ratio = len(warned_steps) / len(passed_steps)
        if fallback_ratio >= ratio:
            if level != 'critical':
                level = 'warn'
            reasons.append(
                f'纠错救回步骤占比 {fallback_ratio:.0%}（{len(warned_steps)}/{len(passed_steps)}），'
                f'超过阈值 {ratio:.0%}'
            )

    return {'level': level, 'reasons': reasons}


def _adb_evidence(r, start):
    """把 subprocess 结果归一化为 ADB 证据 dict（兼容测试 mock 返回 None）。"""
    latency = round(time.time() - start, 3)
    if r is None:
        return {'ok': True, 'returncode': 0, 'stderr': '', 'latency': latency}
    return {
        'ok': getattr(r, 'returncode', 0) == 0,
        'returncode': getattr(r, 'returncode', 0),
        'stderr': str(getattr(r, 'stderr', '') or '')[:300],
        'latency': latency,
    }


class ExecutionStopped(RuntimeError):
    """用户手动停止执行时抛出的中断异常，用于打断进行中的 VLM 调用。"""


def _clamp_wait_after(seconds, floor=0.2, ceil=5.0):
    """录制实测 wait_after 兜底：下限 0.2s、上限 5s。
    实测值会包含录制时的 VLM 思考时间，若不设上限会被原样重放（几十秒空等）。"""
    try:
        return max(min(round(float(seconds), 2), ceil), floor)
    except (TypeError, ValueError):
        return floor


def _clamp_wait_duration(action, default=3, floor=0.5, ceil=60):
    """wait 动作时长解析：仅当指令明确给出秒数（duration）时按该值等待。
    缺失/非法回落 default（3s），越界 clamp 到 [floor, ceil]（0.5~60s）。"""
    raw = (action or {}).get('duration', default)
    try:
        dur = float(raw)
    except (TypeError, ValueError):
        return default
    if dur <= 0:
        return default
    return min(max(dur, floor), ceil)


def _norm_instruction(text):
    """规范化步骤文案：NFKC 统一全半角，去空白与常见标点，用于宽松匹配。"""
    import unicodedata
    t = unicodedata.normalize('NFKC', str(text or ''))
    t = re.sub(r'[\s，。！？、,.!?；;：:"“”‘’()（）【】\[\]<>《》\-—_]+', '', t)
    return t.strip().lower()


def _instruction_similar(recorded, current):
    """步骤文案宽松匹配：归一化后相等，或文本高度相似（SequenceMatcher 容忍
    标点/空白差异与"就/请/的"等插入词）；长度悬殊不配，防止"点击同意"误配
    "点击同意并继续"。"""
    import difflib
    a, b = _norm_instruction(recorded), _norm_instruction(current)
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if len(longer) > len(shorter) * 1.5:
        return False
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.88


def _resolve_coord(a, coord, ref):
    """回放坐标解析：优先用百分比按当前设备分辨率换算（分辨率无关），
    百分比缺失/无效时退回旧录制的像素值，兼容 10x 百分比。"""
    pct = a.get(f'{coord}_pct')
    pct_v = _normalize_pct(pct)
    if pct_v is not None and pct_v > 0:
        return int(round(pct_v / 100.0 * ref))
    try:
        return int(float(a.get(coord, 0) or 0))
    except (TypeError, ValueError):
        return 0


def _execute_replay_action(device_id, ios_dev, a):
    """执行单个回放动作（坐标已解析为像素）。

    返回 {'ok', 'evidence', 'message'}：环境错误（ADB 非 0 / WDA 非 200 /
    请求异常）以 ok=False 上报，供上层采集 adb_error / wda_error 异常；
    stable_wait_timeout 标记页面稳定等待是否超时（不阻塞执行）。"""
    start = time.time()
    result = {'ok': True, 'evidence': {}, 'message': '',
              'stable_wait_timeout': False}
    action_type = a.get('action', 'tap')
    if action_type in ('tap', 'click'):
        if ios_dev:
            ev = ios_dev.tap(a['x'], a['y'])
            result['evidence'] = ev
            if not ev.get('ok', True):
                result['ok'] = False
                result['message'] = f"WDA tap 失败: {ev.get('error', '')}"
        else:
            ev = _adb_evidence(_adb(device_id, 'shell', 'input', 'tap', str(a['x']), str(a['y'])), start)
            result['evidence'] = ev
            if not ev.get('ok', True):
                result['ok'] = False
                result['message'] = f"ADB tap 失败: {ev.get('stderr', '')}"
    elif action_type == 'swipe':
        if ios_dev:
            ev = ios_dev.execute_action(a)
        else:
            ev = adb_execute(device_id, a)
        result['evidence'] = ev
        if not ev.get('ok', True):
            result['ok'] = False
            result['message'] = f"{'WDA' if ios_dev else 'ADB'} swipe 失败: {ev.get('error') or ev.get('stderr', '')}"
    elif action_type == 'input':
        if ios_dev:
            ev = ios_dev.execute_action(a)
        else:
            ev = adb_input_text(device_id, a.get('text', ''))
        result['evidence'] = ev
        if not ev.get('ok', True):
            result['ok'] = False
            result['message'] = f"{'WDA' if ios_dev else 'ADB'} input 失败: {ev.get('error') or ev.get('stderr', '')}"
    elif action_type == 'back':
        if ios_dev:
            ev = ios_dev.execute_action(a)
        else:
            ev = _adb_evidence(_adb(device_id, 'shell', 'input', 'keyevent', 'KEYCODE_BACK'), start)
        result['evidence'] = ev
        if not ev.get('ok', True):
            result['ok'] = False
            result['message'] = f"{'WDA' if ios_dev else 'ADB'} back 失败: {ev.get('error') or ev.get('stderr', '')}"
    elif action_type == 'home':
        if ios_dev:
            ev = ios_dev.execute_action(a)
        else:
            ev = _adb_evidence(_adb(device_id, 'shell', 'input', 'keyevent', 'KEYCODE_HOME'), start)
        result['evidence'] = ev
        if not ev.get('ok', True):
            result['ok'] = False
            result['message'] = f"{'WDA' if ios_dev else 'ADB'} home 失败: {ev.get('error') or ev.get('stderr', '')}"
    elif action_type == 'long_press':
        if ios_dev:
            ev = ios_dev.execute_action(a)
        else:
            ev = adb_execute(device_id, a)
        result['evidence'] = ev
        if not ev.get('ok', True):
            result['ok'] = False
            result['message'] = f"{'WDA' if ios_dev else 'ADB'} long_press 失败: {ev.get('error') or ev.get('stderr', '')}"
    elif action_type == 'wait':
        # 显式等待：仅当录制时带 duration 才按该时长等；无 duration 保持默认 3s。
        # wait 本身就是等待，结束后直接返回，不再追加"页面稳定等待"。
        time.sleep(_clamp_wait_duration(a))
        return result
    # swipe 动画需要更长等待（基线），之后统一走页面稳定等待
    if action_type in ('swipe',):
        time.sleep(1.5)
    # 等页面稳定：稳定即继续，最多 5s 超时（超时不阻塞，交给后续校验/VLM 兜底）。
    # 不再重放录制 wait_after 绝对值——它含录制时 VLM 思考时间，且录制环境快慢不代表回放。
    result['stable_wait_timeout'] = not _wait_screen_stable(
        device_id, ios_dev, timeout=5.0, check_interval=0.5, label='动作后页面')
    return result


def _replay_actions(device_id, ios_dev, actions, width, height, gate_all=False, anomalies=None):
    """回放动作序列（条件和普通步骤共用）：支持 tap/click、swipe、input、back、home、long_press。
    坐标优先用百分比按当前设备分辨率换算，兼容旧录制像素值与 10x 百分比。
    门控规则：旧数据（无 before_hash）与普通步骤的目标动作（conditional=false）无条件执行；
    障碍动作（conditional=true），或 gate_all=True 的条件步骤内所有动作，按 before_hash 门控——
    当前页面匹配才执行，不匹配跳过该动作继续。返回 {'played': n, 'skipped': m}。
    anomalies：可选列表参数（传入后保持返回结构不变），跳过/环境错误/稳定等待
    超时事件会追加到该列表，供调用方随步骤结果落库。"""
    played = 0
    skipped = 0
    if anomalies is None:
        anomalies = []
    for raw in actions:
        a = dict(raw)
        action_type = a.get('action', 'tap')
        # 坐标统一解析：优先百分比，缺失/无效退回像素
        if action_type in ('tap', 'click', 'long_press'):
            a['x'] = _resolve_coord(a, 'x', width)
            a['y'] = _resolve_coord(a, 'y', height)
        elif action_type == 'swipe':
            for coord in ('x1', 'y1', 'x2', 'y2'):
                ref = width if coord.startswith('x') else height
                a[coord] = _resolve_coord(a, coord, ref)

        cond_flag = a.get('conditional')
        if isinstance(cond_flag, str):
            cond_flag = cond_flag.lower() == 'true'
        need_gate = bool(a.get('before_hash')) and (cond_flag or gate_all)
        if need_gate:
            png = ios_dev.screenshot() if ios_dev else adb_screenshot(device_id)
            if not _is_same_page_by_hash(png, a['before_hash']):
                skipped += 1
                logger.info(f'[Runner] 回放跳过动作 {action_type}: 前置页面不匹配')
                anomalies.append(_build_anomaly(
                    'action_skipped',
                    f'回放跳过动作 {action_type}: 前置页面与录制不匹配',
                    evidence={'action': action_type,
                              'before_hash': str(a['before_hash']),
                              'current_hash': str(_phash(png))},
                    recovered=True,
                ))
                time.sleep(0.5)  # 留页面稳定余量
                continue

        exec_result = _execute_replay_action(device_id, ios_dev, a)
        played += 1
        if not exec_result.get('ok', True):
            atype = 'wda_error' if ios_dev else 'adb_error'
            anomalies.append(_build_anomaly(
                atype,
                exec_result.get('message') or f'{atype} 执行失败',
                evidence=exec_result.get('evidence', {}),
                recovered=True,
            ))
        if exec_result.get('stable_wait_timeout'):
            anomalies.append(_build_anomaly(
                'stable_wait_timeout',
                f'回放动作 {action_type} 后页面稳定等待超时(5s)，继续执行',
                evidence={'action': action_type, 'timeout': 5.0},
                recovered=True,
            ))
    return {'played': played, 'skipped': skipped}

def adb_screenshot(device_id):
    result = subprocess.run(['adb','-s',device_id,'exec-out','screencap','-p'], capture_output=True, timeout=15, **_SUBPROCESS_KWARGS)
    if result.returncode != 0 or not result.stdout: raise RuntimeError('截图失败')
    return result.stdout

def adb_get_screen_size(device_id):
    """返回实际截图尺寸（以 screencap 实测为准），失败回退 wm size。"""
    try:
        size = png_size(adb_screenshot(device_id))
        if size:
            return size
    except Exception:
        pass
    r = _adb(device_id, 'shell', 'wm', 'size')
    m = re.search(r'(\d+)x(\d+)', r.stdout)
    return (int(m.group(1)), int(m.group(2))) if m else (1080,1920)

def grant_permissions(device_id, package):
    for p in ['android.permission.CAMERA','android.permission.READ_EXTERNAL_STORAGE',
              'android.permission.WRITE_EXTERNAL_STORAGE','android.permission.ACCESS_FINE_LOCATION',
              'android.permission.ACCESS_COARSE_LOCATION','android.permission.READ_PHONE_STATE',
              'android.permission.RECORD_AUDIO','android.permission.READ_CONTACTS','android.permission.POST_NOTIFICATIONS']:
        try: _adb(device_id, 'shell', 'pm', 'grant', package, p, timeout=5)
        except: pass


# ============================================================
# 截图压缩 + 保存
# ============================================================

def png_size(png_bytes):
    """读取 PNG 实际像素尺寸 (width, height)；解析失败返回 None。"""
    try:
        from PIL import Image; import io
        return Image.open(io.BytesIO(png_bytes)).size
    except Exception:
        return None

def _compress_png(png_bytes):
    """等比压缩：最长边不超过 900px，保持原图宽高比，避免方向/比例失真。"""
    try:
        from PIL import Image; import io
        img = Image.open(io.BytesIO(png_bytes))
        w, h = img.size
        max_side = max(w, h)
        if max_side > 900:
            scale = 900.0 / max_side
            w2 = max(1, int(round(w * scale)))
            h2 = max(1, int(round(h * scale)))
            img = img.resize((w2, h2), Image.LANCZOS)
        buf = io.BytesIO(); img.save(buf, format='PNG'); return buf.getvalue()
    except: return png_bytes

def _phash(png_bytes):
    """感知哈希：8x8灰度图 → 64位指纹"""
    try:
        from PIL import Image; import io
        img = Image.open(io.BytesIO(png_bytes)).convert('L').resize((8, 8), Image.LANCZOS)
        pixels = list(img.getdata())
        avg = sum(pixels) / 64
        return sum((1 << i) for i, v in enumerate(pixels) if v > avg)
    except: return 0

def _is_same_page(png1, png2):
    """比较两张截图的感知哈希，汉明距离 < 3 判定为同一页"""
    h1 = _phash(png1)
    h2 = _phash(png2)
    if h1 == 0 or h2 == 0:
        return False
    return (h1 ^ h2).bit_count() < 3

def _smart_wait(device_id, ios_dev, before_png, max_wait=2.0, check_interval=0.5):
    """智能等待：每隔check_interval截图对比，页面稳定后立即返回"""
    deadline = time.time() + max_wait
    time.sleep(check_interval)  # 先等第一帧
    while time.time() < deadline:
        png = ios_dev.screenshot() if ios_dev else adb_screenshot(device_id)
        if _is_same_page(before_png, png):
            return  # 页面没变，动作可能已生效，继续
        before_png = png
        time.sleep(check_interval)


def _wait_after_input(device_id, ios_dev, before_png, min_wait=1.2, max_wait=4.0,
                      check_interval=0.4):
    """input 后等待：先静默等 min_wait 给网络校验/自动跳转留时间；
    期间页面若开始变化（如验证码输入后自动跳转），继续跟踪到连续两次稳定为止（最多 max_wait）。
    普通输入（页面一直静止）在 min_wait 后返回，避免拖慢流程。"""
    start = time.time()
    changed = False
    while time.time() - start < max_wait:
        time.sleep(check_interval)
        try:
            cur = ios_dev.screenshot() if ios_dev else adb_screenshot(device_id)
        except Exception:
            continue
        if _is_same_page(before_png, cur):
            if not changed and time.time() - start >= min_wait:
                return  # 普通输入：静默窗口已过，页面未动，直接继续
            continue
        # 页面开始变化（跳转/加载）：跟踪到连续两次稳定
        changed = True
        before_png = cur
        time.sleep(check_interval)
        try:
            cur2 = ios_dev.screenshot() if ios_dev else adb_screenshot(device_id)
        except Exception:
            continue
        if _is_same_page(before_png, cur2):
            return
        before_png = cur2
    logger.info(f'[Runner] input 后等待结束(页面变化={changed}, 耗时{time.time()-start:.1f}s)')


def _wait_screen_stable(device_id, ios_dev, timeout=15.0, check_interval=0.8, label='页面'):
    """等待页面稳定：连续两次截图相同（pHash 距离 <3）即认为页面稳定。
    用于启动后等待首帧稳定、条件步骤判定前等待跳转/加载完成等场景。
    超时返回 False，不阻塞执行（交给后续逻辑/VLM 自行判断当前页面）。"""
    deadline = time.time() + timeout
    time.sleep(check_interval)  # 先等第一帧
    prev = None
    while time.time() < deadline:
        png = ios_dev.screenshot() if ios_dev else adb_screenshot(device_id)
        if prev is not None and _is_same_page(prev, png):
            logger.info(f'[Runner] {label}已稳定，等待耗时 {timeout - max(deadline - time.time(), 0):.1f}s')
            return True
        prev = png
        time.sleep(check_interval)
    logger.warning(f'[Runner] 等待{label}稳定超时({timeout}s)，继续执行')
    return False


def _is_same_page_by_hash(png_bytes, expected_hash):
    """比较截图pHash与预期hash"""
    try:
        expected = int(expected_hash)
    except (ValueError, TypeError):
        return False
    h = _phash(png_bytes)
    if h == 0:
        return False
    return (h ^ expected).bit_count() < 3


CONDITION_CONFIRM_PROMPT = (
    '当前是条件步骤，指令: {instruction}\n'
    '请观察截图，判断指令条件中描述的目标页面/元素是否出现。\n'
    '同时判断当前截图是否属于「全局提示」中需要先处理的障碍（如权限弹窗、渠道选择页等）；若是，请把 anomaly 填 true。\n'
    '只输出 JSON，不要输出任何其他内容：{{"present": true或false, "anomaly": true或false, "reasoning": "一句话说明"}}'
)


GLOBAL_OBSTACLE_PROMPT = (
    '当前任务：清理「全局提示」中需要先处理的障碍（如权限弹窗、渠道选择页、活动/会员弹窗等）。\n'
    '请观察截图：若有这类障碍，按全局提示执行相应动作；若当前没有任何需要处理的障碍，直接返回 {{"action":"done"}}。\n'
    '只输出动作 JSON，不要输出其他内容。'
)


# 元素确认只用最轻量的 system prompt：只做判断、不执行动作，减小请求体避免慢响应
CONDITION_CONFIRM_SYSTEM = (
    '你是移动端界面识别助手。根据截图判断条件目标是否出现、以及当前是否为需先处理的全局障碍。\n'
    '{context}\n'
    '只输出 JSON，不要输出多余内容。'
)


def _ask_condition_present(png_bytes, instruction, model_config, width, height, context='', stop_checker=None):
    """轻量 VLM 确认：条件步骤目标元素是否出现、当前是否为全局障碍。
    返回 (present, anomaly, reasoning)；anomaly 缺省视为 False（向后兼容）。"""
    raw = call_vlm(png_bytes, CONDITION_CONFIRM_PROMPT.format(instruction=instruction),
                   model_config, width=width, height=height, context=context,
                   system_prompt=CONDITION_CONFIRM_SYSTEM,
                   return_raw=True, max_tokens=256, stop_checker=stop_checker)
    logger.info(f'[Condition] 元素确认响应: {str(raw)[:200]}')
    m = re.search(r'"present"\s*:\s*(true|false)', raw, re.IGNORECASE)
    if not m:
        raise ValueError(f'元素确认响应缺少 present 字段: {str(raw)[:200]}')
    present = m.group(1).lower() == 'true'
    am = re.search(r'"anomaly"\s*:\s*(true|false)', raw, re.IGNORECASE)
    anomaly = bool(am) and am.group(1).lower() == 'true'
    reasoning = ''
    rm = re.search(r'"reasoning"\s*:\s*"([^"]*)"', raw)
    if rm:
        reasoning = rm.group(1)
    return present, anomaly, reasoning


def _confirm_condition_target(device_id, ios_dev, instruction, model_config, width, height,
                              initial_png=None, max_attempts=2, wait_interval=2.0,
                              context='', stop_checker=None):
    """条件步骤目标元素确认（带加载等待）：
    - 目标存在 → ('present', 当前截图, reasoning)，播放录制动作
    - 页面稳定且目标不存在、也非全局障碍 → ('absent', 当前截图, reasoning)，判定条件不满足跳过
    - 当前截图是全局提示里的障碍 → ('anomaly', 截图, reasoning)，由调用方降至 VLM 先处理障碍
    - 页面一直在变化(加载中)重试耗尽 / 确认调用失败 → (None, 截图, reasoning)，由调用方降至 VLM
    """
    png = initial_png
    last_png = None
    stable_count = 0
    reasoning = ''
    for attempt in range(max_attempts):
        if png is None:
            png = ios_dev.screenshot() if ios_dev else adb_screenshot(device_id)
        try:
            present, anomaly, reasoning = _ask_condition_present(
                png, instruction, model_config, width, height, context=context,
                stop_checker=stop_checker)
        except ExecutionStopped:
            raise  # 用户停止：不降级、不重试，直接向上传递
        except Exception as e:
            logger.warning(f'[Condition] 元素确认失败({e})，降至VLM')
            return None, png, ''
        if present:
            logger.info(f'[Condition] 目标元素确认存在: {reasoning[:120]}')
            return 'present', png, reasoning
        if anomaly:
            logger.info(f'[Condition] 检测到全局障碍，降至VLM处理: {reasoning[:120]}')
            return 'anomaly', png, reasoning
        # 未出现：判断页面是否仍在变化（加载中）
        if last_png is not None and _is_same_page(last_png, png):
            stable_count += 1
        else:
            stable_count = 0
        last_png = png
        if attempt >= 1 and stable_count >= 1:
            logger.info(f'[Condition] 页面稳定且目标未出现，条件不满足: {reasoning[:120]}')
            return 'absent', png, reasoning
        logger.info(f'[Condition] 目标未出现(第{attempt+1}/{max_attempts}次)，页面仍在变化，{wait_interval}s后重试')
        png = None
        time.sleep(wait_interval)
    logger.warning('[Condition] 重试耗尽仍未确认目标元素，降至VLM')
    return None, last_png, reasoning


def _clear_global_obstacle(device_id, ios_dev, model_config, width, height, context='',
                           max_attempts=3, stop_checker=None):
    """用完整 VLM 把当前屏幕的全局障碍清掉；已清完/无障碍返回 (True, '')，否则 (False, 描述)。"""
    for attempt in range(max_attempts):
        if stop_checker and stop_checker():
            raise ExecutionStopped('用户已停止执行')
        png = ios_dev.screenshot() if ios_dev else adb_screenshot(device_id)
        action = call_vlm(png, GLOBAL_OBSTACLE_PROMPT, model_config, width, height,
                          context=context, stop_checker=stop_checker)
        if action.get('action') == 'done':
            return True, ''
        _replay_actions(device_id, ios_dev, [action], width, height)
    return False, f'全局障碍清理尝试{max_attempts}次未完成'


def _action_fingerprint(action):
    """动作指纹：覆盖 swipe 四坐标与 input 文本，用于卡死判定（对齐 aiAct）。"""
    t = action.get('action', '')
    parts = [t]
    for coord in ('x', 'y', 'x1', 'y1', 'x2', 'y2'):
        if action.get(coord) is not None:
            parts.append(f'{coord}={action[coord]}')
    if t == 'input':
        parts.append(f'text={action.get("text", "")}')
    return '|'.join(parts)


def _action_fingerprint_desc(action):
    """动作指纹的人类可读描述，用于卡死报错信息。"""
    t = action.get('action', '')
    if t in ('tap', 'click', 'long_press'):
        return f"{t}({action.get('x_pct', action.get('x', '?'))},{action.get('y_pct', action.get('y', '?'))})"
    if t == 'swipe':
        return (f"swipe(({action.get('x1_pct', action.get('x1', '?'))},"
                f"{action.get('y1_pct', action.get('y1', '?'))})->"
                f"({action.get('x2_pct', action.get('x2', '?'))},"
                f"{action.get('y2_pct', action.get('y2', '?'))}))")
    if t == 'input':
        return f"input(text={str(action.get('text', ''))[:20]})"
    return str(t)


def _push_step_memory(step_memory, step_num, instruction, action_type='', data=''):
    """记录已完成步骤摘要，供后续步骤 prompt 注入跨步记忆。"""
    entry = {'step': step_num, 'instruction': str(instruction)[:60], 'action': action_type}
    if data:
        entry['data'] = str(data)[:200]
    step_memory.append(entry)


def save_screenshot(png_bytes, execution_id, step_num, suffix=''):
    d = os.path.join(settings.MEDIA_ROOT, 'midscene', str(execution_id))
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, f'step_{step_num}{suffix}.png')
    with open(p, 'wb') as f: f.write(png_bytes)
    return f'{settings.MEDIA_URL}midscene/{execution_id}/step_{step_num}{suffix}.png'

def delete_execution_media(execution_id):
    """删除执行记录对应的截图目录（media/midscene/{execution_id}/），防止磁盘无限增长"""
    try:
        midscene_root = os.path.join(settings.MEDIA_ROOT, 'midscene')
        target = os.path.join(midscene_root, str(execution_id))
        root_abs = os.path.abspath(midscene_root)
        target_abs = os.path.abspath(target)
        # 越界保护：只允许清理 midscene 根目录下的执行截图目录
        if os.path.commonpath([root_abs, target_abs]) != root_abs:
            logger.warning(f'[Media] 拒绝清理越界路径: {target_abs}')
            return False
        if os.path.isdir(target_abs):
            shutil.rmtree(target_abs, ignore_errors=True)
            logger.info(f'[Media] 已清理执行截图目录: {target_abs}')
            return True
    except Exception as e:
        logger.warning(f'[Media] 清理截图目录失败: {e}')
    return False


# ============================================================
# VLM
# ============================================================

VLM_SYSTEM_PROMPT = """你是移动端自动化测试助手。观察手机截图，精确找出操作目标位置。

截图分辨率: {width}x{height} 像素
{context}

响应（一行JSON）：
{"action":"tap","x_pct":50,"y_pct":25,"step_status":"done","reasoning":"..."}
{"action":"long_press","x_pct":50,"y_pct":25,"duration":2000,"step_status":"done","reasoning":"..."}
{"action":"input","text":"hello","step_status":"done","reasoning":"..."}
{"action":"swipe","x1_pct":50,"y1_pct":80,"x2_pct":50,"y2_pct":30,"step_status":"done","reasoning":"..."}
{"action":"back","step_status":"done","reasoning":"..."}
{"action":"wait","duration":5,"step_status":"in_progress","reasoning":"页面加载中，等待..."}
{"action":"assert","passed":true,"reasoning":"..."}
{"action":"query","data":"提取的数据","reasoning":"..."}
{"action":"done","reasoning":"..."}

step_status 说明：
- "done": 动作直接完成了当前步骤指令，可以进入下一步
- "in_progress": 动作是在处理弹窗/渠道选择/权限请求等障碍（需根据全局提示处理），步骤尚未完成，仍需继续

规则：
- 指令含"验证/检查/确认/断言"→用assert，看图判断passed=true/false
- 断言时页面仍在加载（加载转圈/骨架屏/进度条）→先用wait，不要断言，等页面加载完成再判断
- 指令含"提取/获取/查询"→用query，data字段放提取结果
- 如果界面加载完毕但找不到目标→用swipe滑动查找。绝对不要猜坐标
- 如果界面还在加载/动画/过渡中→用wait等待；仅当指令明确给出秒数（如"等待20秒"）时，duration填该秒数（1-60），未等完可连续输出wait；指令没有明确时长时不要填duration（保持默认3秒）
- 滚动选项列表/下拉框：
  - 从可滚动的选择器、下拉框、菜单等选项列表中选择时，先打开该控件；列表打开后与列表本身交互，不要操作页面其他区域
  - 列表打开且目标选项可见→直接精确点击该选项；目标不可见→先滚动打开的列表/下拉框查找，不要放弃或去点其他元素
  - 在打开的列表/下拉框内查找时，使用带明确距离的小步滚动（通常50-120像素），不要省略滚动距离，否则默认滚动距离可能跳过目标选项并造成来回振荡
  - 列表内查找用短滚动，避免跳过中间选项
- 输入文字后：上一步已执行输入动作且当前输入框不为空→直接视为输入成功；不要因为截图可见文字与目标不同（可能由裁剪、横向滚动、窄输入框、选中、光标或识别误差导致）就重复输入或修正输入；仅当输入框明确为空或页面出现明确错误提示时才重试输入
- x_pct/y_pct必须是0到100之间的数字（如62表示62%，不要用625这样的三位数）
- 顶部元素对应y_pct很小（例如最顶部按钮y_pct约5~8）
- x_pct: 从左到右的百分比（0=最左，50=中间，100=最右）
- y_pct: 从上到下的百分比（0=最上，50=中间，100=最下）
- 智能规划模式下：每次只返回一个操作。完成后返回done。
- 逐行模式下：只返回动作JSON，不要返回done。单行指令只做一个动作。"""

def _parse_vlm_response(content):
    logger.info(f'[VLM] 原始响应(前500字符): {content[:500]}')
    for line in content.strip().split('\n'):
        line = line.strip()
        if not line or not line.startswith('{'): continue
        # 修复常见 VLM JSON 错误
        line = re.sub(r'([,\{])\s*([a-z_]+)="([^"]*)"', r'\1"\2":"\3"', line)
        line = re.sub(r'([,\{])\s*([a-z_]+)=(\d+)', r'\1"\2":\3', line)
        line = re.sub(r'"x"\s*:\s*(\d+),(\d+)\s*,', r'"x":\1,"y":\2,', line)
        # 修复 y_pct="623  → "y_pct":"623" (VLM 常见格式错误)
        line = re.sub(r'([a-z_]+)="(\d+)([,}\]])', r'"\1":"\2"\3', line)
        # 修复 y_pct="   → "y_pct":0 (空值)
        line = re.sub(r'([a-z_]+)="([,}\]])', r'"\1":0\2', line)
        # 修复 VLM 误输出 ] 而非 } 或 ,  (如 y_pct":590]  → y_pct":590,)
        line = re.sub(r'(\d+)\]\s*"', r'\1,"', line)
        try:
            r = json.loads(line)
            if isinstance(r, dict) and 'action' in r: return r
        except: continue
    # 正则兜底
    am = re.search(r'"action"\s*:\s*"([^"]+)"', content)
    if am:
        return {'action': am.group(1),
                'x': int(re.search(r'"x"\s*:\s*(\d+)', content).group(1)) if re.search(r'"x"\s*:\s*(\d+)', content) else 0,
                'y': int(re.search(r'"y"\s*:\s*(\d+)', content).group(1)) if re.search(r'"y"\s*:\s*(\d+)', content) else 0,
                'text': (re.search(r'"text"\s*:\s*"([^"]*)"', content) or re.search(r'"text"\s*:\s*"([^"]*)', content) or [None,''])[1],
                'reasoning': (re.search(r'"reasoning"\s*:\s*"([^"]*)"', content) or [None,''])[1] or '',
                'step_status': (re.search(r'"step_status"\s*:\s*"([^"]+)"', content) or [None,'done'])[1]}
    raise ValueError(f'无法解析 VLM 响应: {content[:300]}')


def call_vlm(png_bytes, instruction, model_config, width=1080, height=1920, context='',
             system_prompt=None, return_raw=False, max_tokens=1024, stop_checker=None,
             timeout=90.0):
    """调用 VLM。system_prompt 可替换（aiAct 引擎传入规划/locate 提示词）；
    return_raw=True 时返回模型原始文本（XML 规划协议），否则返回解析后的 JSON 动作。"""
    png_bytes = _compress_png(png_bytes)
    png_w, png_h = png_size(png_bytes) or (width, height)
    logger.info(f'[VLM] 截图已压缩: {len(png_bytes)} bytes ({png_w}x{png_h})')
    b64 = base64.b64encode(png_bytes).decode('utf-8')
    ctx = f'全局提示: {context}' if context else ''
    system_prompt = (VLM_SYSTEM_PROMPT if system_prompt is None else system_prompt)
    system_prompt = (system_prompt
                     .replace('{width}', str(png_w)).replace('{height}', str(png_h))
                     .replace('{context}', ctx))
    base_url = model_config.base_url if hasattr(model_config, 'base_url') else model_config.get('base_url','')
    api_key = model_config.api_key if hasattr(model_config, 'api_key') else model_config.get('api_key','')
    model_name = model_config.model_name if hasattr(model_config, 'model_name') else model_config.get('model_name','')
    if not api_key: raise ValueError('VLM API Key 未配置')
    api_url = base_url.rstrip('/')
    if not api_url.endswith('/v1'): api_url += '/v1'
    api_url += '/chat/completions'
    logger.info(f'[VLM] 调用模型 {model_name}: {instruction}')
    last_error = None
    for attempt in range(3):
        if stop_checker and stop_checker():
            raise ExecutionStopped('用户已停止执行')
        try:
            with httpx.Client(timeout=timeout) as client:
                r = client.post(api_url, headers={'Authorization': f'Bearer {api_key}','Content-Type':'application/json'},
                                json={'model':model_name, 'messages':[
                                    {'role':'system','content':system_prompt},
                                    {'role':'user','content':[
                                        {'type':'image_url','image_url':{'url':f'data:image/png;base64,{b64}'}},
                                        {'type':'text','text':instruction}]}],
                                      'max_tokens':max_tokens,'temperature':0.1})
                r.raise_for_status()
            break
        except ExecutionStopped:
            raise
        except Exception as e:
            last_error = e
            if attempt < 2:
                logger.warning(f'[VLM] 第{attempt+1}次超时，重试...')
                time.sleep(3)
    else:
        raise last_error
    content = r.json()['choices'][0]['message']['content']
    logger.info(f'[VLM] 响应: {content[:200]}')
    if return_raw:
        return content
    return _parse_vlm_response(content)


# ============================================================
# 主执行逻辑
# ============================================================

def run_midscene_test(ai_prompt, device, model_config, execution_record, progress_callback=None,
                      record_mode=False, replay_mode=False, replay_index=0, clear_app_data=False,
                      app_package_override=''):
    steps = parse_ai_prompt(ai_prompt)
    if not steps: raise ValueError('ai_prompt 中没有有效的测试步骤')

    def _user_stopped():
        """VLM 调用期间检查用户是否点了停止（避免最长 90s×3 重试无法中断）。"""
        try:
            execution_record.refresh_from_db()
        except Exception:
            return False
        return execution_record.status in ('stopped', 'stopping')

    platform = device.platform
    mc = execution_record.midscene_case
    ai_context = (mc.ai_act_context if mc and mc.ai_act_context else '')
    # 回放: 兼容旧格式(dict)和新格式(list)
    _raw_replay = mc.replay_data if mc and replay_mode else None
    if isinstance(_raw_replay, dict):
        _raw_replay = [_raw_replay]
    if _raw_replay and isinstance(_raw_replay, list) and len(_raw_replay) > 0:
        idx = min(replay_index, len(_raw_replay) - 1)
        replay_data = _raw_replay[idx]
    else:
        replay_data = None
    recording = []  # 录制数据：每步的 instruction + actions + after_hash
    pre_step_anomalies = []  # 启动阶段采集的异常（随第一个步骤结果落库）

    # ---- 平台初始化 ----
    try:
        ios_dev = None
        device_id = None
        if platform == 'android':
            device_id = device.adb_serial
            if not device_id: raise ValueError('Android 设备标识无效')
        elif platform == 'ios':
            from .ios_device import IOSDevice
            wda_host = (device.wda_host or 'localhost:8100').replace('http://','').replace('https://','').rstrip('/')
            host, port_str = wda_host.rsplit(':', 1) if ':' in wda_host else (wda_host, '8100')
            port = int(port_str)
            ios_bundle = (mc.app_package if mc and mc.app_package
                          else (mc.project.default_app_package if mc and mc.project else ''))
            ios_dev = IOSDevice(host, int(port), ios_bundle)
            ios_dev.connect()
            device_id = device.tidevice_udid or device.device_id
        else:
            raise ValueError(f'不支持的平台: {platform}')

        logger.info(f'[Runner] 开始执行: {execution_record.id}, 平台={platform}, 设备={device_id}, 步骤数={len(steps)}')

        # ---- 获取分辨率 ----
        if platform == 'android':
            width, height = adb_get_screen_size(device_id)
        else:
            width, height = ios_dev.screen_size
            try:
                size = png_size(ios_dev.screenshot())
                if size:
                    width, height = size
            except Exception:
                pass
        logger.info(f'[Runner] 屏幕分辨率: {width}x{height}')

        # ---- 启动应用 ----
        if platform == 'android':
            # Android: 执行前指定安装包 → 用例包名 → 项目Android包名
            app_pkg = (app_package_override or
                       (mc.app_package if mc and mc.app_package
                        else (mc.project.default_app_package if mc and mc.project else '')))
            if app_pkg:
                # 清除App数据
                if clear_app_data:
                    logger.info(f'[Runner] 清除App数据: {app_pkg}')
                    _adb(device_id, 'shell', 'pm', 'clear', app_pkg, timeout=10)
                    time.sleep(1)
                grant_permissions(device_id, app_pkg)
                _adb(device_id, 'shell', 'monkey', '-p', app_pkg, '-c', 'android.intent.category.LAUNCHER', '1', timeout=10)
                if not _wait_screen_stable(device_id, None, label='启动画面'):
                    pre_step_anomalies.append(_build_anomaly(
                        'stable_wait_timeout',
                        '启动画面稳定等待超时(15s)，继续执行',
                        evidence={'phase': 'startup', 'timeout': 15.0},
                        recovered=True,
                    ))
        elif platform == 'ios':
            # iOS: 用例包名 → 项目iOS Bundle ID
            ios_bid = (mc.app_package if mc and mc.app_package
                       else (mc.project.default_ios_bundle_id if mc and mc.project else ''))
            if ios_bid:
                ios_dev.bundle_id = ios_bid
                ios_dev.launch_app()
                # iOS 17+ 必须激活应用到前台，否则 WDA tap 会被蒙层挡住
                import requests as _req
                try:
                    _req.post(f'http://{host}:{port}/session/{ios_dev.session_id}/wda/apps/activate',
                              json={'bundleId': ios_bid}, timeout=5)
                except Exception: pass
                if not _wait_screen_stable(None, ios_dev, label='启动画面'):
                    pre_step_anomalies.append(_build_anomaly(
                        'stable_wait_timeout',
                        '启动画面稳定等待超时(15s)，继续执行',
                        evidence={'phase': 'startup', 'timeout': 15.0},
                        recovered=True,
                    ))

        # 启动的包名（Android app_pkg / iOS ios_bid），供"打开应用"快捷分支与 aiAct 使用
        app_package = app_pkg if platform == 'android' else (ios_bid if platform == 'ios' else '')

        # ---- 智能规划模式 ----
        auto_plan = getattr(execution_record, 'auto_plan', False)
        if auto_plan and steps:
            full_goal = ai_prompt.replace('\n', '，')
            logger.info(f'[Runner] aiAct 模式: VLM 持续决策，总目标={full_goal[:80]}...')
            steps = [{'instruction': full_goal}]  # 合并为一个任务
            # 新引擎：规划 -> 定位 -> 执行 -> 反馈 -> 重规划（对齐 Midscene）
            from .midscene_ai.engine import run_ai_act
            device_ctx = {
                'platform': platform,
                'device_id': device_id,
                'ios_dev': ios_dev,
                'width': width,
                'height': height,
            }
            use_locate = getattr(mc, 'use_locate', None) if mc is not None else None
            use_deep_locate = getattr(mc, 'use_deep_locate', None) if mc is not None else None
            return run_ai_act(
                goal=full_goal,
                device_ctx=device_ctx,
                model_config=model_config,
                max_steps=getattr(mc, 'max_steps', 30) if mc is not None else 30,
                action_delay=getattr(mc, 'action_delay', 0.5) if mc is not None else 0.5,
                context=ai_context,
                progress_callback=progress_callback,
                execution_record=execution_record,
                use_locate=use_locate,
                use_deep_locate=use_deep_locate,
            )

        # ---- 逐步执行 ----
        results = []
        prev_png = None
        step_retry_count = {}
        step_idx = 0
        stopped = False
        step_memory = []  # 跨步记忆：已完成步骤摘要 + 提取数据，供后续步骤注入 prompt

        # ---- 逐步执行 ----
        replay_available = replay_data and replay_data.get('steps') and not auto_plan
        if replay_available:
            logger.info(f'[Runner] 回放模式: 已录制{len(replay_data["steps"])}步')
        replay_pass = 0; replay_fail = 0
        branch_state = {}  # 缩进分组分支：记录每个分支头是否进入，用于门控其子步骤

        while step_idx < len(steps):
            step = steps[step_idx]
            instruction = step['instruction']
            is_repeat = step.get('repeat', False)
            is_ai_act = auto_plan  # 智能规划模式 VLM 自己决定 done
            # 本步骤异常采集：启动阶段异常并入第一步，纠错埋点随后追加
            step_anomalies = list(pre_step_anomalies)
            pre_step_anomalies = []

            # ---- 缩进分组分支：子步骤门控 + 分支头门控 ----
            parent = step.get('branch_parent')
            if parent is not None and branch_state.get(parent) is False:
                # 所属分支未进入 → 整组跳过，不再单独判断
                logger.info(f'[Runner] 步骤 {step_idx+1} 分支未进入，跳过: {instruction}')
                if progress_callback:
                    progress_callback(step_idx+1, len(steps), {
                        'type': 'step_start', 'step': step_idx+1, 'total': len(steps),
                        'instruction': instruction, 'progress': int(step_idx / len(steps) * 100)
                    })
                replay_pass += 1
                results.append({'step': step_idx+1, 'instruction': instruction, 'status': 'passed',
                                'screenshot': '', 'aiReasoning': ['[回放] 分支未进入，跳过'],
                                'action': 'skip', 'anomalies': list(step_anomalies)})
                _push_step_memory(step_memory, step_idx + 1, instruction, 'skip')
                if record_mode:
                    while len(recording) <= step_idx:
                        recording.append(None)
                    recording[step_idx] = None
                step_idx += 1
                if progress_callback:
                    progress_callback(step_idx, len(steps), {
                        'type': 'step_done', 'step': step_idx, 'total': len(steps),
                        'instruction': instruction, 'status': 'passed', 'screenshot': '',
                        'aiReasoning': ['[回放] 分支未进入，跳过'],
                        'anomalies': list(step_anomalies),
                        'progress': int(step_idx / len(steps) * 100)
                    })
                continue

            if step.get('type') == 'branch':
                # 分支头：只做一次门控，命中激活子步骤，未命中整组跳过
                if progress_callback:
                    progress_callback(step_idx+1, len(steps), {
                        'type': 'step_start', 'step': step_idx+1, 'total': len(steps),
                        'instruction': instruction, 'progress': int(step_idx / len(steps) * 100)
                    })
                png_gate = ios_dev.screenshot() if ios_dev else adb_screenshot(device_id)
                entered = None
                gate_reason = ''
                r_step_gate = None
                if replay_available and step_idx < len(replay_data['steps']):
                    candidate = replay_data['steps'][step_idx]
                    if candidate and _instruction_similar(candidate.get('instruction', ''), instruction):
                        r_step_gate = candidate
                rec_entered = r_step_gate.get('branch_entered') if r_step_gate else None
                act_hash = (r_step_gate.get('act_before_hash', '') if r_step_gate else '')
                after_hash = (r_step_gate.get('after_hash', '') if r_step_gate else '')
                if rec_entered is True and act_hash and _is_same_page_by_hash(png_gate, act_hash):
                    entered = True
                    gate_reason = '分支命中-录制同路径'
                elif rec_entered is False and after_hash and _is_same_page_by_hash(png_gate, after_hash):
                    entered = False
                    gate_reason = '分支跳过-录制同路径'
                if entered is None:
                    # 快速路径未命中 → 元素确认兜底；无法判定时按未进入处理并记异常
                    try:
                        status, png_gate, reasoning = _confirm_condition_target(
                            device_id, ios_dev, step.get('condition', instruction), model_config,
                            width, height, context=ai_context, initial_png=png_gate,
                            stop_checker=_user_stopped)
                        entered = (status == 'present')
                        if status == 'anomaly':
                            # B方案：先清全局障碍，再重新门控判断
                            cleared, clr_desc = _clear_global_obstacle(
                                device_id, ios_dev, model_config, width, height,
                                context=ai_context, stop_checker=_user_stopped)
                            step_anomalies.append(_build_anomaly(
                                'hash_mismatch_fallback',
                                f'分支头{step_idx+1} 检测到全局障碍，清理后重新判断',
                                evidence={'step': step_idx + 1, 'reason': 'global_anomaly',
                                          'cleared': cleared},
                                recovered=True))
                            if cleared:
                                status, png_gate, reasoning = _confirm_condition_target(
                                    device_id, ios_dev, step.get('condition', instruction),
                                    model_config, width, height, context=ai_context,
                                    stop_checker=_user_stopped)
                                entered = (status == 'present')
                                if status == 'present':
                                    gate_reason = '分支命中-清理障碍后元素确认: ' + reasoning[:80]
                                elif status == 'absent':
                                    gate_reason = '分支跳过-清理障碍后元素确认: ' + reasoning[:80]
                                else:
                                    gate_reason = '分支门控清理障碍后仍异常/无法判定，按未进入处理'
                            else:
                                entered = False
                                gate_reason = '分支门控全局障碍清理未完成，按未进入处理: ' + str(clr_desc)[:80]
                        elif status == 'absent':
                            gate_reason = '分支跳过-元素确认: ' + reasoning[:80]
                        elif status == 'present':
                            gate_reason = '分支命中-元素确认: ' + reasoning[:80]
                        else:
                            gate_reason = '分支门控无法判定，按未进入处理'
                    except ExecutionStopped:
                        stopped = True
                        results.append({'step': step_idx+1, 'instruction': instruction,
                                        'status': 'stopped', 'screenshot': '',
                                        'aiReasoning': ['[停止] 用户已停止执行'],
                                        'action': 'stopped', 'anomalies': list(step_anomalies)})
                        break
                    except Exception as e:
                        logger.warning(f'[Runner] 分支头 {step_idx+1} 门控确认失败({e})，按未进入处理')
                        entered = False
                        gate_reason = f'分支门控确认失败，按未进入处理: {str(e)[:80]}'
                        step_anomalies.append(_build_anomaly(
                            'hash_mismatch_fallback',
                            f'分支头{step_idx+1} 门控确认失败，按未进入处理',
                            evidence={'step': step_idx + 1, 'error': str(e)[:200]},
                            recovered=True))
                branch_state[step_idx] = bool(entered)
                if record_mode:
                    gate_rec = {
                        'instruction': instruction,
                        'type': 'branch',
                        'condition': step.get('condition', ''),
                        'branch_entered': bool(entered),
                        'actions': [],
                    }
                    if entered:
                        gate_rec['act_before_hash'] = str(_phash(png_gate))
                        gate_rec['after_hash'] = ''
                    else:
                        gate_rec['after_hash'] = str(_phash(png_gate))
                        gate_rec['act_before_hash'] = ''
                    while len(recording) <= step_idx:
                        recording.append(None)
                    recording[step_idx] = gate_rec
                prev_png = png_gate
                screenshot_url = save_screenshot(png_gate, execution_record.id, step_idx+1)
                replay_pass += 1
                results.append({'step': step_idx+1, 'instruction': instruction, 'status': 'passed',
                                'screenshot': screenshot_url,
                                'aiReasoning': ['[回放] 分支门控: ' + gate_reason],
                                'action': 'branch', 'anomalies': list(step_anomalies)})
                _push_step_memory(step_memory, step_idx + 1, instruction,
                                  'branch' if entered else 'branch_skip')
                step_idx += 1
                if progress_callback:
                    progress_callback(step_idx, len(steps), {
                        'type': 'step_done', 'step': step_idx, 'total': len(steps),
                        'instruction': instruction, 'status': 'passed',
                        'screenshot': screenshot_url,
                        'aiReasoning': ['[回放] 分支门控: ' + gate_reason],
                        'anomalies': list(step_anomalies),
                        'progress': int(step_idx / len(steps) * 100)
                    })
                continue

            if not auto_plan and re.match(r'^打开.*(?:com\.|应用|app|APP)', instruction) and app_package:
                results.append({'step':step_idx+1,'instruction':instruction,'status':'passed',
                                'screenshot':'','aiReasoning':['ADB启动'],'action':'launch',
                                'anomalies': list(step_anomalies)})
                step_idx += 1; continue

            logger.info(f'[Runner] 步骤 {step_idx+1}/{len(steps)}: {instruction}')

            # ---- 回放尝试（每步独立） ----
            if replay_available and step_idx < len(replay_data['steps']):
                r_step = replay_data['steps'][step_idx]
                # r_step 可能为 None：未录制到的步骤保留占位，保证与 ai_prompt 步骤索引一一对应
                if r_step and _instruction_similar(r_step.get('instruction', ''), instruction):
                    r_actions = r_step.get('actions', [])
                    is_cond = instruction.startswith('如果') or instruction.startswith('若')
                    # 条件步骤判定模型：
                    #   快速路径: 指纹命中 act_before_hash → 播放录制动作（after_hash 仅记日志，加载帧也会失真）
                    #   主路径:   指纹未命中（如录制到加载帧）→ 元素级 VLM 确认，等待加载完成，存在→播放，稳定不存在→跳过
                    #   兜底:     确认失败/无法判定 → replay_fail+1 落到 VLM 判断，不做盲目播放
                    if is_cond:
                        if progress_callback:
                            progress_callback(step_idx+1, len(steps), {
                                'type': 'step_start', 'step': step_idx+1, 'total': len(steps),
                                'instruction': instruction, 'progress': int(step_idx / len(steps) * 100)
                            })
                        png = ios_dev.screenshot() if ios_dev else adb_screenshot(device_id)
                        act_hash = r_step.get('act_before_hash', '')
                        after_hash = r_step.get('after_hash', '')
                        if r_actions:
                            # 快速路径：当前页匹配录制动作执行前指纹 → 直接播放
                            if act_hash and _is_same_page_by_hash(png, act_hash):
                                _replay_actions(device_id, ios_dev, r_actions, width, height,
                                                anomalies=step_anomalies)
                                png_after = ios_dev.screenshot() if ios_dev else adb_screenshot(device_id)
                                if after_hash and not _is_same_page_by_hash(png_after, after_hash):
                                    # after_hash 在加载帧下同样失真，不阻断，仅记录
                                    logger.warning(f'[Runner] 条件步骤{step_idx+1} 执行后pHash与录制不一致(可能为加载帧)，按通过处理')
                                    step_anomalies.append(_build_anomaly(
                                        'hash_mismatch_fallback',
                                        f'条件步骤{step_idx+1} 执行后pHash与录制不一致(可能为加载帧)，按通过处理',
                                        evidence={'step': step_idx + 1,
                                                  'expected_hash': str(after_hash),
                                                  'current_hash': str(_phash(png_after))},
                                        recovered=True,
                                    ))
                                replay_pass += 1
                                screenshot_url = save_screenshot(png, execution_record.id, step_idx+1)
                                after_url = save_screenshot(png_after, execution_record.id, step_idx+1, '_after') if step_anomalies else ''
                                results.append({'step': step_idx+1, 'instruction': instruction, 'status': 'passed',
                                                'screenshot': screenshot_url, 'aiReasoning': ['[回放] 脚本播放(条件同路径)'],
                                                'action': r_actions[-1].get('action', 'tap'),
                                                'anomalies': list(step_anomalies),
                                                'after_screenshot': after_url})
                                if record_mode:
                                    while len(recording) <= step_idx: recording.append(None)
                                    recording[step_idx] = dict(r_step)
                                _push_step_memory(step_memory, step_idx + 1, instruction,
                                                  r_actions[-1].get('action', 'tap') if r_actions else '')
                                prev_png = png_after; step_idx += 1
                                if progress_callback:
                                    progress_callback(step_idx, len(steps), {
                                        'type': 'step_done', 'step': step_idx, 'total': len(steps),
                                        'instruction': instruction, 'status': 'passed',
                                        'screenshot': screenshot_url,
                                        'aiReasoning': ['[回放] 脚本播放(条件同路径)'],
                                        'action': r_actions[-1].get('action', 'tap'),
                                        'anomalies': list(step_anomalies),
                                        'after_screenshot': after_url,
                                        'progress': int(step_idx / len(steps) * 100)
                                    })
                                logger.info(f'[Runner] 条件步骤 {step_idx} 回放通过(同路径)')
                                continue
                            # 主路径：指纹未命中 → 元素级确认（等待加载完成，避免录制到加载帧导致永久不匹配）
                            try:
                                status, png_conf, reasoning = _confirm_condition_target(
                                    device_id, ios_dev, instruction, model_config, width, height,
                                    context=ai_context, initial_png=png, stop_checker=_user_stopped)
                            except ExecutionStopped:
                                stopped = True
                                results.append({'step': step_idx+1, 'instruction': instruction,
                                                'status': 'stopped', 'screenshot': '',
                                                'aiReasoning': ['[停止] 用户已停止执行'],
                                                'action': 'stopped',
                                                'anomalies': list(step_anomalies)})
                                break
                            if status == 'present':
                                _replay_actions(device_id, ios_dev, r_actions, width, height,
                                                anomalies=step_anomalies)
                                png_after = ios_dev.screenshot() if ios_dev else adb_screenshot(device_id)
                                if after_hash and not _is_same_page_by_hash(png_after, after_hash):
                                    logger.warning(f'[Runner] 条件步骤{step_idx+1} 执行后pHash与录制不一致(可能为加载帧)，按通过处理')
                                    step_anomalies.append(_build_anomaly(
                                        'hash_mismatch_fallback',
                                        f'条件步骤{step_idx+1} 执行后pHash与录制不一致(可能为加载帧)，按通过处理',
                                        evidence={'step': step_idx + 1,
                                                  'expected_hash': str(after_hash),
                                                  'current_hash': str(_phash(png_after))},
                                        recovered=True,
                                    ))
                                replay_pass += 1
                                screenshot_url = save_screenshot(png_conf, execution_record.id, step_idx+1)
                                after_url = save_screenshot(png_after, execution_record.id, step_idx+1, '_after') if step_anomalies else ''
                                results.append({'step': step_idx+1, 'instruction': instruction, 'status': 'passed',
                                                'screenshot': screenshot_url,
                                                'aiReasoning': [f'[回放] 条件满足-元素确认: {reasoning[:80]}'],
                                                'action': r_actions[-1].get('action', 'tap'),
                                                'anomalies': list(step_anomalies),
                                                'after_screenshot': after_url})
                                if record_mode:
                                    while len(recording) <= step_idx: recording.append(None)
                                    recording[step_idx] = dict(r_step)
                                _push_step_memory(step_memory, step_idx + 1, instruction,
                                                  r_actions[-1].get('action', 'tap') if r_actions else '')
                                prev_png = png_after; step_idx += 1
                                if progress_callback:
                                    progress_callback(step_idx, len(steps), {
                                        'type': 'step_done', 'step': step_idx, 'total': len(steps),
                                        'instruction': instruction, 'status': 'passed',
                                        'screenshot': screenshot_url,
                                        'aiReasoning': [f'[回放] 条件满足-元素确认: {reasoning[:80]}'],
                                        'action': r_actions[-1].get('action', 'tap'),
                                        'anomalies': list(step_anomalies),
                                        'after_screenshot': after_url,
                                        'progress': int(step_idx / len(steps) * 100)
                                    })
                                logger.info(f'[Runner] 条件步骤 {step_idx} 回放通过(元素确认-条件满足)')
                                continue
                            if status == 'absent':
                                # 页面稳定且目标元素不存在 → 条件不满足，跳过
                                replay_pass += 1
                                screenshot_url = save_screenshot(png_conf, execution_record.id, step_idx+1)
                                results.append({'step': step_idx+1, 'instruction': instruction, 'status': 'passed',
                                                'screenshot': screenshot_url,
                                                'aiReasoning': [f'[回放] 条件不满足-元素确认: {reasoning[:80]}'],
                                                'anomalies': list(step_anomalies)})
                                if record_mode:
                                    while len(recording) <= step_idx: recording.append(None)
                                    recording[step_idx] = dict(r_step)
                                _push_step_memory(step_memory, step_idx + 1, instruction)
                                prev_png = png_conf; step_idx += 1
                                if progress_callback:
                                    progress_callback(step_idx, len(steps), {
                                        'type': 'step_done', 'step': step_idx, 'total': len(steps),
                                        'instruction': instruction, 'status': 'passed',
                                        'screenshot': screenshot_url,
                                        'aiReasoning': [f'[回放] 条件不满足-元素确认: {reasoning[:80]}'],
                                        'anomalies': list(step_anomalies),
                                        'progress': int(step_idx / len(steps) * 100)
                                    })
                                logger.info(f'[Runner] 条件步骤 {step_idx} 跳过(条件不满足-元素确认)')
                                continue
                            # 确认失败/无法判定 → 降至VLM
                            replay_fail += 1
                            if status == 'anomaly':
                                logger.info(f'[Runner] 条件步骤 {step_idx+1} 检测到全局障碍，降至VLM处理')
                                step_anomalies.append(_build_anomaly(
                                    'hash_mismatch_fallback',
                                    f'条件步骤{step_idx+1} 检测到全局障碍，降至VLM处理',
                                    evidence={'step': step_idx + 1, 'reason': 'global_anomaly'},
                                    recovered=True,
                                ))
                            else:
                                logger.info(f'[Runner] 条件步骤 {step_idx+1} 元素确认无法判定，降至VLM')
                                step_anomalies.append(_build_anomaly(
                                    'hash_mismatch_fallback',
                                    f'条件步骤{step_idx+1} 元素确认无法判定，降至VLM',
                                    evidence={'step': step_idx + 1, 'reason': 'element_confirm_failed'},
                                    recovered=True,
                                ))
                        else:
                            # 录制时条件不满足(无动作)：after_hash 即"跳过"指纹
                            if after_hash and _is_same_page_by_hash(png, after_hash):
                                replay_pass += 1
                                screenshot_url = save_screenshot(png, execution_record.id, step_idx+1)
                                results.append({'step': step_idx+1, 'instruction': instruction, 'status': 'passed',
                                                'screenshot': screenshot_url, 'aiReasoning': ['[回放] 条件步骤跳过(条件不满足)'],
                                                'anomalies': list(step_anomalies)})
                                if record_mode:
                                    while len(recording) <= step_idx: recording.append(None)
                                    recording[step_idx] = dict(r_step)
                                _push_step_memory(step_memory, step_idx + 1, instruction)
                                prev_png = png; step_idx += 1
                                if progress_callback:
                                    progress_callback(step_idx, len(steps), {
                                        'type': 'step_done', 'step': step_idx, 'total': len(steps),
                                        'instruction': instruction, 'status': 'passed',
                                        'screenshot': screenshot_url,
                                        'aiReasoning': ['[回放] 条件步骤跳过(条件不满足)'],
                                        'anomalies': list(step_anomalies),
                                        'progress': int(step_idx / len(steps) * 100)
                                    })
                                logger.info(f'[Runner] 条件步骤 {step_idx} 跳过(条件不满足)')
                                continue
                            # 当前页不是录制时的跳过状态 → 未知（可能条件满足或路径不同），降至VLM
                            replay_fail += 1
                            logger.info(f'[Runner] 条件步骤 {step_idx+1} 页面与录制跳过状态不符，降至VLM')
                            step_anomalies.append(_build_anomaly(
                                'hash_mismatch_fallback',
                                f'条件步骤{step_idx+1} 页面与录制跳过状态不符，降至VLM',
                                evidence={'step': step_idx + 1,
                                          'expected_hash': str(after_hash),
                                          'current_hash': str(_phash(png))},
                                recovered=True,
                            ))
                    else:
                        # 普通步骤：播放动作序列（障碍动作按前置指纹门控，目标动作必播）
                        before_png = ios_dev.screenshot() if ios_dev else adb_screenshot(device_id)
                        r_stats = _replay_actions(device_id, ios_dev, r_actions, width, height,
                                                  anomalies=step_anomalies)
                        if r_stats['skipped']:
                            logger.info(f'[Runner] 步骤 {step_idx+1} 回放跳过 {r_stats["skipped"]} 个不匹配的障碍动作')

                        if progress_callback:
                            progress_callback(step_idx+1, len(steps), {
                                'type': 'step_start', 'step': step_idx+1, 'total': len(steps),
                                'instruction': instruction, 'progress': int(step_idx / len(steps) * 100)
                            })
                        # 普通步骤 pHash 校验（条件步骤已在前面处理）
                        # 下一步是条件步骤 → 不驗 after_hash（当前步执行后的页面受路径分叉影响）
                        next_cond = (step_idx + 1 < len(steps)
                                     and (steps[step_idx + 1]['instruction'].startswith('如果')
                                          or steps[step_idx + 1]['instruction'].startswith('若')))
                        png = ios_dev.screenshot() if ios_dev else adb_screenshot(device_id)
                        expected_hash = r_step.get('after_hash', '') if not next_cond else ''
                        # 动作生效判据：执行前后页面发生变化 或 与录制 after_hash 匹配。
                        # after_hash 在页面分叉/动态内容/加载时序下会失真，若动作已生效
                        # （页面确实变了）仍按通过处理并记警告，避免"已成功却降级重做"。
                        primary_action = r_actions[-1].get('action', '') if r_actions else ''
                        is_input = (primary_action == 'input')
                        hash_ok = (not expected_hash) or _is_same_page_by_hash(png, expected_hash)
                        page_changed = not _is_same_page(before_png, png)
                        # 输入类动作：整屏 pHash 难以感知文本输入的变化，若仅因"页面未变"
                        # 就降级 VLM，每个 input 步骤都会白花一次 API。回放已忠实执行录制的
                        # input（目标动作必播），这里按"已执行"放行并记警告。
                        effective = hash_ok or page_changed or is_input
                        if effective:
                            if not hash_ok:
                                warn_msg = (
                                    '输入后页面未变且pHash与录制不一致(文本变化对粗粒度pHash不可见)'
                                    if is_input
                                    else '动作已生效但执行后pHash与录制不一致(页面分叉/动态内容)'
                                )
                                logger.warning(
                                    f'[Runner] 回放步骤{step_idx+1} {warn_msg}，按通过处理')
                                step_anomalies.append(_build_anomaly(
                                    'hash_mismatch_fallback',
                                    f'回放步骤{step_idx+1} {warn_msg}，按通过处理',
                                    evidence={'step': step_idx + 1,
                                              'expected_hash': str(expected_hash),
                                              'current_hash': str(_phash(png))},
                                    recovered=True,
                                ))
                            replay_pass += 1
                            screenshot_url = save_screenshot(before_png, execution_record.id, step_idx+1)
                            after_url = save_screenshot(png, execution_record.id, step_idx+1, '_after') if step_anomalies else ''
                            last_action = r_actions[-1].get('action', 'tap') if r_actions else 'assert'
                            results.append({'step': step_idx+1, 'instruction': instruction, 'status': 'passed',
                                            'screenshot': screenshot_url, 'aiReasoning': ['[回放] 脚本播放'],
                                            'action': last_action,
                                            'anomalies': list(step_anomalies),
                                            'after_screenshot': after_url})
                            if record_mode:
                                while len(recording) <= step_idx: recording.append(None)
                                recording[step_idx] = dict(r_step)
                            _push_step_memory(step_memory, step_idx + 1, instruction, last_action)
                            prev_png = png; step_idx += 1
                            if progress_callback:
                                progress_callback(step_idx, len(steps), {
                                    'type': 'step_done', 'step': step_idx, 'total': len(steps),
                                    'instruction': instruction, 'status': 'passed',
                                    'screenshot': screenshot_url, 'aiReasoning': ['[回放] 脚本播放'],
                                    'action': last_action, 'anomalies': list(step_anomalies),
                                    'after_screenshot': after_url,
                                    'progress': int(step_idx / len(steps) * 100)
                                })
                            logger.info(f'[Runner] 回放步骤 {step_idx} 通过')
                            continue
                        else:
                            replay_fail += 1
                            logger.warning(
                                f'[Runner] 回放步骤{step_idx+1} 动作未生效'
                                f'(页面未变且pHash不匹配)，降至VLM')
                            step_anomalies.append(_build_anomaly(
                                'hash_mismatch_fallback',
                                f'回放步骤{step_idx+1} 动作未生效(页面未变且pHash不匹配)，降至VLM',
                                evidence={'step': step_idx + 1,
                                          'expected_hash': str(expected_hash),
                                          'current_hash': str(_phash(png))},
                                recovered=True,
                            ))
                else:
                    # 文案不一致：不盲放旧脚本，直接降级 VLM，并记录差异便于排查
                    if r_step and r_step.get('instruction'):
                        logger.warning(
                            f'[Runner] 步骤 {step_idx+1} 文案与录制不一致，跳过回放降至VLM'
                            f'（录制: {r_step.get("instruction")!r} / 当前: {instruction!r}）')
            # ---- 回放结束 ----

            if progress_callback:
                progress_callback(step_idx+1, len(steps), {'type':'step_start','step':step_idx+1,'total':len(steps),
                                                     'instruction':instruction,'progress':int(step_idx/len(steps)*100)})

            reasonings = []
            step_actions = []  # 录制: 当前步骤的所有动作
            max_turns = 20 if is_ai_act else 8
            screenshot_url = ''
            last_png = None  # 录制用: 最后截图的原始字节
            step_before_png = None  # 录制用: 本步骤第一轮发送给VLM的截图（动作执行前的页面状态）
            last_action = ''
            step_after_png = None  # 异常展示用: 本步骤动作执行后的截图（tap 复用已有轮询图，避免重截）
            step_after_url = ''    # 异常展示用: 执行后截图的媒体 URL
            last_exec_time = None  # 录制用: 上一动作执行完成时刻（实测 wait_after 起点）
            last_rec_idx = None    # 录制用: 上一动作在 step_actions 中的索引
            # 重复动作检测（每步独立）
            last_action_fp = ''
            repeat_count = 0
            last_tap_feedback = ''  # tap 连续失败后的定向纠错提示，注入下一轮 prompt

            try:
                for turn in range(max_turns):
                    # 检查是否被用户停止
                    execution_record.refresh_from_db()
                    if execution_record.status in ('stopped', 'stopping'):
                        stopped = True
                        results.append({'step': step_idx+1, 'instruction': instruction, 'status': 'stopped',
                                        'screenshot': '', 'aiReasoning': reasonings, 'action': 'stopped',
                                        'anomalies': list(step_anomalies)})
                        break
                    # 录制: 实测上一动作的 wait_after（动作执行完成 → 本次截图开始）
                    if record_mode and last_exec_time is not None and last_rec_idx is not None:
                        step_actions[last_rec_idx]['wait_after'] = _clamp_wait_after(time.time() - last_exec_time)
                        last_exec_time = None
                        last_rec_idx = None
                    # 截图（分平台）
                    png = ios_dev.screenshot() if ios_dev else adb_screenshot(device_id)
                    last_png = png
                    if turn == 0:
                        step_before_png = png

                    # 页面未变检测
                    page_unchanged = False
                    if prev_png is not None and _is_same_page(prev_png, png):
                        if turn == 0 and step_idx > 0 and last_action in ('tap', 'click'):
                            # 新步骤开头页面与上一步结束时一样 → 上一步操作未生效
                            retries = step_retry_count.get(step_idx - 1, 0)
                            if retries < 1:
                                # 移除上一条无效结果和录制，退回重试一次
                                step_retry_count[step_idx - 1] = retries + 1
                                logger.warning(f'[Runner] 新步骤页面未变，上一步操作可能未生效，退回步骤 {step_idx} 重试')
                                if results:
                                    results.pop()
                                reasonings = []
                                step_idx -= 1
                                instruction = steps[step_idx]['instruction']
                                prev_png = png
                                continue
                            else:
                                # 已重试过，不再回退，继续当前步骤
                                logger.info(f'[Runner] 上一步已重试过，不再回退')
                        page_unchanged = True
                        logger.info(f'[Runner] 步骤 {step_idx+1} 页面未变化')
                    prev_png = png

                    # aiAct 模式: 参照 Midscene conversationHistory 机制
                    if is_ai_act and reasonings:
                        # 只保留最近3步的简洁描述（避免 prompt 膨胀）
                        hist_items = []
                        for r in reasonings[-3:]:
                            if '] ' in r:
                                txt = r.split('] ', 1)[1]
                                # 去掉冗长推理，只留核心动作
                                txt = re.sub(r'根据(总目标|用户指令|当前步骤).*?(需要|这是|点击)', r'\2', txt)
                                hist_items.append(txt[:60])
                        hist_text = '\n'.join(f'- {h}' for h in hist_items)
                        prompt = (
                            f'总目标: {instruction}\n'
                            f'最近操作: {hist_text}\n'
                            f'注意：如果用户给的是具体步骤，逐条执行，不多做也不少做。'
                            f'全部完成后返回 done，否则执行下一步。'
                        )
                    elif is_ai_act:
                        # 第一步：要求 VLM 自己拆解并执行
                        prompt = (
                            f'你需要完成以下任务:\n{instruction}\n\n'
                            f'观察截图，执行第一个操作。完成后逐步继续。'
                            f'注意：如果用户给的是具体步骤，逐条执行，不多做也不少做。'
                            f'全部完成后返回 done。'
                        )
                    else:
                        # 条件步骤检测
                        is_conditional = instruction.startswith('如果') or instruction.startswith('若')
                        # 构建本步骤已有的操作历史
                        history_text = ''
                        if reasonings:
                            recent = [r.split('] ', 1)[1] if '] ' in r else r for r in reasonings[-3:]]
                            history_text = '\n'.join(f'第{turn-len(recent)+j+1}次: {r[:80]}' for j, r in enumerate(recent))
                            history_text = f'\n你本轮已执行的操作:\n{history_text}\n请基于以上历史判断下一步，不要重复已做过的操作。'
                        conditional_hint = ''
                        if is_conditional:
                            conditional_hint = '这是一个条件步骤：如果截图中能看到目标就点击，看不到就直接返回 done 跳过。'
                        memory_text = ''
                        if step_memory:
                            mem_lines = [f"第{m['step']}步 {m['instruction']}"
                                         + (f"（提取: {m['data']}）" if m.get('data') else '')
                                         for m in step_memory[-3:]]
                            memory_text = '\n'.join(mem_lines)
                            memory_text = f'\n已完成步骤:\n{memory_text}\n提取到的数据在后续步骤可直接使用。'
                        prompt = (
                            f'当前步骤({step_idx+1}/{len(steps)}): {instruction}\n'
                            f'{conditional_hint}'
                            f'{memory_text}'
                            f'如果当前截图与步骤目标无关（如弹窗、渠道选择页），'
                            f'请根据「全局提示」处理，step_status 填 "in_progress"。'
                            f'只有当你的动作直接执行了这条步骤指令时，step_status 填 "done"。'
                            f'{history_text}'
                        )

                    if page_unchanged:
                        if last_tap_feedback:
                            prompt += f'\n{last_tap_feedback}'
                        else:
                            prompt += '\n上一次操作后页面未变化，请自行判断是否需要重试或调整。'
                    action = call_vlm(png, prompt, model_config, width, height, ai_context,
                                      stop_checker=_user_stopped)

                    # 百分比→像素
                    for coord in ('x','y','x1','y1','x2','y2'):
                        pk = f'{coord}_pct'
                        if pk in action and coord not in action:
                            v = float(action[pk])
                            ref = width if coord.startswith('x') else height
                            # >100 的是旧模型(qwen3-vl-plus)的10x百分比，≤100 的已是真实百分比
                            pct = v / 10.0 if v > 100 else v
                            action[coord] = int(pct/100.0*ref)

                    t = action.get('action','done')
                    reason = action.get('reasoning','')
                    reasonings.append(f'[轮{turn+1}] {reason}')

                    # 录制: 保存动作参数（wait_after在执行后确定）
                    if record_mode and t not in ('assert', 'query', 'done'):
                        step_actions.append(_build_action_rec(action, png))
                    prev_action = last_action
                    last_action = t

                    # 重复动作检测：相同指纹（覆盖swipe四坐标/input文本）+ 页面未变 → 卡死
                    action_fp = _action_fingerprint(action)
                    if (action_fp == last_action_fp
                            and t in ('tap', 'click', 'long_press', 'swipe', 'input')
                            and page_unchanged):
                        repeat_count += 1
                    else:
                        last_action_fp = action_fp
                        repeat_count = 0
                    if repeat_count >= 2:
                        # 同一动作指纹连续重复且页面未变化：多为幂等/已生效但无可见页面变化
                        # （如发送/点赞/切换按钮）。判定为动作已生效，完成本步并记可恢复异常，不再硬失败。
                        step_anomalies.append(_build_anomaly(
                            'tap_repeat_no_change',
                            f'同一动作连续{repeat_count+1}次且页面未变化，判定动作已生效但无可见页面变化',
                            evidence={'fingerprint': action_fp, 'repeat_count': repeat_count,
                                      'page_unchanged': True},
                            recovered=True,
                        ))
                        logger.info(f'[Runner] 步骤 {step_idx+1} 重复动作且页面未变化，判定已生效，完成本步')
                        action['step_status'] = 'done'
                        screenshot_url = save_screenshot(png, execution_record.id, step_idx+1)
                        break

                    # 1. 按类型执行
                    if t == 'done': screenshot_url = save_screenshot(png, execution_record.id, step_idx+1); break
                    if t == 'wait':
                        time.sleep(_clamp_wait_duration(action))  # 指令明确时长则按时长等待，否则默认3s
                        continue  # 加载中等待
                    if t == 'swipe':
                        ev = ios_dev.execute_action(action) if ios_dev else adb_execute(device_id, action)
                        if ev and not ev.get('ok', True):
                            step_anomalies.append(_build_anomaly(
                                'wda_error' if ios_dev else 'adb_error',
                                f'swipe 执行失败: {ev.get("error") or ev.get("stderr", "")}',
                                evidence=ev, recovered=True))
                        if record_mode and step_actions:
                            last_exec_time = time.time()
                            last_rec_idx = len(step_actions) - 1
                    elif t == 'assert':
                        if not action.get('passed',True): raise AssertionError(f'断言失败: {reason}')
                        if is_ai_act and prev_action == 'assert':
                            reasonings.append('[Done] 连续断言通过，任务完成')
                            screenshot_url = save_screenshot(png, execution_record.id, step_idx+1); break
                        if not is_ai_act: screenshot_url = save_screenshot(png, execution_record.id, step_idx+1); break
                    elif t == 'query':
                        logger.info(f'[Runner] 提取: {str(action.get("data",""))[:200]}')
                        if not is_ai_act: screenshot_url = save_screenshot(png, execution_record.id, step_idx+1); break
                    else:  # tap/click/long_press/input/back
                        ev = ios_dev.execute_action(action) if ios_dev else adb_execute(device_id, action)
                        if ev and not ev.get('ok', True):
                            step_anomalies.append(_build_anomaly(
                                'wda_error' if ios_dev else 'adb_error',
                                f'{t} 执行失败: {ev.get("error") or ev.get("stderr", "")}',
                                evidence=ev, recovered=True))
                        if record_mode and step_actions:
                            last_exec_time = time.time()
                            last_rec_idx = len(step_actions) - 1

                    # 2. 智能等待 + tap 自动重试
                    if t in ('tap', 'click'):
                        _smart_wait(device_id, ios_dev, png, max_wait=2.0, check_interval=0.8)
                        after_png = ios_dev.screenshot() if ios_dev else adb_screenshot(device_id)
                        step_after_png = after_png
                        if _is_same_page(png, after_png):
                            # 轮内重试: 页面没变就原地再点一次
                            logger.info(f'[Runner] 步骤 {step_idx+1} tap未生效，轮内重试')
                            tap_anom = _build_anomaly(
                                'tap_retry',
                                f'步骤 {step_idx+1} {t} 未生效，轮内重试',
                                evidence={'action': _action_fingerprint_desc(action),
                                          'attempt': 1, 'page_unchanged': True},
                                recovered=True, severity='minor')
                            step_anomalies.append(tap_anom)
                            if ios_dev: ios_dev.execute_action(action)
                            else: adb_execute(device_id, action)
                            _smart_wait(device_id, ios_dev, png, max_wait=2.0, check_interval=0.5)
                            # 重试后再校验：仍没变化时保留模型语义（不再强制 in_progress）
                            after2 = ios_dev.screenshot() if ios_dev else adb_screenshot(device_id)
                            step_after_png = after2
                            if _is_same_page(png, after2):
                                # 重试后仍无变化：不再强制 in_progress，保留模型语义判断。
                                # 模型已 done -> 判定动作已生效，结束本步；模型仍 in_progress -> 继续处理。
                                will_accept = (action.get('step_status', 'done') != 'in_progress')
                                logger.info(
                                    f'[Runner] 步骤 {step_idx+1} 重试后页面仍未变化，'
                                    + ('判定动作已生效，完成本步' if will_accept else '保留模型判断，继续处理'))
                                tap_anom['recovered'] = will_accept
                                step_anomalies.append(_build_anomaly(
                                    'tap_retry',
                                    f'步骤 {step_idx+1} {t} 重试后页面仍未变化'
                                    + ('，判定动作已生效' if will_accept else '，继续处理'),
                                    evidence={'action': _action_fingerprint_desc(action),
                                              'attempt': 2, 'page_unchanged': True},
                                    recovered=will_accept))
                                last_tap_feedback = (
                                    f"上次 {t} 坐标 ({action.get('x_pct', action.get('x', '?'))},"
                                    f"{action.get('y_pct', action.get('y', '?'))}) 点击后页面几乎无变化，"
                                    f"但发送/点赞/切换这类按钮点击后页面变化可能很小。若你判断动作已生效，"
                                    f"请直接返回 done；若确实没点中，可小幅调整坐标（仅一次），不要反复重复同一坐标")
                            else:
                                last_tap_feedback = ''
                        else:
                            last_tap_feedback = ''
                    else:
                        if t == 'input':
                            # 输入后可能触发网络校验/自动跳转（验证码、登录等），
                            # 先静默等 1.2s，页面开始变化则跟踪到稳定（最多 4s）
                            _wait_after_input(device_id, ios_dev, png)
                        else:
                            w = {'long_press':0.5,'back':0.5,'swipe':1.5,
                                 'wait':0,'assert':0,'query':0,'done':0}.get(t,0.5)
                            if w: time.sleep(w)

                    # 3. aiAct 继续循环；逐行模式按 step_status 决定是否结束本轮
                    if is_ai_act: continue
                    step_status = action.get('step_status', 'done')
                    if step_status == 'in_progress':
                        logger.info(f'[Runner] 步骤 {step_idx+1} 处理障碍中，继续...')
                        continue
                    # step_status == 'done': 重复步骤检测页面是否还有变化
                    if is_repeat and not is_ai_act:
                        time.sleep(0.5)
                        after_png = ios_dev.screenshot() if ios_dev else adb_screenshot(device_id)
                        if not _is_same_page(png, after_png):
                            # 页面还在变化，可能还有下一层弹窗，继续循环
                            logger.info(f'[Runner] 重复步骤 {step_idx+1} 页面有变化，继续下一次')
                            action['step_status'] = 'in_progress'
                            continue
                    screenshot_url = save_screenshot(png, execution_record.id, step_idx+1)
                    # 异常步骤补执行后图：tap 复用已有轮询图，其他交互动作才补截
                    after_url = ''
                    if step_anomalies:
                        if step_after_png is not None:
                            after_url = save_screenshot(step_after_png, execution_record.id, step_idx+1, '_after')
                        elif last_action in ('tap', 'click', 'swipe', 'input', 'back', 'long_press'):
                            try:
                                after_png = ios_dev.screenshot() if ios_dev else adb_screenshot(device_id)
                                after_url = save_screenshot(after_png, execution_record.id, step_idx+1, '_after')
                            except Exception:
                                after_url = ''
                    step_after_url = after_url
                    break
                else:
                    raise RuntimeError(f'达到最大轮次({max_turns})')

                if stopped:
                    break  # 用户已停止：退出整轮执行，不再处理剩余步骤

                passed_extra = {}
                if last_action == 'assert':
                    passed_extra['assert_passed'] = True
                results.append({'step':step_idx+1,'instruction':instruction,'status':'passed',
                                'screenshot':screenshot_url,'aiReasoning':reasonings,'action':last_action,
                                'anomalies': list(step_anomalies), 'after_screenshot': step_after_url,
                                **passed_extra})
                mem_data = str(action.get('data', '')) if (last_action == 'query' and action) else ''
                _push_step_memory(step_memory, step_idx + 1, instruction, last_action, mem_data)

                if progress_callback:
                    progress_callback(step_idx+1, len(steps), {'type':'step_done','step':step_idx+1,'total':len(steps),
                                                         'instruction':instruction,'status':'passed',
                                                         'screenshot':screenshot_url,'aiReasoning':reasonings,
                                                         'action':last_action,'anomalies': list(step_anomalies),
                                                         'after_screenshot': step_after_url,
                                                         **passed_extra,
                                                         'progress':int((step_idx+1)/len(steps)*100)})
                logger.info(f'[Runner] 步骤 {step_idx+1} 通过: {reasonings[-1] if reasonings else ""}')

                # 录制: 为每个动作补上 wait_after
                if record_mode:
                    # 确保 recording 列表足够长（step_idx 是当前步骤在 steps 中的索引）
                    while len(recording) <= step_idx:
                        recording.append(None)
                    after_png = ios_dev.screenshot() if ios_dev else adb_screenshot(device_id)
                    # 最后一个动作后直接结束（done/assert/query 收尾）: 用本步最终截图补实测等待
                    if last_exec_time is not None and last_rec_idx is not None and step_actions:
                        step_actions[last_rec_idx]['wait_after'] = _clamp_wait_after(time.time() - last_exec_time)
                        last_exec_time = None
                        last_rec_idx = None
                    # 无实测（旧路径兜底）: 用默认等待
                    if step_actions:
                        for a in step_actions:
                            a.setdefault('wait_after', _DEFAULT_WAIT_AFTER.get(a['action'], 0.5))
                    after_hash = str(_phash(after_png))
                    rec_data = {
                        'instruction': instruction,
                        'actions': step_actions,
                        'after_hash': after_hash,
                    }
                    # 条件步骤三态模型：有动作的步骤记录动作执行前的页面指纹（无动作时 after_hash 即"跳过"指纹）
                    if step_actions and step_before_png is not None:
                        rec_data['act_before_hash'] = str(_phash(step_before_png))
                    recording[step_idx] = rec_data

                step_idx += 1

            except Exception as e:
                if isinstance(e, ExecutionStopped) or execution_record.status in ('stopped', 'stopping'):
                    stopped = True
                    logger.info('[Runner] 用户已停止，中断执行')
                    results.append({'step': step_idx+1, 'instruction': instruction, 'status': 'stopped',
                                    'screenshot': '', 'aiReasoning': reasonings, 'action': 'stopped',
                                    'anomalies': list(step_anomalies)})
                    break
                logger.error(f'[Runner] 步骤 {step_idx+1} 失败: {e}')
                su = ''; png = None
                try:
                    png = ios_dev.screenshot() if ios_dev else adb_screenshot(device_id)
                    su = save_screenshot(png, execution_record.id, step_idx+1)
                except: pass
                failed_extra = {}
                if isinstance(e, AssertionError):
                    failed_extra['assert_passed'] = False
                err_text = str(e)
                if '截图失败' in err_text or 'WDA截图' in err_text:
                    step_anomalies.append(_build_anomaly(
                        'screenshot_error',
                        f'截图失败: {err_text[:300]}',
                        evidence={'error': err_text[:300]},
                        recovered=False,
                    ))
                results.append({'step':step_idx+1,'instruction':instruction,'status':'failed',
                                'action':last_action,'error':str(e),'screenshot':su,
                                'aiReasoning':reasonings,'anomalies': list(step_anomalies),
                                **failed_extra})
                step_idx += 1

    finally:
        # 清理 iOS 连接
        if ios_dev:
            try: ios_dev.disconnect()
            except: pass

    total = len(results); passed = sum(1 for r in results if r['status']=='passed')
    failed = sum(1 for r in results if r['status']=='failed')
    if replay_pass > 0 or replay_fail > 0:
        logger.info(f'[Runner] 回放统计: {replay_pass}步直放, {replay_fail}步纠错')
    logger.info(f'[Runner] 执行完成: {passed}/{total} 通过')
    result = {'totalSteps':total,'passedSteps':passed,'failedSteps':failed,'steps':results,
              'status':'stopped' if stopped else ('passed' if failed==0 else 'failed')}
    if record_mode and any(r is not None for r in recording):
        result['replay_data'] = {
            'name': f"录制 {datetime.now().strftime('%m-%d %H:%M')}",
            'device': {'name': device.name or device.device_id, 'platform': platform,
                       'resolution': {'width': width, 'height': height}},
            'recorded_at': datetime.now().isoformat(),
            # 保留 None 占位：步骤与 ai_prompt 索引一一对应，避免"打开应用"等快捷分支导致错位
            'steps': recording,
        }
    return result
