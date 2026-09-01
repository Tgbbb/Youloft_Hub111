"""文档解析与切块服务

支持 xmind / pdf / docx / md / txt 文档的统一解析接口，
并提供递归文本切块器（段落 → 句子 → 字符）保证 chunk 大小可控。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List


class DocumentParser:
    """文档解析器，统一返回 List[{content, metadata}]"""

    @staticmethod
    def parse(file_path: str, file_type: str) -> List[Dict]:
        """
        主入口：根据文件类型分发到具体解析器

        Args:
            file_path: 文件绝对路径
            file_type: 文件类型（xmind/pdf/docx/md/txt）

        Returns:
            List[Dict]: [{'content': str, 'metadata': dict}, ...]
        """
        parsers = {
            'xmind': DocumentParser._parse_xmind,
            'pdf': DocumentParser._parse_pdf,
            'docx': DocumentParser._parse_docx,
            'md': DocumentParser._parse_markdown,
            'txt': DocumentParser._parse_text,
        }
        parser = parsers.get(file_type)
        if not parser:
            raise ValueError(f"不支持的文件类型: {file_type}")
        return parser(file_path)

    @staticmethod
    def _parse_xmind(file_path: str) -> List[Dict]:
        """解析 XMind，转为带路径前缀的分层 chunks

        策略：每个非叶子节点 = 1 个 chunk
        - chunk 内容 = 完整路径前缀（【根 > 父 > 当前】）+ 节点子项列表
        - 这样"实时截屏 > 业务规则"成为一个 chunk，包含"截图限额"等所有业务规则
        - 每个 chunk 自带完整路径信息，检索时不会被上下文稀释
        """
        try:
            import xmindparser
        except ImportError as e:
            raise ImportError(
                "请先安装 xmindparser: pip install xmindparser"
            ) from e

        workbook = xmindparser.xmind_to_dict(file_path)
        sheets = workbook if isinstance(workbook, list) else [workbook]

        chunks: List[Dict] = []
        for sheet in sheets:
            sheet_title = sheet.get('title', '未命名工作表')
            topic = sheet.get('topic', {}) or {}
            for c in DocumentParser._xmind_node_chunks(
                topic, path=[sheet_title], depth=0
            ):
                chunks.append(c)
        return chunks

    @staticmethod
    def _xmind_extract_notes(topic: Dict) -> str:
        """提取 xmind 节点的备注"""
        notes = topic.get('notes')
        if not notes:
            return ''
        if isinstance(notes, str):
            return notes.strip()
        plain = (notes.get('plain', {}) or {}).get('content', '')
        return plain.strip() if plain else ''

    @staticmethod
    def _xmind_node_chunks(
        topic: Dict, path: List[str], depth: int
    ) -> List[Dict]:
        """递归为每个非叶子节点生成 1 个 chunk

        chunk 内容格式：
            【根 > 父 > 当前节点】
            - 子项 1
            - 子项 2
              备注说明
            - 子项 3

        同时支持：
        - 节点的 notes 拼到 chunk 末尾
        - 子项的 notes 缩进显示
        """
        title = (topic.get('title') or '').strip()
        if not title:
            return []

        children = topic.get('topics') or []
        current_path = path + [title]
        chunks: List[Dict] = []

        if children:
            # 收集所有子项
            child_lines: List[str] = []
            for child in children:
                child_title = (child.get('title') or '').strip()
                if not child_title:
                    continue
                child_lines.append(f"- {child_title}")
                # 子项的 notes 作为补充说明
                child_notes = DocumentParser._xmind_extract_notes(child)
                if child_notes:
                    for line in child_notes.split('\n'):
                        line = line.strip()
                        if line:
                            child_lines.append(f"  {line}")

            if child_lines:
                path_str = " > ".join(current_path)
                content = f"【{path_str}】\n" + "\n".join(child_lines)

                # 当前节点的备注
                own_notes = DocumentParser._xmind_extract_notes(topic)
                if own_notes:
                    content += f"\n\n> {own_notes}"

                # 标签
                labels = topic.get('labels') or []
                if labels:
                    content += f"\n\n**标签**: {', '.join(labels)}"

                # 链接
                href = topic.get('href')
                if href:
                    content += f"\n\n[链接]({href})"

                chunks.append({
                    'content': content,
                    'metadata': {
                        'source': 'xmind',
                        'sheet': path[0] if path else '未命名',
                        'path': current_path,
                    }
                })

            # 递归处理子节点（不管当前是否生成了 chunk）
            for child in children:
                chunks.extend(
                    DocumentParser._xmind_node_chunks(
                        child, current_path, depth + 1
                    )
                )

        return chunks

    @staticmethod
    def _xmind_topic_to_markdown(topic: Dict, lines: List[str], level: int) -> None:
        """递归把 XMind topic 转 Markdown"""
        title = (topic.get('title') or '').strip()
        if title:
            prefix = "#" * level
            lines.append(f"{prefix} {title}")
            lines.append("")

        # 备注
        notes = topic.get('notes')
        if notes:
            note_text = notes if isinstance(notes, str) else (notes.get('plain', {}) or {}).get('content', '')
            if note_text and note_text.strip():
                lines.append(f"> {note_text.strip()}")
                lines.append("")

        # 标签
        labels = topic.get('labels') or []
        if labels:
            lines.append(f"**标签**: {', '.join(labels)}")
            lines.append("")

        # 链接
        href = topic.get('href')
        if href:
            lines.append(f"[链接]({href})")
            lines.append("")

        # 子主题递归
        for child in topic.get('topics') or []:
            DocumentParser._xmind_topic_to_markdown(child, lines, level + 1)

    @staticmethod
    def _parse_pdf(file_path: str) -> List[Dict]:
        """解析 PDF，按"结构化分块"返回。

        关键设计：识别 PDF 文本中的"伪章节标题"，将其作为 chunk 的 path prefix，
        避免上下文稀释（对比 xmind 的路径前缀机制）。

        两层标题识别：
        1. 跨行标题：独立一行的短词（2-6 字符、无标点、不是版本号、不是常见动词）
        2. 行内子标题：长行中 "短词+：+..." 的模式（子主题引出子内容）

        输出 chunks:
            【轻练 > 自由训练】动作库选择动作...
            【轻练 > 自由训练 > 导入训练】分享码：6 位数字母...
        """
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        chunks: List[Dict] = []

        # 跨行/行内子标题候选：2-6 字符纯中文（或 2-6 字符纯英文）
        _head_candidate_re = re.compile(r'^[\u4e00-\u9fa5]{2,6}$|^[A-Za-z]{2,6}$')
        # 排除：纯数字 / 版本号
        _version_re = re.compile(r'^[vV]?\d+(\.\d+)*$')
        # 常见动词/语气词（不作为标题）
        _common_verbs = set("""
            点击 输入 展示 设置 打开 关闭 切换 跳转 返回 弹窗 弹起 弹出 提示 默认 选中 选
            切换 限制 勾选 滑动 长按 拖动 排序 删除 完成 添加 修改 编辑 重置 刷新 确认 取消
            放弃 继续 加载 上传 下载 同步 保存 复制 粘贴 分享 发送 接收 推送 拉取
            选择 选择 选中 标识 拖拽 弹窗 收起 展开 折叠 停止 启动 重启 退出 卸载
            立即 跳过 延长 增加 减少 显示 隐藏 提示 弹窗 文字 图片 视频 加载
            在 用 是 有 和 与 及 或 也 不 没 但 而 被 从 到 把 让 给 向
            手动 自动 全部 已 未 当 当前 之前 之后 完成 进行 操作 处理
        """.split())

        def _is_heading(s: str) -> bool:
            s = s.strip()
            if not _head_candidate_re.match(s):
                return False
            if _version_re.match(s):
                return False
            if s in _common_verbs:
                return False
            return True

        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            text = text.strip()
            if not text:
                continue

            lines = [ln.rstrip() for ln in text.split('\n')]
            page_chunks: List[Dict] = []
            current_path: List[str] = []
            current_body: List[str] = []

            def flush():
                if not current_body and not current_path:
                    return
                body_text = '\n'.join(current_body).strip()
                if not body_text:
                    return
                prefix = '【' + ' > '.join(current_path) + '】\n' if current_path else ''
                content = f"{prefix}{body_text}".strip()
                if content:
                    page_chunks.append({
                        'content': content,
                        'metadata': {
                            'source': 'pdf',
                            'page': i + 1,
                            'section_path': current_path.copy(),
                        }
                    })

            for ln in lines:
                stripped = ln.strip()
                if not stripped:
                    if current_body and current_body[-1] != '':
                        current_body.append('')
                    continue

                # 1. 跨行标题检测
                if _is_heading(stripped):
                    flush()
                    current_path = [stripped]
                    current_body = []
                    continue

                # 2. 行内子标题检测（更严格）：
                # 仅识别 "短词+：+..." 模式，确保是子主题引出子内容
                # 例: "导入训练\n分享码：6..."  → 但这跨行了
                # 例: "导入训练 分享码：6..."    → 用空格分隔的子主题
                # 用 "短词 短词：+内容" 来识别
                sub_re = re.compile(
                    r'(?<![\u4e00-\u9fa5])'  # 前面不是中文（避免截断词中）
                    r'(?P<head>[\u4e00-\u9fa5]{2,6})'  # 短词
                    r'(?=\s+[\u4e00-\u9fa5]{1,8}[:：])'  # 后跟"短词+冒号"
                )
                m = sub_re.search(stripped)
                if m and _is_heading(m.group('head')):
                    head = m.group('head')
                    # 把 m.start() 之前作为正文，head 之后作为新 section 的 body
                    pre = stripped[:m.start()].strip()
                    post = stripped[m.end():].strip()
                    if pre:
                        current_body.append(pre)
                    flush()
                    current_path = current_path + [head]
                    current_body = [post] if post else []
                else:
                    current_body.append(stripped)

            # 收尾
            flush()

            if page_chunks:
                chunks.extend(page_chunks)
            else:
                # 回退：整页作为 1 个 chunk
                chunks.append({
                    'content': text,
                    'metadata': {'source': 'pdf', 'page': i + 1}
                })

        return chunks

    @staticmethod
    def _parse_docx(file_path: str) -> List[Dict]:
        """解析 Word 文档"""
        from docx import Document
        doc = Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text and p.text.strip()]
        content = "\n\n".join(paragraphs)
        return [{
            'content': content,
            'metadata': {'source': 'docx'}
        }]

    @staticmethod
    def _parse_markdown(file_path: str) -> List[Dict]:
        """解析 Markdown"""
        text = Path(file_path).read_text(encoding='utf-8')
        return [{
            'content': text,
            'metadata': {'source': 'markdown'}
        }]

    @staticmethod
    def _parse_text(file_path: str) -> List[Dict]:
        """解析纯文本"""
        text = Path(file_path).read_text(encoding='utf-8', errors='ignore')
        return [{
            'content': text,
            'metadata': {'source': 'text'}
        }]


class TextChunker:
    """文本分块器：段落 → 句子 → 字符回退，保留 overlap"""

    @staticmethod
    def chunk(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """
        递归切分：先按段落，再按句子，最后按字符
        """
        if not text or not text.strip():
            return []

        # 清理多余空白
        text = re.sub(r'\n{3,}', '\n\n', text).strip()

        if len(text) <= chunk_size:
            return [text]

        chunks: List[str] = []
        paragraphs = re.split(r'\n\s*\n', text)
        current = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current) + len(para) + 2 <= chunk_size:
                current = f"{current}\n\n{para}" if current else para
            else:
                if current:
                    chunks.append(current)
                # 单段过长：按句子切
                if len(para) > chunk_size:
                    sentences = re.split(r'(?<=[。！？!?\.])\s*', para)
                    sub_current = ""
                    for sent in sentences:
                        sent = sent.strip()
                        if not sent:
                            continue
                        if len(sub_current) + len(sent) + 1 <= chunk_size:
                            sub_current = f"{sub_current}{sent}" if sub_current else sent
                        else:
                            if sub_current:
                                chunks.append(sub_current)
                            # 单句还长：强制按 chunk_size 切
                            if len(sent) > chunk_size:
                                for i in range(0, len(sent), chunk_size - overlap):
                                    chunks.append(sent[i:i + chunk_size])
                                sub_current = ""
                            else:
                                sub_current = sent
                    if sub_current:
                        chunks.append(sub_current)
                    current = ""
                else:
                    current = para

        if current:
            chunks.append(current)

        # 加 overlap：保留前一块尾部作为下块开头
        if overlap > 0 and len(chunks) > 1:
            overlapped = [chunks[0]]
            for i in range(1, len(chunks)):
                prev_tail = overlapped[-1][-overlap:] if len(overlapped[-1]) > overlap else overlapped[-1]
                overlapped.append(prev_tail + chunks[i])
            chunks = overlapped

        return [c.strip() for c in chunks if c.strip()]
