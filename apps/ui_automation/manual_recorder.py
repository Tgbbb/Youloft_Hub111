# -*- coding: utf-8 -*-
"""真机手操录制：adb shell getevent 采集 -> tap/swipe/long_press 动作脚本。

v1 仅支持 Android 本机直连（USB/WiFi ADB）：
- 采集 `adb -s <serial> shell getevent -lt` 常驻输出；
- 解析 ABS_MT_POSITION_X/Y、BTN_TOUCH、ABS_MT_TRACKING_ID、SYN_REPORT，
  把手势识别为 tap / swipe / long_press，坐标按设备分辨率归一化为百分比；
- 手指抬起后静默 >= 1.5s 自动切分为一步，步间记录 wait_after；
- 键盘 input 事件（EV_KEY 非 BTN_TOUCH）一律忽略；
- 生成结构与现有录制 (replay_data) 完全一致的脚本，供「纯动作直放」回放。

文本输入 v1 不处理（getevent 只吐 keycode），由用户在预览里人工补 input 步骤。
"""
import logging
import os
import re
import subprocess
import threading
import time
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

# ---- 可调参数 ----
SESSION_TTL = 30 * 60          # 会话 TTL（秒）：超时未停止自动回收
STOPPED_TTL = 30 * 60          # 停止后预览/保存数据的保留时长（秒）
STEP_PAUSE = 1.5               # 停顿阈值（秒）：抬起后静默超过该值视为一步结束
LONG_PRESS_MS = 600            # 长按阈值（毫秒）
MAX_WAIT_AFTER = 120.0         # 步间等待上限（秒），回放时等待不超过该值
SWIPE_MIN_MS = 100             # swipe 时长下限（毫秒）
SWIPE_MAX_MS = 5000            # swipe 时长上限（毫秒）
TRACKING_ID_UP = 0xFFFFFFFF   # ABS_MT_TRACKING_ID 抬起标记

_WIN_KW = {}
if os.name == 'nt':
    _WIN_KW['creationflags'] = subprocess.CREATE_NO_WINDOW

# getevent -lt 行样例：
# [ 40946.973909] /dev/input/event5: EV_ABS       ABS_MT_POSITION_X    00000138
# [ 40946.973915] /dev/input/event5: EV_KEY       BTN_TOUCH            DOWN
_LINE_RE = re.compile(
    r'^\s*(?:\[\s*([\d.]+)\]\s+)?\S+:\s+(\S+)\s+(\S+)\s+(\S+)\s*$'
)
_PANEL_LINE = re.compile(
    r'ABS_MT_POSITION_([XY])\s*:\s*value\s+-?\d+,\s*min\s+(-?\d+),\s*max\s+(-?\d+)'
)


# ============================================================
# getevent 行解析（纯函数）
# ============================================================
def _parse_value(val_str):
    """getevent 值：DOWN/UP 标签或十六进制；解析失败返回 None。"""
    if val_str in ('DOWN', 'down'):
        return 1
    if val_str in ('UP', 'up'):
        return 0
    try:
        return int(val_str, 16)
    except (TypeError, ValueError):
        return None


def parse_getevent_line(line):
    """解析一行 getevent -lt 输出。

    返回 {'t': float|None, 'type': str, 'code': str, 'value': int|None}；
    无法解析的行返回 None。t 为设备时间戳（秒），-t 缺失时为 None。
    """
    if not line:
        return None
    m = _LINE_RE.match(line.strip())
    if not m:
        return None
    t_str, etype, code, val_str = m.groups()
    try:
        t = float(t_str) if t_str else None
    except (TypeError, ValueError):
        t = None
    return {'t': t, 'type': etype, 'code': code, 'value': _parse_value(val_str)}


def _clamp100(v):
    return max(0.0, min(100.0, v))


def _coord_pct(raw, ref, rng, authoritative=False):
    """原始坐标 -> 0..100 百分比。

    优先使用触摸面板坐标区间（getevent -lp 读取，权威）；面板区间不可用且
    观察到的坐标域远大于屏幕（如 0..4095）时，用会话 min/max 兜底归一化；
    否则按设备分辨率归一化。
    """
    if raw is None:
        return None
    lo, hi = (rng or (None, None))
    if ref and ref > 0:
        if hi is not None and lo is not None and hi > lo and \
           (authoritative or hi > ref * 1.6):
            return _clamp100((raw - lo) / (hi - lo) * 100.0)
        return _clamp100(raw / ref * 100.0)
    if hi is not None and lo is not None and hi > lo:
        return _clamp100((raw - lo) / (hi - lo) * 100.0)
    return None


def events_to_strokes(events):
    """过滤后的 getevent 事件流 -> 笔划列表（单指模型）。

    stroke: {'start_t': float|None, 'end_t': float|None,
             'points': [(x_raw, y_raw, t), ...]}（t 与坐标都可能为 None 的
             X/Y 分列进场会先在 SYN 处合并）。
    键盘事件（EV_KEY 非 BTN_TOUCH）在编码层面即被忽略。
    """
    strokes = []
    cur = None
    pending_x = pending_y = None

    def open_stroke(t):
        nonlocal pending_x, pending_y
        st = {'start_t': t, 'end_t': None, 'points': []}
        if pending_x is not None or pending_y is not None:
            st['points'].append((pending_x, pending_y, t))
            pending_x = pending_y = None
        return st

    def close_stroke(close_t=None):
        nonlocal cur
        if cur is not None:
            pts = [p for p in cur['points'] if p[0] is not None and p[1] is not None]
            if pts:
                last_t = pts[-1][2] if pts[-1][2] is not None else cur['start_t']
                end_t = close_t if close_t is not None else last_t
                if last_t is not None and close_t is not None and last_t > close_t:
                    end_t = last_t
                strokes.append({
                    'start_t': pts[0][2] if pts[0][2] is not None else cur['start_t'],
                    'end_t': end_t,
                    'points': pts,
                })
        cur = None

    for ev in events:
        code = ev.get('code') or ''
        etype = ev.get('type') or ''
        value = ev.get('value')
        t = ev.get('t')
        if code == 'ABS_MT_POSITION_X':
            pending_x = value
        elif code == 'ABS_MT_POSITION_Y':
            pending_y = value
        elif code == 'ABS_MT_TRACKING_ID':
            if value is None or value in (-1, TRACKING_ID_UP):
                close_stroke(t)
                pending_x = pending_y = None
            elif cur is None:
                cur = open_stroke(t)
        elif code == 'BTN_TOUCH':
            if value == 0:
                close_stroke(t)
                pending_x = pending_y = None
            elif value == 1 and cur is None:
                cur = open_stroke(t)
        elif code == 'SYN_REPORT' or (etype == 'EV_SYN' and value == 0):
            if cur is not None and (pending_x is not None or pending_y is not None):
                cur['points'].append((pending_x, pending_y, t))
            pending_x = pending_y = None
    close_stroke()
    return strokes


def _stroke_ranges(strokes):
    """所有笔划坐标的 min/max（会话级兜底归一化）。"""
    xs = [p[0] for s in strokes for p in s['points'] if p[0] is not None]
    ys = [p[1] for s in strokes for p in s['points'] if p[1] is not None]
    xr = (min(xs), max(xs)) if xs else (None, None)
    yr = (min(ys), max(ys)) if ys else (None, None)
    return xr, yr


def _tap_max_dist(width, height):
    diag = (float(width) ** 2 + float(height) ** 2) ** 0.5
    return max(24.0, diag * 0.03)


def _net_dist(pts):
    """首点 -> 末点位移（用于 tap/swipe 判定）。

    getevent 在 60~120Hz 下会吐出大量中间坐标点，相邻单帧步进很小；
    若用『最大单帧步进』判定，一段真实滑动会被误判成 tap。因此这里
    使用整段手势的首末位移——这也与 swipe 动作落地成 (x1,y1)->(x2,y2)
    的表示一致。
    """
    if len(pts) < 2:
        return 0.0
    (x0, y0, _), (x1, y1, _) = pts[0], pts[-1]
    return ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5


def classify_stroke(stroke, width, height, x_range=None, y_range=None,
                    x_authoritative=False, y_authoritative=False):
    """单个笔划 -> 动作 dict（百分比坐标）。

    位移小且时长短 -> tap；位移小但时长超阈值 -> long_press；
    否则 -> swipe（首点到末点）。坐标缺失时返回 None。
    """
    pts = [p for p in stroke['points'] if p[0] is not None and p[1] is not None]
    if not pts:
        return None
    x0, y0 = pts[0][0], pts[0][1]
    x1, y1 = pts[-1][0], pts[-1][1]
    duration = 0.0
    if stroke.get('start_t') is not None and stroke.get('end_t') is not None:
        duration = max(0.0, stroke['end_t'] - stroke['start_t'])
    elif pts[0][2] is not None and pts[-1][2] is not None:
        duration = max(0.0, pts[-1][2] - pts[0][2])
    dist = _net_dist(pts)
    x_pct = _coord_pct(x0, width, x_range, x_authoritative)
    y_pct = _coord_pct(y0, height, y_range, y_authoritative)
    if x_pct is None or y_pct is None:
        return None
    dur_ms = int(round(duration * 1000))
    if dist <= _tap_max_dist(width, height):
        if dur_ms >= LONG_PRESS_MS:
            return {
                'action': 'long_press',
                'x_pct': round(x_pct, 2),
                'y_pct': round(y_pct, 2),
                'duration': max(LONG_PRESS_MS, min(5000, dur_ms)),
            }
        return {'action': 'tap', 'x_pct': round(x_pct, 2), 'y_pct': round(y_pct, 2)}
    x2_pct = _coord_pct(x1, width, x_range, x_authoritative)
    y2_pct = _coord_pct(y1, height, y_range, y_authoritative)
    if x2_pct is None or y2_pct is None:
        return {'action': 'tap', 'x_pct': round(x_pct, 2), 'y_pct': round(y_pct, 2)}
    return {
        'action': 'swipe',
        'x1_pct': round(x_pct, 2),
        'y1_pct': round(y_pct, 2),
        'x2_pct': round(x2_pct, 2),
        'y2_pct': round(y2_pct, 2),
        'duration': max(SWIPE_MIN_MS, min(SWIPE_MAX_MS, dur_ms or SWIPE_MIN_MS)),
    }


def segment_strokes(strokes, pause=STEP_PAUSE):
    """按停顿把笔划切分为步骤组。

    抬起后静默 >= pause（在下一笔开始时确认）即关闭上一步；
    返回 [{'strokes': [...], 'wait_after': float}]，wait_after 为上一步
    结束后到下一步开始的静默时长（回放时按此等待），首/尾步为 0。
    """
    groups = []
    cur = None
    prev_end = None
    for s in strokes:
        gap = (s['start_t'] - prev_end) if prev_end is not None else None
        if cur is not None and gap is not None and gap >= pause:
            cur['wait_after'] = min(gap, MAX_WAIT_AFTER)
            groups.append(cur)
            cur = None
        if cur is None:
            cur = {'strokes': [s], 'wait_after': 0.0}
        else:
            cur['strokes'].append(s)
        prev_end = s['end_t']
    if cur is not None:
        groups.append(cur)
    return groups


def parse_lines_to_steps(lines, width, height, pause=STEP_PAUSE, ranges=None):
    """原始行流 -> 步骤列表。lines: [(monotonic_ts, line_text), ...]。

    每步 {'instruction': '步骤 N', 'actions': [...], 'wait_after': float}，
    actions 结构对齐现有 replay_data（x_pct/y_pct/swipe 百分比坐标）。
    ranges: {'x': (min,max), 'y': (min,max)} 触摸面板坐标区间（权威）；
    缺省时按会话观察范围/屏幕尺寸兜底。
    """
    events = []
    for mono, text in lines:
        ev = parse_getevent_line(text)
        if ev is not None:
            if ev['t'] is None:
                ev['t'] = mono
            events.append(ev)
    strokes = events_to_strokes(events)
    x_range, y_range = _stroke_ranges(strokes)
    panel_ranges = ranges or {}
    px, py = panel_ranges.get('x'), panel_ranges.get('y')
    x_authoritative = y_authoritative = False
    if px and px[1] > px[0]:
        x_range, x_authoritative = px, True
    if py and py[1] > py[0]:
        y_range, y_authoritative = py, True
    groups = segment_strokes(strokes, pause)
    steps = []
    for i, g in enumerate(groups):
        actions = []
        for si, s in enumerate(g['strokes']):
            act = classify_stroke(s, width, height, x_range, y_range,
                                  x_authoritative, y_authoritative)
            if act is None:
                continue
            if si > 0 and s['start_t'] is not None and g['strokes'][si - 1]['end_t'] is not None:
                act['wait_after'] = round(max(0.0, s['start_t'] - g['strokes'][si - 1]['end_t']), 2)
            actions.append(act)
        steps.append({
            'instruction': f'步骤 {i + 1}',
            'actions': actions,
            'wait_after': round(float(g.get('wait_after') or 0.0), 2),
        })
    return steps


def build_replay_data(steps, device, width, height, name='', recorded_at=None):
    """步骤列表 -> replay_data 条目（结构一致：device/resolution/steps）。"""
    return {
        'name': name or f"手操录制 {time.strftime('%m-%d %H:%M')}",
        'mode': 'manual',
        'device': {
            'name': getattr(device, 'name', '') or getattr(device, 'device_id', ''),
            'platform': getattr(device, 'platform', 'android'),
            'resolution': {'width': width, 'height': height},
        },
        'recorded_at': recorded_at or datetime.now().isoformat(timespec='seconds'),
        'steps': steps,
    }


def read_panel_ranges(serial, timeout=10):
    """读取触摸面板坐标区间（getevent -lp）。

    返回 {'x': (min, max), 'y': (min, max)}；读取失败返回 None。
    面板区间权威：坐标比例不受"只点了屏幕一角"影响。
    """
    try:
        r = subprocess.run(
            ['adb', '-s', serial, 'shell', 'getevent', '-lp'],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            timeout=timeout, **_WIN_KW,
        )
    except Exception as e:
        logger.warning(f'[ManualRecorder] 读取面板坐标区间失败: {e}')
        return None
    x = y = None
    for line in (r.stdout or '').splitlines():
        m = _PANEL_LINE.search(line)
        if not m:
            continue
        axis, lo, hi = m.group(1), int(m.group(2)), int(m.group(3))
        if axis == 'X':
            x = (lo, hi)
        else:
            y = (lo, hi)
    if x is None and y is None:
        return None
    return {'x': x, 'y': y}


# ============================================================
# 采集会话（进程 + 后台读行线程）
# ============================================================
class _LineCollector(threading.Thread):
    """后台读取 getevent stdout，逐行带单调时间戳落盘到内存列表。"""

    def __init__(self, proc):
        super().__init__(daemon=True)
        self.proc = proc
        self.lines = []
        # 注意：不能用 self._stop 命名停止标记——threading.Thread 在收尾时
        # 会调用内部 self._stop()，被布尔值遮蔽会导致 is_alive() 崩溃
        self._quit = False

    def run(self):
        try:
            for raw in self.proc.stdout:
                if self._quit:
                    break
                self.lines.append((time.monotonic(), raw))
        except Exception as e:
            logger.debug(f'[ManualRecorder] 读行线程结束: {e}')

    def stop(self):
        self._quit = True


_sessions = {}      # session_id -> running session
_stopped = {}       # session_id -> stopped preview data（供 save）
_lock = threading.Lock()


def _expire_locked():
    now = time.monotonic()
    for sid, s in list(_sessions.items()):
        if now - s['ts'] <= SESSION_TTL:
            continue
        _sessions.pop(sid, None)
        try:
            from .models import MidsceneDevice
            device = MidsceneDevice.objects.get(id=s['device_id'])
            device.unlock()
        except Exception as e:
            logger.warning(f'[ManualRecorder] 会话 {sid} 超时回收，解锁设备失败: {e}')
        logger.warning(f'[ManualRecorder] 会话 {sid} 超时回收')
    for sid in [k for k, s in _stopped.items() if now - s['ts'] > STOPPED_TTL]:
        _stopped.pop(sid, None)


def start_session(device, user):
    """锁定设备并启动 getevent 采集，返回 session_id。

    device: MidsceneDevice（Android）；user: 锁设备用户。
    占用校验由视图层负责；这里失败时自动回滚锁定。
    """
    serial = getattr(device, 'adb_serial', '') or getattr(device, 'device_id', '')
    if not serial:
        raise ValueError('Android 设备标识无效')
    with _lock:
        _expire_locked()
        for s in _sessions.values():
            if s['device_id'] == device.id:
                raise ValueError('该设备已有录制会话进行中，请先停止')
        width = height = 0
        panel_ranges = None
        try:
            from .midscene_runner import adb_get_screen_size
            width, height = adb_get_screen_size(serial)
        except Exception as e:
            logger.warning(f'[ManualRecorder] 读取分辨率失败: {e}')
        panel_ranges = read_panel_ranges(serial)
        proc = subprocess.Popen(
            ['adb', '-s', serial, 'shell', 'getevent', '-lt'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8', errors='replace', **_WIN_KW,
        )
        collector = _LineCollector(proc)
        collector.start()
        session_id = uuid.uuid4().hex[:12]
        _sessions[session_id] = {
            'device_id': device.id,
            'device_name': getattr(device, 'name', '') or serial,
            'user_id': getattr(user, 'id', None),
            'proc': proc,
            'collector': collector,
            'width': width,
            'height': height,
            'ranges': panel_ranges,
            'ts': time.monotonic(),
            'started_at': datetime.now().isoformat(timespec='seconds'),
        }
    try:
        device.lock(user)
    except Exception:
        with _lock:
            _sessions.pop(session_id, None)
        _terminate_proc(proc, collector)
        raise
    return session_id


def _terminate_proc(proc, collector):
    collector.stop()
    try:
        proc.terminate()
    except Exception:
        pass
    try:
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    if collector.is_alive():
        collector.join(timeout=5)
    try:
        if proc.stdout:
            proc.stdout.close()
        if proc.stderr:
            proc.stderr.close()
    except Exception:
        pass


def stop_session(session_id):
    """停止采集、解锁设备、解析并缓存预览数据。

    返回 (steps, {'width','height'})；解析后数据缓存在 _stopped 供 save 使用。
    """
    with _lock:
        session = _sessions.pop(session_id, None)
        if session is None:
            raise KeyError(session_id)
    proc = session['proc']
    collector = session['collector']
    # 终止采集；无论是否成功都保证解锁设备（避免设备卡在 locked）
    try:
        _terminate_proc(proc, collector)
    except Exception as e:
        logger.error(f'[ManualRecorder] 终止采集进程失败: {e}', exc_info=True)
    finally:
        try:
            from .models import MidsceneDevice
            device = MidsceneDevice.objects.get(id=session['device_id'])
            device.unlock()
        except Exception as e:
            logger.warning(f'[ManualRecorder] 解锁设备失败: {e}')
    stderr_tail = ''
    try:
        if proc.stderr and proc.poll() is not None:
            stderr_tail = (proc.stderr.read() or '')[-500:]
    except Exception:
        pass
    lines = list(collector.lines)
    if not lines and proc.poll() not in (None, 0):
        raise ValueError('getevent 采集失败（设备可能离线）: ' + (stderr_tail or '未知错误'))
    width = session['width'] or 1080
    height = session['height'] or 1920
    steps = parse_lines_to_steps(lines, width, height, ranges=session.get('ranges'))
    with _lock:
        _stopped[session_id] = {
            'steps': steps,
            'width': width,
            'height': height,
            'device_id': session['device_id'],
            'device_name': session['device_name'],
            'ts': time.monotonic(),
        }
    return steps, {'width': width, 'height': height}


def get_stopped_preview(session_id):
    """获取已停止会话的预览数据（save 用），过期/不存在抛 KeyError。"""
    with _lock:
        _expire_locked()
        data = _stopped.get(session_id)
        if data is None:
            raise KeyError(session_id)
        return data


def discard_stopped(session_id):
    with _lock:
        _stopped.pop(session_id, None)


def current_sessions():
    """运行中会话快照（调试/测试用）。"""
    with _lock:
        return list(_sessions.keys())
