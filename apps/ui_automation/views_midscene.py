# -*- coding: utf-8 -*-
"""
Midscene AI 移动端自动化 - API 视图
"""
import logging
from django.utils import timezone
from django.db import models as db_models
from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import (
    MidsceneProject, MidsceneDevice, MidsceneCase, MidsceneExecutionRecord
)
from .serializers_midscene import (
    MidsceneProjectSerializer,
    MidsceneDeviceSerializer,
    MidsceneDeviceSimpleSerializer,
    MidsceneCaseSerializer,
    MidsceneCaseCreateSerializer,
    MidsceneExecutionRecordSerializer,
)

logger = logging.getLogger(__name__)


class MidsceneProjectViewSet(viewsets.ModelViewSet):
    """Midscene 移动端测试项目"""
    queryset = MidsceneProject.objects.all()
    serializer_class = MidsceneProjectSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'updated_at', 'name']

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(
            db_models.Q(owner=self.request.user) |
            db_models.Q(members=self.request.user)
        ).distinct()

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class MidsceneDeviceViewSet(viewsets.ModelViewSet):
    """Midscene 设备管理（Android + iOS）"""
    queryset = MidsceneDevice.objects.all()
    serializer_class = MidsceneDeviceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['platform', 'status']
    search_fields = ['name', 'device_id']
    ordering_fields = ['platform', 'status', 'created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return MidsceneDeviceSerializer
        return super().get_serializer_class()

    @action(detail=False, methods=['get'])
    def simple_list(self, request):
        """返回简化设备列表（用于下拉选择）"""
        devices = self.get_queryset().filter(status__in=['online', 'available'])
        serializer = MidsceneDeviceSimpleSerializer(devices, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def discover_android(self, request):
        """发现 Android 设备（ADB）"""
        import subprocess
        import platform as sys_platform

        adb_path = request.data.get('adb_path', 'adb')
        try:
            kwargs = {}
            if sys_platform.system() == 'Windows':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

            result = subprocess.run(
                [adb_path, 'devices', '-l'],
                capture_output=True, text=True, timeout=10, **kwargs
            )
            lines = result.stdout.strip().split('\n')[1:]
            discovered = []
            for line in lines:
                line = line.strip()
                if not line or 'offline' in line:
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    device_id = parts[0]
                    status = 'available' if parts[1] == 'device' else 'offline'

                    # 更新或创建
                    device, created = MidsceneDevice.objects.update_or_create(
                        device_id=device_id,
                        defaults={
                            'platform': 'android',
                            'status': status,
                            'adb_serial': device_id,
                            'name': '',
                        }
                    )
                    # 尝试获取设备名称
                    try:
                        info = subprocess.run(
                            [adb_path, '-s', device_id, 'shell', 'getprop', 'ro.product.model'],
                            capture_output=True, text=True, timeout=5, **kwargs
                        )
                        if info.returncode == 0 and info.stdout.strip():
                            device.name = info.stdout.strip()
                        ver = subprocess.run(
                            [adb_path, '-s', device_id, 'shell', 'getprop', 'ro.build.version.release'],
                            capture_output=True, text=True, timeout=5, **kwargs
                        )
                        if ver.returncode == 0 and ver.stdout.strip():
                            device.android_version = ver.stdout.strip()
                        device.save(update_fields=['name', 'android_version'])
                    except Exception:
                        pass

                    discovered.append(device_id)

            return Response({
                'message': f'发现 {len(discovered)} 台 Android 设备',
                'devices': discovered,
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['post'])
    def discover_ios(self, request):
        """发现 iOS 设备（tidevice）"""
        import subprocess
        import platform as sys_platform

        tidevice_path = request.data.get('tidevice_path', 'tidevice')
        try:
            kwargs = {}
            if sys_platform.system() == 'Windows':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

            # tidevice list
            result = subprocess.run(
                [tidevice_path, 'list'],
                capture_output=True, text=True, timeout=10, **kwargs
            )
            discovered = []
            for line in result.stdout.strip().split('\n'):
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) >= 1:
                    udid = parts[0]
                    name = ' '.join(parts[1:]) if len(parts) > 1 else ''

                    device, created = MidsceneDevice.objects.update_or_create(
                        device_id=udid,
                        defaults={
                            'platform': 'ios',
                            'status': 'available',
                            'tidevice_udid': udid,
                            'name': name,
                            'wda_host': f'127.0.0.1:8100',
                        }
                    )

                    # 获取 iOS 版本
                    try:
                        info = subprocess.run(
                            [tidevice_path, 'info', udid],
                            capture_output=True, text=True, timeout=5, **kwargs
                        )
                        if info.returncode == 0:
                            import re
                            ver_match = re.search(r'ProductVersion["\']?\s*:["\']?\s*(\d+\.\d+)', info.stdout)
                            if ver_match:
                                device.ios_version = ver_match.group(1)
                                device.save(update_fields=['ios_version'])
                    except Exception:
                        pass

                    discovered.append(udid)

            return Response({
                'message': f'发现 {len(discovered)} 台 iOS 设备',
                'devices': discovered,
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=True, methods=['post'])
    def lock(self, request, pk=None):
        """锁定设备"""
        device = self.get_object()
        try:
            device.lock(request.user)
            return Response({'status': 'locked'})
        except ValueError as e:
            return Response({'error': str(e)}, status=409)

    @action(detail=True, methods=['post'])
    def unlock(self, request, pk=None):
        """解锁设备"""
        device = self.get_object()
        device.unlock()
        return Response({'status': 'unlocked'})

    @action(detail=True, methods=['post'])
    def screenshot(self, request, pk=None):
        """获取设备实时截图（Base64）"""
        device = self.get_object()
        import subprocess
        import platform as sys_platform
        import base64

        kwargs = {}
        if sys_platform.system() == 'Windows':
            kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

        try:
            if device.platform == 'android':
                adb_path = request.data.get('adb_path', 'adb')
                result = subprocess.run(
                    [adb_path, '-s', device.adb_serial, 'exec-out', 'screencap', '-p'],
                    capture_output=True, timeout=10, **kwargs
                )
                if result.returncode == 0:
                    b64 = base64.b64encode(result.stdout).decode('utf-8')
                    return Response({'screenshot': f'data:image/png;base64,{b64}'})
            elif device.platform == 'ios':
                # iOS 用 WDA 截图
                import requests as req
                wda_url = f'http://{device.wda_host}/screenshot'
                resp = req.get(wda_url, timeout=10)
                if resp.status_code == 200:
                    b64 = base64.b64encode(resp.content).decode('utf-8')
                    return Response({'screenshot': f'data:image/png;base64,{b64}'})

            return Response({'error': '截图失败'}, status=500)
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class MidsceneCaseViewSet(viewsets.ModelViewSet):
    """Midscene AI 用例"""
    queryset = MidsceneCase.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['project']
    search_fields = ['name', 'ai_prompt']
    ordering_fields = ['created_at', 'updated_at', 'name']

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return MidsceneCaseCreateSerializer
        return MidsceneCaseSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        """执行 Midscene 用例"""
        midscene_case = self.get_object()
        device_id = request.data.get('device_id')

        if not device_id:
            return Response({'error': '请选择执行设备'}, status=400)

        try:
            device = MidsceneDevice.objects.get(id=device_id)
        except MidsceneDevice.DoesNotExist:
            return Response({'error': '设备不存在'}, status=404)

        if device.status == 'locked' and device.locked_by != request.user:
            return Response({'error': f'设备已被 {device.locked_by.username} 锁定'}, status=409)

        # 检查设备在线状态
        if device.status in ('offline',):
            return Response({'error': f'设备 {device.name or device.device_id} 不在线'}, status=400)

        # 预计算步骤数
        from .midscene_runner import parse_ai_prompt
        steps = parse_ai_prompt(midscene_case.ai_prompt)

        # 创建执行记录
        auto_plan = request.data.get('auto_plan', False)
        execution = MidsceneExecutionRecord.objects.create(
            midscene_case=midscene_case,
            case_name=midscene_case.name,
            device=device,
            platform=device.platform,
            status='pending',
            auto_plan=auto_plan,
            total_steps=len(steps),
            executed_by=request.user,
            model_config_snapshot={
                'name': midscene_case.ai_model_config.name if midscene_case.ai_model_config else '',
                'model_type': midscene_case.ai_model_config.model_type if midscene_case.ai_model_config else '',
                'model_name': midscene_case.ai_model_config.model_name if midscene_case.ai_model_config else '',
            } if midscene_case.ai_model_config else {},
        )

        # 异步执行
        from .tasks import execute_midscene_task
        task = execute_midscene_task.delay(execution.id)

        # 记录 Celery task_id
        execution.task_id = task.id
        execution.save(update_fields=['task_id'])

        return Response({
            'execution_id': execution.id,
            'task_id': task.id,
            'status': 'pending',
        })

    @action(detail=False, methods=['post'])
    def generate_steps(self, request):
        """AI 生成详细测试步骤（从简要描述展开）"""
        description = request.data.get('description', '')
        if not description:
            return Response({'error': '请输入测试描述'}, status=400)

        # 使用 AI 展开
        from apps.requirement_analysis.views import AIModelConfig
        config_id = request.data.get('model_config_id')

        try:
            if config_id:
                config = AIModelConfig.objects.get(id=config_id, is_active=True)
            else:
                config = AIModelConfig.objects.filter(
                    role='app_automation_vision', is_active=True
                ).first()

            if not config:
                return Response({'error': '没有可用的 VLM 模型配置'}, status=400)

            # 构造 prompt
            prompt = f"""你是一个移动端测试专家。请将以下测试场景描述展开为详细的、可执行的测试步骤。
每行一个步骤，用自然语言描述具体操作。注意：
1. 步骤要足够具体，AI 能直接执行（如"点击底部'我的'按钮"而不是"进入我的页面"）
2. 包括必要的等待步骤
3. 包括验证步骤（如"验证页面显示'登录成功'"）

场景描述：
{description}

请直接输出步骤列表，每行一个步骤，以序号开头："""

            import requests as req
            import json

            headers = {
                'Authorization': f'Bearer {config.api_key}',
                'Content-Type': 'application/json',
            }
            resp = req.post(
                f'{config.base_url}/chat/completions',
                json={
                    'model': config.model_name,
                    'messages': [{'role': 'user', 'content': prompt}],
                    'max_tokens': config.max_tokens,
                    'temperature': config.temperature,
                },
                headers=headers,
                timeout=30,
            )

            if resp.status_code == 200:
                data = resp.json()
                content = data['choices'][0]['message']['content']
                return Response({'steps': content})
            else:
                return Response({'error': f'AI 调用失败: {resp.status_code}'}, status=500)

        except Exception as e:
            logger.error(f'AI 生成步骤失败: {e}')
            return Response({'error': str(e)}, status=500)


class MidsceneExecutionRecordViewSet(viewsets.ReadOnlyModelViewSet, mixins.DestroyModelMixin):
    """Midscene 执行记录"""
    queryset = MidsceneExecutionRecord.objects.all()
    serializer_class = MidsceneExecutionRecordSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'platform']
    search_fields = ['case_name']
    ordering_fields = ['created_at', 'status']

    @action(detail=True, methods=['post'])
    def stop(self, request, pk=None):
        """停止执行"""
        execution = self.get_object()
        if execution.status not in ('pending', 'running'):
            return Response({'error': '任务不在执行中'}, status=400)

        # 撤销 Celery 任务
        if execution.task_id:
            from celery import current_app
            current_app.control.revoke(execution.task_id, terminate=True)

        execution.status = 'stopped'
        execution.finished_at = timezone.now()
        execution.save(update_fields=['status', 'finished_at'])

        return Response({'status': 'stopped'})
