"""核心模块测试"""
import re

from django.test import SimpleTestCase

from apps.core.variable_resolver import VariableResolver


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
