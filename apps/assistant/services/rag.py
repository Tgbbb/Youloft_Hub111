"""RAG 检索服务

v2 改造：接入 Hybrid Retrieval（Dense + BM25 + RRF 融合）。
- 不直接调用 LLM
- Agent 通过 `search_knowledge_base` 工具调用本服务获取相关片段
- 返回的 chunk 字段保持与 v1 兼容（chunk_id / content / metadata / score）

v1 兼容性:
- 保留 DEFAULT_TOP_K / MIN_SCORE 常量
- search() 签名不变
- invalidate_cache() 行为不变（额外清掉 hybrid 缓存）
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from apps.assistant.models import KnowledgeBase
from apps.assistant.services.retrieval.hybrid import HybridSearcher

logger = logging.getLogger(__name__)


class RAGService:
    """知识库检索（Hybrid: Dense + BM25 → RRF 融合）

    知识库规模 < 100MB 时此方案性能足够。
    """

    DEFAULT_TOP_K = 5
    # Hybrid RRF 得分阈值（用于过滤低相关度噪声）
    # 经验值：RRF 得分 < 0.005 的基本是低相关噪声
    MIN_SCORE = 0.005

    def __init__(self, knowledge_base_id: int) -> None:
        self.kb = KnowledgeBase.objects.get(id=knowledge_base_id)
        self.hybrid = HybridSearcher(self.kb)
        self.top_k = self.DEFAULT_TOP_K
        # 保留旧 cache 字段以兼容老调用方
        self._cache: Optional[Dict] = None

    def _load_all_chunks(self) -> Dict:
        """v1 兼容：直接走 hybrid"""
        return {'hybrid': self.hybrid}

    def invalidate_cache(self) -> None:
        """KB 文档/分块变化时调用，清 dense + BM25 缓存"""
        self._cache = None
        try:
            self.hybrid.invalidate_cache()
        except Exception as e:
            logger.warning(f"清 hybrid 缓存失败: {e}")

    def search(self, question: str, top_k: Optional[int] = None) -> List[Dict]:
        """
        检索 Top-K 相关分块（Hybrid: Dense + BM25 + RRF）

        Args:
            question: 用户问题
            top_k: 返回片段数（默认 5）

        Returns:
            List[Dict]: [{'chunk_id', 'content', 'metadata', 'score',
                          'dense_score', 'bm25_score'}, ...]
        """
        if top_k is None:
            top_k = self.top_k

        # 召回 20 条 → RRF 融合 → 取 top_k
        # recall_k 应 >= top_k 且 <= 该 KB 总 chunk 数
        results = self.hybrid.search(question, top_k=top_k, recall_k=20)

        # 应用 MIN_SCORE 阈值
        filtered = [r for r in results if r['score'] >= self.MIN_SCORE]
        if len(filtered) < len(results):
            logger.info(
                f"[RAG] score 过滤: {len(results)} → {len(filtered)} "
                f"(MIN_SCORE={self.MIN_SCORE})"
            )
        return filtered

    def format_for_prompt(self, retrieved: List[Dict]) -> str:
        """把检索结果格式化为可拼到 LLM prompt 的文本

        显式标注 dense_score 和 bm25_score，便于 Agent 评估置信度。
        """
        if not retrieved:
            return "（知识库中未找到相关内容）"

        parts: List[str] = []
        for i, r in enumerate(retrieved, 1):
            meta = r['metadata'] or {}
            source = meta.get('source', 'unknown')
            section = (
                meta.get('section')
                or meta.get('sheet')
                or meta.get('section_path')
                or ''
            )
            # 把 section_path（list）转成字符串
            if isinstance(section, list):
                section = ' > '.join(section)

            header = f"[片段{i}] 来源:{source}"
            if section:
                header += f" / {section}"
            header += f" (相关度:{r['score']:.3f}"
            if r.get('dense_score', 0) > 0:
                header += f" | 语义:{r['dense_score']:.2f}"
            if r.get('bm25_score', 0) > 0:
                header += f" | 关键词:{r['bm25_score']:.2f}"
            header += ")"
            parts.append(f"{header}\n{r['content']}")
        return "\n\n---\n\n".join(parts)
