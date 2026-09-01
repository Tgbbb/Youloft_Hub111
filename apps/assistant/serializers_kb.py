"""知识库 RAG 序列化器"""
from rest_framework import serializers

from .models import KnowledgeBase, KnowledgeChunk, KnowledgeDocument


class KnowledgeBaseSerializer(serializers.ModelSerializer):
    """知识库列表/详情序列化器"""

    document_count = serializers.SerializerMethodField()
    chunk_count = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(
        source='created_by.username', read_only=True, default=''
    )

    class Meta:
        model = KnowledgeBase
        fields = [
            'id', 'name', 'description',
            'embedding_model', 'embedding_dim',
            'chunk_size', 'chunk_overlap',
            'is_active',
            'document_count', 'chunk_count', 'created_by_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['embedding_dim', 'created_at', 'updated_at']

    def get_document_count(self, obj: KnowledgeBase) -> int:
        return obj.documents.count()

    def get_chunk_count(self, obj: KnowledgeBase) -> int:
        return obj.chunks.count()


class KnowledgeDocumentSerializer(serializers.ModelSerializer):
    """知识库文档序列化器"""

    uploaded_by_name = serializers.CharField(
        source='uploaded_by.username', read_only=True, default=''
    )
    knowledge_base_name = serializers.CharField(
        source='knowledge_base.name', read_only=True
    )
    file_size_kb = serializers.SerializerMethodField()

    class Meta:
        model = KnowledgeDocument
        fields = [
            'id', 'knowledge_base', 'knowledge_base_name',
            'file_name', 'file_type', 'file_size', 'file_size_kb',
            'total_chunks', 'status', 'error_message',
            'uploaded_by_name', 'created_at', 'processed_at',
        ]
        read_only_fields = [
            'file_size', 'file_size_kb', 'total_chunks', 'status',
            'error_message', 'created_at', 'processed_at',
        ]

    def get_file_size_kb(self, obj: KnowledgeDocument) -> float:
        return round(obj.file_size / 1024, 2) if obj.file_size else 0


class KnowledgeChunkSerializer(serializers.ModelSerializer):
    """知识库分块序列化器（含内容预览）"""

    document_name = serializers.CharField(
        source='document.file_name', read_only=True
    )
    content_preview = serializers.SerializerMethodField()

    class Meta:
        model = KnowledgeChunk
        fields = [
            'id', 'document', 'document_name',
            'chunk_index', 'content', 'content_preview',
            'content_length', 'chunk_metadata', 'created_at',
        ]

    def get_content_preview(self, obj: KnowledgeChunk) -> str:
        return obj.content[:200] + ('...' if len(obj.content) > 200 else '')
