# -*- coding: utf-8 -*-
"""aiAct 主循环：规划 -> 定位 -> 执行 -> 反馈 -> 重规划。

对齐 Midscene 的 unified plan/replan loop：
- 每轮一次规划调用，模型输出 <complete> 或一个动作（互斥，同时出现时忽略
  complete，与 Midscene 一致）；
- 交互动作（tap/long_press/swipe/input）默认走两阶段 locate，可关闭；
- 执行结果/错误截断 500 字符回填到下一轮规划；
- 双信号终止：<complete success="true|false">；
- replanning_cycle_limit（默认 3）：连续未成功推进的重规划次数上限，
  成功执行一个动作后重置；超限失败。
- max_errors_per_loop（默认 5）：整轮执行中错误累计上限（对齐 Midscene
  errorCountInOnePlanningLoop 的累计语义），成功动作不重置；超限失败。
- 两个上限均可用环境变量 AIACT_REPLANNING_CYCLE_LIMIT /
  AIACT_MAX_ERRORS_PER_LOOP 覆盖；失败消息携带定位信息（最近规划输出、
  最近动作、已执行动作数与轮次）。
- 输出截断检测：XML 标签不完整视为错误反馈重规划，不执行残缺动作。
- 无进展检测：连续 no_progress_threshold（默认 3，AIACT_NO_PROGRESS_LIMIT）
  个动作页面均无变化（含 wait）时错误反馈，防止白屏/加载卡死无限等待。
"""

import os
import logging

from .protocol import parse_planning_response
from .conversation_history import ConversationHistory
from .prompts import PLANNING_SYSTEM_PROMPT, build_planning_user_prompt
from .actions import INTERACTIVE_ACTIONS, action_fingerprint, normalize_action
from .locate import resolve_action_coords
from .executor import execute_with_before, screenshot as _screenshot

logger = logging.getLogger(__name__)


def _env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_bool(name, default):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in ('1', 'true', 'yes', 'on')


def run_ai_act(goal, device_ctx, model_config, max_steps=30, action_delay=0.5,
               context='', progress_callback=None, execution_record=None,
               use_locate=True, replanning_cycle_limit=None,
               max_errors_per_loop=None, feedback_truncate=None,
               stuck_threshold=None, no_progress_threshold=None):
    """执行一个 aiAct 目标，返回与逐行模式一致的结果结构。

    参数：
      goal              用户目标文本
      device_ctx        {'platform','device_id','ios_dev','width','height'}
      model_config      AIModelConfig（走 call_vlm）
      max_steps         最大动作数（复用用例配置）
      action_delay      操作间隔秒数
      context           全局提示（ai_act_context）
      progress_callback 每动作回调一次 step_done
      execution_record  用于 stopped 轮询与截图落盘
      use_locate        两阶段定位开关，默认开
      其余常量可传参覆盖，未传时读环境变量，再取默认值。

    返回 {'status','totalSteps','passedSteps','failedSteps','steps'}，
    steps 每动作一条，含可选字段 query_data/assert_passed/complete_message。
    """
    from ..midscene_runner import call_vlm, png_size  # 延迟导入避免循环依赖

    width = int(device_ctx.get('width', 1080))
    height = int(device_ctx.get('height', 1920))
    ctx_text = context or ''

    replanning_cycle_limit = int(replanning_cycle_limit if replanning_cycle_limit is not None
                                 else _env_int('AIACT_REPLANNING_CYCLE_LIMIT', 3))
    max_errors_per_loop = int(max_errors_per_loop if max_errors_per_loop is not None
                              else _env_int('AIACT_MAX_ERRORS_PER_LOOP', 5))
    feedback_truncate = int(feedback_truncate if feedback_truncate is not None
                            else _env_int('AIACT_FEEDBACK_TRUNCATE', 500))
    stuck_threshold = int(stuck_threshold if stuck_threshold is not None
                          else _env_int('AIACT_STUCK_THRESHOLD', 2))
    no_progress_threshold = int(no_progress_threshold if no_progress_threshold is not None
                                else _env_int('AIACT_NO_PROGRESS_LIMIT', 3))
    if use_locate is None:
        use_locate = _env_bool('AIACT_USE_LOCATE', True)

    history = ConversationHistory(feedback_truncate=feedback_truncate)
    steps = []
    actions_done = 0
    replan_count = 0          # 连续未成功推进的重规划次数，成功动作后重置
    loop_errors = 0           # 整轮执行累计错误（对齐 Midscene）
    last_fp = None
    stuck_count = 0
    no_progress_count = 0
    stopped = False
    last_executed_action = ''

    def _build_planning_sys(w, h):
        sys_p = PLANNING_SYSTEM_PROMPT.replace('{width}', str(w)).replace('{height}', str(h))
        return sys_p.replace('{context}', f'全局提示: {ctx_text}' if ctx_text else '')

    def _is_stopped():
        nonlocal stopped
        if stopped:
            return True
        if execution_record is not None:
            try:
                execution_record.refresh_from_db()
                if getattr(execution_record, 'status', None) == 'stopped':
                    stopped = True
            except Exception:
                pass
        return stopped

    def _record_step(png, status, instruction, reasoning, action_type='', extra=None, error=''):
        url = ''
        if png is not None and execution_record is not None and getattr(execution_record, 'id', None):
            try:
                from ..midscene_runner import save_screenshot
                url = save_screenshot(png, execution_record.id, len(steps) + 1)
            except Exception as e:
                logger.warning(f'[Engine] 保存截图失败: {e}')
        entry = {
            'step': len(steps) + 1,
            'instruction': instruction,
            'status': status,
            'screenshot': url,
            'aiReasoning': list(reasoning),
            'action': action_type,
        }
        if error:
            entry['error'] = error
        if extra:
            entry.update(extra)
        steps.append(entry)
        if progress_callback is not None:
            try:
                total = max_steps or len(steps)
                progress_callback(len(steps), total, {
                    'type': 'step_done',
                    'step': len(steps),
                    'total': total,
                    'instruction': instruction,
                    'status': status,
                    'screenshot': url,
                    'aiReasoning': list(reasoning),
                    'action': action_type,
                    'error': error,
                    'progress': int(len(steps) / max(1, total) * 100),
                })
            except Exception as e:
                logger.warning(f'[Engine] progress_callback 异常: {e}')
        return entry

    def _fail(error_msg, png, raw='', action_hint=''):
        """失败路径：记录一个 failed 步骤，消息携带定位信息。"""
        detail = error_msg
        if action_hint:
            detail += f' | 最近动作: {action_hint}'
        if raw:
            detail += f' | 最近规划输出: {str(raw)[:200]}'
        detail += f' | 已执行动作数: {actions_done}, 重规划次数: {replan_count}, 累计错误数: {loop_errors}'
        _record_step(png, 'failed', goal, [f'[失败] {detail}'], 'failed', error=detail)
        return False

    def _plan_error(err_msg, raw, png):
        """错误反馈 -> 下一轮重规划；超限时失败并返回 False。"""
        nonlocal loop_errors, replan_count
        loop_errors += 1
        replan_count += 1
        history.set_feedback(f'错误: {err_msg}')
        logger.warning(f'[Engine] 第{replan_count}次重规划: {err_msg}')
        if replan_count > replanning_cycle_limit:
            return _fail(f'连续重规划超过 {replanning_cycle_limit} 次，任务失败', png, raw=raw,
                         action_hint=last_executed_action)
        if loop_errors > max_errors_per_loop:
            return _fail(f'整轮执行累计错误超过 {max_errors_per_loop} 次，任务失败', png, raw=raw,
                         action_hint=last_executed_action)
        return True

    while True:
        if _is_stopped():
            _record_step(None, 'stopped', goal, ['[停止] 用户已停止执行'], 'stopped')
            break

        if actions_done >= max_steps:
            _fail(f'达到最大执行步数上限({max_steps})，任务未完成', None,
                  action_hint=last_executed_action)
            break

        png = _screenshot(device_ctx)
        # 以当次截图实际尺寸为准（横竖屏切换/缩放差异都跟随真实像素）
        w, h = png_size(png) or (width, height)

        # ---- 规划 ----
        try:
            raw = call_vlm(
                png,
                build_planning_user_prompt(goal, history.snapshot_text()),
                model_config,
                width=w,
                height=h,
                context=ctx_text,
                system_prompt=_build_planning_sys(w, h),
                return_raw=True,
                max_tokens=2048,
            )
        except Exception as e:
            if not _plan_error(f'规划模型调用失败: {e}', '', png):
                break
            continue

        parsed = parse_planning_response(raw)
        # 输出截断：不执行残缺动作，反馈后重规划
        if parsed.truncated:
            err = f'规划输出不完整（疑似被截断）: {str(raw)[:120]}'
            if not _plan_error(err, raw, png):
                break
            continue
        history.clear_feedback()  # 本轮规划已消费上轮反馈
        if parsed.memory:
            history.add_memory(parsed.memory)
        if parsed.log:
            history.add_log(parsed.log)
        if parsed.update_sub_goals:
            history.merge_sub_goals(parsed.update_sub_goals)
        if parsed.mark_finished_indexes:
            history.mark_finished(parsed.mark_finished_indexes)

        thought = (parsed.planning or '').strip()
        log_text = (parsed.log or '').strip()
        instruction = log_text or goal
        reasoning = []
        if thought:
            reasoning.append(f'[规划] {thought[:300]}')
        if log_text:
            reasoning.append(f'[进度] {log_text[:200]}')

        # ---- 双信号终止 ----
        if parsed.complete is not None and not parsed.action_type:
            success = parsed.complete['success']
            message = parsed.complete.get('message', '') or ''
            status = 'passed' if success else 'failed'
            reasoning.append(f'[完成] {message or "任务结束"}')
            _record_step(png, status, message or goal, reasoning, 'complete',
                         extra={'complete_message': message})
            break

        if parsed.complete is not None:
            logger.warning('[Engine] 规划输出同时包含动作与 <complete>，忽略 complete 继续执行（对齐 Midscene）')

        if not parsed.action_type:
            err = f'规划模型报告错误: {parsed.error}' if parsed.error else '规划输出缺少 <action-type> 或 <complete>'
            if not _plan_error(err, raw, png):
                break
            continue

        # ---- 归一化动作 ----
        action = {'action': parsed.action_type, **dict(parsed.action_param or {})}
        ok, norm_action, norm_err = normalize_action(action, w, h)
        if not ok:
            if not _plan_error(norm_err, raw, png):
                break
            continue

        # ---- 两阶段定位 ----
        ok, norm_action, locate_err = resolve_action_coords(
            norm_action, png, model_config, w, h, ctx_text,
            use_locate=use_locate,
        )
        if not ok:
            if not _plan_error(locate_err, raw, png):
                break
            continue

        # ---- 执行 + 效果验证 ----
        try:
            after_png, info = execute_with_before(device_ctx, norm_action, png, action_delay)
            page_changed = info.get('page_changed')
            note = info.get('note', '')

            # 卡死判定：同指纹 + 页面未变（仅交互动作）
            if norm_action['action'] in INTERACTIVE_ACTIONS:
                fp = action_fingerprint(norm_action)
                if fp == last_fp and page_changed is False:
                    stuck_count += 1
                else:
                    stuck_count = 0
                last_fp = fp
                if stuck_count >= stuck_threshold:
                    err = f'连续{stuck_count + 1}次相同动作({norm_action["action"]})且页面未变化，疑似卡死'
                    if not _plan_error(err, raw, png):
                        break
                    continue
            else:
                last_fp = None
                stuck_count = 0

            # 断言失败：记录失败步骤并反馈，让模型决定是否 complete success=false
            if norm_action['action'] == 'assert' and not norm_action.get('passed', True):
                desc = norm_action.get('description', '断言')
                _record_step(after_png, 'failed', instruction,
                             reasoning + [f'[断言失败] {desc}'], 'assert',
                             extra={'assert_passed': False}, error=f'断言失败: {desc}')
                if not _plan_error(f'断言失败: {desc}', raw, after_png):
                    break
                continue

            # 无进展判定（在成功记账之前：触发错误时该动作不视为成功，
            # 不重置 replan_count，让 replan/error 上限尽快兜底）
            if page_changed is False:
                no_progress_count += 1
                if no_progress_count >= no_progress_threshold:
                    err = (f'连续{no_progress_threshold}个动作页面均无变化'
                           f'（最近动作: {norm_action["action"]}），疑似加载卡死或元素不可达')
                    if not _plan_error(err, raw, after_png):
                        break
                    continue
            elif page_changed is True:
                no_progress_count = 0

            # 成功推进：组装反馈
            feedback = f'动作 {norm_action["action"]} 已执行完成'
            if norm_action['action'] == 'query':
                qd = norm_action.get('data', '')
                feedback += f'，提取结果: {str(qd)[:200]}'
            if page_changed is not None:
                feedback += f'，页面变化: {"是" if page_changed else "否"}'
            if note:
                feedback += f'，{note}'
            history.set_feedback(feedback)
            replan_count = 0
            actions_done += 1
            last_executed_action = action_fingerprint(norm_action)

            extra = {}
            if norm_action['action'] == 'assert':
                extra['assert_passed'] = True
            elif norm_action['action'] == 'query':
                extra['query_data'] = norm_action.get('data', norm_action.get('description', ''))
            _record_step(after_png, 'passed', instruction,
                         reasoning + [f'[执行] {feedback[:200]}'],
                         norm_action['action'], extra=extra)
        except Exception as e:
            logger.error(f'[Engine] 动作执行异常: {e}')
            if not _plan_error(f'动作执行失败: {e}', raw, png):
                break
            continue

    # ---- 汇总 ----
    passed = sum(1 for s in steps if s['status'] == 'passed')
    failed = sum(1 for s in steps if s['status'] == 'failed')
    if stopped:
        status = 'stopped'
    elif failed == 0:
        status = 'passed'
    else:
        status = 'failed'
    logger.info(f'[Engine] aiAct 执行完成: {passed}/{len(steps)} 通过, status={status}')
    return {
        'status': status,
        'totalSteps': len(steps),
        'passedSteps': passed,
        'failedSteps': failed,
        'steps': steps,
    }
