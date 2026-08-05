"""API测试统一执行服务

单请求执行、测试套件执行、定时任务执行统一走这里的逻辑，
避免原先 views.py / utils.py 中多份实现行为分叉。
"""
import json
import re
import time

import requests
from django.utils import timezone

from .models import RequestHistory

DEFAULT_TIMEOUT = 30


def safe_json_loads(text):
    """安全解析 JSON，失败返回 None 而不是抛异常"""
    if not text:
        return None
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None


def _replace_variables(text, variables):
    """替换 {{var}} 环境/提取变量"""
    if not isinstance(text, str):
        return text
    result = text
    for key, value in (variables or {}).items():
        if isinstance(value, dict):
            replacement = str(value.get('currentValue', '') or value.get('initialValue', ''))
        else:
            replacement = str(value) if value is not None else ''
        result = result.replace('{{' + key + '}}', replacement)
    return result


def resolve_variables(text, variables, resolver=None):
    """先替换 {{var}}，再解析 ${func()} 动态函数"""
    if resolver is None:
        from .variable_resolver import VariableResolver
        resolver = VariableResolver()
    return resolver.resolve(_replace_variables(text, variables))


def _resolve_in_dict(data, variables, resolver):
    if isinstance(data, dict):
        return {k: _resolve_in_dict(v, variables, resolver) for k, v in data.items()}
    if isinstance(data, list):
        return [_resolve_in_dict(item, variables, resolver) for item in data]
    if isinstance(data, str):
        return resolve_variables(data, variables, resolver)
    return data


def _resolve_env_dict(data, variables, resolver):
    """解析字典中每个值的变量和动态函数，key 保持不变"""
    return _resolve_in_dict(data or {}, variables, resolver)


def _resolve_header_field(field, variables, resolver):
    """请求头支持列表 [{key,value,enabled}] 或字典两种格式"""
    result = {}
    if isinstance(field, list):
        for item in field:
            if item.get('enabled', True) and item.get('key'):
                key = resolve_variables(str(item.get('key', '')), variables, resolver)
                value = resolve_variables(str(item.get('value', '')), variables, resolver)
                result[key] = value
    elif isinstance(field, dict):
        for key, value in field.items():
            result[key] = resolve_variables(str(value) if not isinstance(value, str) else value,
                                            variables, resolver)
    return result


def _normalize_expected(value):
    """把断言期望值做类型归一化：数字字符串转数字"""
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            try:
                return float(value)
            except ValueError:
                return value
    return value


def _values_equal(actual, expected):
    """类型敏感的相等比较，数字与数字字符串视为相等"""
    if actual is None and expected is None:
        return True
    if isinstance(expected, str):
        expected = _normalize_expected(expected)
    if isinstance(actual, str):
        actual = _normalize_expected(actual)
    return actual == expected


def _simple_json_path(data, expr):
    """内置简化 JSONPath 解析（兼容 $.a.b、$['a'].b、$[0] 等常见写法）

    如果环境安装了 jsonpath-ng 则优先使用它；这里作为兜底。
    """
    expr = (expr or '').strip()
    if expr.startswith('$'):
        expr = expr[1:]
    expr = expr.lstrip('.')
    if not expr:
        return data

    tokens = []
    for m in re.finditer(r'(\[[^\]]*\])|([^.\[\]]+)', expr):
        tokens.append(m.group(0))

    current = data
    for tok in tokens:
        if isinstance(current, (dict, list)) and tok.startswith('[') and tok.endswith(']'):
            inner = tok[1:-1].strip()
            if inner.startswith(("'", '"')) and inner.endswith(("'", '"')):
                key = inner[1:-1]
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return None
            else:
                try:
                    idx = int(inner)
                except ValueError:
                    return None
                if isinstance(current, list) and -len(current) <= idx < len(current):
                    current = current[idx]
                else:
                    return None
        elif isinstance(current, dict) and tok in current:
            current = current[tok]
        else:
            return None
    return current


def _extract_json_path(data, json_path):
    """按 JSONPath 取第一个匹配值；优先 jsonpath-ng，缺失时用内置兜底"""
    try:
        from jsonpath_ng import parse
        matches = parse(json_path).find(data)
        return matches[0].value if matches else None
    except ImportError:
        return _simple_json_path(data, json_path)


def execute_assertions(response, assertions, response_time=None):
    """执行断言验证（修复版：不污染 assertion 字典，类型归一化）"""
    results = []

    for assertion in assertions or []:
        result = {
            'name': assertion.get('name', '未命名断言'),
            'type': assertion.get('type'),
            'passed': False,
            'expected': assertion.get('expected', assertion.get('expected_value', assertion.get('value'))),
            'actual': None,
            'error': None,
        }

        try:
            assertion_type = assertion.get('type')
            actual = None
            passed = False

            if assertion_type == 'status_code':
                actual = response.status_code
                passed = _values_equal(actual, assertion.get('expected', assertion.get('value')))

            elif assertion_type == 'response_time':
                actual = response_time if response_time is not None else assertion.get('actual_time')
                expected = _normalize_expected(assertion.get('expected'))
                passed = actual is not None and actual <= expected

            elif assertion_type == 'contains':
                text = response.text or ''
                actual = text[:200] + '...' if len(text) > 200 else text
                passed = str(assertion.get('expected')) in text

            elif assertion_type == 'json_path':
                json_path = assertion.get('json_path', '')
                expected = assertion.get('expected')
                response_json = safe_json_loads(response.text)
                if response_json is None:
                    raise ValueError('响应不是有效JSON')
                if not json_path:
                    raise ValueError('JSON路径表达式不能为空')
                actual = _extract_json_path(response_json, json_path)
                passed = _values_equal(actual, expected)

            elif assertion_type == 'header':
                header_name = assertion.get('header_name', '')
                expected = assertion.get('expected_value', assertion.get('expected'))
                actual = response.headers.get(header_name)
                passed = _values_equal(actual, expected)

            elif assertion_type == 'equals':
                actual = response.text.strip()
                passed = actual == str(assertion.get('expected')).strip()

            result['actual'] = actual
            result['passed'] = passed

        except Exception as e:
            result['error'] = str(e)
            result['passed'] = False

        results.append(result)

    return results


def _build_body(body, method, variables, resolver):
    """根据 body 配置构建发送数据，返回 (body_data, body_type)"""
    body = body or {}
    body_type = body.get('type', 'none')
    content = body.get('data')

    if method not in ['POST', 'PUT', 'PATCH']:
        return None, 'none'

    if body_type == 'json':
        return _resolve_in_dict(content if isinstance(content, dict) else content, variables, resolver), 'json'

    if body_type == 'raw':
        if isinstance(content, str):
            return resolve_variables(content, variables, resolver), 'raw'
        return content, 'raw'

    if body_type in ('form-data', 'x-www-form-urlencoded'):
        rows = []
        for item in (content or []):
            if isinstance(item, dict) and item.get('enabled', True) and item.get('key'):
                rows.append({
                    'key': resolve_variables(str(item.get('key', '')), variables, resolver),
                    'value': resolve_variables(str(item.get('value', '')), variables, resolver),
                    'type': item.get('type', 'text'),
                })
        return rows, body_type

    # none / binary / 未知类型
    return content, body_type


def _send_request(method, url, headers, params, body_data, body_type, timeout=DEFAULT_TIMEOUT):
    """按 body 类型发送请求"""
    if body_type == 'raw':
        return requests.request(method, url, headers=headers, params=params,
                                data=body_data, timeout=timeout)
    if body_type == 'form-data':
        data = {}
        files = {}
        for row in (body_data or []):
            if row.get('type') == 'file':
                files[row['key']] = ('', row.get('value', ''))
            else:
                data[row['key']] = row.get('value', '')
        return requests.request(method, url, headers=headers, params=params,
                                data=data, files=files, timeout=timeout)
    if body_type == 'x-www-form-urlencoded':
        data = {}
        for row in (body_data or []):
            data[row['key']] = row.get('value', '')
        return requests.request(method, url, headers=headers, params=params,
                                data=data, timeout=timeout)
    return requests.request(method, url, headers=headers, params=params,
                            json=body_data, timeout=timeout)


def build_request_payload(api_request, case=None, environment=None, variables=None, resolver=None):
    """解析出一个请求的完整发送参数

    case 支持覆盖：url / method / headers / params / body / assertions
    合并顺序：环境默认值 < 接口定义 < 用例覆盖
    """
    from .variable_resolver import VariableResolver
    resolver = resolver or VariableResolver()
    variables = dict(variables or {})
    case = case or {}

    url = case.get('url') or api_request.url or ''
    if environment and environment.base_url and not url.startswith(('http://', 'https://')):
        url = environment.base_url.rstrip('/') + '/' + url.lstrip('/')
    url = resolve_variables(url, variables, resolver)

    method = case.get('method') or api_request.method

    env_headers = _resolve_header_field(environment.default_headers, variables, resolver) if environment else {}
    request_headers = _resolve_header_field(api_request.headers, variables, resolver)
    case_headers = _resolve_header_field(case.get('headers'), variables, resolver)
    headers = {**env_headers, **request_headers, **case_headers}

    env_params = _resolve_env_dict(environment.default_params, variables, resolver) if environment else {}
    request_params = _resolve_env_dict(api_request.params, variables, resolver) if api_request.params else {}
    case_params = _resolve_env_dict(case.get('params'), variables, resolver) if case.get('params') else {}
    params = {**env_params, **request_params, **case_params}

    if case.get('body') is not None:
        body_source = case.get('body')
    else:
        body_source = api_request.body
    body_data, body_type = _build_body(body_source, method, variables, resolver)

    return {
        'url': url,
        'method': method,
        'headers': headers,
        'params': params,
        'body_data': body_data,
        'body_type': body_type,
    }


class VariableStore:
    """套件执行过程中的运行时变量池（环境变量 + 用例提取的响应变量）"""

    def __init__(self, initial=None):
        self.variables = dict(initial or {})

    def resolve(self, text, resolver=None):
        return resolve_variables(text, self.variables, resolver)

    def resolve_dict(self, data, resolver=None):
        return _resolve_in_dict(data, self.variables, resolver)

    def apply_extract_rules(self, response, rules):
        """按规则从响应中提取变量并写入变量池，返回本次提取结果"""
        extracted = {}
        for rule in rules or []:
            if not rule.get('enabled', True):
                continue
            name = str(rule.get('name', '')).strip()
            if not name:
                continue
            try:
                value = self._extract_one(response, rule)
            except Exception:
                value = None
            if value is not None:
                extracted[name] = value
        self.variables.update(extracted)
        return extracted

    @staticmethod
    def _extract_one(response, rule):
        source = rule.get('source', 'body')
        if source == 'header':
            return response.headers.get(rule.get('header_name', ''))
        if source == 'status':
            return response.status_code
        # body 默认走 JSONPath
        response_json = safe_json_loads(response.text)
        if response_json is None:
            raise ValueError('响应不是有效JSON')
        json_path = rule.get('json_path', '')
        if not json_path:
            raise ValueError('JSONPath不能为空')
        return _extract_json_path(response_json, json_path)


def _save_history(api_request, environment, payload, response, response_time,
                  assertions_results, executed_by):
    return RequestHistory.objects.create(
        request=api_request,
        environment=environment,
        request_data={
            'url': payload['url'],
            'method': payload['method'],
            'headers': payload['headers'],
            'params': payload['params'],
            'body': payload.get('body_data'),
        },
        response_data={
            'headers': dict(response.headers),
            'body': response.text,
            'json': safe_json_loads(response.text),
        },
        status_code=response.status_code,
        response_time=response_time,
        assertions_results=assertions_results,
        executed_by=executed_by,
    )


def execute_single_request(api_request, environment, executed_by, overrides=None):
    """执行单个 API 请求，返回与旧 execute_api_request 兼容的结构"""
    from .variable_resolver import VariableResolver
    resolver = VariableResolver()
    variables = {}
    if environment:
        variables.update(environment.variables or {})

    overrides = overrides or {}
    payload = build_request_payload(api_request, overrides, environment, variables, resolver)

    try:
        start_time = time.time()
        response = _send_request(
            payload['method'], payload['url'], payload['headers'], payload['params'],
            payload['body_data'], payload['body_type']
        )
        end_time = time.time()
        response_time = (end_time - start_time) * 1000

        assertions = overrides.get('assertions', api_request.assertions) or []
        assertions_results = execute_assertions(response, assertions, response_time=response_time)

        store = VariableStore(variables)
        extracted_variables = store.apply_extract_rules(response, overrides.get('extract_rules') or [])

        history = _save_history(api_request, environment, payload, response, response_time,
                                assertions_results, executed_by)

        return {
            'success': True,
            'history_id': history.id,
            'status_code': response.status_code,
            'response_time': response_time,
            'assertions_results': assertions_results,
            'extracted_variables': extracted_variables,
            'response_data': {
                'headers': dict(response.headers),
                'body': response.text,
                'json': safe_json_loads(response.text),
            },
        }

    except Exception as e:
        RequestHistory.objects.create(
            request=api_request,
            environment=environment,
            request_data={
                'url': payload['url'],
                'method': payload['method'],
                'headers': payload['headers'],
                'params': payload['params'],
                'body': payload.get('body_data'),
            },
            error_message=str(e),
            executed_by=executed_by,
        )
        return {
            'success': False,
            'error': str(e),
        }


def execute_suite(test_suite, environment=None, executed_by=None):
    """执行测试套件（支持同接口多用例、响应变量提取），返回兼容结构"""
    from .models import TestExecution
    from .variable_resolver import VariableResolver

    if environment is None:
        environment = test_suite.environment

    try:
        execution = TestExecution.objects.create(
            test_suite=test_suite,
            status='RUNNING',
            start_time=timezone.now(),
            executed_by=executed_by,
        )

        suite_requests = test_suite.testsuiterequest_set.filter(enabled=True).order_by('order')
        execution.total_requests = suite_requests.count()
        execution.save()

        resolver = VariableResolver()
        store = VariableStore(environment.variables if environment else {})

        results = []
        passed_count = 0
        failed_count = 0

        for suite_request in suite_requests:
            api_request = suite_request.request
            case = {
                'headers': suite_request.headers,
                'params': suite_request.params,
                'body': suite_request.body,
            }
            variables_before = dict(store.variables)

            try:
                payload = build_request_payload(api_request, case, environment,
                                                store.variables, resolver)
                start_time = time.time()
                response = _send_request(
                    payload['method'], payload['url'], payload['headers'], payload['params'],
                    payload['body_data'], payload['body_type']
                )
                end_time = time.time()
                response_time = (end_time - start_time) * 1000

                assertions = list(suite_request.assertions or []) + list(api_request.assertions or [])
                assertions_results = execute_assertions(response, assertions, response_time=response_time)

                extracted_variables = store.apply_extract_rules(response, suite_request.extract_rules)

                passed = all(r.get('passed') for r in assertions_results)
                error_message = ''
                if not passed:
                    failed = next((r for r in assertions_results if not r.get('passed')), None)
                    error_message = f"断言失败: {failed.get('name', '未命名断言')} - " \
                                    f"{failed.get('error', '断言不通过')}"

                if passed:
                    passed_count += 1
                else:
                    failed_count += 1

                case_name = suite_request.name or api_request.name
                results.append({
                    'case_id': suite_request.id,
                    'case_name': case_name,
                    'name': case_name,
                    'method': api_request.method,
                    'url': payload['url'],
                    'status_code': response.status_code,
                    'response_time': response_time,
                    'passed': passed,
                    'error': error_message,
                    'assertions_results': assertions_results,
                    'variables_before': variables_before,
                    'extracted_variables': extracted_variables,
                })

                _save_history(api_request, environment, payload, response, response_time,
                              assertions_results, executed_by)

            except Exception as e:
                failed_count += 1
                case_name = suite_request.name or api_request.name
                results.append({
                    'case_id': suite_request.id,
                    'case_name': case_name,
                    'name': case_name,
                    'method': api_request.method,
                    'url': payload['url'] if 'payload' in locals() else api_request.url,
                    'passed': False,
                    'error': str(e),
                    'variables_before': variables_before,
                    'extracted_variables': {},
                })

        execution.end_time = timezone.now()
        execution.passed_requests = passed_count
        execution.failed_requests = failed_count
        execution.status = 'COMPLETED' if failed_count == 0 else 'FAILED'
        execution.results = results
        execution.save()

        return {
            'success': True,
            'execution_id': execution.id,
            'passed_count': passed_count,
            'failed_count': failed_count,
            'total_count': execution.total_requests,
            'results': results,
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e),
        }
