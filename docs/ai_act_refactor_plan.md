# aiAct 重构实施计划（借鉴 Midscene）

> 已实现。以 `E:\midscene-main\midscene-main` 为参照，新建独立引擎模块
> `apps/ui_automation/midscene_ai/`，完整对齐 Midscene 的 XML 规划协议与
> "描述元素 → 定位坐标 → 执行"两阶段交互，用"规划 → 执行 → 反馈 → 重规划"
> 循环替代旧 aiAct 单步循环，并补齐 Android 中文输入。

## 已确认决策

- 完整对齐 XML 规划协议（`<planning>/<memory>/<update-plan-content>/
  <mark-sub-goal-done>/<complete success>/<log>/<error>/<action-type>/
  <action-param-json>`）
- 两阶段 locate 默认开启（`use_locate` 可关，省 API 成本）
- Android 输入：yadb（非 ASCII/特殊字符）+ 单引号转义兜底（ASCII）
- 执行链路入口不变：`run_midscene_test` 签名不变，逐行模式零逻辑改动
- 独立新模块：仓库内新 Python 包，不是独立服务
- 移动端定位与 Midscene 一致：纯截图视觉识别，不引入 DOM/无障碍树
  （Midscene `packages/android/src/device.ts:668` `getElementsInfo()` 返回 `[]`）

## 模块结构

```
apps/ui_automation/midscene_ai/
├── __init__.py              # 对外仅 run_ai_act
├── protocol.py              # XML 规划协议解析（容错对齐 extractXMLTag）
├── conversation_history.py  # 子目标(pending/running/finished) + 记忆 + 上轮反馈(截断500)
├── prompts.py               # 移动端精简版 XML 规划提示词 + locate 提示词
├── actions.py               # 动作白名单 + pct→px + 越界处理 + 动作指纹
├── locate.py                # 两阶段定位：描述元素 → center/rect 坐标
├── executor.py              # 动作执行 + pHash 效果验证 + tap 重试
├── engine.py                # run_ai_act 主循环（plan→locate→execute→feedback→replan）
└── bin/yadb                 # yadb dex（Android 中文输入，GitHub v1.1.1）
```

## 主循环（对齐 Midscene `packages/core/src/agent/tasks.ts`）

```
while True:
    检查 stopped（execution_record.refresh_from_db）
    检查 actions_done >= max_steps -> 失败（带定位信息）
    截图
    规划调用（XML 输出，system prompt = PLANNING_SYSTEM_PROMPT）
    应用 memory / update-plan-content / mark-sub-goal-done / log 到历史
    若 <complete success="true|false"> 且无动作 -> 终止（双信号）
    若同时含动作与 <complete> -> 忽略 complete（与 Midscene 一致）
    无 action-type / <error> -> 错误反馈，重规划
    动作白名单校验 + pct→px 归一化
    交互动作（tap/long_press/swipe/input）两阶段 locate（默认开）
        定位失败 -> 重试 1 次 -> 降级直接坐标 -> 仍失败则错误反馈
    执行 + 效果验证（pHash 对比）
    卡死判定：同指纹（含 swipe 四坐标、input 文本）+ 页面未变
    成功 -> 反馈（截断 500）-> replan_count 重置
    错误 -> 反馈 -> replan_count/loop_errors 递增
    replanning_cycle_limit=3（连续失败重规划上限，成功重置）
    max_errors_per_loop=5（整轮累计错误上限，对齐 Midscene 累计语义）
    超限 -> 失败，错误含：最近规划输出、最近动作、已执行动作数、轮次
```

## 配置

- 复用用例已有 `max_steps`（默认 30）/ `action_delay`（默认 0.5），无迁移
- 用例级 `use_locate` 开关（默认开；当前无模型字段，走环境变量
  `AIACT_USE_LOCATE`，后续加字段无需迁移）
- 常量环境变量可覆盖：`AIACT_REPLANNING_CYCLE_LIMIT`（3）、
  `AIACT_MAX_ERRORS_PER_LOOP`（5）、`AIACT_FEEDBACK_TRUNCATE`（500）、
  `AIACT_STUCK_THRESHOLD`（2）、`AIACT_NO_PROGRESS_LIMIT`（3）
- 规划调用 `max_tokens=2048`（locate/逐行保持 1024），降低 XML 输出被截断概率
- 输出截断保护：XML 标签不完整（`is_truncated`）→ 不执行残缺动作，
  按错误反馈重规划
- 无进展保护：连续 `AIACT_NO_PROGRESS_LIMIT`（默认 3）个动作页面均无变化
  （含 wait/back）→ 错误反馈；触发后该动作不视为成功、不重置重规划计数，
  避免白屏/加载卡死时无限 wait 直到 max_steps
- 单次 `wait` 时长上限 10 秒（防模型输出超长等待拖死执行）

## 入口改动（`midscene_runner.py`）

- `run_midscene_test` auto_plan=True 时调用 `engine.run_ai_act` 并返回其结果；
  逐行模式（录制/三态回放/普通步骤）零逻辑改动
- 修复 P0：`app_package` 未定义（按平台取 `app_pkg`/`ios_bid`），
  "打开应用"快捷分支限定非 aiAct
- `call_vlm` 新增可选 `system_prompt` / `return_raw` 参数（旧调用兼容）
- `adb_input_text` 改为单引号全字符转义（对齐 Midscene `shellEscapeArg`）；
  非 ASCII / `%x` / `\` `` ` `` `$` / 同时含双单引号走 yadb：
  `adb push yadb /data/local/tmp` + `app_process -Djava.class.path=/data/local/tmp/yadb
  /data/local/tmp com.ysbing.yadb.Main -keyboard '...'`

## 返回结构与前端

- `{status, totalSteps, passedSteps, failedSteps, steps}`，steps 每动作一条
- 可选字段：`query_data`（query 结果）、`assert_passed`（断言结果）、
  `complete_message`（<complete> 消息）
- `progress_callback` 复用，每动作一次 `step_done`，截图逐动作落盘

## 测试

- 逐行回归（录制字段、三态回放、普通步骤、P0）——需在真机/既有流程回归
- 新引擎 mocked 36 例：XML 容错、complete 双终止、子目标推进、记忆跨步、
  错误反馈 replan、replan/错误超限失败定位、卡死不误杀/检测可恢复、
  query/assert 入 results、stopped、max_steps、locate 专项（越界重试/降级/
  use_locate=false）、yadb 与转义两条输入路径
- 真机冒烟：中文输入、多阶段目标（打开→登录→搜索→提取）、前端步骤明细

## 风险与备注

- yadb 二进制（zip 内含 classes.dex）随仓库分发；运行时缺失会自动尝试从
  GitHub Release v1.1.1 下载，仍失败则降级 `input text`（非 ASCII 可能无效）
- 规划截图与执行前截图可能相隔一次 VLM 调用时长（分钟级），页面变化判定
  为近似值；tap 已带轮内重试兜底
- `_ensure_yadb` 按设备缓存推送状态，重启进程后重新推送
