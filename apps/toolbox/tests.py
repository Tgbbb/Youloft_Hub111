# -*- coding: utf-8 -*-
"""工具合集 - 推送对比模块测试"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.toolbox import push_check_engine
from apps.toolbox.models import ToolboxConfig, PushCheckRun
from apps.toolbox.tasks import run_push_check

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
