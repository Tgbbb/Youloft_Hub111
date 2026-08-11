# -*- coding: utf-8 -*-
"""回放坐标解析测试：百分比优先、旧像素兜底、10x 百分比兼容。"""
from unittest import mock

from django.test import SimpleTestCase

from apps.ui_automation import midscene_runner


class CoordResolveTests(SimpleTestCase):
    """_resolve_coord 坐标解析。"""

    def test_prefer_pct(self):
        a = {'x_pct': 50, 'y_pct': 50, 'x': 100, 'y': 200}
        self.assertEqual(midscene_runner._resolve_coord(a, 'x', 1080), 540)
        self.assertEqual(midscene_runner._resolve_coord(a, 'y', 2160), 1080)

    def test_legacy_10x_pct(self):
        # 旧模型 10x 格式：600 = 60%
        a = {'x_pct': 600, 'x': 100}
        self.assertEqual(midscene_runner._resolve_coord(a, 'x', 1080), 648)

    def test_fallback_to_pixel_when_pct_missing(self):
        a = {'x': 300, 'y': 400}
        self.assertEqual(midscene_runner._resolve_coord(a, 'x', 1080), 300)
        self.assertEqual(midscene_runner._resolve_coord(a, 'y', 2160), 400)

    def test_pct_zero_falls_back_to_pixel(self):
        a = {'x_pct': 0, 'x': 300}
        self.assertEqual(midscene_runner._resolve_coord(a, 'x', 1080), 300)

    def test_invalid_values(self):
        self.assertEqual(midscene_runner._resolve_coord({}, 'x', 1080), 0)
        a = {'x_pct': 'abc', 'x': 100}
        self.assertEqual(midscene_runner._resolve_coord(a, 'x', 1080), 100)


class NormalizePctTests(SimpleTestCase):
    """录制时百分比归一化。"""

    def test_normalize(self):
        self.assertEqual(midscene_runner._normalize_pct(50), 50)
        self.assertEqual(midscene_runner._normalize_pct(600), 60)
        self.assertEqual(midscene_runner._normalize_pct('50'), 50)
        self.assertIsNone(midscene_runner._normalize_pct(None))
        self.assertIsNone(midscene_runner._normalize_pct('abc'))


class ReplayActionsTests(SimpleTestCase):
    """_replay_actions 实际发出的坐标。"""

    def setUp(self):
        self.calls = []
        self.sleep = mock.patch('time.sleep', return_value=None)
        self.sleep.start()
        patcher = mock.patch.object(
            midscene_runner, '_adb',
            side_effect=lambda *args, **kw: self.calls.append(args),
        )
        patcher.start()
        self.addCleanup(self.sleep.stop)
        self.addCleanup(patcher.stop)

    def test_tap_prefers_pct_for_other_resolution(self):
        # 录制于 1080x2160，回放于 720x1600：优先百分比换算，避免像素点偏
        midscene_runner._replay_actions('dev', None, [
            {'action': 'tap', 'x_pct': 50, 'y_pct': 50, 'x': 540, 'y': 1080},
        ], 720, 1600)
        tap = [c for c in self.calls if 'tap' in c]
        self.assertTrue(tap)
        self.assertEqual(tap[0][-2:], ('360', '800'))

    def test_tap_falls_back_to_pixel(self):
        midscene_runner._replay_actions('dev', None, [
            {'action': 'tap', 'x': 300, 'y': 400},
        ], 720, 1600)
        tap = [c for c in self.calls if 'tap' in c]
        self.assertEqual(tap[0][-2:], ('300', '400'))

    def test_swipe_resolves_pct(self):
        midscene_runner._replay_actions('dev', None, [
            {'action': 'swipe',
             'x1_pct': 10, 'y1_pct': 80, 'x2_pct': 90, 'y2_pct': 20,
             'x1': 108, 'y1': 1728, 'x2': 972, 'y2': 432},
        ], 1080, 2160)
        swipe = [c for c in self.calls if 'swipe' in c]
        self.assertTrue(swipe)
        args = swipe[0]
        # _adb(device_id, 'shell', 'input', 'swipe', x1, y1, x2, y2, duration)
        self.assertEqual(args[-5], '108')
        self.assertEqual(args[-4], '1728')
        self.assertEqual(args[-3], '972')
        self.assertEqual(args[-2], '432')
