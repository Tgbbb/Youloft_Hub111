# -*- coding: utf-8 -*-
"""deepLocate 深度定位测试：区域解析/裁剪放大/off·auto·on 三档语义/配置优先级。"""
import io
import os
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from apps.ui_automation.midscene_ai import locate as locate_mod
from apps.ui_automation.midscene_ai.locate import (
    LocateError, _crop_and_resize, _parse_region_json, deep_locate_element,
    locate_element, resolve_action_coords,
)
from apps.ui_automation.models import MidsceneGlobalConfig

User = get_user_model()


def _make_png(width=400, height=800, color=(80, 120, 200)):
    img = Image.new('RGB', (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def _vlm(seq):
    """按调用顺序返回的 call_vlm_fn mock"""
    state = {'i': 0}
    def fn(*args, **kwargs):
        item = seq[min(state['i'], len(seq) - 1)]
        state['i'] += 1
        if isinstance(item, Exception):
            raise item
        return item
    fn.calls = state
    return fn


class RegionParseTests(TestCase):
    def test_valid_region(self):
        r = _parse_region_json('{"x_pct":10,"y_pct":20,"w_pct":50,"h_pct":30,"reasoning":"ok"}')
        self.assertEqual(r['x_pct'], 10)
        self.assertEqual(r['h_pct'], 30)

    def test_tolerant_json(self):
        r = _parse_region_json("{x_pct: 10, y_pct: 20, w_pct: 50, h_pct: 30}")
        self.assertIsNotNone(r)

    def test_out_of_range_rejected(self):
        self.assertIsNone(_parse_region_json('{"x_pct":120,"y_pct":20,"w_pct":50,"h_pct":30}'))
        self.assertIsNone(_parse_region_json('{"x_pct":10,"y_pct":20,"w_pct":0,"h_pct":30}'))

    def test_missing_field_rejected(self):
        self.assertIsNone(_parse_region_json('{"x_pct":10,"y_pct":20,"w_pct":50}'))


class CropResizeTests(TestCase):
    def test_crop_and_resize(self):
        png = _make_png(400, 800)
        region = {'x_pct': 25, 'y_pct': 25, 'w_pct': 50, 'h_pct': 50}
        crop, src, wh = _crop_and_resize(png, region, 400, 800)
        self.assertEqual(src, {'x': 100, 'y': 200, 'w': 200, 'h': 400})
        self.assertEqual(wh, (200, 400))  # 最长边 400 < 1024，不缩放
        img = Image.open(io.BytesIO(crop))
        self.assertEqual(img.size, (200, 400))

    def test_clamp_and_min_size(self):
        png = _make_png(200, 200)
        region = {'x_pct': 50, 'y_pct': 50, 'w_pct': 1, 'h_pct': 1}
        crop, src, wh = _crop_and_resize(png, region, 200, 200)
        # 1% = 2px，扩展到至少 64，然后 clamp 到图内
        self.assertGreaterEqual(src['w'], 60)
        self.assertGreaterEqual(src['h'], 60)
        self.assertGreaterEqual(src['x'], 0)
        self.assertLessEqual(src['x'] + src['w'], 200)


class ResolveActionCoordsTests(TestCase):
    def setUp(self):
        self.png = _make_png()
        self.width, self.height = 400, 800
        self.action = {'action': 'tap', 'locate': '测试按钮'}
        self.model = mock.Mock(api_key='k')

    def _resolve(self, seq, mode, **kw):
        return resolve_action_coords(
            dict(self.action), self.png, self.model, self.width, self.height,
            use_locate=True, call_vlm_fn=_vlm(seq), use_deep_locate=mode, **kw)

    def test_off_failure_no_deep_upgrade(self):
        ok, action, err, info = self._resolve(['bad', 'bad'], 'off')
        self.assertFalse(ok)
        self.assertNotIn('deep_locate', (info.get('locate') or {}))

    def test_auto_success_single_call(self):
        seq = ['{"x_pct":50,"y_pct":50,"reasoning":"ok"}']
        ok, action, err, info = self._resolve(seq, 'auto')
        self.assertTrue(ok)
        self.assertEqual((action['x'], action['y']), (200, 400))
        self.assertNotIn('deep_locate', (info.get('locate') or {}))

    def test_auto_upgrade_after_normal_fail(self):
        seq = [
            'bad', 'bad',  # normal 第1次 + 重试
            '{"x_pct":25,"y_pct":25,"w_pct":50,"h_pct":50,"reasoning":"ok"}',  # 区域
            '{"x_pct":50,"y_pct":50,"reasoning":"ok"}',  # 裁剪图中心
        ]
        ok, action, err, info = self._resolve(seq, 'auto')
        self.assertTrue(ok)
        # 区域 (100,200,200,400) 中心 (200,400) -> 原图 50%,50%
        self.assertEqual((action['x'], action['y']), (200, 400))
        loc = info['locate']
        self.assertEqual(loc['retries'], 1)
        self.assertIn('deep_locate', loc)
        self.assertEqual(loc['deep_locate']['source_rect'], {'x': 100, 'y': 200, 'w': 200, 'h': 400})

    def test_auto_all_fail_falls_back(self):
        seq = ['bad', 'bad', 'bad_region', 'bad_crop']
        ok, action, err, info = self._resolve(seq, 'auto')
        self.assertFalse(ok)

    def test_on_direct_deep_locate(self):
        seq = [
            '{"x_pct":25,"y_pct":25,"w_pct":50,"h_pct":50,"reasoning":"ok"}',
            '{"x_pct":50,"y_pct":50,"reasoning":"ok"}',
        ]
        ok, action, err, info = self._resolve(seq, 'on')
        self.assertTrue(ok)
        self.assertEqual((action['x'], action['y']), (200, 400))
        self.assertIn('deep_locate', info['locate'])

    def test_on_deep_fail_fallback_normal(self):
        seq = [
            'bad_region',  # deep 区域失败
            'bad',         # normal 第1次失败
            '{"x_pct":50,"y_pct":50,"reasoning":"ok"}',  # normal 重试成功
        ]
        ok, action, err, info = self._resolve(seq, 'on')
        self.assertTrue(ok)
        self.assertEqual((action['x'], action['y']), (200, 400))
        self.assertNotIn('deep_locate', (info.get('locate') or {}))

    def test_on_deep_and_normal_fail(self):
        seq = ['bad_region', 'bad', 'bad']
        ok, action, err, info = self._resolve(seq, 'on')
        self.assertFalse(ok)

    def test_deep_locate_region_parse_failure_raises(self):
        with self.assertRaises(LocateError):
            deep_locate_element('x', self.png, self.model, self.width, self.height,
                                call_vlm_fn=_vlm(['bad']))

    def test_locate_element_raises_without_direct_coords(self):
        with self.assertRaises(LocateError):
            locate_element('x', self.png, self.model, self.width, self.height,
                           call_vlm_fn=_vlm(['bad', 'bad']))


class GlobalConfigTests(TestCase):
    def setUp(self):
        MidsceneGlobalConfig.objects.all().delete()
        self.user = User.objects.create_user(username='cfg-user', password='pass')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_get_defaults(self):
        resp = self.client.get('/api/ui-automation/midscene/config/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(resp.data['config']['use_locate'])
        self.assertEqual(resp.data['config']['use_deep_locate'], '')
        self.assertEqual(resp.data['effective']['use_deep_locate'], 'auto')
        self.assertTrue(resp.data['effective']['use_locate'])

    def test_put_and_effective(self):
        resp = self.client.put('/api/ui-automation/midscene/config/',
                               {'use_locate': True, 'use_deep_locate': 'on'},
                               format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['config']['use_locate'])
        self.assertEqual(resp.data['config']['use_deep_locate'], 'on')
        self.assertEqual(resp.data['effective']['use_deep_locate'], 'on')

    def test_put_invalid_rejected(self):
        resp = self.client.put('/api/ui-automation/midscene/config/',
                               {'use_deep_locate': 'banana'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_put_null_resets(self):
        self.client.put('/api/ui-automation/midscene/config/',
                        {'use_locate': True, 'use_deep_locate': 'on'}, format='json')
        resp = self.client.put('/api/ui-automation/midscene/config/',
                               {'use_locate': None, 'use_deep_locate': ''}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(resp.data['config']['use_locate'])
        self.assertEqual(resp.data['config']['use_deep_locate'], '')


class SwitchResolutionTests(TestCase):
    """resolve_locate_switches 优先级：实例参数 > DB > 环境变量 > 默认。"""

    def setUp(self):
        MidsceneGlobalConfig.objects.all().delete()

    def _pop_env(self, name):
        old = os.environ.pop(name, None)
        self.addCleanup(lambda: os.environ.pop(name, None))
        if old is not None:
            self.addCleanup(lambda: os.environ.__setitem__(name, old))

    def test_defaults(self):
        self._pop_env('AIACT_USE_LOCATE')
        self._pop_env('AIACT_USE_DEEP_LOCATE')
        from apps.ui_automation.midscene_ai.engine import resolve_locate_switches
        locate, deep = resolve_locate_switches()
        self.assertIs(locate, True)
        self.assertEqual(deep, 'auto')

    def test_env_fallback(self):
        self._pop_env('AIACT_USE_DEEP_LOCATE')
        os.environ['AIACT_USE_DEEP_LOCATE'] = 'off'
        os.environ['AIACT_USE_LOCATE'] = '0'
        from apps.ui_automation.midscene_ai.engine import resolve_locate_switches
        locate, deep = resolve_locate_switches()
        self.assertIs(locate, False)
        self.assertEqual(deep, 'off')

    def test_db_overrides_env(self):
        self._pop_env('AIACT_USE_DEEP_LOCATE')
        os.environ['AIACT_USE_DEEP_LOCATE'] = 'off'
        cfg = MidsceneGlobalConfig.get_singleton()
        cfg.use_locate = False
        cfg.use_deep_locate = 'on'
        cfg.save()
        from apps.ui_automation.midscene_ai.engine import resolve_locate_switches
        locate, deep = resolve_locate_switches()
        self.assertIs(locate, False)
        self.assertEqual(deep, 'on')

    def test_instance_param_wins(self):
        MidsceneGlobalConfig.get_singleton().use_deep_locate = 'off'
        MidsceneGlobalConfig.get_singleton().save()
        from apps.ui_automation.midscene_ai.engine import resolve_locate_switches
        _, deep = resolve_locate_switches(use_deep_locate='on')
        self.assertEqual(deep, 'on')
