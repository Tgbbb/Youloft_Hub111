# Learnings

Corrections, insights, and knowledge gaps captured during development.

**Categories**: correction | insight | knowledge_gap | best_practice

---

## [LRN-20260728-001] correction

**Logged**: 2026-07-28
**Priority**: high
**Status**: resolved
**Area**: backend

### Summary
Qwen-Agent Tool `kwargs.get('user')` is always None. All write tools must use `User.objects.first()` fallback.

### Details
FnCallAgent calls `tool.call(params)` without extra kwargs. Any tool relying on `kwargs.get('user')` gets None, causing FK null errors on `created_by`/`author`/`executed_by`.

### Suggested Action
All write tools should start with:
```python
from apps.users.models import User
user = kwargs.get('user') or User.objects.first()
```

### Metadata
- Source: conversation
- Related Files: apps/assistant/tools.py
- Tags: qwen-agent, tools, user, fk

---

## [LRN-20260728-002] correction

**Logged**: 2026-07-28
**Priority**: high
**Status**: resolved
**Area**: backend

### Summary
Three tools had wrong Django Model field names.

### Details
- TestCase: `created_by` -> actually `author`
- TestCase: `type` -> actually `test_type`
- MidsceneCase: `status` field doesn't exist
- ApiRequest: `created_by` is correct

### Suggested Action
Always `grep` model fields before writing tools, don't rely on memory.

### Metadata
- Source: conversation
- Related Files: apps/assistant/tools.py, apps/testcases/models.py, apps/ui_automation/models.py
- Tags: tools, model, field-name

---

## [LRN-20260728-003] insight

**Logged**: 2026-07-28
**Priority**: medium
**Status**: pending
**Area**: backend

### Summary
Qwen native DashScope (`qwen_dashscope`) vs compatible mode (`oai`) have different function calling behavior.

### Details
- `qwen_dashscope`: uses nous XML format natively trained on Qwen models, no XML leakage
- `oai` with DashScope URL: uses OpenAI format, less reliable for function calling
- DeepSeek + nous: XML tags leak into text, infinite tool call loops
- AgentConfig with provider=qwen and empty base_url should use `qwen_dashscope`

### Metadata
- Source: conversation
- Related Files: apps/assistant/agent.py
- Tags: qwen, dashscope, function-calling, nous

---

## [LRN-20260728-004] best_practice

**Logged**: 2026-07-28
**Priority**: medium
**Status**: pending
**Area**: backend

### Summary
Qwen model sometimes "role-plays" tool execution instead of actually calling tools. Also fabricates success results when tool calls fail.

### Details
- User says "create", Agent describes creating but never calls `create_testcase`
- After tool failure, Agent may fabricate success (e.g. "ID: 208" that doesn't exist)
- System prompt now includes "禁止只描述不执行" and "禁止编造成功结果"

### Metadata
- Source: conversation
- Related Files: apps/assistant/agent.py
- Tags: agent, hallucination, function-calling, qwen

---

## [LRN-20260728-005] correction

**Logged**: 2026-07-28
**Priority**: high
**Status**: resolved
**Area**: backend

### Summary
System prompt must include project_id. Agent was guessing wrong project IDs.

### Details
System prompt showed "项目名称: tomo" without ID. Agent guessed project_id=1 (wrong) when tools required specific IDs. Fixed to show "项目名称: tomo (project_id=6)".

### Metadata
- Source: conversation
- Related Files: apps/assistant/agent.py
- Tags: system-prompt, project, context

## [LRN-20260728-006] correction

**Logged**: 2026-07-28
**Priority**: medium
**Status**: resolved
**Area**: frontend

### Summary
CSS 重写时容易丢失交互状态（如 hover 显示删除按钮），需检查所有 `:hover` 下的子元素 visibility。

### Details
Ark UI Endfield 重构 AssistantView 时，`.session-item:hover` 规则漏了 `.session-actions { opacity: 1 }`，导致会话删除按钮永久隐藏。旧版本有这个规则，新版本写 CSS 时遗漏。

### Suggested Action
CSS 重写后检查所有原本有 hover/focus/active 交互的元素是否仍然可操作。

### Metadata
- Source: user_feedback
- Related Files: frontend/src/views/assistant/AssistantView.vue
- Tags: css, hover, regression, endfield

---

## [LRN-20260728-007] insight

**Logged**: 2026-07-28
**Priority**: medium
**Status**: resolved
**Area**: backend

### Summary
Skills 文件系统和 MCP 是两个独立层，分别管理互不冲突。Skill = 指令 (.md)，MCP = 工具 (子进程)。

### Details
- `skills/` 目录存指令文件，Agent 启动时扫描注入 system prompt
- `mcp_servers/` 目录存独立 MCP 配置，Agent 启动时通过 MCPManager 加载工具
- Skill 可以内嵌 `mcp_config.json`，也可以完全独立
- 用户导入 Skill 包 (.zip) → 解压到 `skills/` → 扫描 SKILL.md + mcp_config.json
- Playwright MCP 包名是 `@playwright/mcp` 不是 `@anthropic-ai/mcp-playwright`

### Metadata
- Source: conversation
- Related Files: apps/assistant/skill_loader.py, apps/assistant/agent.py, mcp_servers/
- Tags: skills, mcp, architecture

---

## [LRN-20260728-008] correction

**Logged**: 2026-07-28
**Priority**: high
**Status**: resolved
**Area**: frontend

### Summary
Vue 组件中用了 `reactive` 但没 import，会导致页面 JS 报错白屏。

### Details
AssistantView.vue 中 `const mcpForm = reactive({ name: '', command: '' })` 但 import 行只写了 `ref, computed, onMounted, nextTick`，缺少 `reactive`。编译不报错但运行时直接炸。

### Metadata
- Source: error
- Related Files: frontend/src/views/assistant/AssistantView.vue
- Tags: vue, reactive, import, runtime-error
