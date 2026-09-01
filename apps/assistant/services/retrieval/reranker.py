"""Reranker - 精排（v1 占位实现）

v1 暂未实现真正的 cross-encoder 精排（避免引入 FlagEmbedding 重构 embedder）。
RRF 融合已足以覆盖"模糊关键词"召回需求。

后续可在此实现:
- BGE-reranker-base (~280MB)
- BGE-M3 colbert score (需要 FlagEmbedding)
"""
from __future__ import annotations

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class Reranker:
    """Reranker 占位实现 - 直接透传"""

    def __init__(self, *args, **kwargs) -> None:
        logger.info("[Reranker] v1: passthrough mode (no reranking)")

    def rerank(self, query: str, results: List[Dict], top_k: int = None) -> List[Dict]:
        """直接返回原结果，按 score 降序保留 top_k"""
        if top_k is None:
            top_k = len(results)
        sorted_results = sorted(results, key=lambda r: r.get('score', 0), reverse=True)
        return sorted_results[:top_k]
