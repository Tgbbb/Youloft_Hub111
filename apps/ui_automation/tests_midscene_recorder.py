# -*- coding: utf-8 -*-
"""真机手操录制：getevent 解析 / 停顿切分 / 会话 API / 纯动作直放回放。"""
import io
import time
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.projects.models import Project
from apps.ui_automation import manual_recorder, midscene_runner
from apps.ui_automation.models import (
    MidsceneCase, MidsceneDevice, MidsceneExecutionRecord, MidsceneProject,
)

User = get_user_model()


def _line(t, code, val, etype='EV_ABS'):
    """构造一行 getevent -lt 输出（时间戳用秒/hex 值字符串）。"""
    return (t, f'[ {t:12.6f}] /dev/input/event5: {etype:<14} {code:<22} {val}')


def _tap_lines(t):
    return [
        _line(t, 'ABS_MT_POSITION_X', '00000168'),
        _line(t, 'ABS_MT_POSITION_Y', '00000384'),
        _line(t, 'BTN_TOUCH', 'DOWN', etype='EV_KEY'),
        _line(t, 'SYN_REPORT', '00000000', etype='EV_SYN'),
        _line(t + 0.08, 'BTN_TOUCH', 'UP', etype='EV_KEY'),
        _line(t + 0.08, 'SYN_REPORT', '00000000', etype='EV_SYN'),
    ]


def _swipe_lines(t):
    return [
        _line(t, 'ABS_MT_POSITION_X', '00000168'),
        _line(t, 'ABS_MT_POSITION_Y', '00000384'),
        _line(t, 'BTN_TOUCH', 'DOWN', etype='EV_KEY'),
        _line(t, 'SYN_REPORT', '00000000', etype='EV_SYN'),
        _line(t + 0.12, 'ABS_MT_POSITION_X', '000002a8'),
        _line(t + 0.12, 'ABS_MT_POSITION_Y', '000004b0'),
        _line(t + 0.12, 'SYN_REPORT', '00000000', etype='EV_SYN'),
        _line(t + 0.15, 'BTN_TOUCH', 'UP', etype='EV_KEY'),
        _line(t + 0.15, 'SYN_REPORT', '00000000', etype='EV_SYN'),
    ]


class ParseLineTests(SimpleTestCase):
    """getevent 单行解析：hex 值 / DOWN-UP 标签 / 时间戳缺省。"""

    def test_hex_value(self):
        ev = manual_recorder.parse_getevent_line(
            '[ 100.000000] /dev/input/event5: EV_ABS ABS_MT_POSITION_X 00000168')
        self.assertEqual(ev['code'], 'ABS_MT_POSITION_X')
        self.assertEqual(ev['value'], 0x168)
        self.assertAlmostEqual(ev['t'], 100.0)

    def test_down_up_labels(self):
        down = manual_recorder.parse_getevent_line(
            '[ 100.000008] /dev/input/event5: EV_KEY BTN_TOUCH DOWN')
        up = manual_recorder.parse_getevent_line(
            '[ 100.080000] /dev/input/event5: EV_KEY BTN_TOUCH UP')
        self.assertEqual(down['value'], 1)
        self.assertEqual(up['value'], 0)

    def test_no_timestamp_parses(self):
        ev = manual_recorder.parse_getevent_line(
            '/dev/input/event5: EV_ABS ABS_MT_POSITION_Y 00000384')
        self.assertEqual(ev['code'], 'ABS_MT_POSITION_Y')
        self.assertIsNone(ev['t'])

    def test_garbage_ignored(self):
        self.assertIsNone(manual_recorder.parse_getevent_line(''))
        self.assertIsNone(manual_recorder.parse_getevent_line('adb: device offline'))
        self.assertIsNone(manual_recorder.parse_getevent_line(
            'name: "Virtual Input"'))

    def test_tracking_id_up_value(self):
        ev = manual_recorder.parse_getevent_line(
            '[ 100.000000] /dev/input/event5: EV_ABS ABS_MT_TRACKING_ID ffffffff')
        self.assertEqual(ev['value'], 0xFFFFFFFF)


class StrokeAndStepTests(SimpleTestCase):
    """事件流 -> 笔划 -> 动作：tap/swipe/long_press、面板区间、键盘过滤、停顿切分。"""

    PANEL = {'x': (0, 1079), 'y': (0, 2159)}

    def test_single_tap_with_panel_range(self):
        steps = manual_recorder.parse_lines_to_steps(
            _tap_lines(100.0), 1080, 2160, ranges=self.PANEL)
        self.assertEqual(len(steps), 1)
        actions = steps[0]['actions']
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]['action'], 'tap')
        self.assertAlmostEqual(actions[0]['x_pct'], 360 / 1079 * 100, places=2)
        self.assertAlmostEqual(actions[0]['y_pct'], 900 / 2159 * 100, places=2)

    def test_tap_falls_back_to_screen_size(self):
        steps = manual_recorder.parse_lines_to_steps(_tap_lines(100.0), 1080, 2160)
        self.assertEqual(steps[0]['actions'][0]['x_pct'], 33.33)
        self.assertEqual(steps[0]['actions'][0]['y_pct'], 41.67)

    def test_scaled_panel_uses_observed_range(self):
        # 无面板区间但坐标域远大于屏幕：用会话观察范围归一化
        lines = [
            _line(100.0, 'ABS_MT_POSITION_X', '000003e8'),   # 1000
            _line(100.0, 'ABS_MT_POSITION_Y', '000007d0'),   # 2000
            _line(100.0, 'BTN_TOUCH', 'DOWN', etype='EV_KEY'),
            _line(100.0, 'SYN_REPORT', '00000000', etype='EV_SYN'),
            _line(100.1, 'ABS_MT_POSITION_X', '00000bb8'),   # 3000
            _line(100.1, 'ABS_MT_POSITION_Y', '00000fa0'),   # 4000
            _line(100.1, 'SYN_REPORT', '00000000', etype='EV_SYN'),
            _line(100.15, 'BTN_TOUCH', 'UP', etype='EV_KEY'),
            _line(100.15, 'SYN_REPORT', '00000000', etype='EV_SYN'),
        ]
        steps = manual_recorder.parse_lines_to_steps(lines, 1080, 2160)
        act = steps[0]['actions'][0]
        self.assertEqual(act['action'], 'swipe')
        self.assertEqual(act['x1_pct'], 0.0)
        self.assertEqual(act['x2_pct'], 100.0)
        self.assertEqual(act['y1_pct'], 0.0)
        self.assertEqual(act['y2_pct'], 100.0)

    def test_swipe_duration_clamped(self):
        steps = manual_recorder.parse_lines_to_steps(
            _swipe_lines(100.0), 1080, 2160, ranges=self.PANEL)
        act = steps[0]['actions'][0]
        self.assertEqual(act['action'], 'swipe')
        self.assertLess(act['x1_pct'], act['x2_pct'])
        self.assertGreaterEqual(act['duration'], manual_recorder.SWIPE_MIN_MS)

    def test_long_press(self):
        lines = [
            _line(100.0, 'ABS_MT_POSITION_X', '00000168'),
            _line(100.0, 'ABS_MT_POSITION_Y', '00000384'),
            _line(100.0, 'BTN_TOUCH', 'DOWN', etype='EV_KEY'),
            _line(100.0, 'SYN_REPORT', '00000000', etype='EV_SYN'),
            _line(100.9, 'BTN_TOUCH', 'UP', etype='EV_KEY'),
            _line(100.9, 'SYN_REPORT', '00000000', etype='EV_SYN'),
        ]
        steps = manual_recorder.parse_lines_to_steps(lines, 1080, 2160)
        act = steps[0]['actions'][0]
        self.assertEqual(act['action'], 'long_press')
        self.assertGreaterEqual(act['duration'], 900)

    def test_pause_splits_steps_and_wait_after(self):
        lines = _tap_lines(100.0) + _tap_lines(103.2)  # 停顿 3.2s
        steps = manual_recorder.parse_lines_to_steps(lines, 1080, 2160)
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0]['wait_after'], 3.12)
        self.assertEqual(steps[1]['wait_after'], 0.0)
        self.assertEqual(len(steps[0]['actions']), 1)
        self.assertEqual(len(steps[1]['actions']), 1)

    def test_quick_taps_stay_in_one_step(self):
        lines = _tap_lines(100.0) + _tap_lines(100.8)
        steps = manual_recorder.parse_lines_to_steps(lines, 1080, 2160)
        self.assertEqual(len(steps), 1)
        self.assertEqual(len(steps[0]['actions']), 2)
        # stroke1 在 t+0.08 抬起，stroke2 在 t+0.8 按下 -> 停顿 0.72
        self.assertEqual(steps[0]['actions'][1].get('wait_after'), 0.72)

    def test_wait_after_capped(self):
        lines = _tap_lines(100.0) + _tap_lines(1500.0)
        steps = manual_recorder.parse_lines_to_steps(lines, 1080, 2160)
        self.assertEqual(steps[0]['wait_after'], manual_recorder.MAX_WAIT_AFTER)

    def test_keyboard_events_ignored(self):
        lines = [
            _line(100.0, 'KEYCODE_1', 'DOWN', etype='EV_KEY'),
            _line(100.0, 'KEYCODE_1', 'UP', etype='EV_KEY'),
        ] + _tap_lines(101.0)
        steps = manual_recorder.parse_lines_to_steps(lines, 1080, 2160)
        self.assertEqual(len(steps), 1)
        self.assertEqual(len(steps[0]['actions']), 1)

    def test_tracking_id_protocol(self):
        lines = [
            _line(100.0, 'ABS_MT_TRACKING_ID', '00000000'),
            _line(100.0, 'ABS_MT_POSITION_X', '00000168'),
            _line(100.0, 'ABS_MT_POSITION_Y', '00000384'),
            _line(100.0, 'SYN_REPORT', '00000000', etype='EV_SYN'),
            _line(100.1, 'ABS_MT_POSITION_X', '000002a8'),
            _line(100.1, 'ABS_MT_POSITION_Y', '000004b0'),
            _line(100.1, 'SYN_REPORT', '00000000', etype='EV_SYN'),
            _line(100.12, 'ABS_MT_TRACKING_ID', 'ffffffff'),
            _line(100.12, 'SYN_REPORT', '00000000', etype='EV_SYN'),
        ]
        steps = manual_recorder.parse_lines_to_steps(lines, 1080, 2160)
        self.assertEqual(steps[0]['actions'][0]['action'], 'swipe')

    def test_dense_sampled_slow_swipe_not_tap(self):
        """回归：真实滑动被 getevent 以 60~120Hz 采样成大量中间点，
        相邻单帧步进很小（小于 tap 阈值），但整段手势位移很大。
        若用『最大单帧步进』判定会误判成 tap；必须用首末点净位移。
        """
        x0, y0, x1, y1 = 819, 1228, 2866, 1228
        n = 40
        t0 = 100.0
        lines = [
            _line(t0, 'ABS_MT_POSITION_X', format(x0, 'x')),
            _line(t0, 'ABS_MT_POSITION_Y', format(y0, 'x')),
            _line(t0, 'BTN_TOUCH', 'DOWN', etype='EV_KEY'),
            _line(t0, 'SYN_REPORT', '00000000', etype='EV_SYN'),
        ]
        for i in range(1, n):
            x = x0 + (x1 - x0) * i / (n - 1)
            y = y0 + (6 if i % 4 == 0 else 0)
            tt = t0 + i * 0.025
            lines += [
                _line(tt, 'ABS_MT_POSITION_X', format(int(x), 'x')),
                _line(tt, 'ABS_MT_POSITION_Y', format(int(y), 'x')),
                _line(tt, 'SYN_REPORT', '00000000', etype='EV_SYN'),
            ]
        lines += [
            _line(t0 + 1.0, 'ABS_MT_POSITION_X', format(x1, 'x')),
            _line(t0 + 1.0, 'ABS_MT_POSITION_Y', format(y1, 'x')),
            _line(t0 + 1.0, 'BTN_TOUCH', 'UP', etype='EV_KEY'),
            _line(t0 + 1.0, 'SYN_REPORT', '00000000', etype='EV_SYN'),
        ]
        steps = manual_recorder.parse_lines_to_steps(
            lines, 1080, 2160, ranges={'x': (0, 4095), 'y': (0, 4095)})
        act = steps[0]['actions'][0]
        self.assertEqual(act['action'], 'swipe')
        self.assertTrue(act['x1_pct'] < act['x2_pct'])
        self.assertAlmostEqual(act['x1_pct'], 20.0, places=1)
        self.assertAlmostEqual(act['x2_pct'], 69.99, places=1)


class ScriptReplayRunnerTests(SimpleTestCase):
    """纯动作直放：按 replay_data.steps 顺序执行，不走 parse_ai_prompt/VLM。"""

    def setUp(self):
        self.sleep = mock.patch('time.sleep', return_value=None)
        self.sleep_mock = self.sleep.start()
        self.addCleanup(self.sleep.stop)
        self.adb = mock.patch.object(midscene_runner, '_adb',
                                     return_value=mock.Mock(returncode=0))
        self.adb_mock = self.adb.start()
        self.addCleanup(self.adb.stop)
        self.size = mock.patch.object(midscene_runner, 'adb_get_screen_size',
                                      return_value=(1080, 2160))
        self.size.start()
        self.addCleanup(self.size.stop)
        self.shot = mock.patch.object(midscene_runner, 'adb_screenshot',
                                      return_value=io.BytesIO(b'x'))
        self.shot.start()
        self.addCleanup(self.shot.stop)
        self.stable = mock.patch.object(midscene_runner, '_wait_screen_stable',
                                        return_value=True)
        self.stable.start()
        self.addCleanup(self.stable.stop)

    def _context(self):
        mc = mock.Mock()
        mc.ai_act_context = ''
        mc.app_package = ''
        mc.project = mock.Mock(default_app_package='')
        mc.use_locate = True
        mc.use_deep_locate = 'auto'
        mc.max_steps = 30
        mc.action_delay = 0.5
        mc.replay_data = [{
            'name': '手操录制测试',
            'device': {'name': '设备A', 'platform': 'android',
                       'resolution': {'width': 1080, 'height': 2160}},
            'steps': [
                {'instruction': '步骤 1', 'wait_after': 2.0, 'actions': [
                    {'action': 'tap', 'x_pct': 50, 'y_pct': 50},
                ]},
                {'instruction': '步骤 2', 'wait_after': 1.5, 'actions': [
                    {'action': 'input', 'text': 'hello'},
                ]},
                {'instruction': '步骤 3', 'wait_after': 0.0, 'actions': []},
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

    def test_direct_replay_executes_actions_without_vlm(self):
        mc, execution, device, model = self._context()
        progress = []
        with mock.patch.object(midscene_runner, 'call_vlm',
                               return_value={'action': 'done'}) as vlm, \
             mock.patch.object(midscene_runner, 'save_screenshot',
                               return_value=''):
            result = midscene_runner.run_midscene_test(
                ai_prompt='',  # 直放模式不解析 ai_prompt
                device=device, model_config=model, execution_record=execution,
                replay_mode=True, replay_index=0, script_replay=True,
                skip_launch=True,
                progress_callback=lambda s, t, d: progress.append((s, d.get('type'), d.get('status'))),
            )
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['totalSteps'], 3)
        self.assertEqual([s['status'] for s in result['steps']], ['passed', 'passed', 'passed'])
        vlm.assert_not_called()
        self.adb_mock.assert_any_call('dev', 'shell', 'input', 'tap', '540', '1080')
        self.adb_mock.assert_any_call('dev', 'shell', 'input', 'text', "'hello'")
        # 步间 wait_after 生效（2.0 / 1.5）
        sleep_calls = [c.args[0] for c in self.sleep_mock.call_args_list if c.args and c.args[0] > 1]
        self.assertIn(2.0, sleep_calls)
        self.assertIn(1.5, sleep_calls)
        # 进度回调整齐：每步 start + done
        self.assertEqual([p[1] for p in progress],
                         ['step_start', 'step_done'] * 3)

    def test_direct_replay_requires_valid_replay_data(self):
        mc, execution, device, model = self._context()
        mc.replay_data = [{'name': 'x', 'steps': []}]
        with self.assertRaises(ValueError):
            midscene_runner.run_midscene_test(
                ai_prompt='', device=device, model_config=model,
                execution_record=execution, replay_mode=True, replay_index=0,
                script_replay=True, skip_launch=True,
            )


class _FakeProc:
    def __init__(self, stdout='', stderr=''):
        self.stdout = io.StringIO(stdout)
        self.stderr = io.StringIO(stderr)
        self.returncode = 0

    def terminate(self):
        pass

    def wait(self, timeout=None):
        return 0

    def kill(self):
        pass

    def poll(self):
        return 0


class RecordSessionApiTests(TestCase):
    """录制会话 API：start 锁设备 / stop 解析 / save 保存用例 / execute 直放校验。"""

    def setUp(self):
        self.user = User.objects.create_user(username='recorder', password='x')
        self.other = User.objects.create_user(username='other', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        main = Project.objects.create(name='主项目', owner=self.user)
        self.project = MidsceneProject.objects.create(
            name='P', owner=self.user, main_project=main)
        self.device = MidsceneDevice.objects.create(
            platform='android', device_id='serial1', name='设备A',
            adb_serial='serial1', status='available',
        )

    def _patch_session(self, session_id='sess123', steps=None):
        steps = steps if steps is not None else [
            {'instruction': '步骤 1', 'actions': [
                {'action': 'tap', 'x_pct': 50, 'y_pct': 50}],
             'wait_after': 0.0},
        ]
        return mock.patch.object(
            manual_recorder, 'start_session',
            side_effect=lambda dev, user: dev.lock(user) or session_id,
        ), mock.patch.object(
            manual_recorder, 'stop_session',
            return_value=(steps, {'width': 1080, 'height': 2160}),
        ), mock.patch.object(
            manual_recorder, 'get_stopped_preview',
            return_value={'steps': steps, 'width': 1080, 'height': 2160,
                          'device_id': self.device.id, 'device_name': '设备A'},
        ), mock.patch.object(manual_recorder, 'discard_stopped', return_value=None)

    def test_start_locks_device_and_returns_session(self):
        p_start, p_stop, p_preview, p_discard = self._patch_session()
        with p_start, p_stop, p_preview, p_discard:
            resp = self.client.post('/api/ui-automation/midscene/record-sessions/start/',
                                    {'device_id': self.device.id}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['session_id'], 'sess123')
        self.device.refresh_from_db()
        self.assertEqual(self.device.status, 'locked')
        self.assertEqual(self.device.locked_by, self.user)

    def test_start_rejects_offline_and_non_android(self):
        ios = MidsceneDevice.objects.create(
            platform='ios', device_id='udid1', name='iPhone', status='available')
        resp = self.client.post('/api/ui-automation/midscene/record-sessions/start/',
                                {'device_id': ios.id}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.device.status = 'offline'
        self.device.save(update_fields=['status'])
        resp = self.client.post('/api/ui-automation/midscene/record-sessions/start/',
                                {'device_id': self.device.id}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_start_rejects_locked_by_other(self):
        self.device.lock(self.other)
        resp = self.client.post('/api/ui-automation/midscene/record-sessions/start/',
                                {'device_id': self.device.id}, format='json')
        self.assertEqual(resp.status_code, 409)

    def test_start_rejects_busy_execution(self):
        midscene_case = MidsceneCase.objects.create(
            name='用例', ai_prompt='步骤 1', project=self.project, created_by=self.user)
        MidsceneExecutionRecord.objects.create(
            midscene_case=midscene_case, case_name='用例', device=self.device,
            platform='android', status='running', executed_by=self.user)
        resp = self.client.post('/api/ui-automation/midscene/record-sessions/start/',
                                {'device_id': self.device.id}, format='json')
        self.assertEqual(resp.status_code, 409)

    def test_stop_returns_preview(self):
        p_start, p_stop, p_preview, p_discard = self._patch_session()
        with p_start, p_stop, p_preview, p_discard:
            resp = self.client.post('/api/ui-automation/midscene/record-sessions/sess123/stop/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['step_count'], 1)
        self.assertEqual(resp.data['resolution'], {'width': 1080, 'height': 2160})

    def test_stop_session_end_to_end_unlocks_and_parses(self):
        """不 mock stop_session：手工注入会话，验证终止/解锁/解析/缓存全链路。"""
        self.device.lock(self.user)
        proc = _FakeProc()
        lines = []
        with mock.patch.object(manual_recorder, 'read_panel_ranges',
                               return_value={'x': (0, 1079), 'y': (0, 2159)}):
            for t, text in _tap_lines(100.0):
                lines.append((t, text))
            collector = manual_recorder._LineCollector(proc)
            collector.lines = lines  # 预填充，避免线程竞态
            manual_recorder._sessions['fakesess'] = {
                'device_id': self.device.id, 'device_name': '设备A',
                'user_id': self.user.id, 'proc': proc, 'collector': collector,
                'width': 1080, 'height': 2160, 'ranges': {'x': (0, 1079), 'y': (0, 2159)},
                'ts': time.monotonic(), 'started_at': 'now',
            }
        steps, size = manual_recorder.stop_session('fakesess')
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0]['actions'][0]['action'], 'tap')
        self.assertEqual(size, {'width': 1080, 'height': 2160})
        self.device.refresh_from_db()
        self.assertEqual(self.device.status, 'available')
        self.assertIsNone(self.device.locked_by)
        # 预览缓存可供 save 使用
        preview = manual_recorder.get_stopped_preview('fakesess')
        self.assertEqual(preview['steps'][0]['actions'][0]['x_pct'], 33.36)

    def test_stop_session_with_started_collector_no_crash(self):
        """回归：读行线程真实启动并结束后，stop 不再触发
        "'bool' object is not callable"（_stop 命名遮蔽 threading 内部方法）。"""
        stdout = '\n'.join(text for _, text in _tap_lines(100.0)) + '\n'
        proc = _FakeProc(stdout=stdout)
        collector = manual_recorder._LineCollector(proc)
        collector.start()
        collector.join(timeout=5)
        self.assertFalse(collector.is_alive())  # 旧 bug 在这里崩溃
        self.device.lock(self.user)
        manual_recorder._sessions['started-sess'] = {
            'device_id': self.device.id, 'device_name': '设备A',
            'user_id': self.user.id, 'proc': proc, 'collector': collector,
            'width': 1080, 'height': 2160, 'ranges': None,
            'ts': time.monotonic(), 'started_at': 'now',
        }
        steps, _ = manual_recorder.stop_session('started-sess')
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0]['actions'][0]['action'], 'tap')
        self.device.refresh_from_db()
        self.assertEqual(self.device.status, 'available')

    def test_save_rejects_case_id(self):
        # 手操录制改为独立用例保存：传 case_id 直接拒绝（不再追加现有用例）
        midscene_case = MidsceneCase.objects.create(
            name='已有用例', ai_prompt='步骤 1', project=self.project, created_by=self.user)
        p_start, p_stop, p_preview, p_discard = self._patch_session()
        with p_start, p_stop, p_preview, p_discard:
            resp = self.client.post(
                '/api/ui-automation/midscene/record-sessions/sess123/save/',
                {'case_id': midscene_case.id, 'name': '手操-登录'}, format='json')
        self.assertEqual(resp.status_code, 400)
        midscene_case.refresh_from_db()
        self.assertIsNone(midscene_case.replay_data)

    def test_save_requires_project(self):
        p_start, p_stop, p_preview, p_discard = self._patch_session()
        with p_start, p_stop, p_preview, p_discard:
            resp = self.client.post(
                '/api/ui-automation/midscene/record-sessions/sess123/save/',
                {'name': '手操-无项目'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('项目', resp.data['error'])

    def test_save_creates_new_case_with_placeholder_prompt(self):
        p_start, p_stop, p_preview, p_discard = self._patch_session(steps=[
            {'instruction': '步骤 1', 'actions': [{'action': 'tap', 'x_pct': 10, 'y_pct': 20}],
             'wait_after': 0.0},
            {'instruction': '步骤 2', 'actions': [{'action': 'swipe', 'x1_pct': 0, 'y1_pct': 0,
                                                   'x2_pct': 100, 'y2_pct': 100, 'duration': 300}],
             'wait_after': 1.0},
        ])
        with p_start, p_stop, p_preview, p_discard:
            resp = self.client.post(
                '/api/ui-automation/midscene/record-sessions/sess123/save/',
                {'name': '手操-新UC', 'project_id': self.project.id}, format='json')
        self.assertEqual(resp.status_code, 200)
        case = MidsceneCase.objects.get(id=resp.data['case_id'])
        self.assertEqual(case.name, '手操-新UC')
        self.assertEqual(case.project_id, self.project.id)
        self.assertEqual(case.ai_prompt, '步骤 1\n步骤 2')
        self.assertEqual(len(case.replay_data), 1)
        self.assertEqual(len(case.replay_data[0]['steps']), 2)
        self.assertEqual(case.replay_data[0]['mode'], 'manual')

    def test_save_rejects_expired_session(self):
        with mock.patch.object(manual_recorder, 'get_stopped_preview',
                               side_effect=KeyError('x')):
            resp = self.client.post(
                '/api/ui-automation/midscene/record-sessions/nope/save/', format='json')
        self.assertEqual(resp.status_code, 404)

    def test_execute_script_replay_requires_replay_mode(self):
        case = MidsceneCase.objects.create(
            name='直放用例', ai_prompt='步骤 1', project=self.project, created_by=self.user,
            replay_data=[{'name': '手操', 'steps': [
                {'instruction': '步骤 1', 'actions': []}]}])
        resp = self.client.post(
            f'/api/ui-automation/midscene/cases/{case.id}/execute/',
            {'device_id': self.device.id, 'script_replay': True}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_execute_script_replay_creates_execution_and_passes_flag(self):
        case = MidsceneCase.objects.create(
            name='直放用例', ai_prompt='步骤 1', project=self.project, created_by=self.user,
            replay_data=[{'name': '手操', 'steps': [
                {'instruction': '步骤 1', 'actions': [{'action': 'tap', 'x_pct': 50, 'y_pct': 50}]},
                {'instruction': '步骤 2', 'actions': []},
            ]}])
        delay_mock = mock.Mock()
        delay_mock.id = 'task-1'
        with mock.patch('apps.ui_automation.tasks.execute_midscene_task') as task_cls:
            task_cls.delay.return_value = delay_mock
            resp = self.client.post(
                f'/api/ui-automation/midscene/cases/{case.id}/execute/',
                {'device_id': self.device.id, 'replay': True,
                 'script_replay': True, 'replay_index': 0}, format='json')
        self.assertEqual(resp.status_code, 200)
        execution = MidsceneExecutionRecord.objects.get(id=resp.data['execution_id'])
        self.assertEqual(execution.total_steps, 2)
        self.assertFalse(execution.auto_plan)
        kwargs = task_cls.delay.call_args.kwargs
        self.assertTrue(kwargs['script_replay'])
        self.assertTrue(kwargs['replay_mode'])

    def test_execute_script_replay_bad_index(self):
        case = MidsceneCase.objects.create(
            name='直放用例', ai_prompt='步骤 1', project=self.project, created_by=self.user,
            replay_data=[])
        resp = self.client.post(
            f'/api/ui-automation/midscene/cases/{case.id}/execute/',
            {'device_id': self.device.id, 'replay': True,
             'script_replay': True, 'replay_index': 2}, format='json')
        self.assertEqual(resp.status_code, 400)


def _manual_entry(name='手操脚本', recorded_at='2026-09-09T10:00:00'):
    return {
        'name': name,
        'mode': 'manual',
        'recorded_at': recorded_at,
        'device': {'name': '设备A', 'platform': 'android',
                   'resolution': {'width': 1080, 'height': 2160}},
        'steps': [
            {'instruction': '步骤 1',
             'actions': [{'action': 'tap', 'x_pct': 50, 'y_pct': 50}],
             'wait_after': 0.0},
        ],
    }


class ManualScriptsListApiTests(TestCase):
    """脚本库接口：按 mode='manual' 聚合、项目过滤、历史追加条目、最近执行。"""

    def setUp(self):
        self.user = User.objects.create_user(username='scripts-owner', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.project = MidsceneProject.objects.create(
            name='P-A', owner=self.user,
            main_project=Project.objects.create(name='主项目A', owner=self.user))
        self.project_b = MidsceneProject.objects.create(
            name='P-B', owner=self.user,
            main_project=Project.objects.create(name='主项目B', owner=self.user))
        self.device = MidsceneDevice.objects.create(
            platform='android', device_id='serial-s', name='设备A',
            adb_serial='serial-s', status='available')

    def test_list_aggregates_manual_cases(self):
        MidsceneCase.objects.create(
            name='手操用例', ai_prompt='步骤 1', project=self.project,
            created_by=self.user, replay_data=[_manual_entry()])
        MidsceneCase.objects.create(
            name='普通用例', ai_prompt='点击登录', project=self.project,
            created_by=self.user, replay_data=[{'name': '回放条目', 'steps': []}])
        resp = self.client.get('/api/ui-automation/midscene/record-sessions/scripts/')
        self.assertEqual(resp.status_code, 200)
        rows = resp.data
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['case_id'], MidsceneCase.objects.get(name='手操用例').id)
        self.assertEqual(row['entry_index'], 0)
        self.assertEqual(row['name'], '手操脚本')
        self.assertEqual(row['project'], 'P-A')
        self.assertEqual(row['device'], '设备A')
        self.assertEqual(row['platform'], 'android')
        self.assertEqual(row['resolution'], {'width': 1080, 'height': 2160})
        self.assertEqual(row['step_count'], 1)
        self.assertEqual(row['entry_count'], 1)

    def test_list_filters_by_project(self):
        MidsceneCase.objects.create(
            name='A脚本', ai_prompt='步骤 1', project=self.project,
            created_by=self.user, replay_data=[_manual_entry('A脚本')])
        MidsceneCase.objects.create(
            name='B脚本', ai_prompt='步骤 1', project=self.project_b,
            created_by=self.user, replay_data=[_manual_entry('B脚本')])
        resp = self.client.get(
            '/api/ui-automation/midscene/record-sessions/scripts/',
            {'project': self.project.id})
        self.assertEqual([r['name'] for r in resp.data], ['A脚本'])
        resp = self.client.get(
            '/api/ui-automation/midscene/record-sessions/scripts/',
            {'project': 'abc'})
        self.assertEqual(resp.status_code, 400)

    def test_legacy_appended_entry_returns_correct_index(self):
        # 旧保存方式：manual 条目追加在普通用例里（前面还有别的条目）
        case = MidsceneCase.objects.create(
            name='混合用例', ai_prompt='步骤 1', project=self.project,
            created_by=self.user,
            replay_data=[
                {'name': 'VLM回放', 'steps': []},
                _manual_entry('历史手操', recorded_at='2026-09-08T09:00:00'),
            ])
        resp = self.client.get('/api/ui-automation/midscene/record-sessions/scripts/')
        self.assertEqual(len(resp.data), 1)
        row = resp.data[0]
        self.assertEqual(row['case_id'], case.id)
        self.assertEqual(row['entry_index'], 1)
        self.assertEqual(row['name'], '历史手操')
        self.assertEqual(row['entry_count'], 2)

    def test_latest_result_included(self):
        case = MidsceneCase.objects.create(
            name='手操用例', ai_prompt='步骤 1', project=self.project,
            created_by=self.user, replay_data=[_manual_entry()])
        MidsceneExecutionRecord.objects.create(
            midscene_case=case, case_name='手操用例', device=self.device,
            platform='android', status='passed', total_steps=1, passed_steps=1,
            executed_by=self.user)
        resp = self.client.get('/api/ui-automation/midscene/record-sessions/scripts/')
        latest = resp.data[0]['latest_result']
        self.assertEqual(latest['status'], 'passed')
        self.assertEqual(latest['pass_rate'], 100.0)
