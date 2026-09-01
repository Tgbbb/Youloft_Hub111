"""Knowledge Base Management Service

封装知识库的写入/更新/删除逻辑，供 Agent 工具调用。
所有变更都记录到 KnowledgeUpdateLog，便于审计和回滚。

相似度阈值:
- > 0.92: 视为同一条内容，直接更新原 chunk（in-place 替换）
- 0.75-0.92: 视为相似但有变化，创建新版本（superseded_by 链）
- < 0.75: 视为新内容，直接创建新 chunk
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from django.db import transaction
from django.utils import timezone

from apps.assistant.models import (
    KnowledgeBase,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeUpdateLog,
)
from apps.assistant.services.embedder import Embedder
from apps.assistant.services.rag import RAGService
from apps.assistant.services.retrieval.bm25_retriever import _tokenize

logger = logging.getLogger(__name__)


# 相似度阈值
THRESHOLD_UPDATE = 0.92   # >= 此值视为同一条，更新 in-place
THRESHOLD_VERSION = 0.75  # >= 此值视为相似，创建新版本；< 此值视为新内容
# 查询召回数
SIMILAR_TOP_K = 5


@dataclass
class AddUpdateResult:
    """add_or_update 操作的返回结果"""
    action: str  # 'created' | 'updated' | 'new_version' | 'error'
    chunk_id: Optional[int]
    superseded_chunk_id: Optional[int]
    similarity: float
    summary: str


class KBManagementService:
    """知识库管理服务（供 Agent 工具调用）"""

    def __init__(self, knowledge_base_id: int) -> None:
        self.kb = KnowledgeBase.objects.get(id=knowledge_base_id)
        self.embedder = Embedder()
        # 复用 RAGService 的搜索能力做相似度检索
        self.rag = RAGService(knowledge_base_id)

    @transaction.atomic
    def add_or_update(
        self,
        text: str,
        section_hint: str = "",
        user=None,
        session_id: str = "",
    ) -> AddUpdateResult:
        """添加或更新一个知识点

        Args:
            text: 知识点内容（用户提供的功能描述）
            section_hint: 章节路径提示（可选），如 "心动日常 > 分享码"
            user: 操作用户
            session_id: 触发的智能助手会话 ID

        Returns:
            AddUpdateResult: 包含 action 类型和 chunk_id
        """
        text = (text or "").strip()
        if not text:
            return AddUpdateResult(
                action='error', chunk_id=None, superseded_chunk_id=None,
                similarity=0.0, summary='内容为空，未执行',
            )

        # 1. embedding 化新内容
        try:
            vec = self.embedder.embed_query(text)
        except Exception as e:
            logger.error(f"Embedding 新内容失败: {e}")
            return AddUpdateResult(
                action='error', chunk_id=None, superseded_chunk_id=None,
                similarity=0.0, summary=f'Embedding 失败: {e}',
            )

        # 2. 在 KB 内检索相似 chunks
        similar_chunks = self._search_similar_chunks(text, vec)

        # 3. 决策
        if similar_chunks:
            top = similar_chunks[0]
            sim = top['similarity']
        else:
            sim = 0.0
            top = None

        # 4. 执行
        if sim >= THRESHOLD_UPDATE and top:
            return self._update_existing(top, text, section_hint, user, session_id)
        elif sim >= THRESHOLD_VERSION and top:
            return self._create_new_version(top, text, section_hint, user, session_id)
        else:
            return self._create_new(text, section_hint, user, session_id)

    def _search_similar_chunks(self, text: str, vec) -> List[dict]:
        """在 KB 内查找相似 chunks（用 RAG 走 hybrid 召回）"""
        try:
            results = self.rag.search(text, top_k=SIMILAR_TOP_K)
        except Exception as e:
            logger.warning(f"搜索相似 chunks 失败: {e}")
            return []

        # 转换 hybrid score → cosine similarity（用于决策）
        # hybrid score 已经是 RRF 融合后的排序得分，最高约 0.033
        # 我们需要的是 dense_score（余弦相似度，0-1），用于阈值判断
        return [{
            'chunk': KnowledgeChunk.objects.get(id=r['chunk_id']),
            'similarity': r.get('dense_score', 0.0),
            'content': r['content'],
        } for r in results if r.get('dense_score', 0) > 0]

    def _update_existing(self, top: dict, text: str, section_hint: str,
                          user, session_id: str) -> AddUpdateResult:
        """情况 1: 高相似度，更新原 chunk 的内容（in-place）"""
        old = top['chunk']
        old_id = old.id
        old_content = old.content
        old_version = old.version

        # 更新内容
        old.content = text
        old.content_length = len(text)
        old.bm25_tokens = _tokenize(text)
        # 重新计算 embedding
        old.embedding = Embedder.serialize_vector(
            self.embedder.embed_query(text)
        )
        if section_hint:
            meta = old.chunk_metadata or {}
            meta['section_hint'] = section_hint
            old.chunk_metadata = meta
        old.save()

        # 记录日志
        KnowledgeUpdateLog.objects.create(
            knowledge_base=self.kb,
            chunk=old,
            action='updated',
            summary=f"更新 (v{old_version}, sim={top['similarity']:.3f}): {text[:60]}",
            user=user,
            session_id=session_id,
        )

        # 清缓存
        self._invalidate_cache()

        logger.info(f"[KB] 更新 chunk {old_id} (v{old_version}) sim={top['similarity']:.3f}")
        return AddUpdateResult(
            action='updated', chunk_id=old_id, superseded_chunk_id=None,
            similarity=top['similarity'],
            summary=f"已更新原 chunk #{old_id}（相似度 {top['similarity']:.2%}）",
        )

    def _create_new_version(self, top: dict, text: str, section_hint: str,
                             user, session_id: str) -> AddUpdateResult:
        """情况 2: 中相似度，创建新版本（软删除旧版）"""
        old = top['chunk']
        old_id = old.id
        old_version = old.version
        new_version = old_version + 1

        # 1. 创建新 chunk（作为独立 document: "AI 更新于 {date}"）
        ai_doc, _ = KnowledgeDocument.objects.get_or_create(
            knowledge_base=self.kb,
            file_name=f"[AI 更新于 {timezone.now().strftime('%Y-%m-%d')}]",
            defaults={
                'file_type': 'txt',
                'file_size': len(text),
                'file_path': f'ai_generated/{timezone.now().strftime("%Y%m%d")}/{old_id}_v{new_version}.txt',
                'status': 'done',
                'processed_at': timezone.now(),
            }
        )

        # 2. 重新计算 embedding
        try:
            new_vec = self.embedder.embed_query(text)
        except Exception as e:
            logger.error(f"新版本 embedding 失败: {e}")
            new_vec = self.embedder.embed_query(text)

        new_chunk = KnowledgeChunk.objects.create(
            knowledge_base=self.kb,
            document=ai_doc,
            chunk_index=0,
            content=text,
            content_length=len(text),
            embedding=Embedder.serialize_vector(new_vec),
            chunk_metadata={
                'source': 'ai_update',
                'source_section': section_hint or '',
                'previous_version_chunk_id': old_id,
                'previous_similarity': round(top['similarity'], 3),
            },
            bm25_tokens=_tokenize(text),
            is_active=True,
            version=new_version,
        )

        # 3. 软删除旧版
        old.is_active = False
        old.superseded_by = new_chunk
        old.save(update_fields=['is_active', 'superseded_by'])

        # 4. 记录日志
        KnowledgeUpdateLog.objects.create(
            knowledge_base=self.kb,
            chunk=new_chunk,
            superseded_chunk=old,
            action='new_version',
            summary=f"新增版本 (v{new_version}, sim={top['similarity']:.3f}, 替代 #{old_id}): {text[:50]}",
            user=user,
            session_id=session_id,
        )

        self._invalidate_cache()

        logger.info(f"[KB] 新版 chunk {new_chunk.id} (v{new_version}) 替代 #{old_id} sim={top['similarity']:.3f}")
        return AddUpdateResult(
            action='new_version',
            chunk_id=new_chunk.id,
            superseded_chunk_id=old_id,
            similarity=top['similarity'],
            summary=f"已创建新版本（v{new_version}，相似度 {top['similarity']:.2%}，旧版 #{old_id} 已停用）",
        )

    def _create_new(self, text: str, section_hint: str,
                     user, session_id: str) -> AddUpdateResult:
        """情况 3: 低相似度或无相似，直接创建新 chunk"""
        # 创建/获取 AI 更新专用 document
        ai_doc, _ = KnowledgeDocument.objects.get_or_create(
            knowledge_base=self.kb,
            file_name=f"[AI 更新于 {timezone.now().strftime('%Y-%m-%d')}]",
            defaults={
                'file_type': 'txt',
                'file_size': len(text),
                'file_path': f'ai_generated/{timezone.now().strftime("%Y%m%d")}/new.txt',
                'status': 'done',
                'processed_at': timezone.now(),
            }
        )

        # 计算 embedding
        try:
            new_vec = self.embedder.embed_query(text)
        except Exception as e:
            logger.error(f"新内容 embedding 失败: {e}")
            return AddUpdateResult(
                action='error', chunk_id=None, superseded_chunk_id=None,
                similarity=0.0, summary=f'Embedding 失败: {e}',
            )

        new_chunk = KnowledgeChunk.objects.create(
            knowledge_base=self.kb,
            document=ai_doc,
            chunk_index=ai_doc.total_chunks,
            content=text,
            content_length=len(text),
            embedding=Embedder.serialize_vector(new_vec),
            chunk_metadata={
                'source': 'ai_update',
                'source_section': section_hint or '',
            },
            bm25_tokens=_tokenize(text),
            is_active=True,
            version=1,
        )

        # 更新 document 的 total_chunks
        ai_doc.total_chunks = ai_doc.chunks.count()
        ai_doc.save(update_fields=['total_chunks'])

        # 记录日志
        KnowledgeUpdateLog.objects.create(
            knowledge_base=self.kb,
            chunk=new_chunk,
            action='created',
            summary=f"新增: {text[:60]}",
            user=user,
            session_id=session_id,
        )

        self._invalidate_cache()

        logger.info(f"[KB] 新增 chunk {new_chunk.id}")
        return AddUpdateResult(
            action='created',
            chunk_id=new_chunk.id,
            superseded_chunk_id=None,
            similarity=0.0,
            summary=f"已新增 chunk #{new_chunk.id}",
        )

    @transaction.atomic
    def delete(self, keyword: str, user=None, session_id: str = "") -> dict:
        """根据关键词软删除 chunk（按 hybrid 检索 top 1）"""
        results = self.rag.search(keyword, top_k=3)
        if not results:
            return {
                'success': False,
                'message': f'未找到与 "{keyword}" 相关的 chunk',
                'deleted_chunks': [],
            }

        # 取 top 1
        top = results[0]
        chunk = KnowledgeChunk.objects.get(id=top['chunk_id'])

        if not chunk.is_active:
            return {
                'success': False,
                'message': f'chunk #{chunk.id} 已被删除',
                'deleted_chunks': [],
            }

        # 软删除
        chunk.is_active = False
        chunk.save(update_fields=['is_active'])

        # 记录日志
        KnowledgeUpdateLog.objects.create(
            knowledge_base=self.kb,
            chunk=chunk,
            action='deleted',
            summary=f"软删除: {chunk.content[:60]}",
            user=user,
            session_id=session_id,
        )

        self._invalidate_cache()

        logger.info(f"[KB] 软删除 chunk {chunk.id}")
        return {
            'success': True,
            'message': f'已软删除 chunk #{chunk.id}',
            'deleted_chunks': [{
                'chunk_id': chunk.id,
                'content_preview': chunk.content[:120],
                'similarity': top.get('dense_score', 0),
            }],
        }

    def list_recent_updates(self, days: int = 7, limit: int = 20) -> List[dict]:
        """列出最近 N 天的更新日志"""
        from datetime import timedelta
        since = timezone.now() - timedelta(days=days)
        logs = KnowledgeUpdateLog.objects.filter(
            knowledge_base=self.kb,
            created_at__gte=since,
        ).order_by('-created_at')[:limit]

        return [{
            'log_id': l.id,
            'action': l.action,
            'action_display': l.get_action_display(),
            'summary': l.summary,
            'chunk_id': l.chunk_id,
            'superseded_chunk_id': l.superseded_chunk_id,
            'user': l.user.username if l.user else 'system',
            'session_id': l.session_id,
            'created_at': l.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        } for l in logs]

    def _invalidate_cache(self) -> None:
        """清掉该 KB 的所有缓存"""
        try:
            self.rag.invalidate_cache()
        except Exception as e:
            logger.warning(f"清 RAG 缓存失败: {e}")
