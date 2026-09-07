# -*- coding: utf-8 -*-
"""工具合集 - 配置回复提醒模块测试"""
import email
from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.toolbox import reply_check_engine
from apps.toolbox.models import ReplyCheckConfig, ReplyCheckRun
from apps.toolbox import tasks as toolbox_tasks

User = get_user_model()


def _msg(**headers):
    m = email.message.EmailMessage()
    for k, v in headers.items():
        m[k] = v
    return m


class ReplyCheckEngineLogicTests(SimpleTestCase):
    def test_normalize_subject_strips_cn_prefixes(self):
        self.assertEqual(
            reply_check_engine.normalize_subject('回复：回复：【测试需求】8.28配置'),
            '【测试需求】8.28配置')

    def test_normalize_subject_strips_ascii_prefix(self):
        self.assertEqual(
            reply_check_engine.normalize_subject('Re: 关于常规PUSH的测试需求'),
            '关于常规push的测试需求')

    def test_single_date_current_day_kept(self):
        self.assertFalse(reply_check_engine._has_nontoday_date('标题 8.28 配置', date(2026, 8, 28)))

    def test_single_date_other_day_skipped(self):
        self.assertTrue(reply_check_engine._has_nontoday_date('标题 8.28 配置', date(2026, 8, 27)))

    def test_range_covers_today(self):
        self.assertFalse(reply_check_engine._has_nontoday_date('8.28-8.29', date(2026, 8, 29)))

    def test_range_not_cover_today(self):
        self.assertTrue(reply_check_engine._has_nontoday_date('8.28-8.29', date(2026, 8, 30)))

    def test_range_cross_month(self):
        self.assertFalse(reply_check_engine._has_nontoday_date('8.30-9.1', date(2026, 9, 1)))

    def test_no_date_kept(self):
        self.assertFalse(reply_check_engine._has_nontoday_date('普通配置', date(2026, 8, 28)))

    def test_date_filter_ignores_decimals(self):
        self.assertFalse(reply_check_engine._has_nontoday_date('全局限价：0.5元 版本：6.0.0', date(2026, 9, 1)))

    def test_real_non_today_date_still_skipped(self):
        self.assertTrue(reply_check_engine._has_nontoday_date('标题 8.28 配置', date(2026, 9, 1)))

    def test_strip_script_style_removes_css(self):
        self.assertEqual(
            reply_check_engine._strip_script_style('<style>line-height:1.5;</style><p>正文</p>'),
            '<p>正文</p>')

    def test_recipient_match_by_keyword(self):
        m = _msg(To='品管部 <qc@youloft.com>')
        self.assertTrue(reply_check_engine._recipient_match(m, ['品管部']))
        self.assertTrue(reply_check_engine._recipient_match(m, ['qc@youloft.com']))

    def test_recipient_no_match(self):
        m = _msg(To='其他部门 <other@youloft.com>')
        self.assertFalse(reply_check_engine._recipient_match(m, ['品管部', 'qc@youloft.com']))

    def test_subject_match(self):
        self.assertTrue(reply_check_engine._subject_match('【测试需求】关于常规PUSH', ['测试需求']))
        self.assertFalse(reply_check_engine._subject_match('【日常】通知', ['测试需求']))

    def test_body_match_any_keyword(self):
        self.assertTrue(reply_check_engine._body_match('请QC检查，已核实', ['请QC检查']))
        self.assertTrue(reply_check_engine._body_match('请知悉，已核实内容', ['核对', '已核实', '复核']))
        self.assertFalse(reply_check_engine._body_match('无关内容', ['请QC检查']))

    def test_is_verified_text_true(self):
        self.assertTrue(reply_check_engine._is_verified_text('请QC检查，已验证'))
        self.assertTrue(reply_check_engine._is_verified_text('已核实，请知悉'))

    def test_is_verified_text_false(self):
        self.assertFalse(reply_check_engine._is_verified_text('请QC检查'))

    def test_is_verified_ignores_quoted_history(self):
        body = ('hi 大家好：辛苦配置如下：\n广告ID：123\n'
                '-------\n主　题：回复：旧邮件\n已验证\n已检查')
        self.assertFalse(reply_check_engine._is_verified_text(body))

    def test_build_search_candidates_short_prefix_fallback(self):
        from apps.toolbox import push_check_engine
        cands = push_check_engine.build_search_candidates('身体有恙，腿先知?')
        self.assertIn('身体有', cands)
        self.assertIn('身体有恙', cands)


class ReplyCheckApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='qccheck', password='x')
        self.client = APIClient()

    def test_config_requires_auth(self):
        resp = self.client.get('/api/tools/reply-check/config/')
        self.assertIn(resp.status_code, (401, 403))

    def test_config_get_and_put(self):
        self.client.force_authenticate(self.user)
        cfg = ReplyCheckConfig.get_singleton()
        self.assertIn('品管部', cfg.qc_recipient_keywords)
        resp = self.client.put(
            '/api/tools/reply-check/config/',
            {'notify_threshold_minutes': 45, 'enabled': True},
            format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['notify_threshold_minutes'], 45)

    def test_run_dispatches_task(self):
        self.client.force_authenticate(self.user)
        with mock.patch('apps.toolbox.views.run_reply_check') as task:
            resp = self.client.post('/api/tools/reply-check/run/', {'force': True}, format='json')
        self.assertEqual(resp.status_code, 201)
        task.delay.assert_called_once_with(True)

    def test_today_detail(self):
        self.client.force_authenticate(self.user)
        resp = self.client.get('/api/tools/reply-check/runs/today/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('unreplied_count', resp.data)


class ReplyCheckTaskTests(TestCase):
    def test_tick_throttles(self):
        cfg = ReplyCheckConfig.get_singleton()
        cfg.enabled = True
        cfg.interval_minutes = 15
        cfg.last_check_at = None
        cfg.save()
        with mock.patch('apps.toolbox.tasks.reply_check_engine.run_reply_check_engine') as eng:
            eng.return_value = {
                'ok': True, 'log': 'ok', 'summary': {'unreplied_count': 0,
                                                      'ad_unreplied_count': 0},
                'unreplied': [], 'state': {}}
            toolbox_tasks.run_reply_check_tick()
            self.assertTrue(eng.called)
            # 紧接着再触发，间隔未到应被节流
            eng.reset_mock()
            toolbox_tasks.run_reply_check_tick()
            self.assertFalse(eng.called)

    def test_tick_disabled_skips(self):
        cfg = ReplyCheckConfig.get_singleton()
        cfg.enabled = False
        cfg.save()
        with mock.patch('apps.toolbox.tasks.reply_check_engine.run_reply_check_engine') as eng:
            toolbox_tasks.run_reply_check_tick()
            self.assertFalse(eng.called)
