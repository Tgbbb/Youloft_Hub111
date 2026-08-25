# -*- coding: utf-8 -*-
"""工具合集 - 推送对比模块测试"""
from unittest import mock
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.toolbox import push_check_engine
from apps.toolbox import sync_check_engine
from apps.toolbox.models import ToolboxConfig, PushCheckRun, SyncCheckConfig, SyncCheckRun
from apps.toolbox.tasks import (
    run_push_check,
    run_sync_check_tick,
    run_sync_check as run_sync_check_task,
    _has_push_today,
)

User = get_user_model()

SAMPLE_HTML = (
    '<table><tr>'
    '<td>日期</td><td>时间</td><td>客户端</td><td>推送App</td><td>推送地区</td>'
    '<td>类型</td><td>标题</td><td>描述</td><td>链接</td>'
    '</tr><tr>'
    '<td>8/20</td><td>10:00</td><td>iOS</td><td>万年历</td><td>all</td>'
    '<td></td><td>标题A</td><td>描述A</td><td>http://x/abc?key=123</td>'
    '</tr></table>'
)


def make_email_data(**overrides):
    data = {
        'uid': 1001,
        'date': '2026-08-20T02:00:00.000Z',
        'subject': 'PUSH 测试需求 8月20日',
        'text': '',
        'html': SAMPLE_HTML,
        'attachments': [],
    }
    data.update(overrides)
    return data


def make_backend_record(**overrides):
    rec = {
        'id': 1,
        'taskId': '',
        'taskName': '任务A',
        'taskTitle': '标题A',
        'taskBody': '描述A',
        'url': 'http://x/abc?key=123',
        'versionType': '7',
        'versionValues': '',
        'versionTypeIOS': '1',
        'versionValuesIOS': '',
        'inQueue': 0,
        'icon': '',
        'citys': '',
        'checkItem': '',
        'pushTarget': '0',
        'taskStatus': '0',
    }
    rec.update(overrides)
    return rec


def make_search_result(records):
    return {'succ': True, 'record': {'records': records}}


def make_config(**overrides):
    cfg = {
        'imap': {
            'host': 'imap.example.com',
            'port': 993,
            'user': 'tester',
            'password': 'secret',
            'timeout': 20,
        },
        'backend': {'host': '192.168.1.110', 'port': 8015},
        'push_cookie': 'TaskControl20260820=abc',
        'tesseract_path': '',
    }
    for key, value in overrides.items():
        cfg[key] = value
    return cfg


class PushCheckEngineTests(TestCase):
    """引擎逻辑：解析、跳过、对比、改时间。"""

    def test_parse_schedule_html(self):
        pushes = push_check_engine.parse_schedule_html(SAMPLE_HTML)
        self.assertEqual(len(pushes), 1)
        self.assertEqual(pushes[0]['title'], '标题A')
        self.assertEqual(pushes[0]['platforms'][0]['key'], '123')
        self.assertEqual(pushes[0]['platforms'][0]['client'], 'iOS')

    def test_missing_imap_config(self):
        cfg = make_config()
        cfg['imap']['user'] = ''
        result = push_check_engine.run_push_check_engine(config=cfg, state={})
        self.assertFalse(result['ok'])
        self.assertIn('未配置 IMAP', result['summary']['message'])

    def test_no_new_email(self):
        with mock.patch.object(push_check_engine, 'find_latest_push_email', return_value=None):
            result = push_check_engine.run_push_check_engine(config=make_config(), state={})
        self.assertTrue(result['ok'])
        self.assertEqual(result['summary']['message'], '最近2天无新推送邮件')

    def test_full_pass_edits_time(self):
        with mock.patch.object(
            push_check_engine, 'find_latest_push_email', return_value=make_email_data()
        ), mock.patch.object(
            push_check_engine, 'search_push', return_value=make_search_result([make_backend_record()])
        ), mock.patch.object(
            push_check_engine, 'edit_time', return_value={'Success': True}
        ) as mock_edit:
            result = push_check_engine.run_push_check_engine(config=make_config(), state={})
        self.assertTrue(result['ok'])
        self.assertEqual(result['summary']['edited'], 1)
        self.assertEqual(result['summary']['problems'], 0)
        self.assertEqual(result['state']['lastUid'], 1001)
        mock_edit.assert_called_once()

    def test_problems_not_modified(self):
        rec = make_backend_record(taskTitle='其他标题')
        with mock.patch.object(
            push_check_engine, 'find_latest_push_email', return_value=make_email_data()
        ), mock.patch.object(
            push_check_engine, 'search_push', return_value=make_search_result([rec])
        ), mock.patch.object(
            push_check_engine, 'edit_time', return_value={'Success': True}
        ) as mock_edit:
            result = push_check_engine.run_push_check_engine(config=make_config(), state={})
        self.assertFalse(result['ok'])
        self.assertEqual(result['summary']['problems'], 1)
        self.assertEqual(result['summary']['edited'], 0)
        mock_edit.assert_not_called()

    def test_already_processed_skip_and_force(self):
        state = {'lastDate': '2026-08-20T02:00:00.000Z', 'lastUid': 1001, 'problems': 0}
        with mock.patch.object(
            push_check_engine, 'find_latest_push_email', return_value=make_email_data()
        ), mock.patch.object(push_check_engine, 'search_push') as mock_search:
            result = push_check_engine.run_push_check_engine(config=make_config(), state=state)
        self.assertTrue(result['ok'])
        self.assertIn('已处理', result['summary']['message'])
        mock_search.assert_not_called()

        with mock.patch.object(
            push_check_engine, 'find_latest_push_email', return_value=make_email_data()
        ), mock.patch.object(
            push_check_engine, 'search_push', return_value=make_search_result([make_backend_record()])
        ), mock.patch.object(push_check_engine, 'edit_time', return_value={'Success': True}):
            result = push_check_engine.run_push_check_engine(
                config=make_config(), state=state, force=True)
        self.assertTrue(result['ok'])
        self.assertEqual(result['summary']['edited'], 1)


class PushCheckApiTests(TestCase):
    """配置与运行 API。"""

    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='pass')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_config_api_requires_auth(self):
        anonymous = APIClient()
        resp = anonymous.get('/api/tools/push-check/config/')
        self.assertEqual(resp.status_code, 401)

    def test_config_mask_and_update(self):
        resp = self.client.put(
            '/api/tools/push-check/config/',
            {
                'imap_host': 'imap.qiye.aliyun.com',
                'imap_port': 993,
                'imap_user': 'u@x.com',
                'imap_password': 'secret1234',
                'imap_timeout': 20,
                'backend_host': '192.168.1.110',
                'backend_port': 8015,
                'push_cookie': 'TaskControl20260820=abc',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['imap_password'], '****1234')
        self.assertEqual(resp.data['push_cookie'], '****=abc')

        resp = self.client.get('/api/tools/push-check/config/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['imap_password'], '****1234')

        # 空密码/空Cookie 表示不修改
        resp = self.client.put('/api/tools/push-check/config/', {'imap_password': ''}, format='json')
        self.assertEqual(resp.status_code, 200)
        cfg = ToolboxConfig.get_singleton()
        self.assertEqual(cfg.imap_password, 'secret1234')
        self.assertEqual(cfg.push_cookie, 'TaskControl20260820=abc')

    def test_run_api_dispatch_and_conflict(self):
        with mock.patch('apps.toolbox.views.run_push_check.delay') as mock_delay:
            resp = self.client.post('/api/tools/push-check/run/', {'force': True}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        run_id = resp.data['id']
        self.assertEqual(resp.data['force'], True)
        mock_delay.assert_called_once_with(run_id)

        PushCheckRun.objects.create(status='running', user=self.user)
        resp = self.client.post('/api/tools/push-check/run/', {'force': False}, format='json')
        self.assertEqual(resp.status_code, 409)

        resp = self.client.get('/api/tools/push-check/runs/')
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.data['count'], 1)

    def test_run_detail(self):
        run = PushCheckRun.objects.create(
            status='success', user=self.user, log='日志内容',
            summary={'message': '完成', 'problems': 0},
        )
        resp = self.client.get(f'/api/tools/push-check/runs/{run.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['log'], '日志内容')
        self.assertEqual(resp.data['summary']['message'], '完成')

        resp = self.client.get('/api/tools/push-check/runs/999999/')
        self.assertEqual(resp.status_code, 404)

    def test_clear_history(self):
        PushCheckRun.objects.create(status='success', user=self.user)
        PushCheckRun.objects.create(status='failed', user=self.user)
        resp = self.client.delete('/api/tools/push-check/runs/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['deleted'], 2)
        self.assertEqual(PushCheckRun.objects.count(), 0)

    def test_clear_history_blocked_while_running(self):
        PushCheckRun.objects.create(status='running', user=self.user)
        resp = self.client.delete('/api/tools/push-check/runs/')
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(PushCheckRun.objects.count(), 1)


class PushCheckTaskTests(TestCase):
    """Celery 任务：状态流转与状态回写。"""

    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='pass')

    def test_task_persists_state_and_result(self):
        cfg = ToolboxConfig.get_singleton()
        cfg.last_uid = None
        cfg.last_date = ''
        cfg.last_problems = 0
        cfg.save(update_fields=['last_uid', 'last_date', 'last_problems'])
        run = PushCheckRun.objects.create(status='pending', user=self.user)
        engine_result = {
            'ok': True,
            'summary': {'message': '完成', 'edited': 2, 'problems': 0, 'skipped': 0},
            'log': '运行日志',
            'state': {'lastUid': 2002, 'lastDate': '2026-08-20T02:00:00.000Z', 'problems': 0},
        }
        with mock.patch(
            'apps.toolbox.tasks.run_push_check_engine', return_value=engine_result
        ):
            run_push_check.run(run.id)
        run.refresh_from_db()
        cfg.refresh_from_db()
        self.assertEqual(run.status, 'success')
        self.assertEqual(run.log, '运行日志')
        self.assertEqual(run.summary['message'], '完成')
        self.assertIsNotNone(run.finished_at)
        self.assertEqual(cfg.last_uid, 2002)
        self.assertEqual(cfg.last_date, '2026-08-20T02:00:00.000Z')

    def test_task_marks_failed_on_exception(self):
        run = PushCheckRun.objects.create(status='pending', user=self.user)
        with mock.patch(
            'apps.toolbox.tasks.run_push_check_engine',
            side_effect=RuntimeError('boom'),
        ):
            run_push_check.run(run.id)
        run.refresh_from_db()
        self.assertEqual(run.status, 'failed')
        self.assertEqual(run.summary['message'], 'boom')


SYNC_OCR_TEXT = (
    '推送目标：主包、黄历\n'
    '推送标题：标题A\n'
    '推送内容：内容B\n'
    '安卓版本：all\n'
    'IOS版本：all'
)


def make_sync_email(**overrides):
    data = {
        'uid': 5001,
        'date': '2026-08-24T02:00:00.000Z',
        'subject': '回复：【测试需求】关于常规PUSH的测试需求',
        'text': '已同步至线上~',
        'html': '',
        'attachments': [{'content': b'fake-image', 'size': 10000, 'contentType': 'image/png'}],
    }
    data.update(overrides)
    return data


class SyncCheckEngineTests(TestCase):
    """同步确认引擎：OCR 提取、归一化、对比、超时与重复处理。"""

    def _base_config(self):
        cfg = make_config()
        cfg.update({
            'require_push_activity': True,
            'has_push_today': True,
            'deadline_time': '23:59',
            'mail_subject': '回复：【测试需求】关于常规PUSH的测试需求',
            'mail_body_keyword': '已同步至线上',
        })
        return cfg

    def test_ocr_extract_sync_fields(self):
        parsed = sync_check_engine.ocr_extract_sync_fields(SYNC_OCR_TEXT)
        self.assertEqual(parsed['fields']['push_target'], '主包、黄历')
        self.assertEqual(parsed['fields']['title'], '标题A')
        self.assertEqual(parsed['fields']['content'], '内容B')
        self.assertEqual(parsed['fields']['android_version'], 'all')
        self.assertEqual(parsed['fields']['ios_version'], 'all')

    def test_norm_functions(self):
        self.assertEqual(sync_check_engine.norm_push_target('主包、黄历'), '0,1')
        self.assertEqual(sync_check_engine.norm_push_target('鸿蒙'), '2')
        self.assertEqual(sync_check_engine.norm_push_target('iOS、安卓'), '0,1')
        self.assertEqual(sync_check_engine.norm_version('all'), '1')
        self.assertEqual(sync_check_engine.norm_version('不向iOS推送'), '7')
        self.assertEqual(sync_check_engine.norm_version('7'), '7')

    def test_no_email_keeps_pending(self):
        with mock.patch.object(sync_check_engine, 'find_sync_email', return_value=None):
            result = sync_check_engine.run_sync_check_engine(config=self._base_config(), state={})
        self.assertTrue(result['ok'])
        self.assertEqual(result['summary']['status'], 'pending')
        self.assertFalse(result['state']['done'])

    def test_timeout_after_deadline(self):
        cfg = self._base_config()
        cfg['deadline_time'] = '00:00'
        with mock.patch.object(sync_check_engine, 'find_sync_email') as mock_find:
            result = sync_check_engine.run_sync_check_engine(config=cfg, state={})
        self.assertFalse(result['ok'])
        self.assertEqual(result['summary']['status'], 'timeout')
        self.assertTrue(result['state']['done'])
        mock_find.assert_not_called()

    def test_skip_when_no_push_activity(self):
        cfg = self._base_config()
        cfg['has_push_today'] = False
        cfg['deadline_time'] = '00:00'
        with mock.patch.object(sync_check_engine, 'find_sync_email') as mock_find:
            result = sync_check_engine.run_sync_check_engine(config=cfg, state={})
        self.assertTrue(result['ok'])
        self.assertEqual(result['summary']['status'], 'pending')
        self.assertFalse(result['state']['done'])
        mock_find.assert_not_called()

    def test_no_require_push_activity_continues(self):
        cfg = self._base_config()
        cfg['require_push_activity'] = False
        cfg['has_push_today'] = False
        with mock.patch.object(sync_check_engine, 'find_sync_email', return_value=None):
            result = sync_check_engine.run_sync_check_engine(config=cfg, state={})
        self.assertTrue(result['ok'])
        self.assertEqual(result['summary']['status'], 'pending')

    def test_compare_ok(self):
        rec = make_backend_record(
            taskTitle='标题A', taskBody='内容B', pushTarget='0,1',
            versionType='1', versionTypeIOS='1')
        with mock.patch.object(
            sync_check_engine, 'find_sync_email', return_value=make_sync_email()
        ), mock.patch.object(
            push_check_engine, 'ocr_image', return_value=SYNC_OCR_TEXT
        ), mock.patch.object(
            push_check_engine, 'search_push', return_value=make_search_result([rec])
        ):
            result = sync_check_engine.run_sync_check_engine(config=self._base_config(), state={})
        self.assertTrue(result['ok'])
        self.assertEqual(result['summary']['status'], 'ok')
        self.assertEqual(result['summary']['diffs'], [])
        self.assertEqual(result['state']['done'], True)
        self.assertEqual(result['state']['mail_uid'], 5001)

    def test_compare_fail_lists_diffs(self):
        rec = make_backend_record(
            taskTitle='其他标题', taskBody='内容B', pushTarget='0,1',
            versionType='1', versionTypeIOS='1')
        with mock.patch.object(
            sync_check_engine, 'find_sync_email', return_value=make_sync_email()
        ), mock.patch.object(
            push_check_engine, 'ocr_image', return_value=SYNC_OCR_TEXT
        ), mock.patch.object(
            push_check_engine, 'search_push', return_value=make_search_result([rec])
        ):
            result = sync_check_engine.run_sync_check_engine(config=self._base_config(), state={})
        self.assertFalse(result['ok'])
        self.assertEqual(result['summary']['status'], 'fail')
        self.assertTrue(any('标题不一致' in d for d in result['summary']['diffs']))

    def test_ocr_missing_marks_fail(self):
        with mock.patch.object(
            sync_check_engine, 'find_sync_email', return_value=make_sync_email()
        ), mock.patch.object(push_check_engine, 'ocr_image', return_value=None):
            result = sync_check_engine.run_sync_check_engine(config=self._base_config(), state={})
        self.assertFalse(result['ok'])
        self.assertEqual(result['summary']['status'], 'fail')
        self.assertIn('未解析出配置图片', result['summary']['message'])

    def test_already_done_skip_and_force(self):
        state = {
            'done': True, 'status': 'ok', 'mail_uid': 5001, 'mail_subject': '回复',
            'parsed_fields': {}, 'backend_record': {}, 'diffs': [], 'checked_at': None,
        }
        with mock.patch.object(sync_check_engine, 'find_sync_email') as mock_find:
            result = sync_check_engine.run_sync_check_engine(config=self._base_config(), state=state)
        self.assertTrue(result['ok'])
        self.assertEqual(result['summary']['status'], 'ok')
        mock_find.assert_not_called()

        rec = make_backend_record(
            taskTitle='标题A', taskBody='内容B', pushTarget='0,1',
            versionType='1', versionTypeIOS='1')
        with mock.patch.object(
            sync_check_engine, 'find_sync_email', return_value=make_sync_email()
        ), mock.patch.object(
            push_check_engine, 'ocr_image', return_value=SYNC_OCR_TEXT
        ), mock.patch.object(
            push_check_engine, 'search_push', return_value=make_search_result([rec])
        ):
            result = sync_check_engine.run_sync_check_engine(
                config=self._base_config(), state=state, force=True)
        self.assertEqual(result['summary']['status'], 'ok')


class SyncCheckApiTests(TestCase):
    """同步确认 API。"""

    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='pass')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_config_requires_auth_and_update(self):
        anonymous = APIClient()
        resp = anonymous.get('/api/tools/sync-check/config/')
        self.assertEqual(resp.status_code, 401)

        resp = self.client.get('/api/tools/sync-check/config/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['interval_minutes'], 15)

        resp = self.client.put('/api/tools/sync-check/config/', {'interval_minutes': 30}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['interval_minutes'], 30)
        cfg = SyncCheckConfig.get_singleton()
        self.assertEqual(cfg.interval_minutes, 30)

    def test_today_and_history(self):
        SyncCheckRun.objects.create(date='2026-08-23', status='ok')
        resp = self.client.get('/api/tools/sync-check/runs/today/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'pending')

        resp = self.client.get('/api/tools/sync-check/runs/')
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.data['count'], 2)

        resp = self.client.delete('/api/tools/sync-check/runs/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertGreaterEqual(resp.data['deleted'], 2)
        self.assertEqual(SyncCheckRun.objects.count(), 0)

        resp = self.client.delete('/api/tools/sync-check/runs/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['deleted'], 0)

    def test_manual_trigger(self):
        with mock.patch('apps.toolbox.views.run_sync_check.delay') as mock_delay:
            resp = self.client.post('/api/tools/sync-check/run/', {'force': True}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        mock_delay.assert_called_once_with(True)


class SyncCheckTaskTests(TestCase):
    """同步确认 tick 节流与结果持久化。"""

    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='pass')
        SyncCheckRun.objects.all().delete()

    def test_tick_throttle(self):
        cfg = SyncCheckConfig.get_singleton()
        cfg.last_check_at = timezone.now()
        cfg.save(update_fields=['last_check_at'])
        with mock.patch('apps.toolbox.tasks._execute_sync_check') as mock_exec:
            run_sync_check_tick.run()
        mock_exec.assert_not_called()

        cfg.last_check_at = timezone.now() - timedelta(minutes=30)
        cfg.save(update_fields=['last_check_at'])
        with mock.patch('apps.toolbox.tasks._execute_sync_check') as mock_exec:
            run_sync_check_tick.run()
        mock_exec.assert_called_once_with(force=False)

    def test_tick_disabled(self):
        cfg = SyncCheckConfig.get_singleton()
        cfg.enabled = False
        cfg.last_check_at = None
        cfg.save(update_fields=['enabled', 'last_check_at'])
        with mock.patch('apps.toolbox.tasks._execute_sync_check') as mock_exec:
            run_sync_check_tick.run()
        mock_exec.assert_not_called()

    def test_execute_persists_today(self):
        cfg = SyncCheckConfig.get_singleton()
        cfg.enabled = True
        cfg.save(update_fields=['enabled'])
        engine_result = {
            'ok': True,
            'summary': {'status': 'ok', 'message': '对比全部通过'},
            'log': '✔ 对比全部通过',
            'state': {
                'done': True, 'status': 'ok', 'mail_uid': 5001, 'mail_subject': '回复',
                'parsed_fields': {'title': '标题A'}, 'backend_record': {'id': 1},
                'diffs': [], 'checked_at': '2026-08-24T02:00:00',
            },
        }
        with mock.patch(
            'apps.toolbox.tasks.run_sync_check_engine', return_value=engine_result
        ), mock.patch('apps.toolbox.tasks._has_push_today', return_value=True):
            run_sync_check_task.run(force=False)
        run = SyncCheckRun.objects.get(date=timezone.localdate())
        self.assertEqual(run.status, 'ok')
        self.assertEqual(run.mail_uid, 5001)
        self.assertEqual(run.parsed_fields['title'], '标题A')
        self.assertIn('对比全部通过', run.log)
        cfg.refresh_from_db()
        self.assertIsNotNone(cfg.last_check_at)

    def test_has_push_today_detection(self):
        self.assertFalse(_has_push_today())
        PushCheckRun.objects.create(user=self.user, status='success')
        self.assertTrue(_has_push_today())
