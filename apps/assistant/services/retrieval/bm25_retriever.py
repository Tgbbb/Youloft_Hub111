"""BM25 Retrieval - jieba 分词 + rank_bm25 关键词召回

核心设计：
- 使用 jieba 做中文分词（默认精确模式）
- 使用 rank_bm25 的 BM25Okapi 算法
- 索引按 KB 缓存到 media/retrieval_cache/{kb_id}.pkl
- chunk 变化时调用 invalidate_cache 重建
"""
from __future__ import annotations

import logging
import pickle
import re
from pathlib import Path
from typing import Dict, List, Optional

from apps.assistant.models import KnowledgeBase, KnowledgeChunk

logger = logging.getLogger(__name__)

# 中文停用词（精简版，可按需扩展）
_STOP_WORDS = frozenset("""
的 了 和 是 在 我 你 他 她 它 也 都 就 要 会 能 有 没 不 没 但 而 被 从 到 把 让 给 向 用 于 上 下 个 些 之 与 及 或
一个 一些 这个 那个 这样 那样 这里 那里 什么 怎么 怎样 如何 为什么 多少 几个 哪些
""".split())

# 数字单独成词（防止 BM25 把"1"和"123"等同）
_NUMERIC_RE = re.compile(r'^\d+$')


def _tokenize(text: str) -> List[str]:
    """jieba 精确分词 + 去停用词 + 小写化"""
    import jieba
    # 开启 HMM 识别新词
    tokens = []
    for word in jieba.cut(text, cut_all=False, HMM=True):
        word = word.strip().lower()
        if not word:
            continue
        if word in _STOP_WORDS:
            continue
        if len(word) == 1 and not re.match(r'[\u4e00-\u9fa5]', word):
            # 过滤单字符非中文（避免标点/单字母噪声）
            continue
        if _NUMERIC_RE.match(word):
            # 数字统一映射为占位符（避免长度差异影响 BM25）
            tokens.append('<NUM>')
        else:
            tokens.append(word)
    return tokens


class BM25Retriever:
    """BM25 关键词检索（jieba + rank_bm25）"""

    def __init__(self, knowledge_base: KnowledgeBase) -> None:
        self.kb = knowledge_base
        self._cache: Optional[Dict] = None
        # 索引缓存目录
        from django.conf import settings
        cache_root = Path(settings.MEDIA_ROOT) / 'retrieval_cache'
        cache_root.mkdir(parents=True, exist_ok=True)
        self.cache_path = cache_root / f'bm25_kb{self.kb.id}.pkl'

    def _build_index(self) -> Dict:
        """从 DB 构建 BM25 索引"""
        from rank_bm25 import BM25Okapi

        chunks = KnowledgeChunk.objects.filter(
            knowledge_base=self.kb,
            is_active=True,
        ).values('id', 'content', 'bm25_tokens', 'chunk_metadata')

        ids: List[int] = []
        contents: List[str] = []
        metas: List[Dict] = []
        corpus: List[List[str]] = []

        for c in chunks:
            # 优先使用预存的 tokens（processor.py 写入），避免重复分词
            if c['bm25_tokens']:
                tokens = c['bm25_tokens']
            else:
                tokens = _tokenize(c['content'])
            if not tokens:
                continue
            ids.append(c['id'])
            contents.append(c['content'])
            metas.append(c['chunk_metadata'] or {})
            corpus.append(tokens)

        if corpus:
            bm25 = BM25Okapi(corpus)
        else:
            bm25 = None

        index = {
            'bm25': bm25,
            'ids': ids,
            'contents': contents,
            'metas': metas,
        }
        # 持久化
        try:
            with open(self.cache_path, 'wb') as f:
                pickle.dump(index, f)
        except Exception as e:
            logger.warning(f"[BM25] 缓存写入失败: {e}")

        return index

    def _load_index(self) -> Dict:
        """优先从 pickle 加载；加载失败则重建"""
        if self._cache is not None:
            return self._cache

        if self.cache_path.exists():
            try:
                with open(self.cache_path, 'rb') as f:
                    index = pickle.load(f)
                # 校验：chunk 数量是否一致
                db_count = KnowledgeChunk.objects.filter(
                    knowledge_base=self.kb, is_active=True
                ).count()
                if len(index.get('ids', [])) == db_count:
                    self._cache = index
                    return self._cache
                logger.info(f"[BM25] 缓存失效（db={db_count} vs cache={len(index.get('ids', []))}），重建")
            except Exception as e:
                logger.warning(f"[BM25] 缓存加载失败: {e}，重建")

        self._cache = self._build_index()
        return self._cache

    def invalidate_cache(self) -> None:
        """清缓存并删除磁盘文件"""
        self._cache = None
        try:
            if self.cache_path.exists():
                self.cache_path.unlink()
        except Exception as e:
            logger.warning(f"[BM25] 缓存删除失败: {e}")

    def search(self, query: str, top_k: int = 20) -> List[Dict]:
        """BM25 关键词检索

        Returns: [{'chunk_id', 'content', 'metadata', 'bm25_score'}, ...]
        """
        data = self._load_index()
        bm25 = data.get('bm25')
        if bm25 is None or len(data['ids']) == 0:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        try:
            scores = bm25.get_scores(query_tokens)
        except Exception as e:
            logger.error(f"[BM25] 评分失败: {e}")
            return []

        top_indices = np_argsort_top_k(scores, top_k)
        results: List[Dict] = []
        for idx in top_indices:
            if scores[idx] <= 0:
                continue
            results.append({
                'chunk_id': int(data['ids'][idx]),
                'content': data['contents'][idx],
                'metadata': data['metas'][idx],
                'bm25_score': float(scores[idx]),
            })
        return results


def np_argsort_top_k(arr, k: int):
    """等价 np.argsort(arr)[::-1][:k]，但避免引入 numpy 顶层依赖"""
    import numpy as np
    return np.argsort(arr)[::-1][:k]
