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
from apps.ui_automation.models import MidsceneProject, MidsceneCase


User = get_user_model()


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
        self.shot = mock.patch.object(midscene_runner, 'adb_screenshot', return_value=b'png-bytes')
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
