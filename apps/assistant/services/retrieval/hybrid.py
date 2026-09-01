"""Hybrid Retrieval - Dense + BM25 RRF 融合

RRF (Reciprocal Rank Fusion) 公式:
    score(d) = sum( 1 / (k + rank_d) )  for each retriever

特点:
- 不需要分数归一化（仅用排名）
- 对 outlier 不敏感
- 比 weighted sum 更鲁棒
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Dict, List, Optional

from apps.assistant.models import KnowledgeBase

from .dense_retriever import DenseRetriever
from .bm25_retriever import BM25Retriever

logger = logging.getLogger(__name__)


class HybridSearcher:
    """Dense + BM25 混合检索（RRF 融合）

    使用方式:
        hs = HybridSearcher(kb)
        results = hs.search("分享码", top_k=5)
    """

    # RRF 参数：来自原始论文（Cormack et al. 2009），k=60 经验效果好
    RRF_K = 60

    def __init__(self, knowledge_base: KnowledgeBase) -> None:
        self.kb = knowledge_base
        self.dense = DenseRetriever(knowledge_base)
        self.bm25 = BM25Retriever(knowledge_base)

    def invalidate_cache(self) -> None:
        """KB 内容变化时调用"""
        self.dense.invalidate_cache()
        self.bm25.invalidate_cache()

    def search(
        self,
        query: str,
        top_k: int = 5,
        recall_k: int = 20,
    ) -> List[Dict]:
        """混合检索

        Args:
            query: 用户问题
            top_k: 最终返回的 chunk 数
            recall_k: 每路召回的 chunk 数（>= top_k）

        Returns:
            按混合得分降序的 top_k chunks
            每条: {chunk_id, content, metadata, score, dense_score, bm25_score}
        """
        # 1. 双路召回
        dense_results = self.dense.search(query, top_k=recall_k)
        bm25_results = self.bm25.search(query, top_k=recall_k)
        logger.info(f"[Hybrid] dense={len(dense_results)} bm25={len(bm25_results)}")

        # 2. RRF 融合
        fused: Dict[int, Dict] = defaultdict(lambda: {
            'content': '',
            'metadata': {},
            'rrf_score': 0.0,
            'dense_score': 0.0,
            'bm25_score': 0.0,
        })

        for rank, r in enumerate(dense_results):
            cid = r['chunk_id']
            fused[cid]['content'] = r['content']
            fused[cid]['metadata'] = r['metadata']
            fused[cid]['dense_score'] = r['dense_score']
            fused[cid]['rrf_score'] += 1.0 / (self.RRF_K + rank + 1)

        for rank, r in enumerate(bm25_results):
            cid = r['chunk_id']
            fused[cid]['content'] = r['content'] or fused[cid].get('content', '')
            fused[cid]['metadata'] = fused[cid].get('metadata') or r['metadata']
            fused[cid]['bm25_score'] = r['bm25_score']
            fused[cid]['rrf_score'] += 1.0 / (self.RRF_K + rank + 1)

        # 3. 排序 + 取 top_k
        sorted_results = sorted(
            fused.items(), key=lambda x: x[1]['rrf_score'], reverse=True
        )[:top_k]

        # 4. 格式化输出（score 用 rrf_score）
        results: List[Dict] = []
        for cid, d in sorted_results:
            results.append({
                'chunk_id': cid,
                'content': d['content'],
                'metadata': d['metadata'],
                'score': d['rrf_score'],
                'dense_score': d['dense_score'],
                'bm25_score': d['bm25_score'],
            })
        return results
