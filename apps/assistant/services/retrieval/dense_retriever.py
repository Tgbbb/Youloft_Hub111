"""Dense Retrieval - BGE-M3 向量召回

封装现有的 Embedder，避免直接依赖 sentence_transformers。
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

import numpy as np

from apps.assistant.models import KnowledgeBase, KnowledgeChunk
from apps.assistant.services.embedder import Embedder

logger = logging.getLogger(__name__)


class DenseRetriever:
    """BGE-M3 向量检索（预归一化 + 点积）"""

    def __init__(self, knowledge_base: KnowledgeBase) -> None:
        self.kb = knowledge_base
        self.embedder = Embedder()
        self._cache: Optional[Dict] = None

    def _load_index(self) -> Dict:
        """加载全量向量到内存（按 KB 缓存）"""
        if self._cache is not None:
            return self._cache

        chunks = KnowledgeChunk.objects.filter(
            knowledge_base=self.kb,
            is_active=True,  # 软删除的不检索
        ).values('id', 'content', 'chunk_metadata', 'embedding')

        vectors: List[np.ndarray] = []
        contents: List[str] = []
        ids: List[int] = []
        metas: List[Dict] = []

        for c in chunks:
            try:
                vec = Embedder.deserialize_vector(c['embedding'])
                vectors.append(vec)
                contents.append(c['content'])
                ids.append(c['id'])
                metas.append(c['chunk_metadata'] or {})
            except Exception as e:
                logger.warning(f"[Dense] 跳过损坏 chunk id={c['id']}: {e}")

        if vectors:
            matrix = np.vstack(vectors).astype(np.float32)
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            matrix = matrix / (norms + 1e-10)
        else:
            matrix = np.zeros((0, self.kb.embedding_dim), dtype=np.float32)

        self._cache = {
            'matrix': matrix,
            'contents': contents,
            'ids': ids,
            'metas': metas,
        }
        return self._cache

    def invalidate_cache(self) -> None:
        self._cache = None

    def search(self, query: str, top_k: int = 20) -> List[Dict]:
        """返回 top_k 个最相关的 chunk（带 dense 分数）

        Returns: [{'chunk_id', 'content', 'metadata', 'dense_score'}, ...]
        """
        try:
            q_vec = self.embedder.embed_query(query)
        except Exception as e:
            logger.error(f"[Dense] Embedding 失败: {e}")
            return []
        q_vec = q_vec / (np.linalg.norm(q_vec) + 1e-10)

        data = self._load_index()
        matrix = data['matrix']
        if matrix.shape[0] == 0:
            return []

        scores = matrix @ q_vec
        top_indices = np.argsort(scores)[::-1][:top_k]

        results: List[Dict] = []
        for idx in top_indices:
            results.append({
                'chunk_id': int(data['ids'][idx]),
                'content': data['contents'][idx],
                'metadata': data['metas'][idx],
                'dense_score': float(scores[idx]),
            })
        return results
