# -*- coding: utf-8 -*-
"""分支 if/else 互斥：解析、双槽录制、回放四象限、补录 else API。"""
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


class ParseAiPromptElseTests(SimpleTestCase):
    """parse_ai_prompt：if/else 分组与 else_children 下标。"""

    def test_branch_with_else(self):
        text = '如果展示会员购买页:\n    点击左上角关闭\n    点击下次一定\n  否则:\n    点击跳过\n    点击返回'
        steps = midscene_runner.parse_ai_prompt(text)
        self.assertEqual(steps[0]['type'], 'branch')
        self.assertEqual(steps[0]['children'], [1, 2])
        self.assertEqual(steps[0]['else_children'], [3, 4])
        self.assertEqual(steps[3]['branch_side'], 'else')
        self.assertEqual(steps[3]['branch_parent'], 0)

    def test_branch_without_else(self):
        steps = midscene_runner.parse_ai_prompt('如果展示会员页:\n    点击左上角关闭')
        self.assertEqual(steps[0]['else_children'], [])
        self.assertEqual(steps[0]['children'], [1])

    def test_single_condition_is_step(self):
        steps = midscene_runner.parse_ai_prompt('如果展示会员页，就点击左上角关闭')
        self.assertNotEqual(steps[0].get('type'), 'branch')

    def test_else_not_indented_is_normal_step(self):
        # else 行必须缩进才能作为分支标记；未缩进则当作普通顶层步骤
        steps = midscene_runner.parse_ai_prompt('如果展示会员页:\n    点击关闭\n否则:\n    点击跳过')
        self.assertEqual(steps[0]['else_children'], [])
        self.assertEqual(len(steps), 4)  # 分支头 + 点击关闭 + 否则:(普通步) + 点击跳过(普通步)

    def test_multiple_else_raises(self):
        text = '如果A:\n  否则:\n  否则:\n    点击B'
        with self.assertRaises(ValueError):
            midscene_runner.parse_ai_prompt(text)


class BranchRecordingOtherTests(SimpleTestCase):
    """录制：走了 if 录 if 组、else 组空；走了 else 录 else 组、if 组空。"""

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
            mock.patch.object(midscene_runner, '_is_same_page_by_hash', return_value=False),
        )

    def test_entered_records_if_group(self):
        # 分支命中（entered=True）→ if 组录动作，else 组空
        text = '如果展示会员购买页:\n    点击左上角关闭\n  否则:\n    点击下次一定'
        mc, execution, device, model = self._context()
        # 让元素确认返回 present -> entered=True
        self._confirm = mock.patch.object(
            midscene_runner, '_confirm_condition_target',
            return_value=('present', _make_png(2), '目标存在'),
        )
        p_shot, p_size, p_save, p_hash = self._patches()
        with p_shot, p_size, p_save, p_hash, self._confirm, \
             mock.patch.object(midscene_runner, 'call_vlm', return_value={
                 'action': 'done', 'step_status': 'done', 'reasoning': 'ok',
             }) as vlm:
            result = midscene_runner.run_midscene_test(
                ai_prompt=text, device=device, model_config=model, execution_record=execution,
                record_mode=True, replay_mode=False,
            )
        rec_steps = result['replay_data']['steps']
        self.assertEqual(rec_steps[1]['instruction'], '点击左上角关闭')
        self.assertEqual(rec_steps[1]['actions'], [])
        # else 组留空占位
        self.assertIsNone(rec_steps[2])

    def test_not_entered_records_else_group(self):
        text = '如果展示会员购买页:\n    点击左上角关闭\n  否则:\n    点击下次一定'
        mc, execution, device, model = self._context()
        self._confirm = mock.patch.object(
            midscene_runner, '_confirm_condition_target',
            return_value=('absent', _make_png(2), '目标不存在'),
        )
        p_shot, p_size, p_save, p_hash = self._patches()
        with p_shot, p_size, p_save, p_hash, self._confirm, \
             mock.patch.object(midscene_runner, 'call_vlm', return_value={
                 'action': 'done', 'step_status': 'done', 'reasoning': 'ok',
             }) as vlm:
            result = midscene_runner.run_midscene_test(
                ai_prompt=text, device=device, model_config=model, execution_record=execution,
                record_mode=True, replay_mode=False,
            )
        rec_steps = result['replay_data']['steps']
        self.assertEqual(rec_steps[2]['instruction'], '点击下次一定')
        self.assertEqual(rec_steps[2]['actions'], [])
        self.assertIsNone(rec_steps[1])
        # 分支头 else 槽记录
        self.assertTrue(rec_steps[0]['else_entered'])


class BranchGatingTests(SimpleTestCase):
    """回放门控：if 槽命中 / else 槽命中 / 元素确认兜底。"""

    def setUp(self):
        self.sleep = mock.patch('time.sleep', return_value=None)
        self.sleep.start()
        self.addCleanup(self.sleep.stop)

    def _img(self, seed):
        import random
        rnd = random.Random(seed)
        img = Image.new('L', (64, 64))
        img.putdata([rnd.randint(0, 255) for _ in range(64 * 64)])
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()

    def _context(self, replay_steps):
        mc = mock.Mock()
        mc.ai_act_context = ''
        mc.app_package = ''
        mc.project = mock.Mock(default_app_package='')
        mc.use_locate = True
        mc.use_deep_locate = 'auto'
        mc.max_steps = 30
        mc.action_delay = 0.5
        mc.replay_data = [{'name': 'x', 'steps': replay_steps}]
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

    def _run(self, steps, replay_steps, shot_png, hash_match):
        mc, execution, device, model = self._context(replay_steps)
        with mock.patch.object(midscene_runner, 'adb_screenshot', return_value=shot_png), \
             mock.patch.object(midscene_runner, 'adb_get_screen_size', return_value=(1080, 2160)), \
             mock.patch.object(midscene_runner, 'save_screenshot',
                               return_value='/media/midscene/1/step_1.png'), \
             mock.patch.object(midscene_runner, '_is_same_page_by_hash',
                               side_effect=hash_match), \
             mock.patch.object(midscene_runner, 'call_vlm', return_value={
                 'action': 'done', 'step_status': 'done', 'reasoning': 'ok',
             }):
            return midscene_runner.run_midscene_test(
                ai_prompt=steps, device=device, model_config=model, execution_record=execution,
                replay_mode=True, replay_index=0,
            )

    def test_replay_else_slot_hit_goes_else_group(self):
        # 录制时走了 else（else_entered=True），回放命中 else 态 → 走 else 组
        replay_steps = [
            {'instruction': '如果展示会员购买页:', 'type': 'branch', 'branch_entered': False,
             'after_hash': 'HH', 'else_entered': True, 'else_act_before_hash': 'EE',
             'actions': []},
            {'instruction': '点击左上角关闭', 'actions': []},
            {'instruction': '点击下次一定', 'actions': [], 'branch_side': 'else'},
        ]
        # else 态页匹配 else_act_before_hash
        result = self._run(
            '如果展示会员购买页:\n    点击左上角关闭\n  否则:\n    点击下次一定',
            replay_steps, self._img(1),
            lambda _p, h: h == 'EE',
        )
        self.assertEqual(result['status'], 'passed')
        # else 组子步骤走 done（无回放数据则 VLM 兜底，这里动作空但 leaf 被执行）
        self.assertEqual(result['steps'][2]['status'], 'passed')
        self.assertEqual(result['steps'][1]['status'], 'passed')  # if 组被跳过


class RerunElseApiTests(TestCase):
    """rerun_else 接口：校验与任务投递。"""

    def setUp(self):
        self.user = User.objects.create_user(username='rerun-else', password='pass')
        main = Project.objects.create(name='主项目-rerunelse', owner=self.user)
        project = MidsceneProject.objects.create(
            name='Midscene项目-rerunelse', owner=self.user, main_project=main,
        )
        self.case = MidsceneCase.objects.create(
            project=project, name='补录else用例',
            ai_prompt='如果展示会员页:\n    点击左上角关闭\n  否则:\n    点击跳过',
            created_by=self.user,
        )
        self.case.replay_data = [{
            'name': '脚本', 'steps': [
                {'instruction': '如果展示会员页:', 'type': 'branch', 'branch_entered': True,
                 'act_before_hash': 'IF1', 'actions': []},
                {'instruction': '点击左上角关闭', 'actions': [{'action': 'tap'}]},
                {'instruction': '点击跳过', 'actions': []},
            ],
        }]
        self.case.save(update_fields=['replay_data'])
        self.device = MidsceneDevice.objects.create(
            platform='android', device_id='RERUN-ELSE', name='补录机',
            status='online', adb_serial='RERUN-ELSE',
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.delay_patcher = mock.patch(
            'apps.ui_automation.tasks.rerun_else_task.delay',
            return_value=mock.Mock(id='TASK-ELSE'),
        )
        self.delay = self.delay_patcher.start()
        self.addCleanup(self.delay_patcher.stop)

    def _post(self, **payload):
        return self.client.post(
            f'/api/ui-automation/midscene/cases/{self.case.id}/rerun_else/',
            payload, format='json',
        )

    def test_success_dispatches_once(self):
        resp = self._post(replay_index=0, branch_step_index=0, device_id=self.device.id)
        self.assertEqual(resp.status_code, 200, resp.data)
        exec_id = resp.data['execution_id']
        execution = MidsceneExecutionRecord.objects.get(id=exec_id)
        self.assertEqual(execution.status, 'pending')
        self.delay.assert_called_once()
        self.assertEqual(self.delay.call_args.args[0], execution.id)
        self.assertEqual(self.delay.call_args.args[1], 0)
        self.assertEqual(self.delay.call_args.args[2], 0)

    def test_not_branch_rejected(self):
        # 目标是普通步骤 → 400
        resp = self._post(replay_index=0, branch_step_index=1, device_id=self.device.id)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('不是分支头', resp.data['error'])
        self.delay.assert_not_called()

    def test_no_else_rejected(self):
        self.case.ai_prompt = '如果展示会员页:\n    点击左上角关闭'
        self.case.save(update_fields=['ai_prompt'])
        resp = self._post(replay_index=0, branch_step_index=0, device_id=self.device.id)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('没有 else', resp.data['error'])
        self.delay.assert_not_called()

    def test_offline_device_rejected(self):
        self.device.status = 'offline'
        self.device.save(update_fields=['status'])
        resp = self._post(replay_index=0, branch_step_index=0, device_id=self.device.id)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('不在线', resp.data['error'])
        self.delay.assert_not_called()

    def test_busy_device_rejected(self):
        MidsceneExecutionRecord.objects.create(
            midscene_case=self.case, case_name=self.case.name,
            device=self.device, platform='android', status='running',
            executed_by=self.user,
        )
        resp = self._post(replay_index=0, branch_step_index=0, device_id=self.device.id)
        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertIn('正在执行中', resp.data['error'])
        self.delay.assert_not_called()