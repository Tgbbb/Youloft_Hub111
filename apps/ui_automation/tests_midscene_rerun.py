# -*- coding: utf-8 -*-
"""单步重录（rerun_step）：runner 只跑目标步 / 任务写回 / API 校验。"""
import io
from unittest import mock

from PIL import Image

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.projects.models import Project
from apps.requirement_analysis.models import AIModelConfig
from apps.ui_automation import midscene_runner
from apps.ui_automation.models import (
    MidsceneCase, MidsceneDevice, MidsceneExecutionRecord, MidsceneProject,
)

User = get_user_model()


def _make_png(seed=1):
    import random
    rnd = random.Random(seed)
    img = Image.new('L', (64, 64))
    img.putdata([rnd.randint(0, 255) for _ in range(64 * 64)])
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


class RerunStepRunnerTests(SimpleTestCase):
    """runner rerun_step：只执行目标步骤，其余 skipped，录制结果对齐。"""

    def setUp(self):
        self.sleep = mock.patch('time.sleep', return_value=None)
        self.sleep.start()
        self.addCleanup(self.sleep.stop)

    def _context(self):
        mc = mock.Mock()
        mc.ai_act_context = ''
        mc.app_package = ''
        mc.project = mock.Mock(default_app_package='')
        mc.use_locate = True
        mc.use_deep_locate = 'auto'
        mc.max_steps = 30
        mc.action_delay = 0.5
        mc.replay_data = None
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

    def _patches(self):
        return (
            mock.patch.object(midscene_runner, 'adb_screenshot', return_value=_make_png(1)),
            mock.patch.object(midscene_runner, 'adb_get_screen_size', return_value=(1080, 2160)),
            mock.patch.object(midscene_runner, 'save_screenshot',
                              return_value='/media/midscene/1/step_1.png'),
            mock.patch.object(midscene_runner, 'adb_execute',
                              return_value={'ok': True, 'returncode': 0, 'stderr': '', 'latency': 0.1}),
        )

    def test_rerun_only_executes_target_step(self):
        mc, execution, device, model = self._context()
        p_shot, p_size, p_save, p_exec = self._patches()
        with p_shot, p_size, p_save, p_exec as exec_mock, \
             mock.patch.object(midscene_runner, 'call_vlm', return_value={
                 'action': 'done', 'step_status': 'done', 'reasoning': '页面已就绪',
             }) as vlm:
            result = midscene_runner.run_midscene_test(
                ai_prompt='点击登录\n输入1111\n点击提交',
                device=device, model_config=model, execution_record=execution,
                record_mode=True, replay_mode=False, rerun_step=1, skip_launch=True,
            )
        self.assertEqual(result['status'], 'passed')
        self.assertEqual([s['status'] for s in result['steps']],
                         ['skipped', 'passed', 'skipped'])
        vlm.assert_called_once()
        prompt = vlm.call_args.args[1] if len(vlm.call_args.args) > 1 else ''
        self.assertIn('输入1111', str(prompt))
        exec_mock.assert_not_called()
        rec_steps = result['replay_data']['steps']
        self.assertEqual(len(rec_steps), 3)
        self.assertIsNone(rec_steps[0])
        self.assertEqual(rec_steps[1]['instruction'], '输入1111')
        self.assertEqual(rec_steps[1]['actions'], [])
        self.assertTrue(rec_steps[1]['after_hash'])
        self.assertIsNone(rec_steps[2])

    def test_rerun_target_step_records_tap_action(self):
        mc, execution, device, model = self._context()
        p_shot, p_size, p_save, p_exec = self._patches()
        tap = {'action': 'tap', 'x_pct': 50, 'y_pct': 50, 'x': 540, 'y': 1080,
               'step_status': 'done', 'reasoning': '点击提交'}
        with p_shot, p_size, p_save, p_exec as exec_mock, \
             mock.patch.object(midscene_runner, 'call_vlm', return_value=tap) as vlm:
            result = midscene_runner.run_midscene_test(
                ai_prompt='点击登录\n点击提交\n确认返回首页',
                device=device, model_config=model, execution_record=execution,
                record_mode=True, replay_mode=False, rerun_step=1, skip_launch=True,
            )
        self.assertEqual(result['status'], 'passed')
        self.assertEqual([s['status'] for s in result['steps']],
                         ['skipped', 'passed', 'skipped'])
        self.assertEqual(vlm.call_count, 1)  # tap done 在同一轮内完成，不二次调 VLM
        self.assertGreaterEqual(exec_mock.call_count, 1)  # 首次 + 页面未变轮内重试
        rec = result['replay_data']['steps'][1]
        self.assertEqual(len(rec['actions']), 1)
        self.assertEqual(rec['actions'][0]['action'], 'tap')
        self.assertTrue(rec['after_hash'])

    def test_rerun_none_keeps_normal_behavior(self):
        mc, execution, device, model = self._context()
        p_shot, p_size, p_save, p_exec = self._patches()
        with p_shot, p_size, p_save, p_exec, \
             mock.patch.object(midscene_runner, 'call_vlm', return_value={
                 'action': 'done', 'step_status': 'done', 'reasoning': 'ok',
             }) as vlm:
            result = midscene_runner.run_midscene_test(
                ai_prompt='点击登录\n输入1111',
                device=device, model_config=model, execution_record=execution,
                record_mode=True, replay_mode=False,
            )
        self.assertEqual([s['status'] for s in result['steps']], ['passed', 'passed'])
        self.assertEqual(vlm.call_count, 2)


class RerunStepTaskTests(TestCase):
    """rerun_step_task：只替换目标步，其余步骤/元信息不变；写回目标缺失则 error。"""

    def setUp(self):
        self.user = User.objects.create_user(username='rerun-task', password='pass')
        main = Project.objects.create(name='主项目-reruntask', owner=self.user)
        project = MidsceneProject.objects.create(
            name='Midscene项目-reruntask', owner=self.user, main_project=main,
        )
        self.model_config = AIModelConfig.objects.create(
            name='测试VLM', model_type='qwen', role='app_automation_vision',
            api_key='k', base_url='https://example.com', model_name='qwen-test',
            created_by=self.user,
        )
        self.case = MidsceneCase.objects.create(
            project=project, name='重录用例', ai_prompt='点击登录\n输入1111\n点击提交',
            ai_model_config=self.model_config, created_by=self.user,
        )
        self.device = MidsceneDevice.objects.create(
            platform='android', device_id='RERUN-A', name='重录机',
            status='available', adb_serial='RERUN-A',
        )
        self.case.replay_data = [{
            'name': '旧脚本', 'recorded_at': '2026-01-01T00:00:00',
            'device': {'name': '旧设备', 'platform': 'android',
                       'resolution': {'width': 1080, 'height': 2160}},
            'steps': [
                {'instruction': '点击登录', 'actions': [{'action': 'tap', 'x_pct': 50}], 'after_hash': 'OLD0'},
                {'instruction': '输入1111', 'actions': [{'action': 'input', 'text': '1111'}], 'after_hash': 'OLD1'},
                {'instruction': '点击提交', 'actions': [{'action': 'tap', 'x_pct': 50}], 'after_hash': 'OLD2'},
            ],
        }]
        self.case.save(update_fields=['replay_data'])

    def _execution(self):
        return MidsceneExecutionRecord.objects.create(
            midscene_case=self.case, case_name=self.case.name,
            device=self.device, platform='android', status='pending',
            total_steps=3, executed_by=self.user,
        )

    def _mock_result(self):
        return {
            'status': 'passed', 'totalSteps': 3, 'passedSteps': 1, 'failedSteps': 0,
            'steps': [
                {'step': 1, 'status': 'skipped', 'instruction': '点击登录'},
                {'step': 2, 'status': 'passed', 'instruction': '输入1111'},
                {'step': 3, 'status': 'skipped', 'instruction': '点击提交'},
            ],
            'replay_data': {'name': 'x', 'steps': [
                None,
                {'instruction': '输入1111', 'actions': [{'action': 'input', 'text': '2222'}],
                 'after_hash': 'NEW1'},
                None,
            ]},
        }

    def test_task_replaces_only_target_step(self):
        rec = self._execution()
        with mock.patch('apps.ui_automation.tasks.run_midscene_test',
                        return_value=self._mock_result()) as run_test:
            from apps.ui_automation.tasks import rerun_step_task
            status = rerun_step_task(rec.id, 0, 1)
        self.assertEqual(status, 'passed')
        rec.refresh_from_db()
        self.assertEqual(rec.status, 'passed')
        kwargs = run_test.call_args.kwargs
        self.assertEqual(kwargs['rerun_step'], 1)
        self.assertTrue(kwargs['skip_launch'])
        self.assertTrue(kwargs['record_mode'])
        self.assertFalse(kwargs['clear_app_data'])
        self.case.refresh_from_db()
        entry = self.case.replay_data[0]
        self.assertEqual(entry['name'], '旧脚本')
        self.assertEqual(entry['steps'][1]['after_hash'], 'NEW1')
        self.assertEqual(entry['steps'][1]['actions'][0]['text'], '2222')
        self.assertEqual(entry['steps'][0]['after_hash'], 'OLD0')
        self.assertEqual(entry['steps'][2]['after_hash'], 'OLD2')
        self.device.refresh_from_db()
        self.assertEqual(self.device.status, 'available')

    def test_task_missing_target_marks_error(self):
        rec = self._execution()
        self.case.replay_data = None
        self.case.save(update_fields=['replay_data'])
        with mock.patch('apps.ui_automation.tasks.run_midscene_test',
                        return_value=self._mock_result()):
            from apps.ui_automation.tasks import rerun_step_task
            status = rerun_step_task(rec.id, 0, 1)
        self.assertEqual(status, 'error')
        rec.refresh_from_db()
        self.assertEqual(rec.status, 'error')
        self.assertIn('未写回', rec.error_message)
        self.device.refresh_from_db()
        self.assertEqual(self.device.status, 'available')


class RerunStepApiTests(TestCase):
    """rerun_step 接口：校验与任务投递。"""

    def setUp(self):
        self.user = User.objects.create_user(username='rerun-api', password='pass')
        main = Project.objects.create(name='主项目-rerunapi', owner=self.user)
        project = MidsceneProject.objects.create(
            name='Midscene项目-rerunapi', owner=self.user, main_project=main,
        )
        self.case = MidsceneCase.objects.create(
            project=project, name='重录API用例', ai_prompt='点击登录\n输入1111\n点击提交',
            created_by=self.user,
        )
        self.case.replay_data = [{
            'name': '脚本', 'steps': [
                {'instruction': '点击登录', 'actions': [{'action': 'tap', 'x_pct': 50}], 'after_hash': 'H0'},
                {'instruction': '输入1111', 'actions': [{'action': 'input', 'text': '1111'}], 'after_hash': 'H1'},
                {'instruction': '点击提交', 'actions': [{'action': 'tap', 'x_pct': 50}], 'after_hash': 'H2'},
            ],
        }]
        self.case.save(update_fields=['replay_data'])
        self.device = MidsceneDevice.objects.create(
            platform='android', device_id='RERUN-API', name='重录API机',
            status='online', adb_serial='RERUN-API',
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.delay_patcher = mock.patch(
            'apps.ui_automation.tasks.rerun_step_task.delay',
            return_value=mock.Mock(id='TASK-RERUN'),
        )
        self.delay = self.delay_patcher.start()
        self.addCleanup(self.delay_patcher.stop)

    def _post(self, **payload):
        return self.client.post(
            f'/api/ui-automation/midscene/cases/{self.case.id}/rerun_step/',
            payload, format='json',
        )

    def test_success_creates_execution_and_dispatches_once(self):
        resp = self._post(replay_index=0, step_index=1, device_id=self.device.id)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['status'], 'pending')
        exec_id = resp.data['execution_id']
        execution = MidsceneExecutionRecord.objects.get(id=exec_id)
        self.assertEqual(execution.status, 'pending')
        self.assertEqual(execution.total_steps, 3)
        self.assertEqual(execution.device, self.device)
        self.delay.assert_called_once()
        self.assertEqual(self.delay.call_args.args[0], execution.id)
        self.assertEqual(self.delay.call_args.args[1], 0)
        self.assertEqual(self.delay.call_args.args[2], 1)

    def test_branch_head_rejected(self):
        branch_case = MidsceneCase.objects.create(
            name='分支用例', ai_prompt='如果展示会员页:\n    点击关闭\n    点击下次一定',
            created_by=self.user,
        )
        resp = self.client.post(
            f'/api/ui-automation/midscene/cases/{branch_case.id}/rerun_step/',
            {'replay_index': 0, 'step_index': 0, 'device_id': self.device.id}, format='json',
        )
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('分支头', resp.data['error'])
        self.delay.assert_not_called()

    def test_step_out_of_range_rejected(self):
        resp = self._post(replay_index=0, step_index=99, device_id=self.device.id)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('越界', resp.data['error'])
        self.delay.assert_not_called()

    def test_replay_index_missing_rejected(self):
        resp = self._post(replay_index=99, step_index=0, device_id=self.device.id)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('回放脚本不存在', resp.data['error'])
        self.delay.assert_not_called()

    def test_offline_device_rejected(self):
        self.device.status = 'offline'
        self.device.save(update_fields=['status'])
        resp = self._post(replay_index=0, step_index=0, device_id=self.device.id)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('不在线', resp.data['error'])
        self.delay.assert_not_called()

    def test_busy_device_rejected(self):
        MidsceneExecutionRecord.objects.create(
            midscene_case=self.case, case_name=self.case.name,
            device=self.device, platform='android', status='running',
            executed_by=self.user,
        )
        resp = self._post(replay_index=0, step_index=0, device_id=self.device.id)
        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertIn('正在执行中', resp.data['error'])
        self.delay.assert_not_called()