# Errors

Command failures and integration errors.

---

## [ERR-20260728-001] tools

**Logged**: 2026-07-28
**Priority**: high
**Status**: resolved
**Area**: backend

### Summary
`TestCase.objects.create(created_by=...)` failed — field doesn't exist

### Error
```
TestCase() got unexpected keyword arguments: 'created_by'
```

### Context
- `create_testcase` tool used `created_by=user` but TestCase model uses `author`
- Same pattern repeated for `test_type` (not `type`) and MidsceneCase (no `status`)
- Root cause: assumed field names without checking model definitions

### Suggested Fix
Always grep the actual model file for field names before writing tool code.

### Metadata
- Reproducible: yes
- Related Files: apps/assistant/tools.py, apps/testcases/models.py

---

## [ERR-20260728-002] agent

**Logged**: 2026-07-28
**Priority**: high
**Status**: resolved
**Area**: backend

### Summary
DeepSeek + `nous` function calling format caused XML tag leakage and infinite tool loops

### Error
```
[text] <tool_call
[text] 已达到单轮工具调用上限(10次)
```

### Context
- Qwen-Agent's `nous` format uses `<tool_call>` XML tags
- DeepSeek wasn't trained on this format
- Model output fragmented XML tags into text
- Tool call loop detection triggered after 10 calls

### Suggested Fix
Use `qwen_dashscope` native mode for Qwen models. Don't use `nous` format with non-Qwen models.

### Metadata
- Reproducible: yes
- Related Files: apps/assistant/agent.py

## [ERR-20260728-003] skills-css

**Logged**: 2026-07-28
**Priority**: medium
**Status**: resolved
**Area**: frontend

### Summary
Endfield 重构后删除按钮消失

### Error
会话列表项的删除按钮在 hover 时不显示

### Context
- CSS 重写时 `.session-item:hover` 规则缺少 `.session-actions { opacity: 1 }`
- 修复：加回 `.session-actions { opacity: 1; }`

### Metadata
- Reproducible: yes
- Related Files: frontend/src/views/assistant/AssistantView.vue
