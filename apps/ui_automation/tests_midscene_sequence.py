# -*- coding: utf-8 -*-
"""Midscene 用例编排：回放索引解析 + 项级安装包换包链路。"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.projects.models import Project
from apps.requirement_analysis.models import AIModelConfig
from apps.ui_automation import tasks as midscene_tasks
from apps.ui_automation.models import (
    MidsceneAppPackage, MidsceneCase, MidsceneDevice, MidsceneExecutionRecord,
    MidsceneProject, MidsceneSequence, MidsceneSequenceItem, MidsceneSequenceRun,
)

User = get_user_model()


class SequenceModelTests(SimpleTestCase):
    def test_execution_status_has_skipped(self):
        statuses = [c[0] for c in MidsceneExecutionRecord.STATUS_CHOICES]
        self.assertIn('skipped', statuses)

    def test_item_replay_mode_choices(self):
        choices = [c[0] for c in MidsceneSequenceItem.REPLAY_MODE_CHOICES]
        self.assertEqual(choices, ['auto', 'fixed'])


class SequenceReplayIndexTests(SimpleTestCase):
    def _item(self, replay_mode, replay_index, replay_data):
        item = mock.Mock(replay_mode=replay_mode, replay_index=replay_index)
        item.case = mock.Mock(replay_data=replay_data)
        return item

    def test_fixed_uses_replay_index(self):
        dev = mock.Mock(platform='android', name='X')
        it = self._item('fixed', 7, [{'device': {'platform': 'android'}}])
        self.assertEqual(midscene_tasks._resolve_replay_index(dev, it), 7)

    def test_auto_uses_recommended_index(self):
        dev = mock.Mock(platform='android', name='X')
        it = self._item('auto', 0, [{'device': {'platform': 'android'}}])
        with mock.patch('apps.ui_automation.views_midscene._pick_best_replay',
                        return_value={'recommended_index': 3}):
            self.assertEqual(midscene_tasks._resolve_replay_index(dev, it), 3)

    def test_auto_fallback_latest_when_no_match(self):
        dev = mock.Mock(platform='android', name='X')
        it = self._item('auto', 0, [{'device': {'platform': 'android'}}])
        with mock.patch('apps.ui_automation.views_midscene._pick_best_replay',
                        return_value={'recommended_index': None}):
            self.assertEqual(midscene_tasks._resolve_replay_index(dev, it), 0)

    def test_auto_no_replay_data_falls_back_latest(self):
        dev = mock.Mock(platform='android', name='X')
        it = self._item('auto', 0, None)
        self.assertEqual(midscene_tasks._resolve_replay_index(dev, it), 0)


class SequenceItemInstallTaskTests(TestCase):
    """编排项级安装包：循环内按项安装、clear/skip 语义、链级默认包。"""

    def setUp(self):
        self.user = User.objects.create_user(username='seq-pkg', password='pass')
        main = Project.objects.create(name='主项目-seqpkg', owner=self.user)
        project = MidsceneProject.objects.create(
            name='Midscene项目-seqpkg', owner=self.user, main_project=main,
        )
        self.model_config = AIModelConfig.objects.create(
            name='测试VLM', model_type='qwen', role='app_automation_vision',
            api_key='k', base_url='https://example.com', model_name='qwen-test',
            created_by=self.user,
        )
        self.device = MidsceneDevice.objects.create(
            platform='android', device_id='SERX', name='升级机',
            status='available', adb_serial='SERX',
        )
        self.case = MidsceneCase.objects.create(
            project=project, name='打包步骤', ai_prompt='点击登录\n打开应用',
            ai_model_config=self.model_config, created_by=self.user,
        )
        self.pkg_old = MidsceneAppPackage.objects.create(
            name='旧版', platform='android', package_name='com.example.old',
            version_name='1.0.0', version_code='1',
            file=SimpleUploadedFile('old.apk', b'old', content_type='application/octet-stream'),
            created_by=self.user,
        )
        self.pkg_new = MidsceneAppPackage.objects.create(
            name='新版', platform='android', package_name='com.example.new',
            version_name='2.0.0', version_code='2',
            file=SimpleUploadedFile('new.apk', b'new', content_type='application/octet-stream'),
            created_by=self.user,
        )
        self.sequence = MidsceneSequence.objects.create(name='升级链路', created_by=self.user)

    def _item(self, order, pkg=None, clear=False):
        return MidsceneSequenceItem.objects.create(
            sequence=self.sequence, order=order, case=self.case,
            clear_relaunch=clear, break_on_fail=True,
            replay_mode='fixed', replay_index=0, install_package=pkg,
        )

    def _run(self, items_total):
        return MidsceneSequenceRun.objects.create(
            sequence=self.sequence, sequence_name=self.sequence.name,
            device=self.device, platform='android', status='pending',
            total_steps=items_total, executed_by=self.user,
        )

    def _patch_passed(self):
        result = {'status': 'passed', 'totalSteps': 2, 'passedSteps': 2,
                  'failedSteps': 0, 'steps': [], 'replay_data': None}
        return (mock.patch('apps.ui_automation.midscene_runner.run_midscene_test',
                           return_value=result),
                mock.patch('apps.ui_automation.tasks.run_package_install',
                           return_value=(True, 'ok', '')))

    def test_per_item_package_switch_chain(self):
        # 装旧版(清数据) -> 复用 -> 覆盖装新版(不清数据) -> 验证复用
        self._item(0, pkg=self.pkg_old, clear=True)
        self._item(1, pkg=None, clear=False)
        self._item(2, pkg=self.pkg_new, clear=False)
        self._item(3, pkg=None, clear=False)
        run = self._run(4)
        p_test, p_install = self._patch_passed()
        with p_test as run_test, p_install as run_install:
            from apps.ui_automation.tasks import execute_midscene_sequence_task
            status = execute_midscene_sequence_task(run.id)
        self.assertEqual(status, 'passed')
        run.refresh_from_db()
        self.assertEqual(run.status, 'passed')
        # 两次安装：旧版、新版
        self.assertEqual(len(run_install.call_args_list), 2)
        self.assertEqual(run_install.call_args_list[0].args[0], self.pkg_old)
        self.assertEqual(run_install.call_args_list[0].args[1], self.device)
        self.assertEqual(run_install.call_args_list[0].args[2], {'overwrite': True})
        self.assertEqual(run_install.call_args_list[1].args[0], self.pkg_new)
        calls = run_test.call_args_list
        self.assertEqual(len(calls), 4)
        self.assertEqual(calls[0].kwargs['app_package_override'], 'com.example.old')
        self.assertTrue(calls[0].kwargs['clear_app_data'])
        self.assertFalse(calls[0].kwargs['skip_launch'])
        self.assertEqual(calls[1].kwargs['app_package_override'], '')
        self.assertFalse(calls[1].kwargs['clear_app_data'])
        self.assertTrue(calls[1].kwargs['skip_launch'])
        self.assertEqual(calls[2].kwargs['app_package_override'], 'com.example.new')
        self.assertFalse(calls[2].kwargs['clear_app_data'])
        self.assertFalse(calls[2].kwargs['skip_launch'])
        self.assertEqual(calls[3].kwargs['app_package_override'], '')
        self.assertFalse(calls[3].kwargs['clear_app_data'])
        self.assertTrue(calls[3].kwargs['skip_launch'])
        childs = list(MidsceneExecutionRecord.objects.filter(sequence_run=run))
        self.assertEqual(len(childs), 4)
        self.assertTrue(all(c.status == 'passed' for c in childs))
        self.device.refresh_from_db()
        self.assertEqual(self.device.status, 'available')

    def test_chain_level_package_used_for_first_item_without_own(self):
        # 项未指定包时，链级 install_package_id 只作为首项默认包
        self._item(0, pkg=None, clear=True)
        self._item(1, pkg=None, clear=False)
        run = self._run(2)
        p_test, p_install = self._patch_passed()
        with p_test as run_test, p_install as run_install:
            from apps.ui_automation.tasks import execute_midscene_sequence_task
            status = execute_midscene_sequence_task(run.id, install_package_id=self.pkg_old.id)
        self.assertEqual(status, 'passed')
        self.assertEqual(len(run_install.call_args_list), 1)
        self.assertEqual(run_install.call_args.args[0], self.pkg_old)
        calls = run_test.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0].kwargs['app_package_override'], 'com.example.old')
        self.assertFalse(calls[0].kwargs['skip_launch'])
        self.assertEqual(calls[1].kwargs['app_package_override'], '')
        self.assertTrue(calls[1].kwargs['skip_launch'])

    def test_missing_item_package_marks_child_error(self):
        # 包在接口校验后被删除的竞态：任务内查不到包 -> 该项 error、整链 failed
        self._item(0, pkg=None, clear=False)
        run = self._run(1)
        p_test, p_install = self._patch_passed()
        fake_filter = mock.Mock(first=mock.Mock(return_value=None))
        with p_test as run_test, p_install as run_install, \
             mock.patch.object(MidsceneAppPackage.objects, 'filter',
                               return_value=fake_filter):
            from apps.ui_automation.tasks import execute_midscene_sequence_task
            status = execute_midscene_sequence_task(run.id, install_package_id=99999)
        self.assertEqual(status, 'failed')
        run.refresh_from_db()
        self.assertEqual(run.status, 'failed')
        run_test.assert_not_called()
        child = MidsceneExecutionRecord.objects.get(sequence_run=run)
        self.assertEqual(child.status, 'error')
        self.assertIn('安装包不存在', child.error_message)


class SequenceExecutePackageValidationTests(TestCase):
    """编排执行接口：项级/链级安装包与设备平台防呆。"""

    def setUp(self):
        self.user = User.objects.create_user(username='seq-api', password='pass')
        main = Project.objects.create(name='主项目-seqapi', owner=self.user)
        project = MidsceneProject.objects.create(
            name='Midscene项目-seqapi', owner=self.user, main_project=main,
        )
        self.case = MidsceneCase.objects.create(
            project=project, name='用例', ai_prompt='点击登录',
            created_by=self.user,
        )
        self.device_android = MidsceneDevice.objects.create(
            platform='android', device_id='SEQ-A', name='Android机',
            status='available', adb_serial='SEQ-A',
        )
        self.device_ios = MidsceneDevice.objects.create(
            platform='ios', device_id='SEQ-I', name='iPhone机',
            status='available', wda_host='127.0.0.1:8100',
        )
        self.pkg_android = MidsceneAppPackage.objects.create(
            name='安卓包', platform='android', package_name='com.example.a',
            file=SimpleUploadedFile('a.apk', b'a', content_type='application/octet-stream'),
            created_by=self.user,
        )
        self.pkg_ios = MidsceneAppPackage.objects.create(
            name='iOS包', platform='ios', package_name='com.example.b',
            file=SimpleUploadedFile('b.ipa', b'b', content_type='application/octet-stream'),
            created_by=self.user,
        )
        self.sequence = MidsceneSequence.objects.create(name='校验编排', created_by=self.user)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _item(self, pkg=None):
        return MidsceneSequenceItem.objects.create(
            sequence=self.sequence, order=0, case=self.case,
            clear_relaunch=True, break_on_fail=True,
            replay_mode='fixed', replay_index=0, install_package=pkg,
        )

    def _exec(self, device, pkg_id=None):
        payload = {'device_id': device.id}
        if pkg_id is not None:
            payload['install_package_id'] = pkg_id
        return self.client.post(
            f'/api/ui-automation/midscene/sequences/{self.sequence.id}/execute/',
            payload, format='json',
        )

    def test_item_package_platform_mismatch_400(self):
        self._item(pkg=self.pkg_ios)
        resp = self._exec(self.device_android)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('不匹配', resp.data['error'])
        self.assertEqual(MidsceneSequenceRun.objects.count(), 0)

    def test_chain_package_platform_mismatch_400(self):
        self._item(pkg=None)
        resp = self._exec(self.device_android, pkg_id=self.pkg_ios.id)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('不匹配', resp.data['error'])
        self.assertEqual(MidsceneSequenceRun.objects.count(), 0)
