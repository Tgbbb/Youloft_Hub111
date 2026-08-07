# -*- coding: utf-8 -*-
"""会话历史：子目标 + 记忆 + 上轮执行反馈（对齐 Midscene ConversationHistory 的移动端精简版）。

核心思想：当前截图在后续轮次不可见，因此模型需要用 <memory> 精确保留跨步信息；
复杂任务用子目标列表维护长程进度；上一步的执行结果（成功/失败/页面是否变化）
通过 pending_feedback 回传给规划模型，驱动"反馈 → 重规划"。
"""


class ConversationHistory:
    SUB_GOAL_STATUS = ('pending', 'running', 'finished')

    def __init__(self, feedback_truncate=500, max_memories=20, max_logs=50):
        self.sub_goals = []  # [{'index': int, 'description': str, 'status': str}]
        self.memories = []   # [str]
        self.pending_feedback = ''
        self.logs = []       # 用户可见的一句话进度（<log>）
        self.feedback_truncate = feedback_truncate
        self.max_memories = max_memories
        self.max_logs = max_logs

    def _truncate(self, text, limit=None):
        text = str(text or '')
        limit = limit or self.feedback_truncate
        if len(text) <= limit:
            return text
        return f'{text[:limit]}...[truncated, {len(text) - limit} more characters]'

    # ---- 子目标 ----

    def merge_sub_goals(self, goals):
        """合并/更新子目标列表，保留已有描述（compact 更新时描述可为空）。"""
        if not goals:
            return
        by_index = {g['index']: g for g in self.sub_goals}
        for g in goals:
            existing = by_index.get(g['index'])
            if existing:
                if g.get('description'):
                    existing['description'] = g['description']
                if g.get('status') in self.SUB_GOAL_STATUS:
                    existing['status'] = g['status']
            else:
                by_index[g['index']] = {
                    'index': g['index'],
                    'description': g.get('description', ''),
                    'status': g.get('status', 'pending'),
                }
        self.sub_goals = [by_index[k] for k in sorted(by_index)]
        self._normalize_statuses()

    def mark_finished(self, indexes):
        for g in self.sub_goals:
            if g['index'] in indexes:
                g['status'] = 'finished'
        self._normalize_statuses()

    def _normalize_statuses(self):
        """保证最多一个 running；无 running 时把第一个 pending 置为 running。"""
        if not self.sub_goals:
            return
        if not any(g['status'] == 'running' for g in self.sub_goals):
            for g in self.sub_goals:
                if g['status'] == 'pending':
                    g['status'] = 'running'
                    break

    # ---- 记忆 ----

    def add_memory(self, text):
        text = self._truncate(text.strip())
        if text and (not self.memories or self.memories[-1] != text):
            self.memories.append(text)
            if len(self.memories) > self.max_memories:
                self.memories = self.memories[-self.max_memories:]

    # ---- 反馈 ----

    def set_feedback(self, text):
        self.pending_feedback = self._truncate(text)

    def clear_feedback(self):
        self.pending_feedback = ''

    # ---- 日志 ----

    def add_log(self, text):
        text = self._truncate(text, 200)
        if text:
            self.logs.append(text)
            if len(self.logs) > self.max_logs:
                self.logs = self.logs[-self.max_logs:]

    # ---- 快照（拼进规划 prompt） ----

    def snapshot_text(self):
        parts = []
        if self.sub_goals:
            lines = [f'{g["index"]}. [{g["status"]}] {g["description"] or "（无描述）"}' for g in self.sub_goals]
            parts.append('### 子目标状态\n' + '\n'.join(lines))
        if self.memories:
            lines = '\n'.join(f'- {m}' for m in self.memories[-5:])
            parts.append('### 已记录的信息（后续截图可能不再可见，请依据这些信息继续）\n' + lines)
        if self.pending_feedback:
            parts.append('### 上一步执行反馈\n' + self.pending_feedback)
        return '\n\n'.join(parts)
