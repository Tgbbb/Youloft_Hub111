# -*- coding: utf-8 -*-
"""工具合集 API 视图"""
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ToolboxConfig, PushCheckRun
from .serializers import (
    ToolboxConfigSerializer,
    PushCheckRunListSerializer,
    PushCheckRunDetailSerializer,
)
from .tasks import run_push_check


class PushCheckConfigView(APIView):
    """推送对比工具配置：GET 返回（敏感项掩码），PUT 更新（空值不修改）。"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        cfg = ToolboxConfig.get_singleton()
        return Response(ToolboxConfigSerializer(cfg).data)

    def put(self, request):
        cfg = ToolboxConfig.get_singleton()
        data = dict(request.data or {})
        for field in ('imap_password', 'push_cookie'):
            if field in data and not (data.get(field) or '').strip():
                data.pop(field)
        serializer = ToolboxConfigSerializer(cfg, data=data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        obj = serializer.save(updated_by=request.user)
        return Response(ToolboxConfigSerializer(obj).data)


class PushCheckRunCreateView(APIView):
    """触发一次推送对比检查（同一时间只允许一个任务运行）。"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if PushCheckRun.objects.filter(status__in=('pending', 'running')).exists():
            return Response({'error': '已有任务在执行中，请等待完成后再触发'},
                            status=status.HTTP_409_CONFLICT)
        force_value = (request.data or {}).get('force', False)
        force = force_value is True or force_value in ('true', 'True', '1', 1)
        run = PushCheckRun.objects.create(user=request.user, status='pending', force=force)
        run_push_check.delay(run.id)
        return Response(PushCheckRunDetailSerializer(run).data, status=status.HTTP_201_CREATED)


class PushCheckRunPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class PushCheckRunListView(APIView):
    """推送对比运行历史（分页，不含日志全文）。"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = PushCheckRun.objects.select_related('user').all()
        paginator = PushCheckRunPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        if page is not None:
            serializer = PushCheckRunListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        serializer = PushCheckRunListSerializer(queryset, many=True)
        return Response(serializer.data)

    def delete(self, request):
        """清空全部运行历史；有任务执行中时禁止清空。"""
        if PushCheckRun.objects.filter(status__in=('pending', 'running')).exists():
            return Response({'error': '有任务在执行中，请等待完成后再清空'},
                            status=status.HTTP_409_CONFLICT)
        deleted, _ = PushCheckRun.objects.all().delete()
        return Response({'deleted': deleted})


class PushCheckRunDetailView(APIView):
    """运行详情：状态、日志全文、结果摘要。"""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        run = PushCheckRun.objects.select_related('user').filter(pk=pk).first()
        if run is None:
            return Response({'error': '记录不存在'}, status=status.HTTP_404_NOT_FOUND)
        return Response(PushCheckRunDetailSerializer(run).data)
