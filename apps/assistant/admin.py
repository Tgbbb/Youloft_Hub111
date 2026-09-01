from django.contrib import admin
from .models import (
    AssistantSession,
    AssistantMessage,
    KnowledgeBase,
    KnowledgeDocument,
    KnowledgeChunk,
)


@admin.register(AssistantSession)
class AssistantSessionAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'session_id', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['user__username', 'title', 'session_id']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(AssistantMessage)
class AssistantMessageAdmin(admin.ModelAdmin):
    list_display = ['session', 'message_type', 'content_preview', 'created_at']
    list_filter = ['message_type', 'created_at']
    search_fields = ['session__title', 'content']
    readonly_fields = ['created_at']

    def content_preview(self, obj):
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    content_preview.short_description = '消息内容预览'


@admin.register(KnowledgeBase)
class KnowledgeBaseAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'embedding_model', 'chunk_size', 'is_active',
                    'document_count', 'created_by', 'updated_at']
    list_filter = ['is_active', 'embedding_model']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']

    def document_count(self, obj):
        return obj.documents.count()
    document_count.short_description = '文档数'


@admin.register(KnowledgeDocument)
class KnowledgeDocumentAdmin(admin.ModelAdmin):
    list_display = ['id', 'file_name', 'file_type', 'status', 'total_chunks',
                    'file_size', 'knowledge_base', 'uploaded_by', 'created_at']
    list_filter = ['status', 'file_type']
    search_fields = ['file_name']
    readonly_fields = ['created_at', 'processed_at']


@admin.register(KnowledgeChunk)
class KnowledgeChunkAdmin(admin.ModelAdmin):
    list_display = ['id', 'document', 'chunk_index', 'content_length', 'created_at']
    list_filter = ['knowledge_base']
    search_fields = ['content']
    readonly_fields = ['created_at']
