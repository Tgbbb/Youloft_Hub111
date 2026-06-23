# Feature Requests

Capabilities requested by the user.

---

## [FEAT-20260618-001] reviser_role

**Logged**: 2026-06-18T13:00:00+08:00
**Priority**: high
**Status**: resolved
**Area**: backend

### Requested Capability
为 AI 用例生成流程新增独立的「用例改进专家」（reviser）角色，revise 步骤使用独立配置的快速文本模型。

### User Context
多模态生成时 writer 配 Qwen3-VL-32B，revise 是纯文本任务却复用同一个慢模型，14 分钟延迟。用户确认各步骤是独立 API 调用、不共享上下文后，同意新增 reviser 角色。

### Complexity Estimate
medium

### Suggested Implementation
models.py 加字段 → views.py 加查找 → revise 方法优先用 reviser → 前端/i18n 同步

### Metadata
- Frequency: first_time
- Related Features: clarifier_role

### Resolution
- **Resolved**: 2026-06-18
- **Notes**: 完整实施，migration 0006 已应用。用户需配 reviser 快模型。

---

