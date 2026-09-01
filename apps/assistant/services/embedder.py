"""Embedding 向量化服务（本地 BGE-M3 模型）

使用 sentence-transformers 在本地加载 BGE-M3 模型进行向量化。
- 优势：零 API 成本、离线可用、1024 维
- 模型：首次运行自动从 HuggingFace 下载（约 2.3GB）
- 缓存：模型下载到 ~/.cache/huggingface/ 后续秒级加载
"""
from __future__ import annotations

import logging
import os
import pickle
from pathlib import Path
from typing import List

import numpy as np
from decouple import config

logger = logging.getLogger(__name__)

# 屏蔽 transformers / huggingface 的大量 INFO 日志
os.environ.setdefault('TRANSFORMERS_VERBOSITY', 'error')
os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')


class Embedder:
    """调用本地 BGE-M3 模型批量向量化文本"""

    _model = None  # 类级单例：首次加载后所有实例共享
    _loaded_model_name = None  # 记录已加载的模型名，避免重复加载

    def __init__(self) -> None:
        # 配置项
        self.model_name = config(
            'EMBEDDING_MODEL',
            default='BAAI/bge-m3'
        )
        try:
            self.dim = int(config('EMBEDDING_DIM', default=1024))
        except (TypeError, ValueError):
            self.dim = 1024
        self.cache_dir = config(
            'EMBEDDING_CACHE_DIR',
            default=str(Path.home() / '.cache' / 'huggingface')
        )
        # 设备
        import torch
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        # 懒加载（首次实例化时下载/读取模型）
        self._ensure_model_loaded()

    @classmethod
    def _ensure_model_loaded(cls) -> None:
        """懒加载 SentenceTransformer 模型（单例）"""
        target_name = config('EMBEDDING_MODEL', default='BAAI/bge-m3')
        if cls._model is not None and cls._loaded_model_name == target_name:
            return

        from sentence_transformers import SentenceTransformer
        cache_dir = config(
            'EMBEDDING_CACHE_DIR',
            default=str(Path.home() / '.cache' / 'huggingface')
        )
        import torch as _torch
        device = 'cuda' if _torch.cuda.is_available() else 'cpu'

        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        logger.info(f"Loading embedding model: {target_name} (device={device})")
        print(f"[Embedder] Loading model {target_name} on {device} ...")
        print(f"[Embedder] First time may take 1-3 min to download (~2.3GB)")

        cls._model = SentenceTransformer(
            target_name,
            device=device,
            cache_folder=cache_dir,
            trust_remote_code=True,
        )
        cls._loaded_model_name = target_name
        actual_dim = cls._model.get_sentence_embedding_dimension()
        print(f"[Embedder] Model loaded (dim={actual_dim})")

    def embed_texts(self, texts: List[str], batch_size: int = 16) -> List[np.ndarray]:
        """
        批量向量化（本地推理）

        Args:
            texts: 待向量化的文本列表
            batch_size: 批大小（CPU 建议 8-16，GPU 可 32+）

        Returns:
            List[np.ndarray]: 每个向量 shape=(dim,), dtype=float32
        """
        if not texts:
            return []
        logger.info(f"Embedding {len(texts)} texts, batch_size={batch_size}")
        # BGE-M3 推荐 normalize_embeddings=True 以便后续余弦相似度直接点积
        vecs = self._model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return [v.astype(np.float32) for v in vecs]

    def embed_query(self, text: str) -> np.ndarray:
        """单条向量化（用于查询）"""
        result = self.embed_texts([text], batch_size=1)
        return result[0]

    @staticmethod
    def serialize_vector(vec: np.ndarray) -> bytes:
        """向量 → bytes（用于 MySQL BLOB 存储）"""
        return pickle.dumps(vec)

    @staticmethod
    def deserialize_vector(blob: bytes) -> np.ndarray:
        """bytes → 向量"""
        return pickle.loads(blob)
