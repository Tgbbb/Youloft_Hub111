"""
TestHub Agent - Tools
基于 Qwen-Agent 框架的自定义工具定义
每个 Tool 对应一个 TestHub 业务操作
"""
import json
import logging
from typing import Union, List
from django.db.models import Q
from qwen_agent.tools.base import BaseTool, register_tool

logger = logging.getLogger(__name__)


# ============================================================
# 查询类工具
# ============================================================

@register_tool('get_project_overview')
class GetProjectOverview(BaseTool):
    """获取项目概况"""
    description = '获取项目概况：接口数、用例数、执行状态'
    parameters = [
        {'name': 'project_id', 'type': 'integer', 'description': '项目ID', 'required': True}
    ]

    def call(self, params: Union[str, dict], **kwargs) -> str:
        from apps.projects.models import Project
        from apps.testcases.models import TestCase
        from apps.api_testing.models import ApiProject, ApiRequest, TestExecution

        if isinstance(params, str):
            params = json.loads(params)
        project_id = params.get('project_id')

        try:
            project = Project.objects.get(id=project_id)

            # 测试用例
            testcase_count = TestCase.objects.filter(project_id=project_id).count()

            # 接口测试（关联的 ApiProject）
            api_projects = list(ApiProject.objects.filter(main_project=project)[:3])
            api_count = 0
            collection_count = 0
            recent_executions = []
            for ap in api_projects:
                api_count += ApiRequest.objects.filter(collection__project=ap).count()
                # 也计入未分配集合的接口（collection 为 null）
                api_count += ApiRequest.objects.filter(collection__isnull=True).count()
                collection_count += ap.collections.count()
                execs = TestExecution.objects.filter(
                    test_suite__project=ap
                ).order_by('-created_at')[:3].values(
                    'id', 'status', 'total_requests', 'passed_requests',
                    'failed_requests', 'created_at'
                )
                recent_executions.extend(list(execs))

            # UI 自动化统计
            ui_count = 0
            ui_suite_count = 0
            try:
                from apps.ui_automation.models import UiProject, TestScript as UIScript, TestSuite as UITestSuite
                ui_projects = UiProject.objects.filter(main_project=project)
                for up in ui_projects[:5]:
                    ui_count += UIScript.objects.filter(project=up).count()
                    ui_suite_count += UITestSuite.objects.filter(project=up).count()
            except Exception:
                pass

            # AI智能模式 (Midscene) 统计
            midscene_count = 0
            midscene_device_count = 0
            try:
                from apps.ui_automation.models import MidsceneProject, MidsceneCase, MidsceneDevice
                mp = MidsceneProject.objects.filter(main_project=project)
                for m in mp[:5]:
                    midscene_count += MidsceneCase.objects.filter(project=m).count()
                midscene_device_count = MidsceneDevice.objects.filter(status='online').count()
            except Exception:
                pass

            result = {
                'project_name': project.name,
                'project_status': project.status,
                'project_description': project.description or '',
                'has_knowledge_base': bool(project.knowledge_base),
                'modules': {
                    'testcases': {'count': testcase_count},
                    'api_testing': {
                        'api_project_count': len(api_projects),
                        'collection_count': collection_count,
                        'api_count': api_count,
                    },
                    'ui_automation': {
                        'script_count': ui_count,
                        'suite_count': ui_suite_count,
                    },
                    'midscene': {
                        'case_count': midscene_count,
                        'online_devices': midscene_device_count,
                    }
                },
                'recent_executions': [{'id': e['id'], 'status': e['status'],
                    'passed': e['passed_requests'], 'total': e['total_requests']}
                    for e in recent_executions[:5]],
            }
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception as e:
            return json.dumps({'error': str(e)}, ensure_ascii=False)


@register_tool('search_apis')
class SearchApis(BaseTool):
    """搜索API接口"""
    description = '搜索API接口，按名称/URL/方法匹配'
    parameters = [
        {'name': 'project_id', 'type': 'integer', 'description': '项目ID', 'required': True},
        {'name': 'keyword', 'type': 'string', 'description': '关键词，匹配名称/URL/方法', 'required': False}
    ]

    def call(self, params: Union[str, dict], **kwargs) -> str:
        from apps.api_testing.models import ApiProject, ApiRequest
        from apps.projects.models import Project

        if isinstance(params, str):
            params = json.loads(params)
        project_id = params.get('project_id')
        keyword = params.get('keyword', '')

        try:
            # 通过主 Project 找到关联的 ApiProject
            main_project = Project.objects.get(id=project_id)
            api_projects = ApiProject.objects.filter(main_project=main_project)
            api_project_ids = list(api_projects.values_list('id', flat=True)[:5])

            # 有集合的 + 无集合的（orphaned）
            queryset = ApiRequest.objects.filter(
                Q(collection__project_id__in=api_project_ids) |
                Q(collection__isnull=True)
            )

            if keyword:
                queryset = queryset.filter(
                    Q(name__icontains=keyword) |
                    Q(url__icontains=keyword) |
                    Q(method__iexact=keyword)
                )

            total = queryset.count()
            results = []
            for req in queryset[:10]:
                results.append({
                    'id': req.id,
                    'name': req.name,
                    'method': req.method,
                    'url': req.url[:120],
                })

            resp = {'total': total, 'count': len(results), 'results': results}
            if total > 10:
                resp['hint'] = f'共 {total} 条结果，仅展示前 10 条。可缩小关键词精确查找。'
            return json.dumps(resp, ensure_ascii=False)
        except Exception as e:
            return json.dumps({'error': str(e)}, ensure_ascii=False)


@register_tool('get_api_detail')
class GetApiDetail(BaseTool):
    """获取接口完整信息"""
    description = '获取API接口完整信息：URL、方法、请求头、参数、请求体、断言'
    parameters = [
        {'name': 'request_id', 'type': 'integer', 'description': '接口ID', 'required': True}
    ]

    def call(self, params: Union[str, dict], **kwargs) -> str:
        from apps.api_testing.models import ApiRequest

        if isinstance(params, str):
            params = json.loads(params)
        request_id = params.get('request_id')

        try:
            req = ApiRequest.objects.select_related('collection', 'collection__project').get(id=request_id)

            result = {
                'id': req.id,
                'name': req.name,
                'method': req.method,
                'url': req.url,
                'headers': req.headers,
                'params': req.params,
                'body': req.body,
                'assertions': req.assertions,
                'collection': req.collection.name if req.collection else None,
                'collection_id': req.collection_id,
                'project': req.collection.project.name if req.collection and req.collection.project else None,
            }
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception as e:
            return json.dumps({'error': str(e)}, ensure_ascii=False)


@register_tool('search_testcases')
class SearchTestCases(BaseTool):
    """搜索测试用例"""
    description = '搜索测试用例，按标题/描述关键词'
    parameters = [
        {'name': 'project_id', 'type': 'integer', 'description': '项目ID', 'required': True},
        {'name': 'keyword', 'type': 'string', 'description': '搜索关键词', 'required': False}
    ]

    def call(self, params: Union[str, dict], **kwargs) -> str:
        from apps.testcases.models import TestCase

        if isinstance(params, str):
            params = json.loads(params)
        project_id = params.get('project_id')
        keyword = params.get('keyword', '')

        try:
            queryset = TestCase.objects.filter(project_id=project_id)
            if keyword:
                queryset = queryset.filter(
                    Q(title__icontains=keyword) |
                    Q(description__icontains=keyword)
                )

            total = queryset.count()
            results = []
            for tc in queryset[:10]:
                results.append({
                    'id': tc.id,
                    'title': tc.title,
                    'priority': tc.priority,
                    'status': tc.status,
                })

            resp = {'total': total, 'count': len(results), 'results': results}
            if total > 10:
                resp['hint'] = f'共 {total} 条，仅展示前 10 条。可缩小关键词精确查找。'
            return json.dumps(resp, ensure_ascii=False)
        except Exception as e:
            return json.dumps({'error': str(e)}, ensure_ascii=False)


# ============================================================
# 创建类工具
# ============================================================

@register_tool('create_api_test')
class CreateApiTest(BaseTool):
    """创建API接口测试"""
    description = '创建API接口测试，含URL、方法、请求头、参数、请求体、断言'
    parameters = [
        {'name': 'project_id', 'type': 'integer', 'description': '项目ID', 'required': True},
        {'name': 'name', 'type': 'string', 'description': '接口名称', 'required': True},
        {'name': 'method', 'type': 'string', 'description': 'GET/POST/PUT/DELETE/PATCH', 'required': True},
        {'name': 'url', 'type': 'string', 'description': '请求URL', 'required': True},
        {'name': 'collection_id', 'type': 'integer', 'description': '集合ID（可选）', 'required': False},
        {'name': 'headers', 'type': 'object', 'description': '请求头JSON', 'required': False},
        {'name': 'params', 'type': 'object', 'description': 'URL参数JSON', 'required': False},
        {'name': 'body', 'type': 'object', 'description': '请求体JSON', 'required': False},
        {'name': 'assertions', 'type': 'array', 'description': '断言规则列表', 'required': False},
    ]

    def call(self, params: Union[str, dict], **kwargs) -> str:
        from apps.projects.models import Project
        from apps.api_testing.models import ApiProject, ApiCollection, ApiRequest

        if isinstance(params, str):
            params = json.loads(params)

        try:
            from apps.assistant.agent import TestHubAgent
            user = TestHubAgent.get_current_user()
            main_project = Project.objects.get(id=params['project_id'])
            api_project = ApiProject.objects.filter(main_project=main_project).first()
            if not api_project:
                api_project = ApiProject.objects.create(
                    name=main_project.name,
                    project_type='HTTP',
                    status='IN_PROGRESS',
                    owner=user or main_project.owner,
                    main_project=main_project,
                )

            collection = None
            if params.get('collection_id'):
                collection = ApiCollection.objects.filter(
                    id=params['collection_id'], project=api_project
                ).first()

            request = ApiRequest.objects.create(
                collection=collection,
                name=params['name'],
                method=params.get('method', 'GET'),
                url=params['url'],
                headers=params.get('headers', {}),
                params=params.get('params', {}),
                body=params.get('body', {}),
                assertions=params.get('assertions', []),
                created_by=user
            )

            return json.dumps({
                'success': True,
                'id': request.id,
                'name': request.name,
                'method': request.method,
                'url': request.url,
                'api_project': api_project.name,
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({'success': False, 'error': str(e)}, ensure_ascii=False)


@register_tool('update_api_test')
class UpdateApiTest(BaseTool):
    """修改API接口测试"""
    description = '修改API接口测试的参数、断言等'
    parameters = [
        {'name': 'request_id', 'type': 'integer', 'description': '接口ID', 'required': True},
        {'name': 'name', 'type': 'string', 'description': '新名称', 'required': False},
        {'name': 'method', 'type': 'string', 'description': 'GET/POST/PUT/DELETE/PATCH', 'required': False},
        {'name': 'url', 'type': 'string', 'description': '新URL', 'required': False},
        {'name': 'headers', 'type': 'object', 'description': '请求头JSON', 'required': False},
        {'name': 'params', 'type': 'object', 'description': 'URL参数JSON', 'required': False},
        {'name': 'body', 'type': 'object', 'description': '请求体JSON', 'required': False},
        {'name': 'assertions', 'type': 'array', 'description': '断言规则（替换全部）', 'required': False},
    ]

    def call(self, params: Union[str, dict], **kwargs) -> str:
        from apps.api_testing.models import ApiRequest

        if isinstance(params, str):
            params = json.loads(params)

        try:
            request_id = params.pop('request_id')
            req = ApiRequest.objects.get(id=request_id)
            changed = {}
            for k, v in params.items():
                if v is not None and hasattr(req, k):
                    old = getattr(req, k)
                    setattr(req, k, v)
                    changed[k] = {'old': str(old)[:100], 'new': str(v)[:100]}
            if changed:
                req.save()
            return json.dumps({
                'success': True,
                'id': req.id,
                'name': req.name,
                'changed_fields': list(changed.keys()),
            }, ensure_ascii=False)
        except ApiRequest.DoesNotExist:
            return json.dumps({'success': False, 'error': '接口不存在'}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({'success': False, 'error': str(e)}, ensure_ascii=False)


@register_tool('create_collection')
class CreateCollection(BaseTool):
    """创建接口集合"""
    description = '创建接口集合（文件夹）'
    parameters = [
        {'name': 'project_id', 'type': 'integer', 'description': '项目ID', 'required': True},
        {'name': 'name', 'type': 'string', 'description': '集合名称', 'required': True},
        {'name': 'description', 'type': 'string', 'description': '描述', 'required': False},
        {'name': 'parent_id', 'type': 'integer', 'description': '父集合ID（嵌套用）', 'required': False},
    ]

    def call(self, params: Union[str, dict], **kwargs) -> str:
        from apps.projects.models import Project
        from apps.api_testing.models import ApiProject, ApiCollection

        if isinstance(params, str):
            params = json.loads(params)

        try:
            # 与 create_api_test 一致：通过主 Project ID 查找/创建 ApiProject
            from apps.assistant.agent import TestHubAgent
            user = TestHubAgent.get_current_user()
            main_project = Project.objects.get(id=params['project_id'])
            api_project = ApiProject.objects.filter(main_project=main_project).first()
            if not api_project:
                api_project = ApiProject.objects.create(
                    name=main_project.name,
                    project_type='HTTP',
                    status='IN_PROGRESS',
                    owner=user or main_project.owner,
                    main_project=main_project,
                )

            parent = None
            if params.get('parent_id'):
                parent = ApiCollection.objects.filter(
                    id=params['parent_id'], project=api_project
                ).first()

            collection = ApiCollection.objects.create(
                project=api_project,
                name=params['name'],
                description=params.get('description', ''),
                parent=parent
            )

            return json.dumps({
                'success': True,
                'id': collection.id,
                'name': collection.name,
                'api_project_id': api_project.id,
                'parent': parent.name if parent else None,
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({'success': False, 'error': str(e)}, ensure_ascii=False)


@register_tool('create_testcase')
class CreateTestcase(BaseTool):
    """创建测试用例"""
    description = '创建测试用例，含标题、步骤、优先级'
    parameters = [
        {'name': 'project_id', 'type': 'integer', 'description': '项目ID', 'required': True},
        {'name': 'title', 'type': 'string', 'description': '用例标题', 'required': True},
        {'name': 'priority', 'type': 'string', 'description': 'low/medium/high/critical', 'required': False},
        {'name': 'status', 'type': 'string', 'description': 'draft/active/deprecated', 'required': False},
        {'name': 'description', 'type': 'string', 'description': '描述/前置条件', 'required': False},
        {'name': 'steps', 'type': 'string', 'description': '测试步骤文本', 'required': False},
    ]

    def call(self, params: Union[str, dict], **kwargs) -> str:
        from apps.testcases.models import TestCase

        if isinstance(params, str):
            params = json.loads(params)

        try:
            from apps.assistant.agent import TestHubAgent
            user = TestHubAgent.get_current_user()

            testcase = TestCase.objects.create(
                project_id=params['project_id'],
                title=params['title'],
                priority=params.get('priority', 'medium'),
                status=params.get('status', 'draft'),
                description=params.get('description', ''),
                author=user
            )

            # 如果有步骤（支持纯文本字符串或数组）
            steps = params.get('steps', '')
            if steps:
                if isinstance(steps, str):
                    # 纯文本直接存到 TestCase 的 steps TextField
                    testcase.steps = steps
                    testcase.save()
                elif isinstance(steps, list):
                    from apps.testcases.models import TestCaseStep
                    for i, step_data in enumerate(steps):
                        TestCaseStep.objects.create(
                            testcase=testcase,
                            step_number=i + 1,
                            action=step_data.get('step', step_data.get('action', '')),
                            expected=step_data.get('expected', '')
                        )

            return json.dumps({
                'success': True,
                'id': testcase.id,
                'title': testcase.title,
                'priority': testcase.priority,
                'step_count': len(steps),
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({'success': False, 'error': str(e)}, ensure_ascii=False)


@register_tool('get_testcase_detail')
class GetTestcaseDetail(BaseTool):
    """查看测试用例详情"""
    description = '查看测试用例详情：标题、描述、步骤、预期结果'
    parameters = [
        {'name': 'testcase_id', 'type': 'integer', 'description': '用例ID', 'required': True}
    ]

    def call(self, params: Union[str, dict], **kwargs) -> str:
        from apps.testcases.models import TestCase

        if isinstance(params, str):
            params = json.loads(params)

        try:
            tc = TestCase.objects.prefetch_related('step_details').get(id=params['testcase_id'])
            steps = [{
                'step': s.step_number,
                'action': s.action,
                'expected': s.expected
            } for s in tc.step_details.all()]

            return json.dumps({
                'id': tc.id,
                'title': tc.title,
                'description': tc.description or '',
                'preconditions': tc.preconditions or '',
                'priority': tc.priority,
                'status': tc.status,
                'test_type': tc.test_type or '',
                'expected_result': tc.expected_result or '',
                'step_count': len(steps),
                'steps': steps,
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({'error': str(e)}, ensure_ascii=False)


@register_tool('update_testcase')
class UpdateTestcase(BaseTool):
    """修改测试用例"""
    description = '修改测试用例字段，只传需修改的'
    parameters = [
        {'name': 'testcase_id', 'type': 'integer', 'description': '用例ID', 'required': True},
        {'name': 'title', 'type': 'string', 'description': '新标题', 'required': False},
        {'name': 'description', 'type': 'string', 'description': '新描述', 'required': False},
        {'name': 'priority', 'type': 'string', 'description': 'low/medium/high/critical', 'required': False},
        {'name': 'status', 'type': 'string', 'description': 'draft/active/deprecated', 'required': False},
        {'name': 'preconditions', 'type': 'string', 'description': '前置条件', 'required': False},
        {'name': 'expected_result', 'type': 'string', 'description': '预期结果', 'required': False},
    ]

    def call(self, params: Union[str, dict], **kwargs) -> str:
        from apps.testcases.models import TestCase

        if isinstance(params, str):
            params = json.loads(params)

        try:
            tc = TestCase.objects.get(id=params.pop('testcase_id'))
            updatable = {'title', 'description', 'priority', 'status', 'preconditions', 'expected_result'}
            changed = {}
            for k, v in params.items():
                if k in updatable and v is not None:
                    setattr(tc, k, v)
                    changed[k] = v
            if changed:
                tc.save()
            return json.dumps({
                'success': True,
                'id': tc.id,
                'title': tc.title,
                'changed': list(changed.keys()),
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({'success': False, 'error': str(e)}, ensure_ascii=False)


@register_tool('delete_testcase')
class DeleteTestcase(BaseTool):
    """删除测试用例"""
    description = '删除测试用例，不可恢复'
    parameters = [
        {'name': 'testcase_id', 'type': 'integer', 'description': '用例ID', 'required': True}
    ]

    def call(self, params: Union[str, dict], **kwargs) -> str:
        from apps.testcases.models import TestCase

        if isinstance(params, str):
            params = json.loads(params)

        try:
            tc = TestCase.objects.get(id=params['testcase_id'])
            title = tc.title
            tc.delete()
            return json.dumps({'success': True, 'deleted': title}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({'success': False, 'error': str(e)}, ensure_ascii=False)


@register_tool('update_knowledge_base')
class UpdateKnowledgeBase(BaseTool):
    """更新项目知识库"""
    description = '更新项目知识库内容'
    parameters = [
        {'name': 'project_id', 'type': 'integer', 'description': '项目ID', 'required': True},
        {'name': 'content', 'type': 'string', 'description': '知识库内容', 'required': True},
        {'name': 'mode', 'type': 'string', 'description': 'append=追加, replace=替换', 'required': False},
    ]

    def call(self, params: Union[str, dict], **kwargs) -> str:
        from apps.projects.models import Project

        if isinstance(params, str):
            params = json.loads(params)

        try:
            project = Project.objects.get(id=params['project_id'])
            mode = params.get('mode', 'append')
            if mode == 'replace':
                project.knowledge_base = params['content']
            else:
                existing = project.knowledge_base or ''
                project.knowledge_base = existing + '\n\n' + params['content']
            project.save()
            return json.dumps({
                'success': True,
                'project': project.name,
                'knowledge_base_length': len(project.knowledge_base),
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({'success': False, 'error': str(e)}, ensure_ascii=False)


# ============================================================
# Shell 命令工具（白名单控制）
# ============================================================

@register_tool('bash')
class SafeBash(BaseTool):
    """执行受限shell命令"""
    description = '执行shell命令，仅白名单内命令可用'
    parameters = [
        {'name': 'command', 'type': 'string', 'description': 'shell命令', 'required': True}
    ]

    # 白名单：只允许这些命令
    WHITELIST = [
        'agent-browser', 'curl', 'wget',
    ]

    def call(self, params: Union[str, dict], **kwargs) -> str:
        import subprocess

        if isinstance(params, str):
            params = json.loads(params)
        cmd = params.get('command', '').strip()

        if not cmd:
            return json.dumps({'error': '命令为空'})

        # 检查白名单
        allowed = False
        for w in self.WHITELIST:
            if cmd == w or cmd.startswith(w + ' '):
                allowed = True
                break
        if not allowed:
            return json.dumps({
                'error': f'命令不在白名单中。允许的命令: {", ".join(self.WHITELIST)}'
            }, ensure_ascii=False)

        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True,
                timeout=30, text=True, encoding='utf-8', errors='replace'
            )
            output = (result.stdout or '') + (result.stderr or '')
            # 截断过长的输出
            if len(output) > 3000:
                output = output[:3000] + '\n...(截断)'
            return json.dumps({
                'exit_code': result.returncode,
                'output': output,
            }, ensure_ascii=False)
        except subprocess.TimeoutExpired:
            return json.dumps({'error': '命令执行超时(30秒)'}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({'error': str(e)}, ensure_ascii=False)


# ============================================================
# 执行类工具
# ============================================================

@register_tool('execute_api')
class ExecuteApi(BaseTool):
    """执行API请求"""
    description = '执行API请求并返回状态码、响应体、响应时间'
    parameters = [
        {'name': 'request_id', 'type': 'integer', 'description': '接口ID', 'required': True},
        {'name': 'environment_id', 'type': 'integer', 'description': '环境ID（可选）', 'required': False},
    ]

    def call(self, params: Union[str, dict], **kwargs) -> str:
        from apps.api_testing.models import ApiRequest, Environment
        from apps.api_testing.utils import execute_api_request

        if isinstance(params, str):
            params = json.loads(params)
        request_id = params.get('request_id')

        try:
            api_request = ApiRequest.objects.get(id=request_id)
            environment = None
            if params.get('environment_id'):
                environment = Environment.objects.filter(
                    id=params['environment_id']
                ).first()

            from apps.assistant.agent import TestHubAgent
            user = TestHubAgent.get_current_user()
            result = execute_api_request(api_request, environment, user)

            # 格式化响应体：尝试 JSON 美化
            raw_body = result.get('response_data', {}).get('body', '')
            try:
                import json as _json
                body_str = _json.dumps(_json.loads(raw_body) if isinstance(raw_body, str) else raw_body,
                                       ensure_ascii=False, indent=2)
            except Exception:
                body_str = str(raw_body) if raw_body else ''

            return json.dumps({
                'status_code': result.get('status_code'),
                'response_time_ms': round(result.get('response_time', 0), 1),
                'response_body': (body_str or '')[:400],
                'body_truncated': len(body_str) > 400,
                'assertions': result.get('assertions_results'),
                'error': result.get('error_message', ''),
            }, ensure_ascii=False, default=str)
        except Exception as e:
            return json.dumps({'error': str(e)}, ensure_ascii=False)


# ============================================================
# 项目发现工具（解决各模块项目独立、无FK关联的问题）
# ============================================================

@register_tool('list_api_projects')
class ListApiProjects(BaseTool):
    """列出API测试项目"""
    description = '列出当前用户可访问的API测试项目'
    parameters = [
        {'name': 'keyword', 'type': 'string', 'description': '按名称筛选', 'required': False}
    ]

    def call(self, params: Union[str, dict], **kwargs) -> str:
        from apps.api_testing.models import ApiProject
        if isinstance(params, str):
            params = json.loads(params)
        keyword = params.get('keyword', '')
        queryset = ApiProject.objects.all()
        if keyword:
            queryset = queryset.filter(name__icontains=keyword)
        total = queryset.count()
        results = [{'id': p.id, 'name': p.name, 'status': p.status}
                   for p in queryset[:10]]
        resp = {'total': total, 'count': len(results), 'results': results}
        if total > 10:
            resp['hint'] = f'共 {total} 个 API 项目，仅展示前 10 个。可用 keyword 筛选。'
        return json.dumps(resp, ensure_ascii=False)


@register_tool('list_midscene_projects')
class ListMidsceneProjects(BaseTool):
    """列出Midscene(AI智能模式)项目"""
    description = '列出Midscene项目'
    parameters = [
        {'name': 'keyword', 'type': 'string', 'description': '按名称筛选', 'required': False}
    ]

    def call(self, params: Union[str, dict], **kwargs) -> str:
        from apps.ui_automation.models import MidsceneProject
        if isinstance(params, str):
            params = json.loads(params)
        keyword = params.get('keyword', '')
        queryset = MidsceneProject.objects.all()
        if keyword:
            queryset = queryset.filter(name__icontains=keyword)
        total = queryset.count()
        results = [{'id': p.id, 'name': p.name, 'description': (p.description or '')[:80]}
                   for p in queryset[:10]]
        resp = {'total': total, 'count': len(results), 'results': results}
        if total > 10:
            resp['hint'] = f'共 {total} 个 Midscene 项目，仅展示前 10 个。可用 keyword 筛选。'
        return json.dumps(resp, ensure_ascii=False)


@register_tool('list_midscene_cases')
class ListMidsceneCases(BaseTool):
    """列出Midscene项目用例"""
    description = '列出Midscene项目下的AI智能模式用例'
    parameters = [
        {'name': 'midscene_project_id', 'type': 'integer', 'description': 'Midscene项目ID', 'required': True},
        {'name': 'keyword', 'type': 'string', 'description': '按名称筛选', 'required': False},
    ]

    def call(self, params: Union[str, dict], **kwargs) -> str:
        from apps.ui_automation.models import MidsceneCase
        if isinstance(params, str):
            params = json.loads(params)
        pid = params['midscene_project_id']
        keyword = params.get('keyword', '')
        queryset = MidsceneCase.objects.filter(project_id=pid)
        if keyword:
            queryset = queryset.filter(name__icontains=keyword)
        total = queryset.count()
        results = [{
            'id': c.id,
            'name': c.name,
            'description': (c.description or '')[:100],
            'ai_prompt': (c.ai_prompt or '')[:100],
            'max_steps': c.max_steps,
        } for c in queryset[:10]]
        resp = {'total': total, 'count': len(results), 'results': results}
        if total > 10:
            resp['hint'] = f'共 {total} 个 Midscene 用例，仅展示前 10 个。'
        return json.dumps(resp, ensure_ascii=False, default=str)


@register_tool('update_midscene_case')
class UpdateMidsceneCase(BaseTool):
    """修改Midscene AI用例"""
    description = '修改Midscene用例。ai_prompt每行一个步骤，换行分隔，禁止用→连接'
    parameters = [
        {'name': 'case_id', 'type': 'integer', 'description': '用例ID', 'required': True},
        {'name': 'name', 'type': 'string', 'description': '新名称', 'required': False},
        {'name': 'ai_prompt', 'type': 'string', 'description': 'AI Prompt（换行分隔步骤）', 'required': False},
        {'name': 'description', 'type': 'string', 'description': '新描述', 'required': False},
        {'name': 'max_steps', 'type': 'integer', 'description': '最大执行步数', 'required': False},
        {'name': 'append_step', 'type': 'string', 'description': '追加步骤（自动换行）', 'required': False},
    ]

    def call(self, params: Union[str, dict], **kwargs) -> str:
        from apps.ui_automation.models import MidsceneCase

        if isinstance(params, str):
            params = json.loads(params)

        try:
            case_id = params.pop('case_id')
            case = MidsceneCase.objects.get(id=case_id)
            changed = {}

            # 追加步骤模式：在现有 ai_prompt 末尾加一行
            append_step = params.pop('append_step', None)
            if append_step:
                existing = (case.ai_prompt or '').strip()
                case.ai_prompt = (existing + '\n' + append_step.strip()) if existing else append_step.strip()
                changed['ai_prompt'] = 'appended'

            for k, v in params.items():
                if v is not None and hasattr(case, k):
                    old_val = getattr(case, k)
                    setattr(case, k, v)
                    changed[k] = {'old': str(old_val)[:80], 'new': str(v)[:80]}
            if changed:
                case.save()
            return json.dumps({
                'success': True,
                'id': case.id,
                'name': case.name,
                'ai_prompt': case.ai_prompt,
                'changed_fields': list(changed.keys()),
            }, ensure_ascii=False)
        except MidsceneCase.DoesNotExist:
            return json.dumps({'success': False, 'error': '用例不存在'}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({'success': False, 'error': str(e)}, ensure_ascii=False)


# ============================================================
# 知识库工具
# ============================================================

@register_tool('read_knowledge_base')
class ReadKnowledgeBase(BaseTool):
    """读取项目知识库"""
    description = '读取项目知识库内容'
    parameters = [
        {'name': 'project_id', 'type': 'integer', 'description': '项目ID', 'required': True}
    ]

    def call(self, params: Union[str, dict], **kwargs) -> str:
        from apps.projects.models import Project

        if isinstance(params, str):
            params = json.loads(params)
        project_id = params.get('project_id')

        try:
            project = Project.objects.get(id=project_id)
            if not project.knowledge_base:
                return json.dumps({'content': '', 'message': '该项目未配置知识库'}, ensure_ascii=False)
            # 限制长度，避免上下文溢出
            content = project.knowledge_base[:3000]
            return json.dumps({
                'project_name': project.name,
                'content': content,
                'truncated': len(project.knowledge_base) > 3000,
                'length': len(project.knowledge_base),
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({'error': str(e)}, ensure_ascii=False)


# ============================================================
# 文档解析工具
# ============================================================

@register_tool('parse_swagger')
class ParseSwagger(BaseTool):
    """解析Swagger/OpenAPI文档"""
    description = '解析OpenAPI/Swagger文档URL或JSON，提取接口列表'
    parameters = [
        {'name': 'url', 'type': 'string', 'description': '文档URL', 'required': False},
        {'name': 'content', 'type': 'string', 'description': '文档JSON内容', 'required': False},
    ]

    def call(self, params: Union[str, dict], **kwargs) -> str:
        import requests as sync_requests

        if isinstance(params, str):
            params = json.loads(params)

        try:
            spec = None
            if params.get('url'):
                resp = sync_requests.get(params['url'], timeout=30)
                spec = resp.json()
            elif params.get('content'):
                spec = json.loads(params['content'])
            else:
                return json.dumps({'error': '请提供URL或content参数'})

            endpoints = []
            tags_map = {}

            # 解析 tags
            for tag in spec.get('tags', []):
                tags_map[tag['name']] = tag.get('description', '')

            # 解析 paths
            for path, methods in spec.get('paths', {}).items():
                for method, detail in methods.items():
                    if method in ('get', 'post', 'put', 'delete', 'patch', 'options', 'head'):
                        tag = detail.get('tags', ['默认'])[0] if detail.get('tags') else '默认'
                        endpoints.append({
                            'path': path,
                            'method': method.upper(),
                            'summary': detail.get('summary', ''),
                            'tag': tag,
                            'parameters': detail.get('parameters', []),
                            'request_body': bool(detail.get('requestBody')),
                            'responses': list(detail.get('responses', {}).keys()),
                        })

            # 按 tag 分组统计
            groups = {}
            for ep in endpoints:
                tag = ep['tag']
                if tag not in groups:
                    groups[tag] = []
                groups[tag].append(ep)

            # 精简端点信息（去掉 parameters/requestBody/responses 详情）
            slim_endpoints = []
            for ep in endpoints[:10]:
                slim_endpoints.append({
                    'path': ep['path'],
                    'method': ep['method'],
                    'summary': ep['summary'][:80] if ep['summary'] else '',
                    'tag': ep['tag'],
                })

            result = {
                'total_endpoints': len(endpoints),
                'groups': {tag: len(eps) for tag, eps in groups.items()},
                'sample_count': len(slim_endpoints),
                'endpoints': slim_endpoints,
            }
            if len(endpoints) > 10:
                result['hint'] = f'共 {len(endpoints)} 个接口，仅展示前 10 条概要。可按 tag 分组逐组创建，或指定具体接口。'
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return json.dumps({'error': str(e)}, ensure_ascii=False)


@register_tool('parse_yapi')
class ParseYApi(BaseTool):
    """解析YApi导出的JSON"""
    description = '解析YApi导出JSON，提取接口列表'
    parameters = [
        {'name': 'file_path', 'type': 'string', 'description': 'JSON文件路径', 'required': False},
        {'name': 'content', 'type': 'string', 'description': 'JSON内容', 'required': False},
    ]

    def call(self, params: Union[str, dict], **kwargs) -> str:
        if isinstance(params, str):
            params = json.loads(params)

        try:
            data = None
            if params.get('file_path'):
                with open(params['file_path'], 'r', encoding='utf-8') as f:
                    data = json.load(f)
            elif params.get('content'):
                data = json.loads(params['content'])
            else:
                return json.dumps({'error': '请提供 file_path 或 content'})

            # YApi 导出格式兼容：
            # 1. [{name:"v1", list:[{title, path, method, ...}]}]  — 项目导出（数组包裹版本）
            # 2. {"errcode":0, "data":{"list":[...]}}                — 接口列表导出
            # 3. 直接数组
            items = []
            if isinstance(data, list):
                # 可能是版本数组 [{name, list}]
                for group in data:
                    if isinstance(group, dict) and 'list' in group:
                        items.extend(group['list'])
                    else:
                        items.append(group)
            elif isinstance(data, dict):
                if 'data' in data:
                    inner = data['data']
                    if isinstance(inner, dict) and 'list' in inner:
                        items = inner['list']
                    elif isinstance(inner, list):
                        items = inner
                elif 'list' in data:
                    items = data['list']

            if not items:
                return json.dumps({'error': '未识别的YApi格式，请确认是YApi导出的JSON'})

            endpoints = []
            for item in items[:20]:
                path = item.get('path', '') or (item.get('query_path') or {}).get('path', '')
                ep = {
                    'title': item.get('title', ''),
                    'path': path,
                    'method': (item.get('method') or 'GET').upper(),
                    'desc': (item.get('desc') or '')[:100],
                }
                # 查询参数
                req_query = item.get('req_query', [])
                if req_query:
                    ep['params'] = [{'name': q.get('name',''), 'required': q.get('required')=='1',
                                      'desc': q.get('desc','')} for q in req_query[:10]]
                # 请求体: req_body_other (JSON) 或 req_body_form (表单)
                body = item.get('req_body_other', '') or item.get('req_body_form', [])
                if isinstance(body, str) and body:
                    try: body = json.loads(body)
                    except: pass
                ep['req_body'] = str(body)[:200] if body else ''
                # 响应体
                res = item.get('res_body', '')
                if isinstance(res, str) and res:
                    try: res = json.loads(res)
                    except: pass
                ep['res_body'] = str(res)[:200] if res else ''
                endpoints.append(ep)

            return json.dumps({
                'total': len(items),
                'count': len(endpoints),
                'endpoints': endpoints,
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({'error': str(e)}, ensure_ascii=False)


@register_tool('list_session_files')
class ListSessionFiles(BaseTool):
    """列出会话文件"""
    description = '列出会话所有已上传文件，Agent可自行发现'
    parameters = []

    def call(self, params: Union[str, dict], **kwargs) -> str:
        from apps.assistant.models import AgentFile
        files = AgentFile.objects.filter(source='upload').order_by('-created_at')[:20]
        results = [{'id': f.id, 'file_name': f.file_name, 'file_path': f.file_path,
                     'file_size': f.file_size} for f in files]
        return json.dumps({'count': len(results), 'files': results,
                          'hint': '用 read_session_file(file_path=...) 读内容'}, ensure_ascii=False, default=str)


@register_tool('read_session_file')
class ReadSessionFile(BaseTool):
    """读取会话文件内容"""
    description = '读取会话文件内容。JSON/YAML用此工具；PDF/Word/Excel用simple_doc_parser'
    parameters = [
        {'name': 'file_path', 'type': 'string', 'description': '文件路径', 'required': True},
    ]

    def call(self, params: Union[str, dict], **kwargs) -> str:
        if isinstance(params, str):
            params = json.loads(params)
        fp = params.get('file_path', '')
        if not fp:
            return json.dumps({'error': '请提供file_path'})
        try:
            if 'uploads' not in os.path.abspath(fp) or 'agent' not in fp:
                return json.dumps({'error': '安全限制：只能读会话文件目录'})
            with open(fp, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            return json.dumps({'file': fp, 'size': len(content),
                              'content': content[:3000], 'truncated': len(content) > 3000}, ensure_ascii=False)
        except FileNotFoundError:
            return json.dumps({'error': f'文件不存在: {fp}'})
        except Exception as e:
            return json.dumps({'error': str(e)})
