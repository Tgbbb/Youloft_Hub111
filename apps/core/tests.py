"""核心模块测试"""
import re
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase
from django.test import TestCase

from apps.core.variable_resolver import VariableResolver
from apps.core.models import UnifiedNotificationConfig

User = get_user_model()


class VariableResolverTests(SimpleTestCase):
    """变量解析器回归测试：时间日期函数必须能被 ${func()} 正确替换。"""

    def setUp(self):
        self.resolver = VariableResolver()

    def test_time_date_functions_are_resolved(self):
        cases = [
            ("${timestamp()}", r"^\d{13}$"),
            ("${timestamp_sec()}", r"^\d{10}$"),
            ("${datetime()}", r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$"),
            ("${date()}", r"^\d{4}-\d{2}-\d{2}$"),
            ("${time()}", r"^\d{2}:\d{2}:\d{2}$"),
        ]
        for expr, pattern in cases:
            out = self.resolver.resolve("t=" + expr)
            self.assertNotIn("${", out, f"{expr} 未被替换")
            self.assertRegex(out.split("=", 1)[1], pattern)

    def test_datetime_with_custom_format(self):
        out = self.resolver.resolve("${datetime(%Y-%m-%d)}")
        self.assertNotIn("${", out)
        self.assertTrue(re.match(r"^\d{4}-\d{2}-\d{2}$", out))

    def test_date_offset_is_resolved(self):
        out = self.resolver.resolve("${date_offset(1)}")
        self.assertNotIn("${", out)
        out2 = self.resolver.resolve("${date_offset(0, 2)}")
        self.assertNotIn("${", out2)

    def test_unknown_function_left_as_is(self):
        self.assertEqual(
            self.resolver.resolve("${no_such_fn()}"),
            "${no_such_fn()}",
        )

    def test_random_tool_still_works(self):
        out = self.resolver.resolve("${random_int(1, 9)}")
        self.assertNotIn("${", out)


class CoreNotifyTests(TestCase):
    """统一通知钉钉发送器。"""

    def setUp(self):
        self.user = User.objects.create_user(username='bot', password='pass')

    def _config(self, bots):
        return UnifiedNotificationConfig.objects.create(
            name='钉钉', config_type='webhook_dingtalk',
            webhook_bots=bots, is_active=True, created_by=self.user)

    def test_no_active_bots_no_send(self):
        from apps.core.notifications import send_dingtalk_markdown
        self.assertEqual(send_dingtalk_markdown('T', 'X'), [])

    def test_send_with_secret_signs_url_and_payload(self):
        from apps.core.notifications import send_dingtalk_markdown
        bot = {
            'name': '钉钉群',
            'webhook_url': 'https://oapi.dingtalk.com/robot/send?access_token=abc',
            'enabled': True, 'secret': 'SEC',
        }
        self._config({'dingtalk': bot})
        with mock.patch('apps.core.notifications.requests.post') as m:
            m.return_value.status_code = 200
            m.return_value.json.return_value = {'errcode': 0, 'errmsg': 'ok'}
            res = send_dingtalk_markdown('T', 'X')
        self.assertTrue(res[0]['ok'])
        url = m.call_args[0][0]
        self.assertIn('timestamp=', url)
        self.assertIn('sign=', url)
        payload = m.call_args[1]['json']
        self.assertEqual(payload['msgtype'], 'markdown')
        self.assertEqual(payload['markdown']['title'], 'T')

    def test_send_failure_returns_error_not_raise(self):
        from apps.core.notifications import send_dingtalk_markdown
        bot = {'name': '钉钉群', 'webhook_url': 'https://x', 'enabled': True}
        self._config({'dingtalk': bot})
        with mock.patch(
            'apps.core.notifications.requests.post', side_effect=Exception('boom')):
            res = send_dingtalk_markdown('T', 'X')
        self.assertFalse(res[0]['ok'])
        self.assertIn('boom', res[0]['error'])

    def test_err_code_nonzero_is_failure(self):
        from apps.core.notifications import send_dingtalk_markdown
        bot = {'name': '钉钉群', 'webhook_url': 'https://x', 'enabled': True}
        self._config({'dingtalk': bot})
        with mock.patch('apps.core.notifications.requests.post') as m:
            m.return_value.status_code = 200
            m.return_value.json.return_value = {'errcode': 310000, 'errmsg': 'sign not match'}
            res = send_dingtalk_markdown('T', 'X')
        self.assertFalse(res[0]['ok'])
        self.assertIn('sign not match', res[0]['error'])
