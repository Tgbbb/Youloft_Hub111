"""知识库管理 REST API"""
from __future__ import annotations

import os
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from .models import KnowledgeBase, KnowledgeChunk, KnowledgeDocument, KnowledgeUpdateLog
from .serializers_kb import (
    KnowledgeBaseSerializer,
    KnowledgeChunkSerializer,
    KnowledgeDocumentSerializer,
)
from .services.processor import process_document


class KnowledgeBaseViewSet(viewsets.ModelViewSet):
    """知识库 CRUD"""

    queryset = KnowledgeBase.objects.all()
    serializer_class = KnowledgeBaseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(
        detail=True,
        methods=['post'],
        url_path='upload',
        parser_classes=[MultiPartParser, FormParser],
    )
    def upload_document(self, request, pk=None):
        """
        上传文档到指定知识库

        POST /api/assistant/knowledge-bases/{id}/upload/
        FormData: file=<binary>, file_type=<xmind|pdf|docx|md|txt>
        """
        kb = self.get_object()
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response(
                {'error': '请上传文件'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 校验类型
        ext = (file_obj.name.split('.')[-1] if '.' in file_obj.name else '').lower()
        type_map = {
            'xmind': 'xmind', 'pdf': 'pdf',
            'docx': 'docx', 'md': 'md', 'txt': 'txt',
        }
        if ext not in type_map:
            return Response(
                {'error': f'不支持的文件类型: .{ext}，仅支持 xmind/pdf/docx/md/txt'},
                status=status.HTTP_400_BAD_REQUEST
            )
        file_type = type_map[ext]

        # 保存文件到 MEDIA_ROOT/knowledge_bases/{kb_id}/
        kb_dir = Path(settings.MEDIA_ROOT) / 'knowledge_bases' / str(kb.id)
        kb_dir.mkdir(parents=True, exist_ok=True)
        # 避免文件名冲突：加时间戳
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        safe_name = f"{timestamp}_{file_obj.name}"
        file_path = kb_dir / safe_name
        with open(file_path, 'wb') as f:
            for chunk in file_obj.chunks():
                f.write(chunk)

        # 创建文档记录
        doc = KnowledgeDocument.objects.create(
            knowledge_base=kb,
            file_name=file_obj.name,
            file_type=file_type,
            file_size=file_obj.size,
            file_path=str(file_path),
            status='pending',
            uploaded_by=request.user,
        )

        # 同步触发处理（生产环境可改为 Celery 异步）
        process_document(doc.id)

        return Response(
            KnowledgeDocumentSerializer(doc).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['get'])
    def documents(self, request, pk=None):
        """获取该知识库下的所有文档"""
        kb = self.get_object()
        docs = kb.documents.all()
        return Response(
            KnowledgeDocumentSerializer(docs, many=True).data
        )

    @action(detail=True, methods=['get'])
    def chunks(self, request, pk=None):
        """获取该知识库下的所有分块（含内容预览）"""
        kb = self.get_object()
        chunk_qs = kb.chunks.select_related('document').order_by('document_id', 'chunk_index')

        # 支持分页参数
        try:
            limit = int(request.query_params.get('limit', 50))
            offset = int(request.query_params.get('offset', 0))
        except ValueError:
            limit, offset = 50, 0

        total = chunk_qs.count()
        items = chunk_qs[offset:offset + limit]
        return Response({
            'total': total,
            'limit': limit,
            'offset': offset,
            'items': KnowledgeChunkSerializer(items, many=True).data,
        })

    @action(
        detail=True,
        methods=['delete'],
        url_path=r'documents/(?P<doc_id>[^/.]+)'
    )
    def delete_document(self, request, pk=None, doc_id=None):
        """删除指定文档及其分块"""
        try:
            doc = KnowledgeDocument.objects.get(id=doc_id, knowledge_base_id=pk)
        except KnowledgeDocument.DoesNotExist:
            return Response(
                {'error': '文档不存在'},
                status=status.HTTP_404_NOT_FOUND
            )
        if os.path.exists(doc.file_path):
            try:
                os.remove(doc.file_path)
            except OSError:
                pass
        kb_id = doc.knowledge_base_id
        doc.delete()
        # 清掉检索缓存
        try:
            from apps.assistant.services.rag import RAGService
            RAGService(kb_id).invalidate_cache()
        except Exception:
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'])
    def active(self, request):
        """获取当前激活的知识库（用于助手默认）"""
        kb = KnowledgeBase.objects.filter(is_active=True).first()
        if not kb:
            return Response(
                {'error': '未找到激活的知识库'},
                status=status.HTTP_404_NOT_FOUND
            )
        return Response(KnowledgeBaseSerializer(kb).data)

    @action(detail=True, methods=['get'], url_path='update-logs')
    def update_logs(self, request, pk=None):
        """获取该知识库的最近变更日志（新增/更新/版本/删除）。

        Query params:
            days: 查询最近 N 天，默认 7
            limit: 最多返回 N 条，默认 50
            action: 可选过滤 action 类型 (created/updated/new_version/deleted)
        """
        kb = self.get_object()
        try:
            days = int(request.query_params.get('days', 7))
            limit = int(request.query_params.get('limit', 50))
        except ValueError:
            days, limit = 7, 50

        from datetime import timedelta
        since = timezone.now() - timedelta(days=days)
        qs = KnowledgeUpdateLog.objects.filter(
            knowledge_base=kb,
            created_at__gte=since,
        ).select_related('user').order_by('-created_at')

        action_filter = request.query_params.get('action')
        if action_filter:
            qs = qs.filter(action=action_filter)

        total = qs.count()
        items = qs[:limit]
        return Response({
            'total': total,
            'days': days,
            'items': [{
                'log_id': l.id,
                'action': l.action,
                'action_display': l.get_action_display(),
                'summary': l.summary,
                'chunk_id': l.chunk_id,
                'superseded_chunk_id': l.superseded_chunk_id,
                'user': l.user.username if l.user else 'system',
                'session_id': l.session_id,
                'created_at': l.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            } for l in items],
        })

    @action(detail=True, methods=['get'], url_path='export')
    def export_markdown(self, request, pk=None):
        """导出知识库为 Markdown 文件。

        Query params:
            include_log: 是否包含变更日志附录，默认 1
            log_days: 变更日志天数，默认 7
            style: md（默认，XMind 嵌套树形 + 其他平铺）| md_flat（向后兼容，全平铺）
        """
        kb = self.get_object()

        include_log = request.query_params.get('include_log', '1') != '0'
        try:
            log_days = int(request.query_params.get('log_days', 7))
        except ValueError:
            log_days = 7
        style = request.query_params.get('style', 'md')
        flat = (style == 'md_flat')

        from .services.exporter import KBMarkdownExporter
        exporter = KBMarkdownExporter(
            knowledge_base_id=kb.id,
            include_update_log=include_log,
            update_log_days=log_days,
            flat=flat,
        )
        md_text = exporter.export()

        # 文件名：{KB名}_{时间戳}.md
        # 过滤 Windows 不允许的字符
        safe_name = "".join(
            c for c in kb.name if c not in r'<>:"/\|?*'
        ).strip() or f"kb_{kb.id}"
        suffix = "_flat" if flat else ""
        filename = f"{safe_name}{suffix}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.md"

        from django.http import HttpResponse
        response = HttpResponse(md_text, content_type='text/markdown; charset=utf-8')
        # RFC 5987 支持中文文件名
        response['Content-Disposition'] = (
            f"attachment; filename=\"{filename}\"; "
            f"filename*=UTF-8''{filename}"
        )
        return response


class KnowledgeDocumentViewSet(viewsets.ReadOnlyModelViewSet):
    """知识库文档只读视图"""

    queryset = KnowledgeDocument.objects.all()
    serializer_class = KnowledgeDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
