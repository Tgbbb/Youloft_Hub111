# -*- coding: utf-8 -*-
"""Midscene 执行接口互斥测试：同一设备同时只能有一个 pending/running 任务。"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.projects.models import Project
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
