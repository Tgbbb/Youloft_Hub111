"""Hybrid Retrieval 模块

提供 Dense + BM25 + Rerank 混合检索能力。
- DenseRetriever:  BGE-M3 向量召回
- BM25Retriever:   jieba + rank_bm25 关键词召回
- Reranker:        BGE-M3 colbert 精排（复用同一模型）
- HybridSearcher:  RRF 融合 + 重排
"""
from .dense_retriever import DenseRetriever
from .bm25_retriever import BM25Retriever
from .reranker import Reranker
from .hybrid import HybridSearcher

__all__ = ['DenseRetriever', 'BM25Retriever', 'Reranker', 'HybridSearcher']
