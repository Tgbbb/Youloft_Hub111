# -*- coding: utf-8 -*-
"""项目统一身份（main_project 绑定）相关测试。"""
import json

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from apps.projects.linkage import (
    backfill_main_projects,
    map_status,
    resolve_or_create_main_project,
)
from apps.projects.models import Project
from apps.api_testing.models import ApiProject
from apps.app_automation.models import AppProject
from apps.ui_automation.models import UiProject, MidsceneProject

from apps.api_testing.serializers import ApiProjectSerializer
from apps.ui_automation.serializers import UiProjectCreateSerializer
from apps.app_automation.serializers import AppProjectCreateSerializer
from apps.ui_automation.serializers_midscene import MidsceneProjectSerializer


User = get_user_model()


class LinkageHelperTests(TestCase):
    """linkage 解析/补建规则的单元测试。"""

    def setUp(self):
        self.owner = User.objects.create_user(username='owner', password='pass')
        self.other = User.objects.create_user(username='other', password='pass')

    def test_map_status(self):
        self.assertEqual(map_status('NOT_STARTED'), 'paused')
        self.assertEqual(map_status('IN_PROGRESS'), 'active')
        self.assertEqual(map_status('COMPLETED'), 'completed')
        self.assertEqual(map_status('unknown'), 'active')
        self.assertEqual(map_status(''), 'active')

    def test_reuse_same_name_and_owner(self):
        main = Project.objects.create(name='万年历', owner=self.owner)
        resolved = resolve_or_create_main_project(
            Project, ApiProject,
            name='万年历', owner_id=self.owner.pk, status='IN_PROGRESS',
        )
        self.assertEqual(resolved.pk, main.pk)
        self.assertEqual(Project.objects.count(), 1)

    def test_reuse_name_only(self):
        main = Project.objects.create(name='万年历', owner=self.owner)
        resolved = resolve_or_create_main_project(
            Project, ApiProject,
            name='万年历', owner_id=self.other.pk, status='IN_PROGRESS',
        )
        self.assertEqual(resolved.pk, main.pk)
        self.assertEqual(Project.objects.count(), 1)

    def test_auto_create_when_no_match(self):
        resolved = resolve_or_create_main_project(
            Project, ApiProject,
            name='全新项目', owner_id=self.owner.pk, status='COMPLETED',
            description='desc',
        )
        self.assertEqual(Project.objects.count(), 1)
        self.assertEqual(resolved.name, '全新项目')
        self.assertEqual(resolved.status, 'completed')
        self.assertEqual(resolved.owner_id, self.owner.pk)
        self.assertEqual(resolved.description, 'desc')

    def test_auto_create_when_candidate_occupied(self):
        main = Project.objects.create(name='万年历', owner=self.owner)
        ApiProject.objects.create(
            name='万年历', project_type='HTTP', status='IN_PROGRESS',
            owner=self.owner, main_project=main,
        )
        resolved = resolve_or_create_main_project(
            Project, ApiProject,
            name='万年历', owner_id=self.other.pk, status='IN_PROGRESS',
        )
        self.assertNotEqual(resolved.pk, main.pk)
        self.assertEqual(Project.objects.count(), 2)
        self.assertEqual(resolved.name, '万年历')

    def test_occupancy_is_per_module_table(self):
        main = Project.objects.create(name='心动日常', owner=self.owner)
        AppProject.objects.create(
            name='心动日常', status='IN_PROGRESS', owner=self.owner, main_project=main,
        )
        # 不同模块表（app 与 api）可绑定同一个公共项目
        resolved = resolve_or_create_main_project(
            Project, ApiProject,
            name='心动日常', owner_id=self.owner.pk, status='IN_PROGRESS',
        )
        self.assertEqual(resolved.pk, main.pk)
        self.assertEqual(Project.objects.count(), 1)

    def test_backfill_skips_bound_rows(self):
        main = Project.objects.create(name='已绑定', owner=self.owner)
        ApiProject.objects.create(
            name='已绑定', project_type='HTTP', status='IN_PROGRESS',
            owner=self.owner, main_project=main,
        )
        count = backfill_main_projects(Project, ApiProject)
        self.assertEqual(count, 0)
        self.assertEqual(Project.objects.count(), 1)

    def test_one_to_one_unique_constraint_per_table(self):
        main = Project.objects.create(name='唯一', owner=self.owner)
        ApiProject.objects.create(
            name='唯一', project_type='HTTP', status='IN_PROGRESS',
            owner=self.owner, main_project=main,
        )
        with self.assertRaises(IntegrityError):
            ApiProject.objects.create(
                name='重复绑定', project_type='HTTP', status='IN_PROGRESS',
                owner=self.owner, main_project=main,
            )


class ModuleProjectSerializerTests(TestCase):
    """模块项目序列化器：自动绑定、显式绑定、唯一性校验。"""

    def setUp(self):
        self.user = User.objects.create_user(username='apiowner', password='pass')
        self.factory = APIRequestFactory()

    def _request(self):
        request = self.factory.post('/api/testing/projects/')
        request.user = self.user
        return request

    def test_api_create_auto_binds_main_project(self):
        serializer = ApiProjectSerializer(
            data={
                'name': '自动绑定项目',
                'project_type': 'HTTP',
                'status': 'IN_PROGRESS',
            },
            context={'request': self._request()},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        project = serializer.save()
        self.assertIsNotNone(project.main_project_id)
        self.assertEqual(project.main_project.name, '自动绑定项目')
        data = ApiProjectSerializer(project).data
        self.assertEqual(data['main_project'], project.main_project_id)
        self.assertEqual(data['main_project_name'], '自动绑定项目')

    def test_api_create_with_explicit_main_project(self):
        main = Project.objects.create(name='显式主项目', owner=self.user)
        serializer = ApiProjectSerializer(
            data={
                'name': '子项目',
                'project_type': 'HTTP',
                'status': 'IN_PROGRESS',
                'main_project': main.pk,
            },
            context={'request': self._request()},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        project = serializer.save()
        self.assertEqual(project.main_project_id, main.pk)

    def test_api_create_rejects_occupied_main_project(self):
        main = Project.objects.create(name='占用主项目', owner=self.user)
        ApiProject.objects.create(
            name='已绑定', project_type='HTTP', status='IN_PROGRESS',
            owner=self.user, main_project=main,
        )
        serializer = ApiProjectSerializer(
            data={
                'name': '重复',
                'project_type': 'HTTP',
                'status': 'IN_PROGRESS',
                'main_project': main.pk,
            },
            context={'request': self._request()},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('main_project', serializer.errors)

    def test_ui_create_auto_binds_main_project(self):
        serializer = UiProjectCreateSerializer(
            data={
                'name': 'UI自动绑定',
                'status': 'IN_PROGRESS',
                'base_url': 'https://example.com',
                'owner': self.user.pk,
            },
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        project = serializer.save()
        self.assertIsNotNone(project.main_project_id)
        self.assertEqual(project.main_project.name, 'UI自动绑定')

    def test_app_create_auto_binds_main_project(self):
        serializer = AppProjectCreateSerializer(
            data={
                'name': 'APP自动绑定',
                'status': 'IN_PROGRESS',
            },
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        project = serializer.save(owner=self.user)
        self.assertIsNotNone(project.main_project_id)
        self.assertEqual(project.main_project.name, 'APP自动绑定')

    def test_midscene_create_auto_binds_main_project(self):
        serializer = MidsceneProjectSerializer(
            data={
                'name': 'Midscene自动绑定',
            },
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        project = serializer.save(owner=self.user)
        self.assertIsNotNone(project.main_project_id)
        self.assertEqual(project.main_project.name, 'Midscene自动绑定')


class AssistantLinkageTests(TestCase):
    """助手按 main_project 硬绑定查询，不再依赖名称匹配。"""

    def setUp(self):
        self.user = User.objects.create_user(username='assistowner', password='pass')

    def test_project_overview_counts_bound_api_project(self):
        from apps.assistant.tools import GetProjectOverview

        main = Project.objects.create(name='demo', owner=self.user)
        ApiProject.objects.create(
            name='demo', project_type='HTTP', status='IN_PROGRESS',
            owner=self.user, main_project=main,
        )
        # 未绑定的同名项目不应被统计到
        ApiProject.objects.create(
            name='demo', project_type='HTTP', status='IN_PROGRESS',
            owner=self.user, main_project=Project.objects.create(
                name='demo-other', owner=self.user,
            ),
        )

        resp = json.loads(GetProjectOverview().call(json.dumps({'project_id': main.pk})))
        self.assertNotIn('error', resp)
        self.assertEqual(resp['modules']['api_testing']['api_project_count'], 1)
