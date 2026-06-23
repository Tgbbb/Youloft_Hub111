# Errors

Command failures and integration errors.

---

## [ERR-20260618-001] vue_data_brace_mismatch

**Logged**: 2026-06-18T11:50:00+08:00
**Priority**: high
**Status**: resolved
**Area**: frontend

### Summary
RequirementAnalysisView.vue 页面报错（白屏），控制台无明确错误信息。

### Error
花括号不匹配：`data()` 中 `return { ... }` 后 `  },` 只关闭一层，`return` 对象的 `}` 缺失。JS 解析失败但 Vue 编译器未给出友好提示。

### Context
- 添加 `pendingGeneration` 字段到 `data()` 返回值时，原有的 `  },` 被误认为同时关闭 return 对象和 data 函数
- 实际上 `  },` 只包含一个 `}`，只能关闭一层
- 导致 script 区段 brace depth = 1（差一个 `}`）

### Suggested Fix
在 `return` 对象属性末尾加上 `    }`（4空格缩进，关闭 return 对象），保留原有的 `  },`（2空格缩进，关闭 data 函数）。

### Metadata
- Reproducible: yes
- Related Files: frontend/src/views/requirement-analysis/RequirementAnalysisView.vue

---

## [ERR-20260618-002] multimodal_generation_hang

**Logged**: 2026-06-18T12:00:00+08:00
**Priority**: high
**Status**: resolved
**Area**: backend

### Summary
多模态生成任务 TASK_59235B16 卡在 30% 进度 16+ 分钟无响应。

### Error
```
progress endpoint returning 200 with 171 bytes: {"status":"generating","progress":30,...}
```
stream_buffer 有 1518 chars 但 generated_test_cases 为空。AI API 流式响应开始接收后停止产出 chunk，httpx 流式 read timeout(900s) 未触发。

### Context
- 模型: Qwen/Qwen3-VL-32B-Instruct via SiliconFlow API
- 任务在 11:42:12 后无任何更新
- 错误日志: "Task was destroyed but it is pending!" (async generator 未正确关闭)
- 根因: 32B VL 模型响应极慢（~12 chars/s），revise 阶段 9884 chars 耗时 14 分钟

### Suggested Fix
1. 新增 reviser 角色，revise 用纯文本快模型（已实施）
2. 给流式请求加整体超时（asyncio.wait_for）
3. 前端加超时提示而非无限等待

### Metadata
- Reproducible: yes (with large multimodal input)
- Related Files: apps/requirement_analysis/models.py
- See Also: LRN-20260618-003

---

