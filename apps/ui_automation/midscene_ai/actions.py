# -*- coding: utf-8 -*-
"""动作空间与参数归一化（对齐 Midscene 移动端动作白名单）。

模型只能输出白名单动作；交互动作（tap/long_press/swipe/input）需要坐标，
坐标可以是 locate 描述（由 locate.py 两阶段定位填充），也可以是直接坐标
（x_pct/y_pct 等）。本模块负责：动作类型校验、pct->px 换算、越界处理与
必填参数校验。
"""

INTERACTIVE_ACTIONS = frozenset({'tap', 'long_press', 'swipe', 'input'})
ACTION_WHITELIST = INTERACTIVE_ACTIONS | frozenset({'back', 'home', 'wait', 'assert', 'query'})

# 各动作需要的坐标对（tap/long_press 单个中心点，swipe 起止两点）
_COORD_PAIRS = {
    'tap': (('x', 'y'),),
    'long_press': (('x', 'y'),),
    'swipe': (('x1', 'y1'), ('x2', 'y2')),
}

# locate 字段 -> 填充的坐标对
_LOCATE_FIELDS = {
    'tap': (('locate', ('x', 'y')),),
    'long_press': (('locate', ('x', 'y')),),
    'input': (('locate', ('x', 'y')),),
    'swipe': (('locate_start', ('x1', 'y1')), ('locate_end', ('x2', 'y2'))),
}


def _to_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _has_px(params, coord):
    return params.get(coord) is not None


def _has_pct(params, coord):
    return params.get(f'{coord}_pct') is not None


def fill_pixel_coords(params, width, height):
    """把 x/y/x1/y1/x2/y2 的百分比换算为像素并夹取到屏幕范围。

    优先使用已有像素值；没有像素值才用 pct。百分比必须 0-100，否则返回
    (False, error)；像素越界时夹取到 [0, width/height]。
    """
    for coord in ('x', 'y', 'x1', 'y1', 'x2', 'y2'):
        ref = width if coord.startswith('x') else height
        if _has_px(params, coord):
            params[coord] = int(max(0, min(ref, float(params[coord]))))
            continue
        if _has_pct(params, coord):
            v = _to_float(params.get(f'{coord}_pct'))
            if v is None or not (0 <= v <= 100):
                raw_val = params.get(f'{coord}_pct')
                return False, f'坐标 {coord}_pct 越界或非法: {raw_val}'
            params[coord] = int(round(v / 100.0 * ref))
            continue
        # 交互动作的坐标会在 locate.py 阶段补齐；这里不报错，留给后续校验
    return True, ''


def normalize_action(action, width, height):
    """校验并归一化模型输出的动作。

    返回 (ok, normalized_action, error_msg)。normalized_action 是浅拷贝，
    带 action 类型、默认参数与像素坐标（locate 字段保留给 locate.py 处理）。
    """
    raw = dict(action or {})
    action_type = str(raw.get('action', '')).strip().lower()
    if not action_type:
        return False, {}, '动作类型为空'
    if action_type == 'click':
        action_type = 'tap'
    if action_type not in ACTION_WHITELIST:
        return False, {}, f'动作类型 {action_type!r} 不在白名单: {sorted(ACTION_WHITELIST)}'

    params = dict(raw.get('param', raw))
    params['action'] = action_type

    if action_type in ('tap', 'long_press'):
        if action_type == 'long_press':
            params.setdefault('duration', 2000)
        # 坐标缺失会在 locate 阶段补齐；这里先做 pct->px
        ok, err = fill_pixel_coords(params, width, height)
        if not ok:
            return False, {}, err
    elif action_type == 'swipe':
        params.setdefault('duration', 300)
        ok, err = fill_pixel_coords(params, width, height)
        if not ok:
            return False, {}, err
        has_locate = bool(params.get('locate_start') or params.get('locate_end'))
        has_coords = all(
            _has_px(params, c) or _has_pct(params, c)
            for pair in _COORD_PAIRS['swipe'] for c in pair
        )
        if not (has_locate or has_coords):
            return False, {}, 'swipe 缺少坐标或 locate_start/locate_end 描述'
    elif action_type == 'input':
        if 'text' not in params or params.get('text') is None:
            return False, {}, 'input 缺少 text'
        ok, err = fill_pixel_coords(params, width, height)
        if not ok:
            return False, {}, err
    elif action_type == 'wait':
        try:
            dur = float(params.get('duration', 3) or 3)
        except (TypeError, ValueError):
            dur = 3
        # 单次 wait 上限 10 秒，防止模型输出超长等待把执行拖死
        params['duration'] = min(max(dur, 0.5), 10)
    elif action_type == 'assert':
        params.setdefault('passed', True)
        if not params.get('description'):
            params['description'] = str(params.get('reasoning', '')) or '断言'
    elif action_type == 'query':
        if not params.get('description'):
            params['description'] = str(params.get('reasoning', '')) or '提取信息'

    return True, params, ''


def locate_fields_for(action):
    """返回该动作需要的 locate 字段描述列表。

    每个元素 (locate_key, (coord1, coord2))，供 locate.py 依次定位。
    """
    return _LOCATE_FIELDS.get(action.get('action'), ())


def has_direct_coords(action):
    """是否已有可直接执行的全部坐标（像素或百分比）。"""
    pairs = _COORD_PAIRS.get(action.get('action'))
    if not pairs:
        return True
    return all(
        _has_px(action, c) or _has_pct(action, c)
        for pair in pairs for c in pair
    )


def action_fingerprint(action):
    """动作指纹：覆盖 swipe 四坐标与 input 文本，用于卡死判定。"""
    t = action.get('action', '')
    parts = [t]
    for coord in ('x', 'y', 'x1', 'y1', 'x2', 'y2'):
        if action.get(coord) is not None:
            parts.append(f'{coord}={action[coord]}')
    if t == 'input':
        parts.append(f'text={action.get("text", "")}')
    return '|'.join(parts)
