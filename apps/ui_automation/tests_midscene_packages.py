# -*- coding: utf-8 -*-
"""Midscene 安装包管理测试：上传解析/去重/安装互斥/安装任务/删除。"""
import os
import shutil
import tempfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.projects.models import Project
from apps.requirement_analysis.models import AIModelConfig
from apps.ui_automation.models import (
    MidsceneProject, MidsceneCase, MidsceneDevice, MidsceneExecutionRecord,
    MidsceneAppPackage, MidsceneAppInstallRecord,
)

User = get_user_model()

_APK_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'venv', 'Lib', 'site-packages', 'airtest', 'core', 'android', 'static', 'apks', 'Yosemite.apk',
)


class MidscenePackageApiTests(TestCase):
    """安装包 API 与安装互斥逻辑。"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmp_root = tempfile.mkdtemp(prefix='pkgtest_')
        cls.media_override = override_settings(MEDIA_ROOT=cls.tmp_root)
        cls.media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.media_override.disable()
        shutil.rmtree(cls.tmp_root, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='pass')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.device = MidsceneDevice.objects.create(
            platform='android', device_id='serial1', name='测试机1',
            status='available', adb_serial='serial1',
        )
        self.delay_patcher = mock.patch(
            'apps.ui_automation.tasks.install_app_package_task.delay',
            return_value=mock.Mock(id='TASK-I'),
        )
        self.delay = self.delay_patcher.start()
        self.addCleanup(self.delay_patcher.stop)

    def _upload(self, filename, content):
        return self.client.post(
            '/api/ui-automation/midscene/packages/',
            {'file': SimpleUploadedFile(filename, content, content_type='application/octet-stream')},
            format='multipart',
        )

    def test_upload_apk_parses_metadata(self):
        with open(_APK_PATH, 'rb') as f:
            resp = self._upload('Yosemite.apk', f.read())
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['platform'], 'android')
        self.assertEqual(resp.data['package_name'], 'com.netease.nie.yosemite')
        self.assertEqual(resp.data['version_code'], '449')
        self.assertEqual(resp.data['version_name'], '1.1.0.449')
        self.assertTrue(resp.data['md5'])
        self.assertTrue(resp.data['file_size'] > 0)

    def test_duplicate_upload_rejected(self):
        with open(_APK_PATH, 'rb') as f:
            content = f.read()
        self.assertEqual(self._upload('Yosemite.apk', content).status_code, 201)
        resp = self._upload('Yosemite2.apk', content)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('已存在相同包名和版本', resp.data['error'])
        self.assertEqual(MidsceneAppPackage.objects.count(), 1)

    def test_unsupported_extension_rejected(self):
        resp = self._upload('foo.exe', b'x')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('不支持的文件类型', resp.data['error'])

    def test_ios_install_rejected(self):
        pkg = MidsceneAppPackage.objects.create(
            name='iOS包', platform='ios',
            file=SimpleUploadedFile('app.ipa', b'x', content_type='application/octet-stream'),
            created_by=self.user,
        )
        resp = self.client.post(f'/api/ui-automation/midscene/packages/{pkg.id}/install/',
                                {'device_ids': [self.device.id]}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('仅支持 Android', resp.data['error'])

    def test_install_offline_device_failed(self):
        pkg = self._make_android_pkg()
        self.device.status = 'offline'
        self.device.save(update_fields=['status'])
        resp = self.client.post(f'/api/ui-automation/midscene/packages/{pkg.id}/install/',
                                {'device_ids': [self.device.id]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['installs'], [])
        self.assertEqual(len(resp.data['failed']), 1)
        self.assertIn('不在线', resp.data['failed'][0]['error'])
        self.delay.assert_not_called()
        self.assertEqual(MidsceneAppInstallRecord.objects.count(), 0)

    def test_install_locked_by_other_failed(self):
        other = User.objects.create_user(username='other', password='pass')
        pkg = self._make_android_pkg()
        self.device.lock(other)
        resp = self.client.post(f'/api/ui-automation/midscene/packages/{pkg.id}/install/',
                                {'device_ids': [self.device.id]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['failed']), 1)
        self.assertIn('锁定', resp.data['failed'][0]['error'])
        self.delay.assert_not_called()

    def test_install_creates_record_and_dispatches(self):
        pkg = self._make_android_pkg()
        resp = self.client.post(f'/api/ui-automation/midscene/packages/{pkg.id}/install/',
                                {'device_ids': [self.device.id], 'overwrite': True, 'launch': True},
                                format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['installs']), 1)
        self.assertEqual(resp.data['failed'], [])
        self.delay.assert_called_once()
        record = MidsceneAppInstallRecord.objects.get(id=resp.data['installs'][0]['install_id'])
        self.assertEqual(record.status, 'pending')
        self.assertTrue(record.options['overwrite'])
        self.assertTrue(record.options['launch'])

    def test_install_record_list_filter(self):
        pkg = self._make_android_pkg()
        MidsceneAppInstallRecord.objects.create(package=pkg, device=self.device, status='success',
                                                created_by=self.user)
        resp = self.client.get(f'/api/ui-automation/midscene/install-records/?package={pkg.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['results']), 1)
        self.assertEqual(resp.data['results'][0]['status'], 'success')

    def test_delete_package_removes_record(self):
        pkg = self._make_android_pkg()
        pkg_id = pkg.id
        resp = self.client.delete(f'/api/ui-automation/midscene/packages/{pkg_id}/')
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(MidsceneAppPackage.objects.filter(id=pkg_id).exists())

    def _make_android_pkg(self):
        return MidsceneAppPackage.objects.create(
            name='测试包', platform='android',
            package_name='com.example.test', version_name='1.0.0', version_code='1',
            file=SimpleUploadedFile('test.apk', b'fake-apk', content_type='application/octet-stream'),
            created_by=self.user,
        )


class MidsceneInstallTaskTests(TestCase):
    """安装任务执行逻辑（mock adb）。"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmp_root = tempfile.mkdtemp(prefix='pkgtask_')
        cls.media_override = override_settings(MEDIA_ROOT=cls.tmp_root)
        cls.media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.media_override.disable()
        shutil.rmtree(cls.tmp_root, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='pass')
        self.device = MidsceneDevice.objects.create(
            platform='android', device_id='serial1', name='测试机1',
            status='available', adb_serial='serial1',
        )
        self.pkg = MidsceneAppPackage.objects.create(
            name='测试包', platform='android',
            package_name='com.example.test', version_name='1.0.0', version_code='1',
            file=SimpleUploadedFile('test.apk', b'fake-apk', content_type='application/octet-stream'),
            created_by=self.user,
        )

    def test_task_success_unlocks_device(self):
        record = MidsceneAppInstallRecord.objects.create(
            package=self.pkg, device=self.device, status='pending',
            options={'overwrite': True}, created_by=self.user,
        )
        with mock.patch('apps.ui_automation.tasks.subprocess.run',
                        return_value=mock.Mock(returncode=0, stdout='Success', stderr='')):
            status = None
            from apps.ui_automation.tasks import install_app_package_task
            status = install_app_package_task(record.id)
        record.refresh_from_db()
        self.assertEqual(status, 'success')
        self.assertEqual(record.status, 'success')
        self.assertGreater(record.duration, 0)
        self.device.refresh_from_db()
        self.assertEqual(self.device.status, 'available')

    def test_task_failure_marks_failed(self):
        record = MidsceneAppInstallRecord.objects.create(
            package=self.pkg, device=self.device, status='pending',
            options={'overwrite': True}, created_by=self.user,
        )
        with mock.patch('apps.ui_automation.tasks.subprocess.run',
                        return_value=mock.Mock(returncode=1, stdout='Failure', stderr='INSTALL_FAILED')):
            from apps.ui_automation.tasks import install_app_package_task
            status = install_app_package_task(record.id)
        record.refresh_from_db()
        self.assertEqual(status, 'failed')
        self.assertEqual(record.status, 'failed')
        self.assertIn('INSTALL_FAILED', record.error_message)


class ExecuteTaskInstallPackageTests(TestCase):
    """执行任务携带安装包：装包失败则执行失败，装包成功则传包名并强制清数据。"""

    def setUp(self):
        self.user = User.objects.create_user(username='exec-pkg', password='pass')
        main = Project.objects.create(name='主项目-execpkg', owner=self.user)
        project = MidsceneProject.objects.create(
            name='Midscene项目-execpkg', owner=self.user, main_project=main,
        )
        self.model_config = AIModelConfig.objects.create(
            name='测试VLM', model_type='qwen', role='app_automation_vision',
            api_key='k', base_url='https://example.com', model_name='qwen-test',
            created_by=self.user,
        )
        self.case = MidsceneCase.objects.create(
            project=project, name='装包执行', ai_prompt='点击登录\n打开应用',
            ai_model_config=self.model_config, created_by=self.user,
        )
        self.device = MidsceneDevice.objects.create(
            platform='android', device_id='serial1', name='测试机1',
            status='available', adb_serial='serial1',
        )
        self.pkg = MidsceneAppPackage.objects.create(
            name='测试包', platform='android',
            package_name='com.example.test', version_name='1.0.0', version_code='1',
            file=SimpleUploadedFile('test.apk', b'fake-apk', content_type='application/octet-stream'),
            created_by=self.user,
        )

    def _record(self):
        return MidsceneExecutionRecord.objects.create(
            midscene_case=self.case, case_name=self.case.name,
            device=self.device, platform='android', status='pending',
            executed_by=self.user,
        )

    def test_install_failure_marks_execution_error(self):
        rec = self._record()
        with mock.patch('apps.ui_automation.tasks.run_apk_install',
                        return_value=(False, 'log', 'INSTALL_FAILED')) as run_install, \
             mock.patch('apps.ui_automation.tasks.run_midscene_test') as run_test:
            from apps.ui_automation.tasks import execute_midscene_task
            result = execute_midscene_task(rec.id, install_package_id=self.pkg.id)
        self.assertEqual(result, 'error')
        rec.refresh_from_db()
        self.assertEqual(rec.status, 'error')
        self.assertIn('安装失败', rec.error_message)
        run_install.assert_called_once()
        run_test.assert_not_called()

    def test_install_success_passes_override_and_clear(self):
        rec = self._record()
        with mock.patch('apps.ui_automation.tasks.run_apk_install',
                        return_value=(True, 'Success', '')), \
             mock.patch('apps.ui_automation.tasks.run_midscene_test',
                        return_value={'status': 'passed', 'totalSteps': 0,
                                      'passedSteps': 0, 'failedSteps': 0,
                                      'steps': [], 'replay_data': None}) as run_test:
            from apps.ui_automation.tasks import execute_midscene_task
            result = execute_midscene_task(rec.id, install_package_id=self.pkg.id)
        self.assertEqual(result, 'passed')
        rec.refresh_from_db()
        self.assertEqual(rec.status, 'passed')
        kwargs = run_test.call_args.kwargs
        self.assertEqual(kwargs['app_package_override'], 'com.example.test')
        self.assertTrue(kwargs['clear_app_data'])

    def test_no_install_package_no_override(self):
        rec = self._record()
        with mock.patch('apps.ui_automation.tasks.run_midscene_test',
                        return_value={'status': 'passed', 'totalSteps': 0,
                                      'passedSteps': 0, 'failedSteps': 0,
                                      'steps': [], 'replay_data': None}) as run_test:
            from apps.ui_automation.tasks import execute_midscene_task
            result = execute_midscene_task(rec.id)
        self.assertEqual(result, 'passed')
        self.assertEqual(run_test.call_args.kwargs.get('app_package_override'), '')
