# -*- coding: utf-8 -*-
"""动作执行 + 效果验证（页面 hash 对比）+ tap 重试。

复用 midscene_runner 的底层原语（adb_execute / adb_screenshot /
IOSDevice.execute_action / _is_same_page），不依赖其循环逻辑。
卡死判定在 engine 里基于本模块返回的 page_changed 与动作指纹完成。
"""

import time
import logging

logger = logging.getLogger(__name__)


def _is_same_page(png1, png2):
    from ..midscene_runner import _is_same_page as _impl
    return _impl(png1, png2)


def screenshot(device_ctx):
    """按平台截图，返回 PNG 字节。"""
    ios_dev = device_ctx.get('ios_dev')
    if ios_dev is not None:
        return ios_dev.screenshot()
    from ..midscene_runner import adb_screenshot
    return adb_screenshot(device_ctx['device_id'])


def _execute_raw(device_ctx, action):
    """执行单个底层动作。"""
    ios_dev = device_ctx.get('ios_dev')
    if ios_dev is not None:
        ios_dev.execute_action(action)
        return
    from ..midscene_runner import adb_execute
    adb_execute(device_ctx['device_id'], action)


def _tap(device_ctx, x, y):
    ios_dev = device_ctx.get('ios_dev')
    if ios_dev is not None:
        ios_dev.tap(x, y)
    else:
        from ..midscene_runner import adb_execute as _adb_execute
        _adb_execute(device_ctx['device_id'], {'action': 'tap', 'x': x, 'y': y})


def _sleep(action_type, action_delay):
    """按动作类型等待页面稳定：swipe 动画更长，普通动作按配置间隔。"""
    if action_type == 'swipe':
        time.sleep(max(action_delay or 0, 1.5))
    elif action_type in ('input', 'back', 'home', 'long_press', 'tap'):
        time.sleep(max(action_delay or 0, 0.3))
    elif action_type in ('assert', 'query'):
        time.sleep(0.1)


def execute_with_before(device_ctx, action, before_png, action_delay=0.5):
    """执行归一化后的动作，返回 (after_png, info)。

    info: {'page_changed': bool|None, 'note': str, 'retried': bool}
    - tap：页面未变会原地重试一次；
    - input：若带坐标（locate 结果）先点击输入框聚焦再输入；
    - assert/query/wait：不触碰设备（wait 仅等待）。
    """
    action_type = action.get('action', '')

    if action_type == 'wait':
        time.sleep(float(action.get('duration', 3) or 3))
        try:
            after_png = screenshot(device_ctx)
            return after_png, {
                'page_changed': not _is_same_page(before_png, after_png),
                'note': f'wait {action.get("duration", 3)}s',
                'retried': False,
            }
        except Exception:
            return before_png, {'page_changed': None, 'note': f'wait {action.get("duration", 3)}s', 'retried': False}

    if action_type == 'tap':
        return _tap_with_retry(device_ctx, action, before_png, action_delay)

    if action_type in ('assert', 'query'):
        return before_png, {'page_changed': None, 'note': '', 'retried': False}

    if action_type == 'input':
        # 有坐标（locate 结果）先点击输入框聚焦
        if action.get('x') is not None and action.get('y') is not None:
            _tap(device_ctx, action['x'], action['y'])
            time.sleep(max(action_delay or 0, 0.3))
        _execute_raw(device_ctx, action)
        _sleep('input', action_delay)
        after_png = screenshot(device_ctx)
        return after_png, {
            'page_changed': not _is_same_page(before_png, after_png),
            'note': '',
            'retried': False,
        }

    _execute_raw(device_ctx, action)
    _sleep(action_type, action_delay)
    after_png = screenshot(device_ctx)
    return after_png, {
        'page_changed': not _is_same_page(before_png, after_png),
        'note': '',
        'retried': False,
    }


def _tap_with_retry(device_ctx, action, before_png, action_delay):
    _tap(device_ctx, action['x'], action['y'])
    _sleep('tap', action_delay)
    after_png = screenshot(device_ctx)
    if not _is_same_page(before_png, after_png):
        return after_png, {'page_changed': True, 'note': '', 'retried': False}
    # 页面未变 -> 原地重试一次
    logger.info('[Executor] tap 页面未变，轮内重试')
    _tap(device_ctx, action['x'], action['y'])
    _sleep('tap', action_delay)
    after2 = screenshot(device_ctx)
    still_same = _is_same_page(before_png, after2)
    return after2, {
        'page_changed': not still_same,
        'note': 'tap 重试后页面仍未变化' if still_same else 'tap 重试后生效',
        'retried': True,
    }
