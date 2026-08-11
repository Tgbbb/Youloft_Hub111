# -*- coding: utf-8 -*-
"""Midscene 用例文件夹功能测试：新建/重命名/删除、用例放入/移出文件夹。"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.projects.models import Project
from apps.ui_automation.models import (
    MidsceneProject, MidsceneCase, MidsceneCaseFolder,
)


User = get_user_model()


class MidsceneFolderApiTests(TestCase):
    """文件夹 API 与用例归属逻辑。"""

    def setUp(self):
        self.owner = User.objects.create_user(username='owner', password='pass')
        self.other = User.objects.create_user(username='other', password='pass')
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.main = Project.objects.create(name='测试主项目', owner=self.owner)
        self.project = MidsceneProject.objects.create(
            name='Midscene项目', owner=self.owner, main_project=self.main,
        )
        self.case = MidsceneCase.objects.create(
            project=self.project, name='用例A', ai_prompt='打开应用',
            created_by=self.owner,
        )

    def test_create_and_rename_folder(self):
        resp = self.client.post(
            '/api/ui-automation/midscene/folders/',
            {'name': '登录模块', 'project': self.project.id},
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        folder_id = resp.data['id']
        self.assertEqual(resp.data['case_count'], 0)

        resp = self.client.patch(
            f'/api/ui-automation/midscene/folders/{folder_id}/',
            {'name': '登录与注册'},
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            MidsceneCaseFolder.objects.get(id=folder_id).name, '登录与注册'
        )

    def test_delete_folder_moves_cases_to_uncategorized(self):
        folder = MidsceneCaseFolder.objects.create(
            project=self.project, name='登录模块', created_by=self.owner,
        )
        self.case.folder = folder
        self.case.save(update_fields=['folder'])

        resp = self.client.delete(f'/api/ui-automation/midscene/folders/{folder.id}/')
        self.assertEqual(resp.status_code, 204)

        self.case.refresh_from_db()
        self.assertIsNone(self.case.folder_id)
        self.assertEqual(MidsceneCase.objects.count(), 1)

    def test_put_case_into_folder_and_move_out(self):
        folder = MidsceneCaseFolder.objects.create(
            project=self.project, name='登录模块', created_by=self.owner,
        )
        payload = {
            'name': self.case.name, 'ai_prompt': self.case.ai_prompt,
            'project_id': self.project.id, 'folder_id': folder.id,
        }
        resp = self.client.put(
            f'/api/ui-automation/midscene/cases/{self.case.id}/', payload,
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.case.refresh_from_db()
        self.assertEqual(self.case.folder_id, folder.id)

        # 显式传 folder_id=null 表示移出文件夹
        payload['folder_id'] = None
        resp = self.client.put(
            f'/api/ui-automation/midscene/cases/{self.case.id}/', payload,
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.case.refresh_from_db()
        self.assertIsNone(self.case.folder_id)

    def test_folder_project_mismatch_rejected(self):
        main2 = Project.objects.create(name='项目2', owner=self.owner)
        p2 = MidsceneProject.objects.create(
            name='项目2', owner=self.owner, main_project=main2,
        )
        folder = MidsceneCaseFolder.objects.create(
            project=p2, name='别的项目文件夹', created_by=self.owner,
        )
        resp = self.client.post(
            '/api/ui-automation/midscene/cases/',
            {
                'name': '用例B', 'ai_prompt': '打开应用',
                'project_id': self.project.id, 'folder_id': folder.id,
            },
        )
        self.assertEqual(resp.status_code, 400)

    def test_non_member_cannot_create_folder_in_project(self):
        other_client = APIClient()
        other_client.force_authenticate(self.other)
        resp = other_client.post(
            '/api/ui-automation/midscene/folders/',
            {'name': '越权文件夹', 'project': self.project.id},
        )
        self.assertEqual(resp.status_code, 403)

    def test_case_serializer_includes_folder_info(self):
        folder = MidsceneCaseFolder.objects.create(
            project=self.project, name='登录模块', created_by=self.owner,
        )
        self.case.folder = folder
        self.case.save(update_fields=['folder'])

        resp = self.client.get(f'/api/ui-automation/midscene/cases/{self.case.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['folder'], folder.id)
        self.assertEqual(resp.data['folder_name'], '登录模块')
