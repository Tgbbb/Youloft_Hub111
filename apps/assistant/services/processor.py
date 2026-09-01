"""文档处理流水线

parse → chunk → embed → save

被 views_kb 中上传文档后调用，完成入库全流程。
"""
from __future__ import annotations

import logging
from typing import Optional

from django.utils import timezone

from apps.assistant.models import KnowledgeChunk, KnowledgeDocument
from apps.assistant.services.embedder import Embedder
from apps.assistant.services.parser import DocumentParser, TextChunker
from apps.assistant.services.retrieval.bm25_retriever import _tokenize

logger = logging.getLogger(__name__)


def _tokenize_for_bm25(text: str):
    """为 KnowledgeChunk 预存 jieba 分词结果（避免检索时重复分词）"""
    try:
        return _tokenize(text)
    except Exception as e:
        logger.warning(f"BM25 分词失败: {e}")
        return []


def process_document(doc_id: int) -> None:
    """
    同步处理文档：解析 → 切块 → embedding → 存储

    文档 < 100MB 时同步处理够用，更大规模建议改为 Celery 异步。
    """
    try:
        doc = KnowledgeDocument.objects.get(id=doc_id)
    except KnowledgeDocument.DoesNotExist:
        logger.error(f"KnowledgeDocument {doc_id} 不存在")
        return

    try:
        # 1. 解析
        doc.status = 'parsing'
        doc.save(update_fields=['status'])
        parsed = DocumentParser.parse(doc.file_path, doc.file_type)
        if not parsed:
            raise ValueError("文档解析为空")

        # 2. 切块
        chunker = TextChunker()
        kb = doc.knowledge_base
        all_chunks = []
        for item in parsed:
            pieces = chunker.chunk(
                item['content'],
                chunk_size=kb.chunk_size,
                overlap=kb.chunk_overlap,
            )
            for piece in pieces:
                all_chunks.append({
                    'content': piece,
                    'metadata': {**(item.get('metadata') or {}),
                                 'source_file': doc.file_name},
                })

        if not all_chunks:
            raise ValueError("分块结果为空")

        # 3. Embedding
        doc.status = 'embedding'
        doc.save(update_fields=['status'])
        embedder = Embedder()
        texts = [c['content'] for c in all_chunks]
        vectors = embedder.embed_texts(texts, batch_size=20)
        if len(vectors) != len(all_chunks):
            raise ValueError(
                f"Embedding 数量不匹配: {len(vectors)} vs {len(all_chunks)}"
            )

        # 4. 批量入库
        chunk_objs = [
            KnowledgeChunk(
                knowledge_base=kb,
                document=doc,
                chunk_index=i,
                content=c['content'],
                content_length=len(c['content']),
                embedding=Embedder.serialize_vector(vec),
                chunk_metadata=c['metadata'],
                bm25_tokens=_tokenize_for_bm25(c['content']),
                is_active=True,
                version=1,
            )
            for i, (c, vec) in enumerate(zip(all_chunks, vectors))
        ]
        KnowledgeChunk.objects.bulk_create(chunk_objs, batch_size=100)

        # 5. 完成
        doc.total_chunks = len(chunk_objs)
        doc.status = 'done'
        doc.processed_at = timezone.now()
        doc.error_message = ''
        doc.save(update_fields=['total_chunks', 'status',
                                'processed_at', 'error_message'])

        # 6. 清掉该 KB 的检索缓存（dense + BM25 + hybrid）
        try:
            from apps.assistant.services.rag import RAGService
            RAGService(kb.id).invalidate_cache()
            from apps.assistant.services.retrieval.hybrid import HybridSearcher
            HybridSearcher(kb).invalidate_cache()
        except Exception:
            pass

        logger.info(
            f"文档 {doc.file_name} 处理完成: {len(chunk_objs)} chunks"
        )
    except Exception as e:
        logger.error(f"文档 {doc_id} 处理失败: {e}", exc_info=True)
        try:
            doc.status = 'failed'
            doc.error_message = str(e)[:1000]
            doc.save(update_fields=['status', 'error_message'])
        except Exception:
            pass
