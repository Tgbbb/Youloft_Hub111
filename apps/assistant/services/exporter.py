"""知识库 Markdown 导出器

将一个 KB 的所有 active chunks 导出为 Markdown 文本，便于团队存档。

格式策略（按文档 source 分流）：
- XMind 文档：根据每个 chunk 的 metadata.path 数组重建嵌套树
  （与 xmind 视觉层级一致，2 空格缩进）
- 其他文档（PDF / DOCX / MD / TXT）：保持 chunk 列表平铺展示

输出结构：
```
# 知识库名

> 元信息

## 文档列表
- ...

## <文档名>
（xmind：嵌套大纲；其他：### Chunk 列表）

## 文档名2
...

## 附录：变更日志（最近 7 天）
| 时间 | 动作 | Chunk | 操作人 | 摘要 |
```
"""
from __future__ import annotations

import re
from collections import OrderedDict
from datetime import timedelta
from typing import Optional

from django.utils import timezone

from apps.assistant.models import (
    KnowledgeBase,
    KnowledgeChunk,
    KnowledgeUpdateLog,
)


# 匹配 chunk content 中的 bullet 行（"- xxx" 或 "  - xxx"）
_BULLET_RE = re.compile(r'^[\s]*[-*+]\s+(.+?)\s*$', re.MULTILINE)
# 匹配 chunk content 顶部的 path 前缀（第一行的"【...】"）
_PATH_LINE_RE = re.compile(r'^【(.+?)】\s*\n', re.MULTILINE)


def _parse_bullets(content: str) -> list[str]:
    """从 chunk content 中提取所有 bullet 行（去掉开头的 path 前缀）。"""
    # 先去掉 path 前缀
    content = _PATH_LINE_RE.sub('', content, count=1)
    bullets = _BULLET_RE.findall(content)
    # 过滤空字符串
    return [b.strip() for b in bullets if b.strip()]


class KBMarkdownExporter:
    """将 KB 导出为 Markdown 文本。"""

    # 缩进字符
    INDENT = '  '

    def __init__(
        self,
        knowledge_base_id: int,
        include_update_log: bool = True,
        update_log_days: int = 7,
        flat: bool = False,
    ) -> None:
        """
        Args:
            knowledge_base_id: KB ID
            include_update_log: 是否包含变更日志附录
            update_log_days: 变更日志天数
            flat: True 强制平铺（不区分文档类型），用于向后兼容
        """
        self.kb = KnowledgeBase.objects.get(id=knowledge_base_id)
        self.include_update_log = include_update_log
        self.update_log_days = update_log_days
        self.flat = flat

    def export(self) -> str:
        """生成完整 Markdown 文本。"""
        # 1. 取所有 active chunks（按 document、chunk_index 排序）
        chunks = (
            KnowledgeChunk.objects
            .filter(knowledge_base=self.kb, is_active=True)
            .select_related('document')
            .order_by('document_id', 'chunk_index', 'id')
        )
        chunks_list = list(chunks)
        total = len(chunks_list)

        # 2. 按 document 分组
        grouped: "OrderedDict[int, list[KnowledgeChunk]]" = OrderedDict()
        doc_cache: dict[int, str] = {}
        for c in chunks_list:
            grouped.setdefault(c.document_id, []).append(c)
            if c.document_id not in doc_cache:
                doc_cache[c.document_id] = c.document.file_name

        # 3. 拼接 Markdown
        lines: list[str] = []
        lines.extend(self._render_header(total, len(grouped)))
        lines.append("")
        lines.extend(self._render_doc_index(grouped, doc_cache))
        lines.append("")
        for doc_id, items in grouped.items():
            doc_name = doc_cache[doc_id]
            lines.extend(self._render_document(doc_id, doc_name, items))
        if self.include_update_log:
            lines.append("")
            lines.extend(self._render_update_log())
        return "\n".join(lines).rstrip() + "\n"

    # ---------------------------------------------------------------
    # 段落渲染
    # ---------------------------------------------------------------

    def _render_header(self, chunk_count: int, doc_count: int) -> list[str]:
        return [
            f"# {self.kb.name}",
            "",
            f"> **知识库 ID**: {self.kb.id}  ",
            f"> **Embedding 模型**: {self.kb.embedding_model} (dim={self.kb.embedding_dim})  ",
            f"> **描述**: {self.kb.description or '（无）'}  ",
            f"> **导出时间**: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
            f"> **统计**: {doc_count} 个文档，{chunk_count} 个 active chunks  ",
        ]

    def _render_doc_index(self, grouped, doc_cache) -> list[str]:
        lines = ["## 文档列表", ""]
        for doc_id, items in grouped.items():
            name = doc_cache[doc_id]
            source = self._detect_source(items)
            tag = "（xmind 树形）" if source == 'xmind' else "（chunk 列表）"
            lines.append(f"- `{name}` — {len(items)} 个 chunk {tag}")
        return lines

    def _detect_source(self, items: list[KnowledgeChunk]) -> str:
        """检测该文档的 source 类型。"""
        for c in items:
            meta = c.chunk_metadata or {}
            if meta.get('source') == 'xmind':
                return 'xmind'
        # 兜底：检查文件后缀
        if items and items[0].document.file_name.lower().endswith('.xmind'):
            return 'xmind'
        return 'other'

    def _render_document(
        self,
        doc_id: int,
        doc_name: str,
        items: list[KnowledgeChunk],
    ) -> list[str]:
        """渲染单个文档：xmind 走嵌套树形，其他走 chunk 列表。"""
        lines: list[str] = [f"## {doc_name}", ""]
        if self.flat:
            source = 'other'
        else:
            source = self._detect_source(items)

        if source == 'xmind':
            try:
                lines.extend(self._render_xmind_tree(items))
            except Exception as e:
                # 树形重建失败 → 降级为 chunk 列表
                lines.append(f"> ⚠️ 树形重建失败，已降级为 chunk 列表：{e}")
                lines.append("")
                lines.extend(self._render_chunk_list(items))
        else:
            lines.extend(self._render_chunk_list(items))
        return lines

    # ---------------------------------------------------------------
    # XMind 嵌套树形
    # ---------------------------------------------------------------

    def _render_xmind_tree(self, items: list[KnowledgeChunk]) -> list[str]:
        """根据 chunks 的 metadata.path 重建嵌套树。

        每个 chunk = 一个节点，其 content 的 bullet 列表 = 该节点的直接 children。
        """
        # 1. 构建 path → chunk 索引
        path_to_chunk: dict[tuple, KnowledgeChunk] = {}
        for c in items:
            meta = c.chunk_metadata or {}
            path = meta.get('path')
            if not path or not isinstance(path, list):
                continue
            path_to_chunk[tuple(path)] = c

        if not path_to_chunk:
            return ["（无可用 path 数据）", ""]

        # 2. 找根节点（path 最短）
        root_path = min(path_to_chunk.keys(), key=len)
        root_chunk = path_to_chunk[root_path]
        root_name = root_path[-1]  # 根节点的显示名

        lines: list[str] = []
        # 显示根节点标题（## 二级标题已经是文档名了，根节点再加一行说明）
        if root_name and root_name != root_chunk.document.file_name:
            lines.append(f"**{root_name}**")
            lines.append("")

        # 3. 递归展开
        def walk(node_path: tuple, depth: int) -> None:
            chunk = path_to_chunk.get(node_path)
            if not chunk:
                return
            bullets = _parse_bullets(chunk.content)
            for bullet in bullets:
                lines.append(f"{self.INDENT * depth}- {bullet}")
                # 递归到子节点
                sub_path = node_path + (bullet,)
                if sub_path in path_to_chunk:
                    walk(sub_path, depth + 1)

        walk(root_path, 0)
        return lines

    # ---------------------------------------------------------------
    # 普通 chunk 列表
    # ---------------------------------------------------------------

    def _render_chunk_list(self, items: list[KnowledgeChunk]) -> list[str]:
        lines: list[str] = []
        for c in items:
            section_hint = (c.chunk_metadata or {}).get('section_hint', '') if c.chunk_metadata else ''
            if section_hint:
                lines.append(f"### Chunk #{c.chunk_index} (v{c.version}) — {section_hint}")
            else:
                lines.append(f"### Chunk #{c.chunk_index} (v{c.version})")
            lines.append("")
            lines.append(c.content)
            lines.append("")
        return lines

    # ---------------------------------------------------------------
    # 变更日志
    # ---------------------------------------------------------------

    def _render_update_log(self) -> list[str]:
        since = timezone.now() - timedelta(days=self.update_log_days)
        logs = (
            KnowledgeUpdateLog.objects
            .filter(knowledge_base=self.kb, created_at__gte=since)
            .select_related('user')
            .order_by('-created_at')
        )
        lines = [
            "---",
            "",
            f"## 附录：变更日志（最近 {self.update_log_days} 天）",
            "",
        ]
        if not logs:
            lines.append("（无变更记录）")
            return lines

        lines.append("| 时间 | 动作 | Chunk | 操作人 | 摘要 |")
        lines.append("|------|------|-------|--------|------|")
        for l in logs:
            action_disp = l.get_action_display()
            chunk_ref = f"#{l.chunk_id}" if l.chunk_id else "-"
            superseded = f" (替代 #{l.superseded_chunk_id})" if l.superseded_chunk_id else ""
            user = l.user.username if l.user else 'system'
            summary = l.summary.replace('|', '\\|')
            lines.append(
                f"| {l.created_at.strftime('%Y-%m-%d %H:%M')} "
                f"| {action_disp} "
                f"| {chunk_ref}{superseded} "
                f"| {user} "
                f"| {summary} |"
            )
        return lines
