# Learnings

Corrections, insights, and knowledge gaps captured during development.

**Categories**: correction | insight | knowledge_gap | best_practice

---

## [LRN-20260717-001] best_practice

**Logged**: 2026-07-17
**Priority**: high
**Status**: pending
**Area**: backend

### Summary
VLM 视觉模型对 y 坐标始终输出 10x 真实百分比，需要统一除以 10

### Details
Midscene runner 使用 qwen3-vl-plus 等 VLM 看图识别元素坐标。VLM 对 x 坐标输出基本正确（50=50%），但对 y 坐标始终输出 10x 真实百分比。之前的 `>100 → /10` 修正只能兜住底部元素（y_pct=625→62.5%），顶部元素如 y_pct=65 在 100 以内不做修正，导致 65% 被计算为 1560px 而非实际的 156px（6.5%）。

### Suggested Action
y 坐标始终除以 10，x 坐标保留 >100 修正逻辑。已在 midscene_runner.py 修复。

### Metadata
- Source: conversation
- Related Files: apps/ui_automation/midscene_runner.py
- Tags: vlm, coordinate, mobile-automation, qwen

---

## [LRN-20260717-002] best_practice

**Logged**: 2026-07-17
**Priority**: medium
**Status**: pending
**Area**: backend

### Summary
录制数据按 step_idx 索引写入，而非 append，避免回退重试产生重复条目

### Details
Midscene 录制回放中，步骤被回退重试时会再次执行同一步。如果用 list.append() 存录制数据，会产生重复条目导致回放时下标错位。改用 recording[step_idx] = data 直接索引覆盖，回退重试自动覆盖旧数据。

### Suggested Action
录制数据存储逻辑已改为索引覆盖模式。类似场景（任何需要保证步骤唯一性的列表）都应优先考虑索引写入而非追加。

### Metadata
- Source: conversation
- Related Files: apps/ui_automation/midscene_runner.py
- Tags: recording, replay, midscene, index-overwrite

---

## [LRN-20260717-003] best_practice

**Logged**: 2026-07-17
**Priority**: medium
**Status**: pending
**Area**: backend

### Summary
adb input tap 偶尔丢事件，自动重试可显著减少 VLM 调用

### Details
adb shell input tap 在页面刚跳转完成时偶尔不注册（View 的 OnClickListener 尚未绑定）。tap 后截图对比 pHash，若页面未变则原地重试一次，第二次通常成功，避免触发 VLM 再决策一次。

### Suggested Action
tap/click 类动作增加轮内重试：执行→智能等待→截图对比→未变则重试→仍未变则强制 in_progress 让 VLM 继续

### Metadata
- Source: conversation
- Related Files: apps/ui_automation/midscene_runner.py
- Tags: adb, tap, retry, phash, midscene

---

## [LRN-20260717-004] best_practice

**Logged**: 2026-07-17
**Priority**: medium
**Status**: pending
**Area**: backend

### Summary
智能等待（pHash 轮询）比固定等待节省 30-50% 时间

### Details
原来 tap 后固定等 2s。改用 pHash 每 800ms 截图对比，连续两帧相同时页面稳定即返回。快速页面 0.8s 就过，慢的等满 2s。首次间隔用 800ms 而非 500ms，给 View 初始化留足时间，减少误判。

### Suggested Action
所有 UI 自动化等待都应优先用轮询（截图对比）而非固定延时。初始间隔根据场景调整（tap 类 800ms，输入类 300ms）。

### Metadata
- Source: conversation
- Related Files: apps/ui_automation/midscene_runner.py
- Tags: smart-wait, phash, midscene, optimization

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

