# -*- coding: utf-8 -*-
"""Midscene 执行接口互斥测试：同一设备同时只能有一个 pending/running 任务。"""
from unittest import mock

import celery
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.projects.models import Project
from apps.ui_automation import midscene_runner
from apps.ui_automation.models import (
    MidsceneProject, MidsceneCase, MidsceneDevice, MidsceneExecutionRecord,
)


User = get_user_model()


class DeviceExecuteMutexTests(TestCase):
    """同一设备重复提交互斥：pending/running 时拒绝，不同设备并行放行。"""

    def setUp(self):
        self.owner = User.objects.create_user(username='owner-exec', password='pass')
        main = Project.objects.create(name='主项目-exec', owner=self.owner)
        project = MidsceneProject.objects.create(
            name='Midscene项目-exec', owner=self.owner, main_project=main,
        )
        self.case = MidsceneCase.objects.create(
            project=project, name='执行互斥用例', ai_prompt='点击登录\n打开应用',
            created_by=self.owner,
        )
        self.device_a = MidsceneDevice.objects.create(
            platform='android', device_id='dev-a', name='Pixel A',
            adb_serial='SERA', status='online',
        )
        self.device_b = MidsceneDevice.objects.create(
            platform='android', device_id='dev-b', name='Pixel B',
            adb_serial='SERB', status='online',
        )
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.delay_patcher = mock.patch(
            'apps.ui_automation.tasks.execute_midscene_task.delay',
            return_value=mock.Mock(id='TASK1'),
        )
        self.delay = self.delay_patcher.start()
        self.addCleanup(self.delay_patcher.stop)

    def _post(self, device_id):
        return self.client.post(
            f'/api/ui-automation/midscene/cases/{self.case.id}/execute/',
            {'device_id': device_id}, format='json',
        )

    def _busy_record(self, status='running', device=None):
        return MidsceneExecutionRecord.objects.create(
            midscene_case=self.case,
            case_name=self.case.name,
            device=device or self.device_a,
            platform='android',
            status=status,
            executed_by=self.owner,
        )

    def test_execute_allowed_when_device_idle(self):
        resp = self._post(self.device_a.id)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('execution_id', resp.data)
        self.delay.assert_called_once()

    def test_execute_rejected_when_device_running(self):
        self._busy_record('running')
        resp = self._post(self.device_a.id)
        self.assertEqual(resp.status_code, 409, resp.data)
        self.delay.assert_not_called()

    def test_execute_rejected_when_device_pending(self):
        self._busy_record('pending')
        resp = self._post(self.device_a.id)
        self.assertEqual(resp.status_code, 409, resp.data)
        self.delay.assert_not_called()

    def test_execute_allowed_after_finished(self):
        # 历史执行已完成（failed/passed/stopped）不阻塞重新执行
        self._busy_record('passed')
        self._busy_record('failed')
        self._busy_record('stopped')
        resp = self._post(self.device_a.id)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.delay.assert_called_once()

    def test_different_devices_parallel_allowed(self):
        # 设备 A 执行中，设备 B 仍可并行发起
        self._busy_record('running')
        resp = self._post(self.device_b.id)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.delay.assert_called_once()

    def test_locked_by_other_user_rejected(self):
        other = User.objects.create_user(username='other-exec', password='pass')
        self.device_a.status = 'locked'
        self.device_a.locked_by = other
        self.device_a.save(update_fields=['status', 'locked_by'])
        resp = self._post(self.device_a.id)
        self.assertEqual(resp.status_code, 409, resp.data)
        self.delay.assert_not_called()


class BatchExecuteTests(TestCase):
    """多设备批量执行：各建任务、逐台指定脚本、失败不阻断。"""

    def setUp(self):
        self.owner = User.objects.create_user(username='owner-batch', password='pass')
        main = Project.objects.create(name='主项目-batch', owner=self.owner)
        project = MidsceneProject.objects.create(
            name='Midscene项目-batch', owner=self.owner, main_project=main,
        )
        self.case = MidsceneCase.objects.create(
            project=project, name='批量执行用例', ai_prompt='点击登录\n打开应用',
            created_by=self.owner,
        )
        self.devices = []
        for i in range(3):
            d = MidsceneDevice.objects.create(
                platform='android', device_id=f'dev-b{i}', name=f'Pixel {i}',
                adb_serial=f'SERB{i}', status='online',
            )
            self.devices.append(d)
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def _post(self, payload):
        with mock.patch(
            'apps.ui_automation.tasks.execute_midscene_task.delay',
            return_value=mock.Mock(id='TASK-B'),
        ) as delay:
            resp = self.client.post(
                f'/api/ui-automation/midscene/cases/{self.case.id}/execute/',
                payload, format='json',
            )
        return resp, delay

    def test_batch_multiple_devices(self):
        resp, delay = self._post({'devices': [self.devices[0].id, self.devices[1].id]})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['executions']), 2)
        self.assertEqual(resp.data['failed'], [])
        self.assertEqual(delay.call_count, 2)
        # 每台设备各自创建了执行记录
        self.assertEqual(
            MidsceneExecutionRecord.objects.filter(device__in=self.devices[:2], status='pending').count(),
            2,
        )

    def test_batch_per_device_replay_index(self):
        payload = {'devices': [
            {'device_id': self.devices[0].id, 'replay_index': 1},
            {'device_id': self.devices[1].id, 'replay_index': 2},
        ]}
        resp, delay = self._post(payload)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(delay.call_count, 2)
        indexes = sorted(c.kwargs['replay_index'] for c in delay.call_args_list)
        self.assertEqual(indexes, [1, 2])
        # 每台设备各自带上了指定的 replay_index（通过 execution 记录反查设备）
        for call in delay.call_args_list:
            rec = MidsceneExecutionRecord.objects.get(id=call.args[0])
            expected = 1 if rec.device_id == self.devices[0].id else 2
            self.assertEqual(call.kwargs['replay_index'], expected)

    def test_batch_busy_device_others_ok(self):
        MidsceneExecutionRecord.objects.create(
            midscene_case=self.case, case_name=self.case.name,
            device=self.devices[1], platform='android', status='running',
            executed_by=self.owner,
        )
        resp, delay = self._post({'devices': [self.devices[0].id, self.devices[1].id, self.devices[2].id]})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['executions']), 2)
        self.assertEqual(len(resp.data['failed']), 1)
        self.assertIn('正在执行中', resp.data['failed'][0]['error'])
        self.assertEqual(delay.call_count, 2)

    def test_batch_unknown_device_failed(self):
        resp, delay = self._post({'devices': [self.devices[0].id, 99999]})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['executions']), 1)
        self.assertEqual(resp.data['failed'][0]['error'], '设备不存在')
        self.assertEqual(delay.call_count, 1)

    def test_single_device_legacy_format_unchanged(self):
        resp, _ = self._post({'device_id': self.devices[0].id})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('execution_id', resp.data)
        self.assertNotIn('executions', resp.data)


class BatchReplayMatchTests(TestCase):
    """批量回放匹配：每台设备各自返回匹配结果，分辨率读取失败降级 unknown。"""

    def setUp(self):
        self.owner = User.objects.create_user(username='owner-match-b', password='pass')
        main = Project.objects.create(name='主项目-match-b', owner=self.owner)
        project = MidsceneProject.objects.create(
            name='Midscene项目-match-b', owner=self.owner, main_project=main,
        )
        self.case = MidsceneCase.objects.create(
            project=project, name='批量匹配用例', ai_prompt='打开应用',
            created_by=self.owner,
        )
        self.case.replay_data = [{
            'name': 'Pixel 录制',
            'device': {'name': 'Pixel', 'platform': 'android',
                       'resolution': {'width': 1080, 'height': 2160}},
            'steps': [],
        }]
        self.case.save(update_fields=['replay_data'])
        self.dev_a = MidsceneDevice.objects.create(
            platform='android', device_id='dev-m0', name='Pixel',
            adb_serial='SERM0', status='online',
        )
        self.dev_b = MidsceneDevice.objects.create(
            platform='android', device_id='dev-m1', name='Redmi',
            adb_serial='SERM1', status='online',
        )
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def _post(self, devices):
        return self.client.post(
            f'/api/ui-automation/midscene/cases/{self.case.id}/replay_match_batch/',
            {'devices': devices, 'replay_index': 0}, format='json',
        )

    def test_batch_returns_per_device_result(self):
        def fake_size(serial):
            # 只有 Pixel 1080x2160 一条录制：dev_a 匹配 exact；dev_b 无匹配 → no_match
            return (720, 1600) if serial == 'SERM1' else (1080, 2160)

        with mock.patch.object(midscene_runner, 'adb_get_screen_size', side_effect=fake_size):
            resp = self._post([self.dev_a.id, self.dev_b.id])
        self.assertEqual(resp.status_code, 200, resp.data)
        results = resp.data['results']
        self.assertEqual(len(results), 2)
        by_id = {r['device_id']: r for r in results}
        self.assertEqual(by_id[self.dev_a.id]['match_level'], 'exact')
        self.assertEqual(by_id[self.dev_a.id]['recommended_index'], 0)
        self.assertFalse(by_id[self.dev_a.id]['needs_switch'])
        self.assertTrue(by_id[self.dev_a.id]['has_match'])
        self.assertEqual(by_id[self.dev_b.id]['match_level'], 'no_match')
        self.assertFalse(by_id[self.dev_b.id]['has_match'])
        # no_match 回退到当前选中索引（0），且不提示切换
        self.assertEqual(by_id[self.dev_b.id]['recommended_index'], 0)
        self.assertFalse(by_id[self.dev_b.id]['needs_switch'])
        self.assertIn('current_device', by_id[self.dev_a.id])

    def test_batch_resolution_fail_unknown(self):
        with mock.patch.object(
            midscene_runner, 'adb_get_screen_size',
            side_effect=RuntimeError('adb down'),
        ):
            resp = self._post([self.dev_a.id])
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['results'][0]['match_level'], 'unknown')
        self.assertTrue(resp.data['results'][0]['has_match'])
        self.assertEqual(resp.data['results'][0]['recommended_index'], 0)
        self.assertFalse(resp.data['results'][0]['needs_switch'])

    def test_batch_recommends_per_device_script(self):
        """两条录制分别对应两台设备：每台各自推荐自己的脚本，B 需要切换。"""
        self.case.replay_data = [
            {
                'name': 'Pixel 录制',
                'device': {'name': 'Pixel', 'platform': 'android',
                           'resolution': {'width': 1080, 'height': 2160}},
                'steps': [],
            },
            {
                'name': 'Redmi 录制',
                'device': {'name': 'Redmi', 'platform': 'android',
                           'resolution': {'width': 720, 'height': 1600}},
                'steps': [],
            },
        ]
        self.case.save(update_fields=['replay_data'])

        def fake_size(serial):
            return (720, 1600) if serial == 'SERM1' else (1080, 2160)

        with mock.patch.object(midscene_runner, 'adb_get_screen_size', side_effect=fake_size):
            resp = self._post([self.dev_a.id, self.dev_b.id])
        self.assertEqual(resp.status_code, 200, resp.data)
        by_id = {r['device_id']: r for r in resp.data['results']}
        # dev_a (Pixel) 推荐脚本 0（当前选中，无需切换）
        self.assertEqual(by_id[self.dev_a.id]['recommended_index'], 0)
        self.assertEqual(by_id[self.dev_a.id]['match_level'], 'exact')
        self.assertFalse(by_id[self.dev_a.id]['needs_switch'])
        # dev_b (Redmi) 推荐脚本 1，与当前选中不一致 → 提示切换
        self.assertEqual(by_id[self.dev_b.id]['recommended_index'], 1)
        self.assertEqual(by_id[self.dev_b.id]['match_level'], 'exact')
        self.assertTrue(by_id[self.dev_b.id]['needs_switch'])
        self.assertEqual(by_id[self.dev_b.id]['recommended_name'], 'Redmi 录制')

    def test_batch_unknown_device_has_error(self):
        resp = self._post([99999])
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['results'][0]['error'], '设备不存在')


class StopExecutionTests(TestCase):
    """停止语义：pending 直接 stopped；running 置 stopping，由 worker 确认后转 stopped。"""

    def setUp(self):
        self.owner = User.objects.create_user(username='owner-stop', password='pass')
        main = Project.objects.create(name='主项目-stop', owner=self.owner)
        project = MidsceneProject.objects.create(
            name='Midscene项目-stop', owner=self.owner, main_project=main,
        )
        self.case = MidsceneCase.objects.create(
            project=project, name='停止用例', ai_prompt='点击登录\n打开应用',
            created_by=self.owner,
        )
        self.device = MidsceneDevice.objects.create(
            platform='android', device_id='dev-stop', name='Pixel Stop',
            adb_serial='SERS', status='online',
        )
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def _record(self, status='running', task_id='TASK-STOP'):
        return MidsceneExecutionRecord.objects.create(
            midscene_case=self.case, case_name=self.case.name,
            device=self.device, platform='android', status=status,
            task_id=task_id, executed_by=self.owner,
        )

    def _stop(self, exec_id):
        with mock.patch.object(celery.current_app.control, 'revoke') as rev:
            resp = self.client.post(f'/api/ui-automation/midscene/executions/{exec_id}/stop/')
        return resp

    def test_stop_pending_sets_stopped(self):
        rec = self._record('pending')
        resp = self._stop(rec.id)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['status'], 'stopped')
        rec.refresh_from_db()
        self.assertEqual(rec.status, 'stopped')
        self.assertIsNotNone(rec.finished_at)

    def test_stop_running_sets_stopping(self):
        rec = self._record('running')
        resp = self._stop(rec.id)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['status'], 'stopping')
        rec.refresh_from_db()
        self.assertEqual(rec.status, 'stopping')
        # 未真正停止前不写结束时间，由 worker 确认时再收尾
        self.assertIsNone(rec.finished_at)

    def test_worker_confirms_stopping_on_start(self):
        rec = self._record('stopping')
        from apps.ui_automation.tasks import execute_midscene_task
        result = execute_midscene_task(rec.id)
        self.assertEqual(result, 'stopped')
        rec.refresh_from_db()
        self.assertEqual(rec.status, 'stopped')
        self.assertIsNotNone(rec.finished_at)

    def test_stop_twice_rejected(self):
        rec = self._record('running')
        self.assertEqual(self._stop(rec.id).status_code, 200)
        resp = self._stop(rec.id)
        self.assertEqual(resp.status_code, 400, resp.data)
        rec.refresh_from_db()
        self.assertEqual(rec.status, 'stopping')
