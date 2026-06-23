# Learnings

Corrections, insights, and knowledge gaps captured during development.

**Categories**: correction | insight | knowledge_gap | best_practice

---

## [LRN-20260618-001] best_practice

**Logged**: 2026-06-18T12:00:00+08:00
**Priority**: high
**Status**: resolved
**Area**: frontend

### Summary
Vue Options API `data()` 函数中 `return { ... }` 需要用 `}` 显式关闭 return 对象，再用 `},` 关闭 data 函数本身。添加新字段时容易漏掉 return 对象的闭合花括号导致 JS 解析失败。

### Details
在 `RequirementAnalysisView.vue` 的 `data()` 返回值末尾添加了 `pendingGeneration` 等新属性后，原代码 `  },` 同时充当了 return 对象闭合和 data 函数闭合。但 `},` 只有一个 `}`，只关闭了一层，导致整个组件花括号层级错位，页面白屏无报错。

修复：在 `return` 对象结尾补上 `    }`（4空格缩进），再保留 `  },`（2空格缩进）闭合 `data()`。

### Suggested Action
每当修改 Vue data() 返回值时，用脚本验证花括号平衡：`python -c "..."` 统计 `{` `}` 差值。

### Metadata
- Source: error
- Related Files: frontend/src/views/requirement-analysis/RequirementAnalysisView.vue
- Tags: vue, data, braces, syntax

---

## [LRN-20260618-002] insight

**Logged**: 2026-06-18T12:30:00+08:00
**Priority**: high
**Status**: resolved
**Area**: backend, frontend

### Summary
新增 AI 角色（如 clarifier、reviser）时，前端有 5 处硬编码列表需要同步更新，load_defaults API 也需要加。

### Details
添加新角色需要改的地方：
1. `models.py` — ROLE_CHOICES + PROMPT_CHOICES（后端）
2. `AIModelConfig.vue` — 角色 `<option>` 下拉（前端）
3. `PromptConfig.vue` — 类型 `<option>` 下拉 + `labelMap` + `['writer','reviewer',...]` 数组 + `defaultPrompts` + tabs + `loadDefaults` 创建逻辑（前端，共 7 处）
4. `configuration.js` — `roles: { ... }` i18n（中英文）
5. `requirement.js` — `promptConfig` 相关 key（中英文）
6. `views.py` — `load_defaults` API（后端）

遗漏任何一处都会导致前端不显示或加载为空白。

### Suggested Action
考虑后端提供一个 `GET /api/requirement-analysis/config/role-choices/` 接口返回动态选项，前端下拉框从 API 读取，消除硬编码。

### Metadata
- Source: error + correction
- Related Files: AIModelConfig.vue, PromptConfig.vue, configuration.js, requirement.js, views.py, models.py
- Tags: role, dropdown, hardcoded, sync

---

## [LRN-20260618-003] insight

**Logged**: 2026-06-18T13:00:00+08:00
**Priority**: high
**Status**: pending
**Area**: backend

### Summary
多模态生成流程中 revise（改进）步骤复用了 writer 模型，当 writer 是 32B VL 模型时，纯文本的 revise 耗时 14 分钟（72% 总时间）。

### Details
generate → review → revise 三个步骤各自是独立的 API 调用，每次重新打包完整上下文。revise 的输入（原始用例 + 评审意见 + 改进指令）是纯文本，不需要视觉能力。用 Qwen3-VL-32B 做纯文本生成 ~12 chars/s，换成文本快模型可降到 1-2 分钟。

解决方案：新增 reviser 角色，revise 优先用 reviser 配置，未配时 fallback 到 writer。

### Suggested Action
用户给 reviser 配置一个纯文本快模型（如 DeepSeek-V3），预计总耗时从 ~20 分钟降到 ~7 分钟。

### Metadata
- Source: observation
- Related Files: apps/requirement_analysis/models.py (revise_test_cases_based_on_review)
- Tags: multimodal, performance, revise, model-selection
- See Also: FEAT-20260618-001

---

