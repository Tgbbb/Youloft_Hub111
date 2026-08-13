# -*- coding: utf-8 -*-
"""Midscene 执行测试报告生成器。

参考 Midscene 的 HTML 报告形态：自包含单文件、截图 base64 内嵌、可离线打开。
内容：执行概要 + 步骤时间线（状态/动作/AI推理/错误/截图）。
"""
import base64
import html
import json
import logging
import os

from django.conf import settings

logger = logging.getLogger(__name__)

STATUS_LABEL = {
    'passed': '通过',
    'failed': '失败',
    'stopped': '已停止',
    'pending': '等待中',
    'running': '执行中',
    'error': '异常',
    'complete': '完成',
}

STATUS_COLOR = {
    'passed': '#16a34a',
    'failed': '#dc2626',
    'stopped': '#d97706',
    'pending': '#6b7280',
    'running': '#2563eb',
    'error': '#dc2626',
    'complete': '#16a34a',
}

ACTION_LABEL = {
    'tap': '点击', 'click': '点击', 'long_press': '长按', 'swipe': '滑动',
    'input': '输入', 'back': '返回', 'home': '主页', 'wait': '等待',
    'assert': '断言', 'query': '提取', 'done': '完成', 'launch': '启动',
    'stopped': '停止', 'failed': '失败', 'complete': '完成',
}

ANOMALY_LABEL = {
    'tap_retry': '点击重试',
    'hash_mismatch_fallback': '页面指纹不匹配',
    'action_skipped': '条件动作跳过',
    'stable_wait_timeout': '稳定等待超时',
    'replan': '重规划',
    'stuck_detected': '卡死检测',
    'locate_retry': '定位重试',
    'adb_error': 'ADB 错误',
    'wda_error': 'WDA 错误',
    'screenshot_error': '截图错误',
}

LAYER_LABEL = {
    'execution': '执行环境',
    'app': '应用页面',
    'unknown': '未知',
}

RECOVERED_LABEL = {True: '已恢复', False: '未恢复'}


def _resolve_media_path(url):
    """把 /media/... URL 解析为 MEDIA_ROOT 下的绝对路径；非法/越界/不存在返回 None。"""
    if not url or not url.startswith(settings.MEDIA_URL):
        return None
    rel = url[len(settings.MEDIA_URL):].lstrip('/')
    root = os.path.realpath(settings.MEDIA_ROOT)
    p = os.path.realpath(os.path.join(root, rel))
    if os.path.commonpath([root, p]) != root:
        return None
    return p if os.path.isfile(p) else None


def _png_data_url(url):
    """截图 URL -> data:image/png;base64,xxx；失败返回 None（不阻断报告）。"""
    path = _resolve_media_path(url)
    if not path:
        return None
    try:
        with open(path, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode('ascii')
        return f'data:image/png;base64,{b64}'
    except Exception as e:
        logger.warning(f'[Report] 读取截图失败 {path}: {e}')
        return None


def _fmt_duration(seconds):
    """秒 -> '1m23s' / '45s'。"""
    try:
        seconds = float(seconds or 0)
    except (TypeError, ValueError):
        return '-'
    if seconds <= 0:
        return '-'
    if seconds < 60:
        return f'{round(seconds)}s'
    return f'{int(seconds // 60)}m{round(seconds % 60)}s'


def _fmt_dt(dt):
    if not dt:
        return '-'
    try:
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return '-'


def _collect_anomaly_stats(steps):
    """从 steps_detail 汇总异常统计（按 type/layer），同时统计带异常的通过步骤数。"""
    total = 0
    by_type = {}
    by_layer = {}
    warned = 0
    for s in steps:
        anomalies = s.get('anomalies') or []
        if anomalies and s.get('status') == 'passed':
            warned += 1
        for a in anomalies:
            total += 1
            t = a.get('type', 'unknown')
            by_type[t] = by_type.get(t, 0) + 1
            layer = a.get('layer', 'unknown')
            by_layer[layer] = by_layer.get(layer, 0) + 1
    return {
        'total': total,
        'warned_steps': warned,
        'by_type': dict(sorted(by_type.items(), key=lambda kv: -kv[1])),
        'by_layer': dict(sorted(by_layer.items(), key=lambda kv: -kv[1])),
    }


def _collect_assert_stats(steps):
    """汇总断言统计：断言步骤数、通过/失败（assert_passed 由 runner/engine 写入）。"""
    assert_steps = [s for s in steps if 'assert_passed' in s]
    passed = sum(1 for s in assert_steps if s.get('assert_passed') is True)
    failed = sum(1 for s in assert_steps if s.get('assert_passed') is False)
    return {
        'total': len(assert_steps),
        'passed': passed,
        'failed': failed,
    }


def build_report_data(record):
    """从 MidsceneExecutionRecord 提取结构化报告数据。"""
    steps = list(record.steps_detail or [])
    passed = sum(1 for s in steps if s.get('status') == 'passed')
    failed = sum(1 for s in steps if s.get('status') == 'failed')
    stopped = sum(1 for s in steps if s.get('status') == 'stopped')
    total = len(steps) or record.total_steps or 0
    pass_rate = round(passed / total * 100, 1) if total else 0
    model = record.model_config_snapshot or {}
    anomaly_stats = _collect_anomaly_stats(steps)
    assert_stats = _collect_assert_stats(steps)
    return {
        'case_name': record.case_name or '未命名用例',
        'status': record.status,
        'status_label': STATUS_LABEL.get(record.status, record.status),
        'status_color': STATUS_COLOR.get(record.status, '#6b7280'),
        'platform': record.get_platform_display() if hasattr(record, 'get_platform_display') else record.platform,
        'device_name': (record.device.name or record.device.device_id) if record.device else '-',
        'auto_plan': bool(record.auto_plan),
        'model_name': model.get('model_name') or model.get('name') or '',
        'executed_by': record.executed_by.username if record.executed_by else '-',
        'started_at': _fmt_dt(record.started_at),
        'finished_at': _fmt_dt(record.finished_at),
        'duration': _fmt_duration(record.duration),
        'error_message': record.error_message or '',
        'stats': {'total': total, 'passed': passed, 'failed': failed, 'stopped': stopped},
        'anomaly_stats': anomaly_stats,
        'assert_stats': assert_stats,
        'pass_rate': pass_rate,
        'steps': steps,
    }


def _esc(value):
    return html.escape(str(value if value is not None else ''))


def _render_step(step):
    status = step.get('status', '')
    action = step.get('action', '')
    action_label = ACTION_LABEL.get(action, action or '')
    reasoning = step.get('aiReasoning') or []
    if isinstance(reasoning, str):
        reasoning = [reasoning]
    error = step.get('error', '')
    screenshot = _png_data_url(step.get('screenshot', ''))
    num = _esc(step.get('step', ''))
    anomalies = step.get('anomalies') or []
    warn = status == 'passed' and bool(anomalies)
    status_text = _esc(STATUS_LABEL.get(status, status) + ('（有异常）' if warn else ''))
    color = STATUS_COLOR.get(status, '#6b7280')
    if warn:
        color = '#d97706'  # 通过但带异常：黄标
    title = _esc(step.get('instruction', ''))
    cls = 'msr-step--fail' if status == 'failed' else ''
    if warn:
        cls = 'msr-step--warn'

    parts = [
        f'<div class="msr-step {cls}" id="step-{num}">',
        '  <div class="msr-step__head">',
        f'    <span class="msr-step__num">{num}</span>',
        f'    <span class="msr-step__status" style="color:{color}">{status_text}</span>',
        f'    <span class="msr-step__action">{_esc(action_label)}</span>',
        f'    <span class="msr-step__title">{title}</span>',
        '  </div>',
    ]
    if error:
        parts.append(f'  <div class="msr-step__error">{_esc(error)}</div>')
    if reasoning:
        parts.append('  <div class="msr-step__reason"><div class="msr-label">AI 推理</div>')
        parts.extend(f'    <div class="msr-line">{_esc(r)}</div>' for r in reasoning)
        parts.append('  </div>')
    if anomalies:
        parts.append(f'  <div class="msr-step__anoms"><div class="msr-label">异常事件（{len(anomalies)}）</div>')
        for a in anomalies:
            type_label = ANOMALY_LABEL.get(a.get('type', ''), a.get('type', '未知'))
            layer = LAYER_LABEL.get(a.get('layer', ''), a.get('layer', '未知'))
            recovered = RECOVERED_LABEL.get(bool(a.get('recovered')), '')
            message = _esc(str(a.get('message', ''))[:200])
            evidence = a.get('evidence') or {}
            evidence_html = _esc(json.dumps(evidence, ensure_ascii=False, indent=2))
            parts.append(
                f'    <details class="msr-anom">'
                f'<summary><span class="msr-anom__badge">{_esc(type_label)}</span>'
                f' {message} <span class="msr-anom__meta">层级:{layer} · {recovered}</span></summary>'
                f'<pre class="msr-anom__ev">{evidence_html}</pre></details>'
            )
        parts.append('  </div>')
    if screenshot:
        parts.append(f'  <div class="msr-step__shot"><img src="{screenshot}" alt="step {num} screenshot" /></div>')
    parts.append('</div>')
    return '\n'.join(parts)


def to_html(record):
    """生成自包含 HTML 报告（截图内嵌 base64），可离线打开分享。"""
    data = build_report_data(record)
    stats = data['stats']
    anomaly_stats = data['anomaly_stats']
    assert_stats = data['assert_stats']

    steps_html = '\n'.join(_render_step(s) for s in data['steps'])
    if not steps_html:
        steps_html = '<div class="msr-empty">暂无步骤数据</div>'

    stat_cells = ''.join(
        f'<div class="msr-stat"><span class="msr-stat__value" style="color:{STATUS_COLOR.get(k, "#6b7280")}">{v}</span>'
        f'<span class="msr-stat__label">{label}</span></div>'
        for k, label, v in (
            ('passed', '通过', stats['passed']),
            ('failed', '失败', stats['failed']),
            ('stopped', '停止', stats['stopped']),
        )
    )
    total_cell = (
        f'<div class="msr-stat"><span class="msr-stat__value">{stats["total"]}</span>'
        f'<span class="msr-stat__label">总计</span></div>'
    )
    warn_cell = (
        f'<div class="msr-stat"><span class="msr-stat__value" style="color:#d97706">{anomaly_stats["warned_steps"]}</span>'
        f'<span class="msr-stat__label">带异常通过</span></div>'
    ) if anomaly_stats['warned_steps'] > 0 else ''

    model_text = data['model_name'] or '未记录'
    mode_text = '智能规划 (aiAct)' if data['auto_plan'] else '逐步执行'

    summary_rows = ''.join(
        f'<div class="msr-item"><span class="msr-item__k">{_esc(k)}</span><span class="msr-item__v">{_esc(v)}</span></div>'
        for k, v in (
            ('用例', data['case_name']),
            ('状态', data['status_label']),
            ('平台', data['platform']),
            ('设备', data['device_name']),
            ('执行模式', mode_text),
            ('AI 模型', model_text),
            ('执行人', data['executed_by']),
            ('开始时间', data['started_at']),
            ('结束时间', data['finished_at']),
            ('耗时', data['duration']),
        )
    )
    error_html = ''
    if data['error_message']:
        error_html = f'<div class="msr-err">{_esc(data["error_message"])}</div>'

    # 异常统计块：类型 / 层级 / 断言
    anom_type_chips = ''.join(
        f'<span class="msr-chip">{_esc(ANOMALY_LABEL.get(t, t))} × {n}</span>'
        for t, n in anomaly_stats['by_type'].items()
    ) or '<span class="msr-chip msr-chip--empty">无</span>'
    anom_layer_chips = ''.join(
        f'<span class="msr-chip">{_esc(LAYER_LABEL.get(l, l))} × {n}</span>'
        for l, n in anomaly_stats['by_layer'].items()
    ) or '<span class="msr-chip msr-chip--empty">无</span>'
    if assert_stats['total']:
        assert_block = (
            f'<div class="msr-anom-block__row"><span class="msr-anom-block__k">断言统计</span>'
            f'<span class="msr-chip msr-chip--ok">通过 {assert_stats["passed"]}</span>'
            f'<span class="msr-chip msr-chip--fail">失败 {assert_stats["failed"]}</span>'
            f'<span class="msr-anom-block__sub">共 {assert_stats["total"]} 条断言</span></div>'
        )
    else:
        assert_block = (
            '<div class="msr-anom-block__row"><span class="msr-anom-block__k">断言统计</span>'
            '<span class="msr-chip msr-chip--empty">无</span></div>'
        )
    anomaly_block = f"""
  <div class="msr-section-title">异常与断言</div>
  <div class="msr-anom-block">
    <div class="msr-anom-block__row"><span class="msr-anom-block__k">异常事件</span>
      <span class="msr-anom-block__v">共 {anomaly_stats['total']} 次</span>
      <span class="msr-anom-block__sub">按类型</span></div>
    <div class="msr-anom-block__chips">{anom_type_chips}</div>
    <div class="msr-anom-block__row"><span class="msr-anom-block__k">异常层级</span>
      <span class="msr-anom-block__sub">执行环境 / 应用页面 / 未知</span></div>
    <div class="msr-anom-block__chips">{anom_layer_chips}</div>
    {assert_block}
  </div>
"""

    rate = data['pass_rate']
    rate_width = min(100, rate)
    rate_text = f'{rate:.0f}%' if float(rate).is_integer() else f'{rate:.1f}%'
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{_esc(data['case_name'])} - 测试报告</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: "Noto Sans SC", "Microsoft YaHei", "PingFang SC", sans-serif; background: #f4f4f1; color: #1f2328; padding: 32px 16px; }}
.msr-wrap {{ max-width: 860px; margin: 0 auto; }}
.msr-header {{ background: #fff; border: 1px solid #e5e5e1; padding: 24px 28px; margin-bottom: 16px; }}
.msr-header__top {{ display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }}
.msr-title {{ font-size: 22px; font-weight: 700; }}
.msr-badge {{ font-size: 13px; font-weight: 600; padding: 3px 10px; border-radius: 999px; color: #fff; }}
.msr-sub {{ color: #888; font-size: 12px; margin-top: 6px; }}
.msr-stats {{ display: flex; gap: 10px; margin-top: 16px; flex-wrap: wrap; }}
.msr-stat {{ flex: 1; min-width: 90px; background: #fafaf8; border: 1px solid #efefe9; padding: 10px 12px; text-align: center; }}
.msr-stat__value {{ display: block; font-size: 20px; font-weight: 700; }}
.msr-stat__label {{ font-size: 12px; color: #888; }}
.msr-rate {{ height: 8px; background: #e8e8e4; border-radius: 4px; margin-top: 14px; overflow: hidden; }}
.msr-rate__fill {{ height: 100%; background: #16a34a; }}
.msr-rate__text {{ font-size: 12px; color: #888; margin-top: 6px; }}
.msr-summary {{ background: #fff; border: 1px solid #e5e5e1; padding: 18px 28px; margin-bottom: 16px; display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px 24px; }}
.msr-item {{ display: flex; justify-content: space-between; gap: 16px; font-size: 13px; border-bottom: 1px dashed #f0f0ec; padding-bottom: 6px; }}
.msr-item__k {{ color: #888; white-space: nowrap; }}
.msr-item__v {{ text-align: right; word-break: break-all; }}
.msr-err {{ margin: 10px 0; background: #fef2f2; border: 1px solid #fecaca; color: #b91c1c; font-size: 13px; padding: 10px 12px; }}
.msr-section-title {{ font-size: 15px; font-weight: 700; margin: 20px 0 10px; }}
.msr-step {{ background: #fff; border: 1px solid #e5e5e1; border-left: 4px solid #16a34a; padding: 16px 20px; margin-bottom: 12px; }}
.msr-step--fail {{ border-left-color: #dc2626; }}
.msr-step--warn {{ border-left-color: #d97706; background: #fffdf5; }}
.msr-step__head {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
.msr-step__num {{ font-size: 18px; font-weight: 700; color: #444; }}
.msr-step__status {{ font-size: 13px; font-weight: 600; }}
.msr-step__action {{ font-size: 12px; color: #2563eb; border: 1px solid #bfdbfe; background: #eff6ff; padding: 1px 8px; border-radius: 999px; }}
.msr-step__title {{ font-size: 14px; font-weight: 600; flex: 1; min-width: 200px; }}
.msr-step__error {{ margin-top: 10px; background: #fef2f2; border: 1px solid #fecaca; color: #b91c1c; font-size: 13px; padding: 8px 10px; white-space: pre-wrap; word-break: break-all; }}
.msr-step__anoms {{ margin-top: 10px; background: #fffdf5; border: 1px solid #fde68a; padding: 8px 10px; }}
.msr-anom {{ margin: 6px 0; font-size: 13px; }}
.msr-anom summary {{ cursor: pointer; color: #555; line-height: 1.6; }}
.msr-anom__badge {{ display: inline-block; font-size: 11px; color: #92400e; background: #fef3c7; border: 1px solid #fcd34d; padding: 0 8px; border-radius: 999px; margin-right: 6px; }}
.msr-anom__meta {{ color: #999; font-size: 11px; margin-left: 6px; }}
.msr-anom__ev {{ margin-top: 6px; font-size: 11px; color: #666; background: #fafaf8; border: 1px solid #efefe9; padding: 8px; white-space: pre-wrap; word-break: break-all; }}
.msr-anom-block {{ background: #fff; border: 1px solid #e5e5e1; padding: 16px 24px; margin-bottom: 16px; }}
.msr-anom-block__row {{ display: flex; align-items: center; gap: 10px; font-size: 13px; margin-top: 8px; }}
.msr-anom-block__row:first-child {{ margin-top: 0; }}
.msr-anom-block__k {{ color: #888; min-width: 64px; }}
.msr-anom-block__v {{ font-weight: 700; }}
.msr-anom-block__sub {{ color: #aaa; font-size: 12px; }}
.msr-anom-block__chips {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0 4px 74px; }}
.msr-chip {{ font-size: 12px; color: #555; background: #f5f5f2; border: 1px solid #e3e3dd; padding: 2px 10px; border-radius: 999px; }}
.msr-chip--ok {{ color: #16a34a; border-color: #bbf7d0; background: #f0fdf4; }}
.msr-chip--fail {{ color: #dc2626; border-color: #fecaca; background: #fef2f2; }}
.msr-chip--empty {{ color: #999; }}
.msr-step__reason {{ margin-top: 10px; }}
.msr-label {{ font-size: 11px; color: #999; margin-bottom: 4px; }}
.msr-line {{ font-size: 13px; color: #555; line-height: 1.6; padding: 2px 0; }}
.msr-step__shot {{ margin-top: 10px; }}
.msr-step__shot img {{ max-width: 360px; width: 100%; border: 1px solid #e5e5e1; }}
.msr-empty {{ background: #fff; border: 1px solid #e5e5e1; padding: 32px; text-align: center; color: #999; }}
@media (max-width: 640px) {{ .msr-summary {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<div class="msr-wrap">
  <div class="msr-header">
    <div class="msr-header__top">
      <span class="msr-title">{_esc(data['case_name'])}</span>
      <span class="msr-badge" style="background:{data['status_color']}">{_esc(data['status_label'])}</span>
    </div>
    <div class="msr-sub">执行完成于 {_esc(data['finished_at'])} · 共 {stats['total']} 步</div>
    <div class="msr-stats">{total_cell}{stat_cells}{warn_cell}</div>
    <div class="msr-rate"><div class="msr-rate__fill" style="width:{rate_width}%"></div></div>
    <div class="msr-rate__text">通过率 {rate_text}</div>
  </div>

  <div class="msr-section-title">执行概要</div>
  <div class="msr-summary">{summary_rows}</div>
  {error_html}
  {anomaly_block}

  <div class="msr-section-title">步骤详情</div>
  {steps_html}
</div>
</body>
</html>
"""


def generate_report_file(record, force=False):
    """生成/复用 HTML 报告文件（media/midscene/{id}/report.html），返回 report_path。

    report_path 已存在且非 force 时直接复用；报告随执行记录删除自动清理。
    """
    from .models import MidsceneExecutionRecord
    if not isinstance(record, MidsceneExecutionRecord):
        raise ValueError('record 必须是 MidsceneExecutionRecord 实例')
    if record.report_path and not force:
        return record.report_path
    d = os.path.join(settings.MEDIA_ROOT, 'midscene', str(record.id))
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, 'report.html')
    try:
        with open(p, 'w', encoding='utf-8') as f:
            f.write(to_html(record))
    except Exception as e:
        logger.error(f'[Report] 生成报告文件失败: {e}')
        raise
    report_path = f'{settings.MEDIA_URL}midscene/{record.id}/report.html'
    if record.report_path != report_path:
        record.report_path = report_path
        record.save(update_fields=['report_path'])
    return report_path
