import asyncio
import json
import os
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from agents import (
    MaxTurnsExceeded,
    RawResponsesStreamEvent,
    RunContextWrapper,
    RunItemStreamEvent,
)

from apps.assistant import tools
from apps.assistant.agent import TestHubAgent
from apps.assistant.context import TestHubContext

User = get_user_model()


def _ctx(user, project_id=None):
    return RunContextWrapper(
        TestHubContext(
            user=user,
            user_id=user.id if user else 0,
            project_id=project_id,
        )
    )


class AssistantToolPermissionTests(TestCase):
    """权限/安全相关工具测试。"""

    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="x")
        self.member = User.objects.create_user(username="member", password="x")
        self.outsider = User.objects.create_user(username="outsider", password="x")
        self.admin = User.objects.create_superuser(
            username="admin", password="x", email="admin@test.com"
        )

        from apps.projects.models import Project, ProjectMember

        self.project = Project.objects.create(name="P1", owner=self.owner)
        ProjectMember.objects.create(project=self.project, user=self.member, role="tester")

        from apps.api_testing.models import ApiCollection, ApiProject, ApiRequest

        self.api_project = ApiProject.objects.create(
            name="API1",
            project_type="HTTP",
            status="IN_PROGRESS",
            owner=self.owner,
            main_project=self.project,
        )
        self.collection = ApiCollection.objects.create(name="C1", project=self.api_project)
        self.api_request = ApiRequest.objects.create(
            collection=self.collection,
            name="R1",
            method="GET",
            url="https://example.com/api",
            created_by=self.owner,
        )

        from apps.testcases.models import TestCase

        self.testcase = TestCase.objects.create(
            project=self.project,
            title="TC1",
            expected_result="ok",
            author=self.owner,
        )

        from apps.ui_automation.models import MidsceneProject

        self.midscene = MidsceneProject.objects.create(
            name="M1", owner=self.owner, main_project=self.project
        )

    def test_require_project_allows_member_owner_admin(self):
        tools.require_project(_ctx(self.owner), self.project.id)
        tools.require_project(_ctx(self.member), self.project.id)
        tools.require_project(_ctx(self.admin), self.project.id)

    def test_require_project_denies_outsider(self):
        with self.assertRaises(tools.ToolPermissionError):
            tools.require_project(_ctx(self.outsider), self.project.id)

    def test_require_api_access_denies_outsider(self):
        with self.assertRaises(tools.ToolPermissionError):
            tools.require_api_access(_ctx(self.outsider), self.api_request.id)
        req = tools.require_api_access(_ctx(self.member), self.api_request.id)
        self.assertEqual(req.id, self.api_request.id)

    def test_require_testcase_access_denies_outsider(self):
        with self.assertRaises(tools.ToolPermissionError):
            tools.require_testcase_access(_ctx(self.outsider), self.testcase.id)

    def test_require_midscene_access_denies_outsider(self):
        with self.assertRaises(tools.ToolPermissionError):
            tools.require_midscene_access(_ctx(self.outsider), self.midscene.id)

    def test_search_testcases_scoped(self):
        results = tools.search_testcases(
            _ctx(self.member, self.project.id),
            project_id=self.project.id,
            keyword="TC1",
        )
        self.assertEqual(results["total"], 1)
        with self.assertRaises(tools.ToolPermissionError):
            tools.search_testcases(
                _ctx(self.outsider, self.project.id),
                project_id=self.project.id,
            )

    def test_search_testcases_pagination(self):
        from apps.testcases.models import TestCase

        for i in range(25):
            TestCase.objects.create(
                project=self.project,
                title=f"PAG-{i:02d}",
                expected_result="ok",
                author=self.owner,
            )
        page1 = tools.search_testcases(
            _ctx(self.member, self.project.id),
            project_id=self.project.id,
            page=1,
            page_size=10,
        )
        page3 = tools.search_testcases(
            _ctx(self.member, self.project.id),
            project_id=self.project.id,
            page=3,
            page_size=10,
        )
        self.assertEqual(page1["total"], 26)  # 含 setUp 的 TC1
        self.assertEqual(page1["total_pages"], 3)
        self.assertEqual(len(page1["results"]), 10)
        self.assertEqual(len(page3["results"]), 6)
        self.assertNotIn("hint", page3)

    def test_analyze_testcases_stats(self):
        from apps.testcases.models import TestCase, TestCaseStep

        t1 = TestCase.objects.create(
            project=self.project,
            title="重复标题",
            expected_result="ok",
            author=self.owner,
            priority="high",
            status="active",
            test_type="api",
            description="有描述",
        )
        TestCaseStep.objects.create(
            testcase=t1, step_number=1, action="点按钮", expected="弹窗"
        )
        TestCase.objects.create(
            project=self.project,
            title="重复标题",
            expected_result="",
            author=self.owner,
            priority="low",
            status="draft",
            test_type="functional",
        )
        resp = tools.analyze_testcases(_ctx(self.member), self.project.id)
        self.assertEqual(resp["total"], 3)  # TC1 + t1 + t2
        self.assertEqual(resp["by_status"], {"active": 1, "draft": 2})
        self.assertEqual(resp["by_priority"], {"medium": 1, "high": 1, "low": 1})
        self.assertEqual(
            resp["quality_gaps"],
            {"missing_description": 2, "missing_expected_result": 1, "missing_steps": 2},
        )
        self.assertEqual(resp["duplicate_titles"], [{"title": "重复标题", "count": 2}])

    def test_get_testcase_detail(self):
        from apps.testcases.models import TestCaseStep

        TestCaseStep.objects.create(
            testcase=self.testcase, step_number=1, action="打开页面", expected="页面显示"
        )
        resp = tools.get_testcase_detail(_ctx(self.member), self.testcase.id)
        self.assertEqual(resp["id"], self.testcase.id)
        self.assertEqual(resp["title"], "TC1")
        self.assertEqual(resp["step_count"], 1)
        self.assertIn("打开页面", resp["steps"])
        self.assertFalse(resp["steps_truncated"])
        with self.assertRaises(tools.ToolPermissionError):
            tools.get_testcase_detail(_ctx(self.outsider), self.testcase.id)

    def test_update_api_test_only_changes_whitelisted_fields(self):
        resp = tools.update_api_test(
            _ctx(self.member, self.project.id),
            request_id=self.api_request.id,
            url="https://new.example.com/x",
        )
        self.assertEqual(resp["success"], True)
        self.assertEqual(resp["changed_fields"], ["url"])
        self.api_request.refresh_from_db()
        self.assertEqual(self.api_request.url, "https://new.example.com/x")

    def test_get_api_detail_truncates_large_fields(self):
        self.api_request.headers = {"X-Big": "h" * 3000}
        self.api_request.body = {"big": "b" * 5000}
        self.api_request.save()
        resp = tools.get_api_detail(_ctx(self.member), self.api_request.id)
        self.assertTrue(resp["headers_truncated"])
        self.assertLessEqual(len(resp["headers"]), 2000)
        self.assertTrue(resp["body_truncated"])
        self.assertLessEqual(len(resp["body"]), 2000)

    def test_get_api_detail_keeps_small_fields(self):
        self.api_request.headers = {"Content-Type": "application/json"}
        self.api_request.save()
        resp = tools.get_api_detail(_ctx(self.member), self.api_request.id)
        self.assertFalse(resp["headers_truncated"])
        self.assertIn("Content-Type", resp["headers"])

    def test_execute_api_blocks_private_url(self):
        self.api_request.url = "http://127.0.0.1:8000/secret"
        self.api_request.save()
        with self.assertRaises(tools.ToolPermissionError):
            tools.execute_api(
                _ctx(self.member, self.project.id),
                request_id=self.api_request.id,
            )

    def test_validate_target_url(self):
        with self.assertRaises(tools.ToolPermissionError):
            tools._validate_target_url("http://192.168.1.1/x")
        with self.assertRaises(tools.ToolPermissionError):
            tools._validate_target_url("ftp://example.com/x")
        self.assertEqual(
            tools._validate_target_url("https://api.example.com/x"),
            "https://api.example.com/x",
        )

    def test_safe_session_path_isolates_user_sessions(self):
        from apps.assistant.models import AssistantSession

        with tempfile.TemporaryDirectory() as tmp:
            media_root = os.path.join(tmp, "media")
            sess_dir = os.path.join(media_root, "uploads", "agent", "sess-owner")
            other_dir = os.path.join(media_root, "uploads", "agent", "sess-other")
            os.makedirs(sess_dir)
            os.makedirs(other_dir)
            f1 = os.path.join(sess_dir, "a.json")
            with open(f1, "w", encoding="utf-8") as f:
                f.write('{"a": 1}')
            f2 = os.path.join(other_dir, "b.json")
            with open(f2, "w", encoding="utf-8") as f:
                f.write("{}")

            AssistantSession.objects.create(
                user=self.member,
                session_id="sess-owner",
                title="t",
            )
            with override_settings(MEDIA_ROOT=media_root):
                resolved = tools._safe_session_path(_ctx(self.member), f1)
                self.assertEqual(os.path.realpath(resolved), os.path.realpath(f1))
                with self.assertRaises(tools.ToolPermissionError):
                    tools._safe_session_path(_ctx(self.member), f2)
                with self.assertRaises(tools.ToolPermissionError):
                    tools._safe_session_path(_ctx(self.member), os.path.join(tmp, "x.txt"))


class AgentStreamEventTests(TestCase):
    """事件适配与同步桥测试（不依赖真实模型）。"""

    @staticmethod
    async def _collect(agent, message="hi"):
        events = []
        async for ev in agent._achat(message):
            events.append(ev)
        return events

    def test_stream_event_mapping(self):
        agent = TestHubAgent()

        async def _fake_create():
            return object()

        agent._create_agent = _fake_create

        async def fake_stream():
            yield RawResponsesStreamEvent(
                data=SimpleNamespace(type="response.output_text.delta", delta="你好")
            )
            yield RunItemStreamEvent(
                name="tool_called",
                item=SimpleNamespace(
                    raw_item=SimpleNamespace(
                        id="c1", name="search_apis", arguments='{"project_id": 1}'
                    )
                ),
            )
            yield RunItemStreamEvent(
                name="tool_output",
                item=SimpleNamespace(
                    raw_item=SimpleNamespace(
                        id="c1", name="search_apis", output='{"success": true}'
                    )
                ),
            )

        fake_result = SimpleNamespace(stream_events=fake_stream, final_output="完成")
        with patch("apps.assistant.agent.Runner.run_streamed", return_value=fake_result):
            events = asyncio.run(self._collect(agent))

        self.assertEqual(
            [e["type"] for e in events],
            ["message_delta", "tool_start", "tool_output", "run_done"],
        )
        self.assertEqual(events[1]["name"], "search_apis")
        self.assertEqual(events[1]["args"], {"project_id": 1})
        self.assertEqual(events[3]["final_output"], "完成")

    def test_max_turns_exceeded_yields_error(self):
        agent = TestHubAgent()

        async def _fake_create():
            return object()

        agent._create_agent = _fake_create

        async def fake_stream():
            raise MaxTurnsExceeded("too many turns")
            yield  # pragma: no cover

        fake_result = SimpleNamespace(stream_events=fake_stream, final_output="")
        with patch("apps.assistant.agent.Runner.run_streamed", return_value=fake_result):
            events = asyncio.run(self._collect(agent))

        self.assertEqual(events[0]["type"], "error")
        self.assertEqual(events[1]["type"], "run_done")
        self.assertTrue(events[1]["max_turns_exceeded"])

    def test_sync_bridge(self):
        agent = TestHubAgent()

        async def fake_achat(self, message, history=None):
            yield {"type": "message_delta", "content": "hi"}
            yield {"type": "run_done", "final_output": "hi", "tool_calls": []}

        agent._achat = fake_achat.__get__(agent)
        events = list(agent.chat("hi"))
        self.assertEqual([e["type"] for e in events], ["message_delta", "run_done"])


class ToolRegistryTests(TestCase):
    def test_registered_tools(self):
        names = tools.registered_tool_names()
        for expected in [
            "get_project_overview",
            "create_api_test",
            "execute_api",
            "update_midscene_case",
            "read_session_file",
            "simple_doc_parser",
        ]:
            self.assertIn(expected, names)
        self.assertNotIn("bash", names)
        for tool in tools.get_registered_tools():
            self.assertTrue(tool.name)
            self.assertTrue(tool.description)


class ToolGroupTests(TestCase):
    """工具组解析：按后台功能模块裁剪工具。"""

    def test_all_groups_cover_all_tools(self):
        grouped = set()
        for names in tools.TOOL_GROUPS.values():
            grouped.update(names)
        self.assertEqual(grouped, set(tools.registered_tool_names()))

    def test_resolve_all_when_empty(self):
        self.assertEqual(
            tools.resolve_tool_names(),
            list(tools.TOOL_REGISTRY.keys()),
        )
        self.assertEqual(
            tools.resolve_tool_names([]),
            list(tools.TOOL_REGISTRY.keys()),
        )

    def test_resolve_specific_groups(self):
        names = tools.resolve_tool_names(["testcases", "documents"])
        self.assertEqual(
            set(names),
            set(tools.TOOL_GROUPS["testcases"]) | set(tools.TOOL_GROUPS["documents"]),
        )
        self.assertNotIn("create_api_test", names)

    def test_unknown_groups_fallback_to_all(self):
        names = tools.resolve_tool_names(["not_exist_group"])
        self.assertEqual(names, list(tools.TOOL_REGISTRY.keys()))

    def test_agent_loads_tool_groups_from_config(self):
        from apps.assistant.agent import TestHubAgent

        agent = TestHubAgent(
            llm_config={
                "provider": "qwen",
                "model": "qwen-plus",
                "base_url": "https://example.com/v1",
                "api_key": "k",
                "max_tool_calls": 5,
                "tool_groups": ["testcases"],
            }
        )
        self.assertEqual(agent.tool_names, tools.resolve_tool_names(["testcases"]))

        agent_all = TestHubAgent(
            llm_config={
                "provider": "qwen",
                "model": "qwen-plus",
                "base_url": "https://example.com/v1",
                "api_key": "k",
                "max_tool_calls": 5,
                "tool_groups": [],
            }
        )
        self.assertIsNone(agent_all.tool_names)


class YApiParserTests(TestCase):
    """parse_yapi 应解析全部接口，不再被硬编码的 20 条截断。"""

    def _yapi_data(self, count: int) -> str:
        groups = [
            {
                "name": "v3.7.5",
                "list": [
                    {
                        "path": f"/api/{i}",
                        "method": "GET" if i % 2 == 0 else "POST",
                        "title": f"接口{i}",
                        "req_query": [{"name": "q", "required": "1", "desc": "参数"}],
                        "req_body_other": '{"type":"object"}',
                        "res_body": '{"type":"object"}',
                    }
                    for i in range(count)
                ],
            }
        ]
        return json.dumps(groups)

    def test_parses_all_endpoints_by_default(self):
        resp = tools.parse_yapi(_ctx(None), content=self._yapi_data(24))
        self.assertEqual(resp["total"], 24)
        self.assertEqual(resp["count"], 24)
        self.assertEqual(len(resp["endpoints"]), 24)
        self.assertNotIn("hint", resp)

    def test_limit_caps_endpoints_with_hint(self):
        resp = tools.parse_yapi(_ctx(None), content=self._yapi_data(24), limit=5)
        self.assertEqual(resp["total"], 24)
        self.assertEqual(resp["count"], 5)
        self.assertEqual(len(resp["endpoints"]), 5)
        self.assertIn("hint", resp)

    def test_query_params_not_truncated(self):
        data = json.dumps(
            [
                {
                    "name": "v1",
                    "list": [
                        {
                            "path": "/api/x",
                            "method": "GET",
                            "title": "x",
                            "req_query": [
                                {"name": f"p{i}", "required": "1", "desc": ""}
                                for i in range(12)
                            ],
                        }
                    ],
                }
            ]
        )
        resp = tools.parse_yapi(_ctx(None), content=data)
        self.assertEqual(len(resp["endpoints"][0]["params"]), 12)

    def test_large_docs_fall_back_to_summary(self):
        resp = tools.parse_yapi(_ctx(None), content=self._yapi_data(60))
        self.assertEqual(resp["total"], 60)
        self.assertEqual(resp["count"], 60)
        self.assertTrue(resp["summary_mode"])
        self.assertIn("hint", resp)
        self.assertNotIn("params", resp["endpoints"][0])
        self.assertNotIn("req_body", resp["endpoints"][0])

    def test_large_docs_still_return_full_with_limit(self):
        resp = tools.parse_yapi(_ctx(None), content=self._yapi_data(60), limit=3)
        self.assertNotIn("summary_mode", resp)
        self.assertIn("params", resp["endpoints"][0])


class TestSuiteToolTests(TestCase):
    """测试套件/套件用例工具（建接口→组套件→配执行用例链路）。"""

    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.owner = User.objects.create_user(username="suite-owner", password="x")
        self.member = User.objects.create_user(username="suite-member", password="x")
        self.outsider = User.objects.create_user(username="suite-outsider", password="x")

        from apps.projects.models import Project, ProjectMember

        self.project = Project.objects.create(name="SuiteP", owner=self.owner)
        ProjectMember.objects.create(project=self.project, user=self.member, role="tester")

        from apps.api_testing.models import ApiCollection, ApiProject, ApiRequest, TestSuite

        self.api_project = ApiProject.objects.create(
            name="SuiteAPI",
            project_type="HTTP",
            status="IN_PROGRESS",
            owner=self.owner,
            main_project=self.project,
        )
        self.collection = ApiCollection.objects.create(
            name="C1", project=self.api_project
        )
        self.api_request = ApiRequest.objects.create(
            collection=self.collection,
            name="R1",
            method="GET",
            url="https://example.com/api",
            created_by=self.owner,
        )
        self.suite = TestSuite.objects.create(
            project=self.api_project,
            name="S1",
            description="",
            created_by=self.owner,
        )

    def test_create_and_add_suite_request(self):
        resp = tools.create_test_suite(
            _ctx(self.member, self.project.id),
            project_id=self.project.id,
            name="S2",
        )
        self.assertTrue(resp["success"])
        suite_id = resp["id"]

        add = tools.add_suite_request(
            _ctx(self.member, self.project.id),
            test_suite_id=suite_id,
            request_id=self.api_request.id,
            name="正常场景",
            params={"userid": "123"},
            assertions=[{"name": "status==200", "type": "status_code", "target": 200}],
        )
        self.assertTrue(add["success"])
        self.assertEqual(add["order"], 0)
        self.assertEqual(add["existing_cases_in_suite"], 1)

        listed = tools.list_suite_requests(_ctx(self.member), suite_id)
        self.assertEqual(listed["total"], 1)
        self.assertEqual(listed["results"][0]["name"], "正常场景")
        self.assertTrue(listed["results"][0]["has_params_override"])
        self.assertEqual(listed["results"][0]["assertion_count"], 1)

    def test_create_suite_requires_api_project(self):
        from apps.projects.models import Project

        empty = Project.objects.create(name="Empty", owner=self.owner)
        resp = tools.create_test_suite(
            _ctx(self.owner, empty.id),
            project_id=empty.id,
            name="NoAPI",
        )
        self.assertFalse(resp["success"])

    def test_update_and_delete_suite_request(self):
        from apps.api_testing.models import TestSuiteRequest

        case = TestSuiteRequest.objects.create(
            test_suite=self.suite,
            request=self.api_request,
            name="C1",
            order=0,
            enabled=True,
        )
        upd = tools.update_suite_request(
            _ctx(self.member, self.project.id),
            suite_request_id=case.id,
            order=5,
            enabled=False,
            params={"a": "b"},
        )
        self.assertTrue(upd["success"])
        self.assertEqual(sorted(upd["changed_fields"]), ["enabled", "order", "params"])
        case.refresh_from_db()
        self.assertEqual(case.order, 5)
        self.assertFalse(case.enabled)
        self.assertEqual(case.params, {"a": "b"})

        deleted = tools.delete_suite_request(_ctx(self.member), case.id)
        self.assertTrue(deleted["success"])
        self.assertFalse(TestSuiteRequest.objects.filter(id=case.id).exists())

    def test_execute_test_suite_slims_output(self):
        from unittest.mock import patch

        fake_result = {
            "success": True,
            "execution_id": 99,
            "passed_count": 1,
            "failed_count": 1,
            "total_count": 2,
            "results": [
                {
                    "case_name": "A",
                    "method": "GET",
                    "url": "https://example.com/api",
                    "status_code": 200,
                    "response_time": 10,
                    "passed": True,
                    "error": "",
                    "assertions_results": [{"name": "x"}],
                    "variables_before": {"k": "v"},
                    "extracted_variables": {"t": "1"},
                },
                {
                    "case_name": "B",
                    "method": "GET",
                    "url": "https://example.com/api",
                    "status_code": 500,
                    "response_time": 20,
                    "passed": False,
                    "error": "断言失败: status",
                },
            ],
        }
        with patch("apps.api_testing.services.execute_suite", return_value=fake_result):
            resp = tools.execute_test_suite(_ctx(self.member), self.suite.id)
        self.assertTrue(resp["success"])
        self.assertEqual(resp["passed_count"], 1)
        self.assertEqual(resp["failed_count"], 1)
        self.assertEqual(len(resp["results"]), 2)
        self.assertNotIn("assertions_results", resp["results"][0])
        self.assertNotIn("variables_before", resp["results"][0])

    def test_suite_tools_deny_outsider(self):
        from apps.api_testing.models import TestSuiteRequest

        case = TestSuiteRequest.objects.create(
            test_suite=self.suite,
            request=self.api_request,
            name="C1",
            order=0,
        )
        with self.assertRaises(tools.ToolPermissionError):
            tools.add_suite_request(
                _ctx(self.outsider, self.project.id),
                test_suite_id=self.suite.id,
                request_id=self.api_request.id,
            )
        with self.assertRaises(tools.ToolPermissionError):
            tools.update_suite_request(_ctx(self.outsider), suite_request_id=case.id, order=1)
        with self.assertRaises(tools.ToolPermissionError):
            tools.list_suite_requests(_ctx(self.outsider), self.suite.id)
        with self.assertRaises(tools.ToolPermissionError):
            tools.execute_test_suite(_ctx(self.outsider), self.suite.id)


class AgentConfigProtocolTests(TestCase):
    """AgentConfig 协议字段与 sdk_runtime 强制协议逻辑。"""

    def setUp(self):
        from apps.assistant.models import AgentConfig

        self.config = AgentConfig.objects.create(
            name="Default",
            provider="qwen",
            model_name="qwen-plus",
            api_key="test-key",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            api_protocol="auto",
            is_active=True,
        )

    def test_serializer_contains_protocol(self):
        from apps.assistant.serializers import AgentConfigSerializer

        data = AgentConfigSerializer(self.config).data
        self.assertEqual(data["api_protocol"], "auto")
        self.assertEqual(data["tool_groups"], [])
        self.assertNotIn("api_key", data)

    def test_load_llm_config_reads_protocol(self):
        from apps.assistant import sdk_runtime

        cfg = sdk_runtime.load_llm_config()
        self.assertEqual(cfg["api_protocol"], "auto")
        self.assertEqual(cfg["model"], "qwen-plus")
        self.assertEqual(cfg["tool_groups"], [])

        self.config.api_protocol = "chat_completions"
        self.config.tool_groups = ["api_testing"]
        self.config.save()
        cfg = sdk_runtime.load_llm_config()
        self.assertEqual(cfg["api_protocol"], "chat_completions")
        self.assertEqual(cfg["tool_groups"], ["api_testing"])

    def test_supports_responses_forced_protocol(self):
        from apps.assistant import sdk_runtime

        base = {
            "base_url": "https://example.com/v1",
            "model": "m",
            "api_key": "k",
        }
        # 显式指定协议时不做网络探测
        with patch("apps.assistant.sdk_runtime._probe_responses") as probe:
            self.assertTrue(asyncio.run(sdk_runtime.supports_responses(
                {**base, "api_protocol": "responses"})))
            self.assertFalse(asyncio.run(sdk_runtime.supports_responses(
                {**base, "api_protocol": "chat_completions"})))
            probe.assert_not_called()

    def test_supports_responses_auto_probes(self):
        from apps.assistant import sdk_runtime

        base = {
            "base_url": "https://example.com/v1",
            "model": "m",
            "api_key": "k",
            "api_protocol": "auto",
        }
        sdk_runtime._probe_cache.clear()

        async def probe_false(client, model):
            return False

        async def probe_true(client, model):
            return True

        with patch("apps.assistant.sdk_runtime._probe_responses", side_effect=probe_false):
            self.assertFalse(asyncio.run(sdk_runtime.supports_responses(base)))
        sdk_runtime._probe_cache.clear()
        with patch("apps.assistant.sdk_runtime._probe_responses", side_effect=probe_true):
            self.assertTrue(asyncio.run(sdk_runtime.supports_responses(base)))


class AgentConfigConnectionTests(TestCase):
    """AgentConfig test_connection 接口。"""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="cfguser", password="x")
        self.client.force_login(self.user)

        from apps.assistant.models import AgentConfig

        self.config = AgentConfig.objects.create(
            name="Default",
            provider="qwen",
            model_name="qwen-plus",
            api_key="stored-key",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            api_protocol="auto",
            is_active=True,
        )

    def _fake_post(self, responses_ok=True, chat_ok=False):
        def post(url, **kwargs):
            if url.endswith("/responses"):
                resp = Mock(status_code=200 if responses_ok else 400)
                resp.text = "resp-error"
            else:
                resp = Mock(status_code=200 if chat_ok else 400)
                resp.text = "chat-error"
            resp.headers = {}
            return resp

        return patch("apps.assistant.views_config.requests.post", side_effect=post)

    def test_connection_requires_key_when_not_stored(self):
        resp = self.client.post("/api/assistant/config/agent/test_connection/", {
            "model_name": "qwen-plus",
            "base_url": "https://example.com/v1",
        }, content_type="application/json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("API Key", resp.json()["error"])

    def test_connection_with_stored_key_and_responses(self):
        with self._fake_post(responses_ok=True):
            resp = self.client.post("/api/assistant/config/agent/test_connection/", {
                "config_id": self.config.id,
                "use_stored_key": True,
                "api_protocol": "auto",
            }, content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["protocol"], "responses")

    def test_connection_forced_chat_completions(self):
        with self._fake_post(responses_ok=False, chat_ok=True):
            resp = self.client.post("/api/assistant/config/agent/test_connection/", {
                "config_id": self.config.id,
                "use_stored_key": True,
                "api_protocol": "chat_completions",
            }, content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["protocol"], "chat_completions")

    def test_connection_auto_fallback_to_chat(self):
        with self._fake_post(responses_ok=False, chat_ok=True):
            resp = self.client.post("/api/assistant/config/agent/test_connection/", {
                "config_id": self.config.id,
                "use_stored_key": True,
                "api_protocol": "auto",
            }, content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["protocol"], "chat_completions")
        self.assertFalse(data["protocol_support"]["responses"])
        self.assertTrue(data["protocol_support"]["chat_completions"])

    def test_connection_all_protocols_fail(self):
        with self._fake_post(responses_ok=False, chat_ok=False):
            resp = self.client.post("/api/assistant/config/agent/test_connection/", {
                "config_id": self.config.id,
                "use_stored_key": True,
                "api_protocol": "auto",
            }, content_type="application/json")
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()["success"])
