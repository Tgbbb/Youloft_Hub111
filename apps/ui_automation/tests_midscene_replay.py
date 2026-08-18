# -*- coding: utf-8 -*-
"""回放坐标解析与动作级门控测试：百分比优先、旧像素兜底、10x 百分比兼容、障碍动作条件化。"""
import io
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from PIL import Image
from rest_framework.test import APIClient

from apps.projects.models import Project
from apps.ui_automation import midscene_runner
from apps.ui_automation.models import MidsceneProject, MidsceneCase, MidsceneDevice


User = get_user_model()


def _make_png(seed=1):
    """固定种子的随机图（phash 非 0），供截图 mock 使用。"""
    import random
    rnd = random.Random(seed)
    img = Image.new('L', (64, 64))
    img.putdata([rnd.randint(0, 255) for _ in range(64 * 64)])
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


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


class ClampWaitAfterTests(SimpleTestCase):
    """录制实测 wait_after 的兜底下限。"""

    def test_floor_enforced(self):
        self.assertEqual(midscene_runner._clamp_wait_after(0.05), 0.2)

    def test_round_to_2_decimals(self):
        self.assertEqual(midscene_runner._clamp_wait_after(1.234), 1.23)

    def test_invalid_values_fall_back_to_floor(self):
        self.assertEqual(midscene_runner._clamp_wait_after(None), 0.2)
        self.assertEqual(midscene_runner._clamp_wait_after('abc'), 0.2)

    def test_ceil_enforced(self):
        # 录制实测值含 VLM 思考时间，入库不得超过上限，避免回放被原样重放
        self.assertEqual(midscene_runner._clamp_wait_after(60), 5.0)
        self.assertEqual(midscene_runner._clamp_wait_after(6.7), 5.0)
        self.assertEqual(midscene_runner._clamp_wait_after(0.05), 0.2)


class InstructionSimilarTests(SimpleTestCase):
    """步骤文案宽松匹配：归一化标点/空白、容忍插入词、防误配。"""

    def test_exact_after_normalize(self):
        self.assertTrue(midscene_runner._instruction_similar('点击同意并继续', '点击同意并继续'))
        self.assertTrue(midscene_runner._instruction_similar('点击 同意 并 继续', '点击同意并继续'))
        self.assertTrue(midscene_runner._instruction_similar('点击“同意并继续”', '点击同意并继续'))
        self.assertTrue(midscene_runner._instruction_similar('点击，同意并继续。', '点击同意并继续'))

    def test_middle_word_drift(self):
        self.assertTrue(midscene_runner._instruction_similar(
            '如果展示会员购买页，就点击左上角关闭', '如果展示会员购买页点击左上角关闭'))
        self.assertTrue(midscene_runner._instruction_similar(
            '点击同意并继续', '请点击同意并继续'))

    def test_distinct_steps_not_matched(self):
        # 长度悬殊（“点击同意” vs “点击同意并继续”）不能误配
        self.assertFalse(midscene_runner._instruction_similar('点击同意', '点击同意并继续'))
        self.assertFalse(midscene_runner._instruction_similar('点击找回账号', '点击登录'))

    def test_empty_not_matched(self):
        self.assertFalse(midscene_runner._instruction_similar('', '点击同意并继续'))
        self.assertFalse(midscene_runner._instruction_similar('点击同意并继续', None))


class WaitScreenStableTests(SimpleTestCase):
    """启动首帧稳定等待：连续两帧相同提前返回，持续变化则超时。"""

    def setUp(self):
        self.sleep = mock.patch('time.sleep', return_value=None)
        self.sleep.start()
        self.addCleanup(self.sleep.stop)

    def _img_png(self, seed):
        import random
        rnd = random.Random(seed)
        img = Image.new('L', (64, 64))
        img.putdata([rnd.randint(0, 255) for _ in range(64 * 64)])
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()

    def test_stable_detected(self):
        png = self._img_png(1)
        with mock.patch.object(midscene_runner, 'adb_screenshot', return_value=png):
            ok = midscene_runner._wait_screen_stable('dev', None, timeout=5)
        self.assertTrue(ok)

    def test_timeout_returns_false(self):
        frames = [self._img_png(i) for i in (1, 2, 3, 4)]
        state = {'i': 0}
        def shot(*_args):
            frame = frames[state['i'] % len(frames)]
            state['i'] += 1
            return frame
        with mock.patch.object(midscene_runner, 'adb_screenshot', side_effect=shot):
            ok = midscene_runner._wait_screen_stable('dev', None, timeout=0.1)
        self.assertFalse(ok)


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
        self.shot = mock.patch.object(
            midscene_runner, 'adb_screenshot', return_value=_make_png(1),
        )
        self.shot.start()
        self.addCleanup(self.shot.stop)

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


class BuildActionRecTests(SimpleTestCase):
    """录制条目构造：before_hash / conditional / pct 归一化。"""

    def _img_png(self, seed):
        import random
        rnd = random.Random(seed)
        img = Image.new('L', (64, 64))
        img.putdata([rnd.randint(0, 255) for _ in range(64 * 64)])
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()

    def test_rec_fields_and_before_hash(self):
        png = self._img_png(1)
        rec = midscene_runner._build_action_rec(
            {'action': 'tap', 'x_pct': 600, 'y_pct': 50, 'x': 648, 'y': 1080,
             'text': '', 'step_status': 'in_progress'},
            png,
        )
        self.assertEqual(rec['action'], 'tap')
        self.assertEqual(rec['x_pct'], 60)  # 10x 归一化
        self.assertEqual(rec['y_pct'], 50)
        self.assertEqual(rec['x'], 648)
        self.assertTrue(rec['conditional'])
        self.assertEqual(rec['before_hash'], str(midscene_runner._phash(png)))

    def test_done_is_not_conditional(self):
        rec = midscene_runner._build_action_rec(
            {'action': 'tap', 'x_pct': 50, 'y_pct': 50, 'step_status': 'done'},
            self._img_png(2),
        )
        self.assertFalse(rec['conditional'])

    def test_missing_step_status_defaults_to_done(self):
        rec = midscene_runner._build_action_rec(
            {'action': 'tap', 'x_pct': 50, 'y_pct': 50},
            self._img_png(3),
        )
        self.assertFalse(rec['conditional'])

    def test_pure_color_hash_empty(self):
        buf = io.BytesIO()
        Image.new('L', (8, 8), 255).save(buf, format='PNG')
        rec = midscene_runner._build_action_rec(
            {'action': 'tap', 'x_pct': 50, 'y_pct': 50, 'step_status': 'in_progress'},
            buf.getvalue(),
        )
        self.assertEqual(rec['before_hash'], '')


class GatedReplayTests(SimpleTestCase):
    """_replay_actions 动作级门控。"""

    def setUp(self):
        self.calls = []
        self.sleep = mock.patch('time.sleep', return_value=None)
        self.sleep.start()
        self.adb = mock.patch.object(
            midscene_runner, '_adb',
            side_effect=lambda *args, **kw: self.calls.append(args),
        )
        self.adb.start()
        self.shot = mock.patch.object(midscene_runner, 'adb_screenshot', return_value=_make_png(1))
        self.shot.start()
        self.addCleanup(self.sleep.stop)
        self.addCleanup(self.adb.stop)
        self.addCleanup(self.shot.stop)

    def _patch_match(self, matching):
        patcher = mock.patch.object(
            midscene_runner, '_is_same_page_by_hash',
            side_effect=lambda png, expected: str(expected) in matching,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _tap_calls(self):
        return [c for c in self.calls if 'tap' in c]

    def _action(self, x_pct, y_pct, before_hash='', conditional=False):
        return {'action': 'tap', 'x_pct': x_pct, 'y_pct': y_pct,
                'x': 0, 'y': 0, 'before_hash': before_hash,
                'conditional': conditional}

    def test_obstacle_skipped_target_played(self):
        # 43 号用例场景：权限弹窗不在 → 障碍动作跳过，目标动作照播
        self._patch_match({'H_TARGET'})
        actions = [
            self._action(50, 56, before_hash='H_POPUP', conditional=True),
            self._action(50, 62, before_hash='H_TARGET', conditional=False),
        ]
        stats = midscene_runner._replay_actions('dev', None, actions, 1080, 2160)
        self.assertEqual(stats, {'played': 1, 'skipped': 1})
        taps = self._tap_calls()
        self.assertEqual(len(taps), 1)
        self.assertEqual(taps[0][-2:], ('540', '1339'))  # round(62% * 2160)

    def test_obstacle_played_when_page_matches(self):
        # 权限弹窗在 → 障碍动作与目标动作都播
        self._patch_match({'H_POPUP', 'H_TARGET'})
        actions = [
            self._action(50, 56, before_hash='H_POPUP', conditional=True),
            self._action(50, 62, before_hash='H_TARGET', conditional=False),
        ]
        stats = midscene_runner._replay_actions('dev', None, actions, 1080, 2160)
        self.assertEqual(stats, {'played': 2, 'skipped': 0})
        self.assertEqual(len(self._tap_calls()), 2)

    def test_target_unconditional_even_with_hash(self):
        # 普通步骤目标动作：即使前置指纹不匹配也执行
        self._patch_match(set())
        actions = [self._action(50, 50, before_hash='H_X', conditional=False)]
        stats = midscene_runner._replay_actions('dev', None, actions, 1080, 2160)
        self.assertEqual(stats, {'played': 1, 'skipped': 0})
        self.assertEqual(len(self._tap_calls()), 1)

    def test_gate_all_gates_target_action(self):
        # 条件步骤（gate_all=True）：目标动作也按指纹门控
        self._patch_match(set())
        actions = [self._action(50, 50, before_hash='H_X', conditional=False)]
        stats = midscene_runner._replay_actions('dev', None, actions, 1080, 2160,
                                                gate_all=True)
        self.assertEqual(stats, {'played': 0, 'skipped': 1})
        self.assertEqual(self._tap_calls(), [])

    def test_old_format_unconditional(self):
        # 旧数据：无 before_hash/conditional → 无条件执行
        actions = [{'action': 'tap', 'x_pct': 50, 'y_pct': 50, 'x': 0, 'y': 0}]
        stats = midscene_runner._replay_actions('dev', None, actions, 1080, 2160)
        self.assertEqual(stats, {'played': 1, 'skipped': 0})
        self.assertEqual(len(self._tap_calls()), 1)

    def test_empty_before_hash_no_gate(self):
        # before_hash 为空（纯色页）→ 不加门控，无条件执行
        self._patch_match(set())
        actions = [self._action(50, 50, before_hash='', conditional=True)]
        stats = midscene_runner._replay_actions('dev', None, actions, 1080, 2160)
        self.assertEqual(stats, {'played': 1, 'skipped': 0})
        self.assertEqual(len(self._tap_calls()), 1)


class ConditionalNextCondReplayTests(TestCase):
    """条件步骤判定模型：
    1) 快速路径 → act_before_hash 指纹命中，播放录制动作（after_hash 仅记日志，加载帧会失真）；
    2) 主路径 → 指纹未命中（如录制到加载帧）走元素级 VLM 确认，存在→播放，稳定不存在→跳过；
    3) 兜底 → 确认失败/无法判定，降级 VLM 看图判断，不盲目跳过。
    对应 41/43 号用例：'如果展示会员购买页…' 后跟 '如果展示会员挽留弹窗…'。"""

    def setUp(self):
        self.sleep = mock.patch('time.sleep', return_value=None)
        self.sleep.start()
        self.addCleanup(self.sleep.stop)
        self.adb = mock.patch.object(midscene_runner, '_adb', return_value=mock.Mock(returncode=0))
        self.adb_mock = self.adb.start()
        self.addCleanup(self.adb.stop)
        self.size = mock.patch.object(midscene_runner, 'adb_get_screen_size', return_value=(1080, 2160))
        self.size.start()
        self.addCleanup(self.size.stop)
        self.shot = mock.patch.object(
            midscene_runner, 'adb_screenshot', return_value=_make_png(1),
        )
        self.shot.start()
        self.addCleanup(self.shot.stop)
        self.save = mock.patch.object(
            midscene_runner, 'save_screenshot',
            return_value='/media/midscene/1/step_1.png',
        )
        self.save.start()
        self.addCleanup(self.save.stop)
        self.vlm = mock.patch.object(
            midscene_runner, 'call_vlm',
            return_value={'action': 'done', 'reasoning': 'x'},
        )
        self.vlm_mock = self.vlm.start()
        self.addCleanup(self.vlm.stop)

    def _img_png(self, seed):
        import random
        rnd = random.Random(seed)
        img = Image.new('L', (64, 64))
        img.putdata([rnd.randint(0, 255) for _ in range(64 * 64)])
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()

    def _make_context(self, steps=None):
        mc = mock.Mock()
        mc.ai_act_context = ''
        mc.app_package = ''
        mc.project = mock.Mock(default_app_package='')
        mc.use_locate = True
        mc.max_steps = 30
        mc.action_delay = 0.5
        mc.replay_data = [{
            'steps': steps if steps is not None else [
                {
                    'instruction': '如果展示会员购买页，就点击左上角关闭',
                    'actions': [{'action': 'tap', 'x_pct': 10, 'y_pct': 10, 'x': 108, 'y': 216}],
                    'after_hash': 'H1_AFTER',
                    'act_before_hash': 'H1_ACT',
                },
                {
                    'instruction': '如果展示会员挽留弹窗返回按钮为下次一定，点击下次一定',
                    'actions': [],
                    'after_hash': 'H2_SKIP',
                },
            ],
        }]
        execution = mock.Mock()
        execution.id = 1
        execution.midscene_case = mc
        execution.auto_plan = False
        execution.status = 'running'
        device = mock.Mock()
        device.platform = 'android'
        device.adb_serial = 'dev'
        device.name = '设备'
        model = mock.Mock()
        model.api_key = 'k'
        return mc, execution, device, model

    def _run(self, steps, ai_prompt, hash_match, vlm_side_effect=None, shot_pngs=None,
             progress_callback=None):
        if shot_pngs is None:
            pngs = [self._img_png(1)] * 4
        else:
            pngs = shot_pngs
        state = {'i': 0}
        def shot(*_args):
            frame = pngs[state['i'] % len(pngs)]
            state['i'] += 1
            return frame
        midscene_runner.adb_screenshot.side_effect = shot
        if vlm_side_effect is not None:
            self.vlm_mock.side_effect = vlm_side_effect
        with mock.patch.object(midscene_runner, '_is_same_page_by_hash', side_effect=hash_match):
            _, execution, device, model = self._make_context(steps)
            return midscene_runner.run_midscene_test(
                ai_prompt=ai_prompt, device=device, model_config=model,
                execution_record=execution, replay_mode=True, replay_index=0,
                progress_callback=progress_callback,
            )

    def test_act_hash_match_plays_and_passes(self):
        # 条件满足：act_before_hash 匹配 → 播放动作 → after_hash 匹配 → 通过，不调 VLM
        steps = [{
            'instruction': '如果展示会员购买页，就点击左上角关闭',
            'actions': [{'action': 'tap', 'x_pct': 10, 'y_pct': 10, 'x': 108, 'y': 216}],
            'after_hash': 'H_AFTER',
            'act_before_hash': 'H_ACT',
        }]
        result = self._run(steps, '如果展示会员购买页，就点击左上角关闭',
                           lambda _png, expected: expected in ('H_ACT', 'H_AFTER'))
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['steps'][0]['status'], 'passed')
        self.adb_mock.assert_any_call('dev', 'shell', 'input', 'tap', '108', '216')
        self.vlm_mock.assert_not_called()

    def test_after_hash_mismatch_passes_with_warning(self):
        # 快速路径播放后 after_hash 不符（加载帧失真）→ 仅记日志，按通过处理，不重复播放/不降级
        steps = [{
            'instruction': '如果展示会员购买页，就点击左上角关闭',
            'actions': [{'action': 'tap', 'x_pct': 10, 'y_pct': 10, 'x': 108, 'y': 216}],
            'after_hash': 'H_AFTER',
            'act_before_hash': 'H_ACT',
        }]
        result = self._run(steps, '如果展示会员购买页，就点击左上角关闭',
                           lambda _png, expected: expected == 'H_ACT')
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['steps'][0]['status'], 'passed')
        self.adb_mock.assert_any_call('dev', 'shell', 'input', 'tap', '108', '216')
        self.vlm_mock.assert_not_called()

    def test_act_hash_mismatch_element_absent_skips(self):
        # 指纹未命中 → 元素级确认：页面稳定且目标不存在 → 条件不满足跳过，不播放动作
        steps = [{
            'instruction': '如果展示会员挽留弹窗返回按钮为下次一定，点击下次一定',
            'actions': [{'action': 'tap', 'x_pct': 50, 'y_pct': 76, 'x': 540, 'y': 1641}],
            'after_hash': 'H_AFTER',
            'act_before_hash': 'H_ACT',
        }]
        frame = self._img_png(9)
        result = self._run(steps, '如果展示会员挽留弹窗返回按钮为下次一定，点击下次一定',
                           lambda _png, expected: False,
                           vlm_side_effect=['{"present": false, "reasoning": "未出现目标"}'] * 3,
                           shot_pngs=[frame])
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['steps'][0]['status'], 'passed')
        self.adb_mock.assert_not_called()
        self.assertEqual(self.vlm_mock.call_count, 2)

    def test_no_actions_after_hash_match_skips_without_vlm(self):
        # 录制时条件不满足(无动作)：当前页匹配"跳过"指纹 → 跳过通过，不调 VLM
        steps = [{
            'instruction': '如果展示会员挽留弹窗返回按钮为下次一定，点击下次一定',
            'actions': [],
            'after_hash': 'H_SKIP',
        }]
        result = self._run(steps, '如果展示会员挽留弹窗返回按钮为下次一定，点击下次一定',
                           lambda _png, expected: expected == 'H_SKIP')
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['steps'][0]['status'], 'passed')
        self.vlm_mock.assert_not_called()

    def test_no_actions_after_hash_mismatch_falls_back_to_vlm(self):
        # 无动作但当前页不是"跳过"指纹 → 未知（可能条件满足或路径不同），降级 VLM
        steps = [{
            'instruction': '如果展示会员购买页，就点击左上角关闭',
            'actions': [],
            'after_hash': 'H_SKIP',
        }]
        result = self._run(steps, '如果展示会员购买页，就点击左上角关闭',
                           lambda _png, expected: False)
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['steps'][0]['status'], 'passed')
        self.vlm_mock.assert_called_once()

    def test_missing_act_hash_element_present_plays(self):
        # 缺 act_before_hash（旧数据）→ 元素级确认：目标存在 → 播放录制动作
        steps = [{
            'instruction': '如果展示会员购买页，就点击左上角关闭',
            'actions': [{'action': 'tap', 'x_pct': 10, 'y_pct': 10, 'x': 108, 'y': 216}],
            'after_hash': 'H_AFTER',
        }]
        result = self._run(steps, '如果展示会员购买页，就点击左上角关闭',
                           lambda _png, expected: False,
                           vlm_side_effect=['{"present": true, "reasoning": "购买页左上角关闭按钮存在"}'])
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['steps'][0]['status'], 'passed')
        self.adb_mock.assert_any_call('dev', 'shell', 'input', 'tap', '108', '216')
        self.vlm_mock.assert_called_once()

    def test_element_absent_loading_then_present_plays(self):
        # 第一次问还在加载中(present=false 且页面在变) → 等重试后页面加载完成，目标出现 → 播放动作
        steps = [{
            'instruction': '如果展示会员购买页，就点击左上角关闭',
            'actions': [{'action': 'tap', 'x_pct': 10, 'y_pct': 10, 'x': 108, 'y': 216}],
            'after_hash': 'H_AFTER',
            'act_before_hash': 'H_ACT',
        }]
        result = self._run(steps, '如果展示会员购买页，就点击左上角关闭',
                           lambda _png, expected: False,
                           vlm_side_effect=[
                               '{"present": false, "reasoning": "页面空白，加载中"}',
                               '{"present": true, "reasoning": "加载完成，关闭按钮出现"}',
                           ],
                           shot_pngs=[self._img_png(11), self._img_png(12)])
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['steps'][0]['status'], 'passed')
        self.adb_mock.assert_any_call('dev', 'shell', 'input', 'tap', '108', '216')
        self.assertEqual(self.vlm_mock.call_count, 2)

    def test_condition_confirm_error_falls_back_to_vlm(self):
        # 元素确认调用失败 → 兜底降级 VLM 看图执行
        steps = [{
            'instruction': '如果展示会员购买页，就点击左上角关闭',
            'actions': [{'action': 'tap', 'x_pct': 10, 'y_pct': 10, 'x': 108, 'y': 216}],
            'after_hash': 'H_AFTER',
            'act_before_hash': 'H_ACT',
        }]
        result = self._run(steps, '如果展示会员购买页，就点击左上角关闭',
                           lambda _png, expected: False,
                           vlm_side_effect=[RuntimeError('vlm down'), {'action': 'done', 'reasoning': 'x'}])
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['steps'][0]['status'], 'passed')
        self.adb_mock.assert_not_called()
        self.assertEqual(self.vlm_mock.call_count, 2)

    def test_element_absent_page_changing_exhausts_retries_falls_back_to_vlm(self):
        # 页面一直变化(加载中)且目标始终未出现 → 重试耗尽无法判定，兜底降级 VLM
        steps = [{
            'instruction': '如果展示会员购买页，就点击左上角关闭',
            'actions': [{'action': 'tap', 'x_pct': 10, 'y_pct': 10, 'x': 108, 'y': 216}],
            'after_hash': 'H_AFTER',
            'act_before_hash': 'H_ACT',
        }]
        result = self._run(steps, '如果展示会员购买页，就点击左上角关闭',
                           lambda _png, expected: False,
                           vlm_side_effect=[
                               '{"present": false, "reasoning": "加载中"}',
                               '{"present": false, "reasoning": "加载中"}',
                               {'action': 'done', 'reasoning': 'x'},
                           ],
                           shot_pngs=[self._img_png(21), self._img_png(22)])
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['steps'][0]['status'], 'passed')
        self.adb_mock.assert_not_called()
        self.assertEqual(self.vlm_mock.call_count, 3)

    def test_two_cond_steps_three_state(self):
        # 41/43 场景：步骤1 匹配播放并通过，步骤2 无动作匹配"跳过"指纹 → 跳过通过，全程不调 VLM
        result = self._run(
            None,
            '如果展示会员购买页，就点击左上角关闭\n'
            '如果展示会员挽留弹窗返回按钮为下次一定，点击下次一定',
            lambda _png, expected: expected in ('H1_ACT', 'H1_AFTER', 'H2_SKIP'),
        )
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(len(result['steps']), 2)
        self.assertTrue(all(s['status'] == 'passed' for s in result['steps']))
        self.adb_mock.assert_any_call('dev', 'shell', 'input', 'tap', '108', '216')
        self.vlm_mock.assert_not_called()

    def test_cond_fast_path_emits_progress_done(self):
        # 条件步骤快速路径要发 step_start/step_done，否则前端步骤明细在条件步骤处停滞
        steps = [{
            'instruction': '如果展示会员购买页，就点击左上角关闭',
            'actions': [{'action': 'tap', 'x_pct': 10, 'y_pct': 10, 'x': 108, 'y': 216}],
            'after_hash': 'H_AFTER',
            'act_before_hash': 'H_ACT',
        }]
        events = []
        result = self._run(steps, '如果展示会员购买页，就点击左上角关闭',
                           lambda _png, expected: expected in ('H_ACT', 'H_AFTER'),
                           progress_callback=lambda s, t, d: events.append((d.get('type'), s, d.get('status'))))
        self.assertEqual(result['status'], 'passed')
        self.assertIn(('step_start', 1, None), events)
        self.assertIn(('step_done', 1, 'passed'), events)

    def test_cond_skip_path_emits_progress_done(self):
        # 条件步骤跳过出口同样要发 step_done
        steps = [{
            'instruction': '如果展示会员挽留弹窗返回按钮为下次一定，点击下次一定',
            'actions': [],
            'after_hash': 'H_SKIP',
        }]
        events = []
        result = self._run(steps, '如果展示会员挽留弹窗返回按钮为下次一定，点击下次一定',
                           lambda _png, expected: expected == 'H_SKIP',
                           progress_callback=lambda s, t, d: events.append((d.get('type'), s, d.get('status'))))
        self.assertEqual(result['status'], 'passed')
        self.assertIn(('step_start', 1, None), events)
        self.assertIn(('step_done', 1, 'passed'), events)


class StopInterruptTests(TestCase):
    """用户停止：VLM 调用抛 ExecutionStopped 时立即中断，整轮结果标记 stopped。"""

    def setUp(self):
        self.sleep = mock.patch('time.sleep', return_value=None)
        self.sleep.start()
        self.addCleanup(self.sleep.stop)
        self.adb = mock.patch.object(midscene_runner, '_adb', return_value=mock.Mock(returncode=0))
        self.adb_mock = self.adb.start()
        self.addCleanup(self.adb.stop)
        self.size = mock.patch.object(midscene_runner, 'adb_get_screen_size', return_value=(1080, 2160))
        self.size.start()
        self.addCleanup(self.size.stop)
        self.shot = mock.patch.object(midscene_runner, 'adb_screenshot', return_value=_make_png(1))
        self.shot.start()
        self.addCleanup(self.shot.stop)
        self.save = mock.patch.object(
            midscene_runner, 'save_screenshot', return_value='/media/midscene/1/step_1.png',
        )
        self.save.start()
        self.addCleanup(self.save.stop)

    def _context(self, steps=None):
        mc = mock.Mock()
        mc.ai_act_context = ''
        mc.app_package = ''
        mc.project = mock.Mock(default_app_package='')
        mc.use_locate = True
        mc.max_steps = 30
        mc.action_delay = 0.5
        mc.replay_data = [{
            'steps': steps if steps is not None else [{
                'instruction': '如果展示会员购买页，就点击左上角关闭',
                'actions': [{'action': 'tap', 'x_pct': 10, 'y_pct': 10, 'x': 108, 'y': 216}],
                'after_hash': 'H_AFTER',
                'act_before_hash': 'H_ACT',
            }],
        }]
        execution = mock.Mock()
        execution.id = 1
        execution.midscene_case = mc
        execution.auto_plan = False
        execution.status = 'running'
        device = mock.Mock()
        device.platform = 'android'
        device.adb_serial = 'dev'
        device.name = '设备'
        model = mock.Mock()
        model.api_key = 'k'
        return mc, execution, device, model

    def _run(self, steps, vlm_side_effect, replay_mode=True):
        mc, execution, device, model = self._context(steps)
        with mock.patch.object(midscene_runner, 'call_vlm', side_effect=vlm_side_effect):
            return midscene_runner.run_midscene_test(
                ai_prompt='如果展示会员购买页，就点击左上角关闭',
                device=device, model_config=model, execution_record=execution,
                replay_mode=replay_mode, replay_index=0,
            )

    def test_condition_confirm_stop_returns_stopped(self):
        # 条件步骤元素确认期间停止：ExecutionStopped 不被吞掉，直接中断标记 stopped
        steps = [{
            'instruction': '如果展示会员购买页，就点击左上角关闭',
            'actions': [{'action': 'tap', 'x_pct': 10, 'y_pct': 10, 'x': 108, 'y': 216}],
            'after_hash': 'H_AFTER',
            'act_before_hash': 'H_ACT',
        }]
        with mock.patch.object(midscene_runner, '_is_same_page_by_hash', return_value=False):
            result = self._run(steps, midscene_runner.ExecutionStopped('用户已停止'))
        self.assertEqual(result['status'], 'stopped')
        self.assertTrue(all(s['status'] == 'stopped' for s in result['steps']))
        self.adb_mock.assert_not_called()

    def test_main_vlm_stop_returns_stopped(self):
        # 普通步骤 VLM 调用期间停止 → 中断并标记 stopped
        steps = [{
            'instruction': '点击同意并继续',
            'actions': [{'action': 'tap', 'x_pct': 50, 'y_pct': 50, 'x': 540, 'y': 1080}],
            'after_hash': 'H',
        }]
        result = self._run(steps, midscene_runner.ExecutionStopped('用户已停止'), replay_mode=False)
        self.assertEqual(result['status'], 'stopped')
        self.assertTrue(all(s['status'] == 'stopped' for s in result['steps']))


def _make_case(owner):
    main = Project.objects.create(name='测试主项目', owner=owner)
    project = MidsceneProject.objects.create(
        name='Midscene项目', owner=owner, main_project=main,
    )
    return MidsceneCase.objects.create(
        project=project, name='用例A', ai_prompt='打开应用', created_by=owner,
    )


class ReplayEntrySaveTests(TestCase):
    """tasks._append_replay_entry：失败也保留、不限条数、自动命名。"""

    def setUp(self):
        self.owner = User.objects.create_user(username='owner-rp', password='pass')
        self.case = _make_case(self.owner)

    def test_failed_result_still_saved_with_name(self):
        from apps.ui_automation import tasks
        tasks._append_replay_entry(
            self.case, {'steps': []},
            {'passedSteps': 1, 'failedSteps': 2, 'totalSteps': 3},
        )
        self.case.refresh_from_db()
        self.assertEqual(len(self.case.replay_data), 1)
        entry = self.case.replay_data[0]
        self.assertTrue(entry['name'])
        self.assertEqual(entry['result'], '1/3 通过，2 失败')

    def test_no_limit_and_newest_first(self):
        from apps.ui_automation import tasks
        for i in range(5):
            tasks._append_replay_entry(
                self.case, {'steps': [i]},
                {'passedSteps': 1, 'failedSteps': 0, 'totalSteps': 1},
            )
        self.case.refresh_from_db()
        self.assertEqual(len(self.case.replay_data), 5)
        self.assertEqual(self.case.replay_data[0]['steps'], [4])

    def test_existing_dict_normalized_to_list(self):
        from apps.ui_automation import tasks
        self.case.replay_data = {'steps': []}
        self.case.save(update_fields=['replay_data'])
        tasks._append_replay_entry(
            self.case, {'steps': ['new']},
            {'passedSteps': 1, 'failedSteps': 0, 'totalSteps': 1},
        )
        self.case.refresh_from_db()
        self.assertEqual(len(self.case.replay_data), 2)
        self.assertEqual(self.case.replay_data[0]['steps'], ['new'])

    def test_name_includes_device_name(self):
        # 多设备同时录制：命名带设备名，避免同名条目无法区分
        from apps.ui_automation import tasks
        tasks._append_replay_entry(
            self.case,
            {'steps': [], 'device': {'name': 'Pixel A', 'platform': 'android'}},
            {'passedSteps': 1, 'failedSteps': 0, 'totalSteps': 1},
        )
        tasks._append_replay_entry(
            self.case,
            {'steps': [], 'device': {'name': 'Pixel B', 'platform': 'android'}},
            {'passedSteps': 1, 'failedSteps': 0, 'totalSteps': 1},
        )
        self.case.refresh_from_db()
        names = [e['name'] for e in self.case.replay_data]
        self.assertTrue(any('[Pixel A]' in n for n in names))
        self.assertTrue(any('[Pixel B]' in n for n in names))

    def test_name_without_device_name_no_suffix(self):
        from apps.ui_automation import tasks
        tasks._append_replay_entry(
            self.case, {'steps': []},
            {'passedSteps': 1, 'failedSteps': 0, 'totalSteps': 1},
        )
        self.case.refresh_from_db()
        self.assertNotIn('[', self.case.replay_data[0]['name'])


class ReplayRenameApiTests(TestCase):
    """录制条目重命名接口。"""

    def setUp(self):
        self.owner = User.objects.create_user(username='owner-rn', password='pass')
        self.case = _make_case(self.owner)
        self.case.replay_data = [
            {'name': '旧名称', 'steps': [{'instruction': '打开应用'}]},
        ]
        self.case.save(update_fields=['replay_data'])
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def test_rename_replay(self):
        resp = self.client.post(
            f'/api/ui-automation/midscene/cases/{self.case.id}/rename_replay/',
            {'index': 0, 'name': '登录流程'}, format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.case.refresh_from_db()
        self.assertEqual(self.case.replay_data[0]['name'], '登录流程')

    def test_rename_replay_empty_name_rejected(self):
        resp = self.client.post(
            f'/api/ui-automation/midscene/cases/{self.case.id}/rename_replay/',
            {'index': 0, 'name': '   '}, format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.case.refresh_from_db()
        self.assertEqual(self.case.replay_data[0]['name'], '旧名称')

    def test_rename_replay_invalid_index_rejected(self):
        resp = self.client.post(
            f'/api/ui-automation/midscene/cases/{self.case.id}/rename_replay/',
            {'index': 5, 'name': '新名称'}, format='json',
        )
        self.assertEqual(resp.status_code, 400)


class ReplayMatchApiTests(TestCase):
    """回放前设备匹配检查 replay_match：型号=设备名、分辨率一致优先、adb 不可用降级。"""

    def setUp(self):
        self.owner = User.objects.create_user(username='owner-mt', password='pass')
        self.case = _make_case(self.owner)
        self.case.replay_data = [
            {
                'name': 'A设备录制',
                'device': {'name': 'Pixel 7', 'platform': 'android',
                           'resolution': {'width': 1080, 'height': 2160}},
                'steps': [],
            },
            {
                'name': 'B设备录制',
                'device': {'name': 'Redmi Note 12', 'platform': 'android',
                           'resolution': {'width': 720, 'height': 1600}},
                'steps': [],
            },
        ]
        self.case.save(update_fields=['replay_data'])
        self.device = MidsceneDevice.objects.create(
            platform='android', device_id='dev-001', name='Pixel 7',
            adb_serial='SERIAL01', status='online',
        )
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.size_patcher = mock.patch.object(
            midscene_runner, 'adb_get_screen_size', return_value=(1080, 2160),
        )
        self.size_patcher.start()
        self.addCleanup(self.size_patcher.stop)

    def _get(self, index=0, device_id=None):
        return self.client.get(
            f'/api/ui-automation/midscene/cases/{self.case.id}/replay_match/',
            {'device_id': device_id or self.device.id, 'replay_index': index},
        )

    def _set_size(self, size):
        self.size_patcher.stop()
        self.size_patcher = mock.patch.object(
            midscene_runner, 'adb_get_screen_size', return_value=size,
        )
        self.size_patcher.start()
        self.addCleanup(self.size_patcher.stop)

    def test_exact_match(self):
        resp = self._get(0)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['match_level'], 'exact')
        self.assertEqual(resp.data['matching'], [])
        self.assertEqual(resp.data['current_device']['resolution'], '1080x2160')

    def test_same_resolution_diff_model_is_ok(self):
        self.device.name = 'Pixel 7 Pro'
        self.device.save(update_fields=['name'])
        resp = self._get(0)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['match_level'], 'ok')

    def test_resolution_mismatch_with_candidate(self):
        # 选中 1080x2160 的条目，但当前设备是 720x1600 → 命中 B 条目候选
        self._set_size((720, 1600))
        resp = self._get(0)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['match_level'], 'resolution_mismatch')
        self.assertEqual([m['index'] for m in resp.data['matching']], [1])

    def test_resolution_mismatch_no_candidate(self):
        self._set_size((1440, 3200))
        resp = self._get(0)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['match_level'], 'resolution_mismatch')
        self.assertEqual(resp.data['matching'], [])

    def test_adb_unavailable_unknown(self):
        self.size_patcher.stop()
        self.size_patcher = mock.patch.object(
            midscene_runner, 'adb_get_screen_size', side_effect=RuntimeError('adb down'),
        )
        self.size_patcher.start()
        self.addCleanup(self.size_patcher.stop)
        resp = self._get(0)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['match_level'], 'unknown')

    def test_platform_mismatch(self):
        self.case.replay_data[0]['device']['platform'] = 'ios'
        self.case.save(update_fields=['replay_data'])
        resp = self._get(0)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['match_level'], 'platform_mismatch')

    def test_invalid_index_rejected(self):
        resp = self._get(index=99)
        self.assertEqual(resp.status_code, 400)
