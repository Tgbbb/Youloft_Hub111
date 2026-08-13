# -*- coding: utf-8 -*-
"""异常分层采集（anomaly 机制）测试：
构建器分层规则、ADB/WDA 证据返回、回放纠错埋点、报告异常/断言统计、
aiAct 引擎 replan / locate_retry 埋点。"""
import io
from unittest import mock

from django.test import SimpleTestCase, TestCase
from PIL import Image

from apps.ui_automation import midscene_runner
from apps.ui_automation.ios_device import IOSDevice
from apps.ui_automation.midscene_ai.engine import run_ai_act
from apps.ui_automation.midscene_report import build_report_data, to_html
from apps.ui_automation.models import MidsceneExecutionRecord


def _make_png(seed=1):
    """固定种子的随机图（phash 非 0）。"""
    import random
    rnd = random.Random(seed)
    img = Image.new('L', (64, 64))
    img.putdata([rnd.randint(0, 255) for _ in range(64 * 64)])
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def _build_record(steps_detail):
    return MidsceneExecutionRecord.objects.create(
        case_name='异常用例',
        platform='android',
        status='passed',
        total_steps=len(steps_detail),
        steps_detail=steps_detail,
    )


class BuildAnomalyTests(SimpleTestCase):
    """_build_anomaly 分层规则：环境硬证据 -> execution；环境正常页面事件 -> app；无旁证 -> unknown。"""

    def test_execution_layer_on_adb_nonzero(self):
        a = midscene_runner._build_anomaly(
            'adb_error', 'ADB tap 失败',
            evidence={'returncode': 1, 'stderr': 'device offline'})
        self.assertEqual(a['type'], 'adb_error')
        self.assertEqual(a['layer'], 'execution')
        self.assertEqual(a['label'], 'ADB 错误')
        self.assertTrue(a['recovered'])
        self.assertEqual(a['evidence']['returncode'], 1)

    def test_execution_layer_on_wda_non200(self):
        a = midscene_runner._build_anomaly(
            'wda_error', 'WDA tap 失败', evidence={'status_code': 500})
        self.assertEqual(a['layer'], 'execution')

    def test_execution_layer_on_fallback_first_status(self):
        # 新版端点失败降级旧版成功：first_status 非 200 仍归执行环境
        a = midscene_runner._build_anomaly(
            'wda_error', 'tap 降级', evidence={
                'status_code': 200, 'fallback_used': True, 'first_status': 500})
        self.assertEqual(a['layer'], 'execution')

    def test_app_layer_when_env_ok(self):
        # 调用成功（returncode=0）但页面类间接证据 -> app
        a = midscene_runner._build_anomaly(
            'tap_retry', 'tap 未生效', evidence={'returncode': 0})
        self.assertEqual(a['layer'], 'app')

    def test_unknown_when_no_evidence(self):
        a = midscene_runner._build_anomaly('tap_retry', 'tap 未生效')
        self.assertEqual(a['layer'], 'unknown')

    def test_action_skipped_default_app(self):
        a = midscene_runner._build_anomaly(
            'action_skipped', '回放跳过动作',
            evidence={'action': 'tap', 'before_hash': 'h1', 'current_hash': 'h2'})
        self.assertEqual(a['layer'], 'app')
        self.assertTrue(a['recovered'])

    def test_recovered_flag(self):
        a = midscene_runner._build_anomaly(
            'stuck_detected', '连续重复动作',
            evidence={'page_unchanged': True}, recovered=False)
        self.assertFalse(a['recovered'])
        self.assertEqual(a['layer'], 'app')


class AdbEvidenceTests(SimpleTestCase):
    """adb_execute / adb_input_text 返回结构化证据。"""

    def test_adb_execute_ok(self):
        with mock.patch.object(
                midscene_runner, '_adb',
                return_value=mock.Mock(returncode=0, stderr='')) as m:
            ev = midscene_runner.adb_execute('dev', {'action': 'tap', 'x': 10, 'y': 20})
        self.assertTrue(ev['ok'])
        self.assertEqual(ev['returncode'], 0)
        self.assertIn('latency', ev)
        m.assert_called_once()
        self.assertEqual(m.call_args.args[-2:], ('10', '20'))

    def test_adb_execute_failure(self):
        with mock.patch.object(
                midscene_runner, '_adb',
                return_value=mock.Mock(returncode=1, stderr='device offline')):
            ev = midscene_runner.adb_execute('dev', {'action': 'back'})
        self.assertFalse(ev['ok'])
        self.assertEqual(ev['returncode'], 1)
        self.assertIn('device offline', ev['stderr'])

    def test_input_ascii_no_fallback(self):
        with mock.patch.object(midscene_runner, '_needs_yadb', return_value=False), \
             mock.patch.object(midscene_runner, '_adb',
                               return_value=mock.Mock(returncode=0, stderr='')):
            ev = midscene_runner.adb_input_text('dev', 'hello')
        self.assertTrue(ev['ok'])
        self.assertFalse(ev['fallback_used'])

    def test_input_fallback_flag_when_yadb_unavailable(self):
        with mock.patch.object(midscene_runner, '_needs_yadb', return_value=True), \
             mock.patch.object(midscene_runner, '_yadb_input', return_value=False), \
             mock.patch.object(midscene_runner, '_adb',
                               return_value=mock.Mock(returncode=0, stderr='')):
            ev = midscene_runner.adb_input_text('dev', '中文')
        self.assertTrue(ev['ok'])
        self.assertTrue(ev['fallback_used'])


class IOSDeviceEvidenceTests(SimpleTestCase):
    """iOS 动作返回 {ok, status_code, error, latency, fallback_used}。"""

    def setUp(self):
        self.dev = IOSDevice('localhost', 8100, 'com.example.app')
        self.dev.session_id = 's1'
        self.post = mock.patch('apps.ui_automation.ios_device.http.post')
        self.post_mock = self.post.start()
        self.addCleanup(self.post.stop)

    def test_tap_new_endpoint_ok(self):
        self.post_mock.return_value = mock.Mock(status_code=200, text='')
        ev = self.dev.tap(10, 20)
        self.assertTrue(ev['ok'])
        self.assertEqual(ev['status_code'], 200)
        self.assertFalse(ev['fallback_used'])
        self.assertEqual(self.post_mock.call_count, 1)
        self.assertIn('/wda/tap', self.post_mock.call_args.args[0])

    def test_tap_fallback_records_first_status(self):
        self.post_mock.side_effect = [
            mock.Mock(status_code=500, text='bad'),
            mock.Mock(status_code=200, text=''),
        ]
        ev = self.dev.tap(10, 20)
        self.assertTrue(ev['ok'])
        self.assertTrue(ev['fallback_used'])
        self.assertEqual(ev['first_status'], 500)
        self.assertEqual(self.post_mock.call_count, 2)

    def test_tap_all_fail(self):
        self.post_mock.side_effect = [
            mock.Mock(status_code=500, text='bad'),
            mock.Mock(status_code=503, text='down'),
        ]
        ev = self.dev.tap(10, 20)
        self.assertFalse(ev['ok'])
        self.assertEqual(ev['status_code'], 503)
        self.assertTrue(ev['fallback_used'])

    def test_execute_action_swipe_error(self):
        self.post_mock.return_value = mock.Mock(status_code=500, text='bad')
        ev = self.dev.execute_action({'action': 'swipe', 'x1': 1, 'y1': 2, 'x2': 3, 'y2': 4})
        self.assertFalse(ev['ok'])
        self.assertEqual(ev['status_code'], 500)


class ReplayAnomalyTests(SimpleTestCase):
    """_replay_actions 纠错点埋点：跳过 / 环境错误。"""

    def setUp(self):
        self.calls = []
        self.sleep = mock.patch('time.sleep', return_value=None)
        self.sleep.start()
        self.adb = mock.patch.object(
            midscene_runner, '_adb',
            side_effect=lambda *args, **kw: self.calls.append(args) or mock.Mock(returncode=0, stderr=''),
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

    def test_skip_records_action_skipped(self):
        self._patch_match(set())
        anomalies = []
        stats = midscene_runner._replay_actions(
            'dev', None,
            [{'action': 'tap', 'x_pct': 50, 'y_pct': 50, 'x': 0, 'y': 0,
              'before_hash': 'H_X', 'conditional': True}],
            1080, 2160, anomalies=anomalies)
        self.assertEqual(stats, {'played': 0, 'skipped': 1})
        self.assertEqual(len(anomalies), 1)
        a = anomalies[0]
        self.assertEqual(a['type'], 'action_skipped')
        self.assertEqual(a['layer'], 'app')
        self.assertTrue(a['recovered'])
        self.assertIn('before_hash', a['evidence'])

    def test_adb_error_records_execution_anomaly(self):
        with mock.patch.object(
                midscene_runner, '_adb',
                return_value=mock.Mock(returncode=1, stderr='device offline')):
            anomalies = []
            midscene_runner._replay_actions(
                'dev', None,
                [{'action': 'tap', 'x_pct': 50, 'y_pct': 50, 'x': 0, 'y': 0}],
                1080, 2160, anomalies=anomalies)
        a = anomalies[0]
        self.assertEqual(a['type'], 'adb_error')
        self.assertEqual(a['layer'], 'execution')
        self.assertTrue(a['recovered'])


class AnomalyReportTests(TestCase):
    """报告三块：异常事件统计、断言统计、带异常通过步骤黄标。"""

    def test_build_report_data_stats(self):
        record = _build_record([
            {
                'step': 1, 'instruction': '点击同意', 'status': 'passed',
                'action': 'tap', 'screenshot': '', 'aiReasoning': [],
                'anomalies': [midscene_runner._build_anomaly(
                    'tap_retry', 'tap 未生效，轮内重试', evidence={'returncode': 0})],
            },
            {
                'step': 2, 'instruction': '验证已登录', 'status': 'passed',
                'action': 'assert', 'screenshot': '', 'aiReasoning': [],
                'assert_passed': True, 'anomalies': [],
            },
            {
                'step': 3, 'instruction': '验证首页', 'status': 'failed',
                'action': 'assert', 'screenshot': '', 'aiReasoning': [],
                'assert_passed': False, 'error': '断言失败',
                'anomalies': [],
            },
        ])
        data = build_report_data(record)
        self.assertEqual(data['anomaly_stats']['total'], 1)
        self.assertEqual(data['anomaly_stats']['warned_steps'], 1)
        self.assertEqual(data['anomaly_stats']['by_type']['tap_retry'], 1)
        self.assertEqual(data['anomaly_stats']['by_layer']['app'], 1)
        self.assertEqual(data['assert_stats'], {'total': 2, 'passed': 1, 'failed': 1})

    def test_to_html_renders_warn_and_anomaly_blocks(self):
        record = _build_record([
            {
                'step': 1, 'instruction': '点击同意', 'status': 'passed',
                'action': 'tap', 'screenshot': '', 'aiReasoning': [],
                'anomalies': [midscene_runner._build_anomaly(
                    'hash_mismatch_fallback', 'pHash 不匹配，降至 VLM',
                    evidence={'expected_hash': 'h1', 'current_hash': 'h2'})],
            },
        ])
        html_text = to_html(record)
        self.assertIn('异常与断言', html_text)
        self.assertIn('msr-step--warn', html_text)
        self.assertIn('页面指纹不匹配', html_text)
        self.assertIn('层级', html_text)
        self.assertIn('expected_hash', html_text)
        self.assertIn('断言统计', html_text)

    def test_assert_failure_is_not_an_anomaly(self):
        # 断言失败保持硬失败：不计入 anomalies
        record = _build_record([
            {
                'step': 1, 'instruction': '验证', 'status': 'failed',
                'action': 'assert', 'screenshot': '', 'aiReasoning': [],
                'assert_passed': False, 'error': '断言失败',
                'anomalies': [],
            },
        ])
        data = build_report_data(record)
        self.assertEqual(data['anomaly_stats']['total'], 0)
        self.assertEqual(data['assert_stats'], {'total': 1, 'passed': 0, 'failed': 1})


class EngineAnomalyTests(SimpleTestCase):
    """aiAct 引擎 replan / locate_retry 埋点随步骤结果透传。"""

    def setUp(self):
        self.sleep = mock.patch('time.sleep', return_value=None)
        self.sleep.start()
        self.shot = mock.patch.object(
            midscene_runner, 'adb_screenshot', return_value=_make_png(7))
        self.shot.start()
        self.adb = mock.patch.object(
            midscene_runner, '_adb',
            return_value=mock.Mock(returncode=0, stderr=''))
        self.adb.start()
        self.addCleanup(self.sleep.stop)
        self.addCleanup(self.shot.stop)
        self.addCleanup(self.adb.stop)

    def _ctx(self):
        return {'platform': 'android', 'device_id': 'dev', 'ios_dev': None,
                'width': 1080, 'height': 2160}

    def test_replan_anomaly_on_truncated_output(self):
        responses = iter([
            '<planning>观察</planning><action-type>tap</action-type>'
            '<action-param-json>{"locate":"返回按钮"}',
            '<complete success="true">完成</complete>',
        ])
        with mock.patch.object(
                midscene_runner, 'call_vlm',
                side_effect=lambda *args, **kwargs: next(responses)):
            result = run_ai_act('测试任务', self._ctx(), model_config=mock.Mock(),
                                max_steps=5)
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(len(result['steps']), 1)
        types = [a['type'] for a in result['steps'][0].get('anomalies', [])]
        self.assertIn('replan', types)
        replan = next(a for a in result['steps'][0]['anomalies'] if a['type'] == 'replan')
        self.assertTrue(replan['recovered'])
        self.assertEqual(replan['evidence']['replan_count'], 1)

    def test_locate_retry_anomaly_on_retry_success(self):
        responses = iter([
            '<planning>定位目标</planning><action-type>tap</action-type>'
            '<action-param-json>{"locate":"返回按钮"}</action-param-json>',
            '{"x":999}',
            '{"x_pct":50,"y_pct":50,"reasoning":"ok"}',
            '<complete success="true">完成</complete>',
        ])
        with mock.patch.object(
                midscene_runner, 'call_vlm',
                side_effect=lambda *args, **kwargs: next(responses)):
            result = run_ai_act('测试任务', self._ctx(), model_config=mock.Mock(),
                                max_steps=5)
        self.assertEqual(result['status'], 'passed')
        tap_step = next(s for s in result['steps'] if s.get('action') == 'tap')
        types = [a['type'] for a in tap_step.get('anomalies', [])]
        self.assertIn('locate_retry', types)
        loc = next(a for a in tap_step['anomalies'] if a['type'] == 'locate_retry')
        self.assertTrue(loc['recovered'])
        self.assertEqual(loc['evidence']['retries'], 1)
