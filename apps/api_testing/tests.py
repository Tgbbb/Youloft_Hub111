"""接口测试模块核心逻辑单元测试（执行服务 / 断言 / 变量提取 / 请求构建）"""
from types import SimpleNamespace

from django.test import SimpleTestCase

from .services import (
    VariableStore,
    build_request_payload,
    execute_assertions,
    safe_json_loads,
    _build_body,
)


class FakeResponse:
    def __init__(self, text='', headers=None, status_code=200):
        self.text = text
        self.headers = headers or {}
        self.status_code = status_code


class SafeJsonLoadsTest(SimpleTestCase):
    def test_valid_json(self):
        self.assertEqual(safe_json_loads('{"a": 1}'), {'a': 1})

    def test_invalid_json_returns_none(self):
        self.assertIsNone(safe_json_loads('<html>not json</html>'))

    def test_empty_returns_none(self):
        self.assertIsNone(safe_json_loads(''))


class AssertionTest(SimpleTestCase):
    def test_status_code_with_string_expected(self):
        response = FakeResponse(status_code=200)
        results = execute_assertions(response, [
            {'name': '状态码', 'type': 'status_code', 'expected': '200'}
        ])
        self.assertTrue(results[0]['passed'])
        self.assertEqual(results[0]['actual'], 200)

    def test_status_code_with_value_fallback(self):
        response = FakeResponse(status_code=404)
        results = execute_assertions(response, [
            {'name': '状态码', 'type': 'status_code', 'value': 404}
        ])
        self.assertTrue(results[0]['passed'])

    def test_json_path_numeric_comparison(self):
        response = FakeResponse('{"data": {"count": 3}}', {'content-type': 'application/json'})
        results = execute_assertions(response, [
            {'name': '数量', 'type': 'json_path', 'json_path': '$.data.count', 'expected': '3'}
        ])
        self.assertTrue(results[0]['passed'])

    def test_json_path_no_match(self):
        response = FakeResponse('{"data": {}}', {'content-type': 'application/json'})
        results = execute_assertions(response, [
            {'name': 'token', 'type': 'json_path', 'json_path': '$.data.token', 'expected': 'abc'}
        ])
        self.assertFalse(results[0]['passed'])
        self.assertIsNone(results[0]['actual'])

    def test_response_time_passed_externally(self):
        response = FakeResponse()
        results = execute_assertions(response, [
            {'name': '耗时', 'type': 'response_time', 'expected': 1000}
        ], response_time=500)
        self.assertTrue(results[0]['passed'])

    def test_response_time_zero_actual(self):
        response = FakeResponse()
        results = execute_assertions(response, [
            {'name': '耗时', 'type': 'response_time', 'expected': 1000}
        ], response_time=0)
        self.assertTrue(results[0]['passed'])

    def test_response_time_string_expected(self):
        response = FakeResponse()
        results = execute_assertions(response, [
            {'name': '耗时', 'type': 'response_time', 'expected': '1000'}
        ], response_time=500)
        self.assertTrue(results[0]['passed'])

    def test_header_assertion(self):
        response = FakeResponse(headers={'X-Token': 'abc'})
        results = execute_assertions(response, [
            {'name': '响应头', 'type': 'header', 'header_name': 'X-Token', 'expected_value': 'abc'}
        ])
        self.assertTrue(results[0]['passed'])

    def test_contains_assertion(self):
        response = FakeResponse('hello world')
        results = execute_assertions(response, [
            {'name': '包含', 'type': 'contains', 'expected': 'world'}
        ])
        self.assertTrue(results[0]['passed'])

    def test_equals_assertion(self):
        response = FakeResponse('  ok  ')
        results = execute_assertions(response, [
            {'name': '相等', 'type': 'equals', 'expected': 'ok'}
        ])
        self.assertTrue(results[0]['passed'])

    def test_assertion_dict_not_mutated(self):
        assertion = {'name': '耗时', 'type': 'response_time', 'expected': 1000}
        response = FakeResponse()
        execute_assertions(response, [assertion], response_time=200)
        self.assertNotIn('actual_time', assertion)

    def test_non_json_response_for_json_path(self):
        response = FakeResponse('<html></html>', {'content-type': 'text/html'})
        results = execute_assertions(response, [
            {'name': 'json', 'type': 'json_path', 'json_path': '$.a', 'expected': 1}
        ])
        self.assertFalse(results[0]['passed'])
        self.assertIn('JSON', results[0]['error'])


class VariableStoreTest(SimpleTestCase):
    def test_extract_body_json_path(self):
        store = VariableStore({'base': '1'})
        response = FakeResponse('{"data": {"token": "abc123"}}')
        extracted = store.apply_extract_rules(response, [
            {'name': 'token', 'source': 'body', 'json_path': '$.data.token', 'enabled': True}
        ])
        self.assertEqual(extracted, {'token': 'abc123'})
        self.assertEqual(store.variables['token'], 'abc123')

    def test_extract_header_and_status(self):
        store = VariableStore()
        response = FakeResponse('{}', headers={'X-Total': '99'}, status_code=201)
        extracted = store.apply_extract_rules(response, [
            {'name': 'total', 'source': 'header', 'header_name': 'X-Total'},
            {'name': 'code', 'source': 'status'},
        ])
        self.assertEqual(extracted, {'total': '99', 'code': 201})

    def test_extract_disabled_rule_skipped(self):
        store = VariableStore()
        response = FakeResponse('{"data": {"token": "abc"}}')
        extracted = store.apply_extract_rules(response, [
            {'name': 'token', 'source': 'body', 'json_path': '$.data.token', 'enabled': False}
        ])
        self.assertEqual(extracted, {})

    def test_extract_no_match_skips(self):
        store = VariableStore({'token': 'old'})
        response = FakeResponse('{}')
        extracted = store.apply_extract_rules(response, [
            {'name': 'token', 'source': 'body', 'json_path': '$.data.token'}
        ])
        self.assertEqual(extracted, {})
        self.assertEqual(store.variables['token'], 'old')

    def test_resolve_variable_syntax(self):
        store = VariableStore({'token': 'abc123'})
        self.assertEqual(store.resolve('Bearer {{token}}'), 'Bearer abc123')


class BuildRequestPayloadTest(SimpleTestCase):
    def _api_request(self):
        return SimpleNamespace(
            url='/api/pets',
            method='POST',
            headers={'Authorization': 'Bearer {{token}}'},
            params={'page': '1'},
            body={'type': 'json', 'data': {'name': '{{name}}'}},
        )

    def _environment(self):
        return SimpleNamespace(
            base_url='http://dev.com:8080',
            default_headers={'X-Env': 'dev'},
            default_params={'trace': '1'},
            variables={'token': 'abc', 'name': '小白'},
        )

    def test_merge_order(self):
        api_request = self._api_request()
        env = self._environment()
        case = {
            'params': {'page': '2'},
            'headers': {'X-Case': '1'},
            'body': {'type': 'json', 'data': {'name': '{{name}}', 'extra': 1}},
        }
        payload = build_request_payload(api_request, case, env, env.variables)
        self.assertEqual(payload['url'], 'http://dev.com:8080/api/pets')
        self.assertEqual(payload['headers']['Authorization'], 'Bearer abc')
        self.assertEqual(payload['headers']['X-Env'], 'dev')
        self.assertEqual(payload['params']['page'], '2')
        self.assertEqual(payload['params']['trace'], '1')
        self.assertEqual(payload['body_data'], {'name': '小白', 'extra': 1})
        self.assertEqual(payload['body_type'], 'json')

    def test_case_body_overrides_request_body(self):
        api_request = self._api_request()
        env = self._environment()
        case = {'body': {'type': 'raw', 'data': '{{name}}'}}
        payload = build_request_payload(api_request, case, env, env.variables)
        self.assertEqual(payload['body_data'], '小白')
        self.assertEqual(payload['body_type'], 'raw')

    def test_absolute_url_not_prefixed(self):
        api_request = self._api_request()
        api_request.url = 'https://other.com/api'
        env = self._environment()
        payload = build_request_payload(api_request, None, env, env.variables)
        self.assertEqual(payload['url'], 'https://other.com/api')

    def test_build_body_form_data(self):
        body_data, body_type = _build_body(
            {'type': 'form-data', 'data': [
                {'key': 'a', 'value': '{{x}}', 'enabled': True, 'type': 'text'},
                {'key': 'b', 'value': '2', 'enabled': False},
            ]},
            'POST',
            {'x': '1'},
            None,
        )
        self.assertEqual(body_type, 'form-data')
        self.assertEqual(body_data, [{'key': 'a', 'value': '1', 'type': 'text'}])
