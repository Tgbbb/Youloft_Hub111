# -*- coding: utf-8 -*-
"""
Midscene AI 移动端自动化 - Celery 异步任务
纯 Python Runner，不依赖 Node.js Sidecar
"""
import logging
import platform as sys_platform
import subprocess
import time
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)

from .midscene_runner import run_midscene_test

_SUBPROCESS_KWARGS = {}
if sys_platform.system() == 'Windows':
    _SUBPROCESS_KWARGS['creationflags'] = subprocess.CREATE_NO_WINDOW


def run_apk_install(pkg, device, options=None):
    """同步执行 adb install（供安装任务与执行前装包复用）。
    返回 (ok, log, error)；不更新安装记录、不锁定设备，由调用方负责。"""
    def _run(cmd, timeout=600):
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                              encoding='utf-8', errors='replace', **_SUBPROCESS_KWARGS)

    path = pkg.file.path
    opts = options or {}
    cmd = ['adb', '-s', device.adb_serial, 'install']
    if opts.get('overwrite', True):
        cmd.append('-r')
    if opts.get('downgrade'):
        cmd.append('-d')
    cmd.append(path)

    r = _run(cmd)
    log = (r.stdout + r.stderr).strip()
    if r.returncode == 0:
        if opts.get('launch') and pkg.package_name:
            try:
                _run(['adb', '-s', device.adb_serial, 'shell', 'monkey',
                      '-p', pkg.package_name, '-c', 'android.intent.category.LAUNCHER', '1'],
                     timeout=60)
            except Exception as e:
                log += f'\n[安装后启动失败] {e}'
        return True, log, ''
    return False, log, log[-500:]


def run_ipa_install(pkg, device, options=None):
    """同步执行 tidevice install（iOS 覆盖安装，同一 bundle 覆盖升级保留沙盒数据）。
    返回 (ok, log, error)；不更新安装记录、不锁定设备，由调用方负责。"""
    def _run(cmd, timeout=600):
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                              encoding='utf-8', errors='replace', **_SUBPROCESS_KWARGS)

    path = pkg.file.path
    opts = options or {}
    udid = (getattr(device, 'tidevice_udid', '') or '').strip() or (device.device_id or '')
    cmd = ['tidevice']
    if udid:
        cmd += ['-u', udid]
    cmd += ['install']
    if opts.get('launch'):
        cmd.append('-L')
    cmd.append(path)

    r = _run(cmd)
    log = (r.stdout + r.stderr).strip()
    if r.returncode == 0:
        return True, log, ''
    return False, log, log[-500:]


def run_package_install(pkg, device, options=None):
    """按设备平台分发安装（Android adb install / iOS tidevice install）。
    返回 (ok, log, error)；不更新安装记录、不锁定设备，由调用方负责。"""
    if getattr(device, 'platform', '') == 'ios':
        return run_ipa_install(pkg, device, options)
    return run_apk_install(pkg, device, options)

def _append_replay_entry(midscene_case, entry, result):
    """把本次录制写入用例 replay_data：新条目插队首，不限制条数，自动命名。
    返回保存后的总条数。"""
    passed = result.get('passedSteps', 0)
    failed = result.get('failedSteps', 0)
    total = result.get('totalSteps', 0)
    # 命名带设备名：多设备同时录制时互不混淆（缺失设备名则不加后缀）
    dev = entry.get('device') or {}
    device_name = str(dev.get('name', '') or '').strip()
    name_suffix = f' [{device_name}]' if device_name else ''
    entry.setdefault('name', f"录制 {timezone.now().strftime('%m-%d %H:%M')}{name_suffix}")
    entry['result'] = f'{passed}/{total} 通过' + (f'，{failed} 失败' if failed else '')
    existing = midscene_case.replay_data
    if isinstance(existing, dict):
        existing = [existing]
    elif not isinstance(existing, list):
        existing = []
    existing.insert(0, entry)
    midscene_case.replay_data = existing
    midscene_case.save(update_fields=['replay_data'])
    return len(existing)


def _send_progress_update(execution_id, status, progress, message=''):
    """通过 Django Channels 推送进度到前端"""
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f'midscene_execution_{execution_id}',
                {
                    'type': 'execution_update',
                    'execution_id': execution_id,
                    'status': status,
                    'progress': progress,
                    'message': message,
                }
            )
    except Exception as e:
        logger.debug(f'WebSocket 推送跳过: {e}')


def _send_progress_update_run(run_id, status, progress, message=''):
    """推送编排运行进度到前端（组名 midscene_sequence_run_{id}）。"""
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f'midscene_sequence_run_{run_id}',
                {
                    'type': 'execution_update',
                    'run_id': run_id,
                    'status': status,
                    'progress': progress,
                    'message': message,
                }
            )
    except Exception as e:
        logger.debug(f'WebSocket 推送(编排)跳过: {e}')


@shared_task(bind=True, max_retries=0)
def execute_midscene_task(self, execution_id, record_mode=False, replay_mode=False,
                          replay_index=0, clear_app_data=False, install_package_id=None,
                          script_replay=False):
    """
    异步执行 Midscene 测试任务（纯 Python Runner）。
    """
    from .models import MidsceneExecutionRecord

    execution = None
    device = None

    try:
        execution = MidsceneExecutionRecord.objects.get(id=execution_id)
        midscene_case = execution.midscene_case

        if execution.status in ('stopped', 'stopping'):
            if execution.status == 'stopping':
                # 启动前已被请求停止：worker 确认收尾
                execution.status = 'stopped'
                execution.finished_at = timezone.now()
                execution.save(update_fields=['status', 'finished_at'])
            logger.info(f'[Task] 执行记录 {execution_id} 已在启动前被停止，跳过执行')
            return 'stopped'

        if not midscene_case:
            raise ValueError('执行记录没有关联的测试用例')

        device = execution.device
        if not device:
            raise ValueError('没有选择执行设备')

        model_config = midscene_case.ai_model_config
        if not script_replay and (not model_config or not model_config.api_key):
            raise ValueError('未配置 AI 模型或 API Key')

        # 锁定设备
        device.lock(execution.executed_by)

        # 更新状态
        execution.status = 'running'
        execution.started_at = timezone.now()
        execution.save(update_fields=['status', 'started_at'])

        _send_progress_update(execution.id, 'running', 5, '开始执行...')

        # ---- 执行前安装：选了安装包则覆盖安装（Android/iOS），失败则整个执行失败 ----
        app_package_override = ''
        if install_package_id:
            from .models import MidsceneAppPackage
            install_pkg = MidsceneAppPackage.objects.filter(id=install_package_id).first()
            if not install_pkg:
                raise ValueError('安装包不存在或已被删除')
            _send_progress_update(execution.id, 'running', 5,
                                  f'安装 {install_pkg.name or install_pkg.package_name}...')
            logger.info(f'[Task] 执行前安装: {install_pkg.name or install_pkg.package_name} -> {device.device_id}')
            ok, log, err = run_package_install(install_pkg, device, {'overwrite': True})
            if not ok:
                logger.error(f'[Task] 执行前安装失败(记录 {execution_id}): {err}')
                raise ValueError(f'安装包安装失败: {err}')
            logger.info(f'[Task] 安装完成: {install_pkg.name or install_pkg.package_name} '
                        f'({install_pkg.package_name})')
            app_package_override = install_pkg.package_name or ''
            clear_app_data = True  # 单用例选了包强制清数据

        # 进度回调
        def on_progress(step, total, data):
            msg_type = data.get('type', '')
            if msg_type == 'step_start':
                execution.refresh_from_db()
                execution.progress = data.get('progress', 0)
                execution.save(update_fields=['progress'])
                _send_progress_update(
                    execution.id, 'running', data.get('progress', 0),
                    f"步骤 {step}/{total}: {data.get('instruction', '')}"
                )
            elif msg_type == 'step_done':
                execution.refresh_from_db()
                execution.progress = data.get('progress', 0)
                execution.steps_detail = execution.steps_detail or []
                execution.steps_detail.append({
                    'step': step,
                    'instruction': data.get('instruction', ''),
                    'status': data.get('status', 'failed'),
                    'screenshot': data.get('screenshot', ''),
                    'aiReasoning': data.get('aiReasoning', []),
                    'error': data.get('error', ''),
                    'action': data.get('action', ''),
                    'anomalies': data.get('anomalies', []),
                    'query_data': data.get('query_data', ''),
                    'assert_passed': data.get('assert_passed'),
                    'complete_message': data.get('complete_message', ''),
                })
                execution.passed_steps = sum(
                    1 for s in execution.steps_detail if s['status'] == 'passed'
                )
                execution.failed_steps = sum(
                    1 for s in execution.steps_detail if s['status'] == 'failed'
                )
                execution.save()

        # ---- 执行 ----
        result = run_midscene_test(
            ai_prompt=midscene_case.ai_prompt,
            device=device,
            model_config=model_config,
            execution_record=execution,
            progress_callback=on_progress,
            record_mode=record_mode,
            replay_mode=replay_mode,
            replay_index=replay_index,
            clear_app_data=clear_app_data,
            app_package_override=app_package_override,
            script_replay=script_replay,
        )

        # ---- 保存结果 ----
        execution.refresh_from_db()
        if result['status'] == 'stopped':
            # 用户手动停止：worker 检测到 stopping 后确认收尾为 stopped
            execution.status = 'stopped'
        else:
            # 正常完成；若停止请求与任务收尾竞态，以实际执行结果为准
            execution.status = result['status']
        execution.finished_at = timezone.now()
        if execution.started_at:
            execution.duration = (execution.finished_at - execution.started_at).total_seconds()
        execution.progress = 100
        execution.total_steps = result['totalSteps']
        execution.passed_steps = result['passedSteps']
        execution.failed_steps = result['failedSteps']
        # 保存完整步骤详情（包含失败步骤的错误信息）
        execution.steps_detail = result.get('steps', [])
        execution.save()

        # ---- 录制: 无论通过/失败/停止都保留本次录制，不限制条数 ----
        if record_mode and result.get('replay_data'):
            midscene_case.refresh_from_db()
            entry = result['replay_data']
            count = _append_replay_entry(midscene_case, entry, result)
            logger.info(f'[Task] 回放数据已保存到用例 {midscene_case.id}（共{count}条）')

        if result['status'] == 'stopped':
            _send_progress_update(execution.id, 'stopped', execution.progress or 0, '用户已停止执行')
        else:
            _send_progress_update(
                execution.id, result['status'], 100,
                f"执行完成: {result['passedSteps']}/{result['totalSteps']} 通过"
            )

    except Exception as e:
        logger.error(f'Midscene 执行失败: {e}', exc_info=True)
        if execution:
            execution.refresh_from_db()
            execution.status = 'error'
            execution.finished_at = timezone.now()
            execution.error_message = str(e)
            if execution.started_at:
                execution.duration = (execution.finished_at - execution.started_at).total_seconds()
            execution.save()
            _send_progress_update(execution.id, 'error', execution.progress or 0, f'执行异常: {e}')

    finally:
        if device:
            try:
                device.refresh_from_db()
                device.unlock()
            except Exception as e:
                logger.error(f'解锁设备失败: {e}')

    return execution.status if execution else 'error'


@shared_task(bind=True, max_retries=0)
def rerun_step_task(self, execution_id, replay_index, step_index):
    """单步重录：在用户手动准备好的页面上只录制目标步骤，并写回对应回放脚本。

    不启动/不清理应用（skip_launch=True），尊重用户手动准备的页面状态；
    只执行目标步骤的录制循环，其余步骤仅标记 skipped；成功后仅替换该步录制数据。
    """
    from .models import MidsceneExecutionRecord

    execution = None
    device = None
    try:
        execution = MidsceneExecutionRecord.objects.get(id=execution_id)
        midscene_case = execution.midscene_case
        if not midscene_case:
            raise ValueError('执行记录没有关联的测试用例')
        if execution.status in ('stopped', 'stopping'):
            if execution.status == 'stopping':
                execution.status = 'stopped'
                execution.finished_at = timezone.now()
                execution.save(update_fields=['status', 'finished_at'])
            logger.info(f'[Task] 单步重录执行 {execution_id} 已在启动前被停止，跳过')
            return 'stopped'
        device = execution.device
        if not device:
            raise ValueError('没有选择执行设备')
        model_config = midscene_case.ai_model_config
        if not model_config or not model_config.api_key:
            raise ValueError('未配置 AI 模型或 API Key')

        device.lock(execution.executed_by)
        execution.status = 'running'
        execution.started_at = timezone.now()
        execution.save(update_fields=['status', 'started_at'])
        _send_progress_update(execution.id, 'running', 0,
                              f'单步重录：步骤 {step_index + 1}（请保持设备处于该步执行前页面）')

        def on_progress(step, total, data):
            msg_type = data.get('type', '')
            if msg_type == 'step_start':
                execution.refresh_from_db()
                execution.progress = data.get('progress', 0)
                execution.save(update_fields=['progress'])
                _send_progress_update(execution.id, 'running', data.get('progress', 0),
                                      f"步骤 {step}/{total}: {data.get('instruction', '')}")
            elif msg_type == 'step_done':
                execution.refresh_from_db()
                execution.progress = data.get('progress', 0)
                execution.steps_detail = execution.steps_detail or []
                execution.steps_detail.append({
                    'step': step,
                    'instruction': data.get('instruction', ''),
                    'status': data.get('status', 'failed'),
                    'screenshot': data.get('screenshot', ''),
                    'aiReasoning': data.get('aiReasoning', []),
                    'error': data.get('error', ''),
                    'action': data.get('action', ''),
                    'anomalies': data.get('anomalies', []),
                    'query_data': data.get('query_data', ''),
                    'assert_passed': data.get('assert_passed'),
                    'complete_message': data.get('complete_message', ''),
                })
                execution.passed_steps = sum(
                    1 for s in execution.steps_detail if s['status'] == 'passed')
                execution.failed_steps = sum(
                    1 for s in execution.steps_detail if s['status'] == 'failed')
                execution.save()
                _send_progress_update(execution.id, 'running', data.get('progress', 0),
                                      f"步骤 {step}/{total}: {data.get('instruction', '')}")

        result = run_midscene_test(
            ai_prompt=midscene_case.ai_prompt, device=device, model_config=model_config,
            execution_record=execution, progress_callback=on_progress,
            record_mode=True, replay_mode=False, clear_app_data=False,
            skip_launch=True, rerun_step=step_index,
        )

        # 取目标步骤的录制结果，仅替换该步，其余步骤/名称/设备信息不动
        rec_data = None
        if result.get('replay_data'):
            rec_steps = result['replay_data'].get('steps') or []
            if 0 <= step_index < len(rec_steps):
                rec_data = rec_steps[step_index]
        wrote_back = False
        if rec_data is not None:
            midscene_case.refresh_from_db()
            raw = midscene_case.replay_data
            if isinstance(raw, dict):
                raw = [raw]
            if isinstance(raw, list) and 0 <= replay_index < len(raw):
                entry = raw[replay_index]
                if isinstance(entry, dict) and isinstance(entry.get('steps'), list) \
                        and 0 <= step_index < len(entry['steps']):
                    entry['steps'][step_index] = rec_data
                    midscene_case.replay_data = raw
                    midscene_case.save(update_fields=['replay_data'])
                    wrote_back = True
        if not wrote_back:
            raise ValueError('重录目标脚本不存在或已被删除，未写回')

        execution.refresh_from_db()
        execution.status = result['status']
        execution.progress = 100
        execution.total_steps = result['totalSteps']
        execution.passed_steps = result['passedSteps']
        execution.failed_steps = result['failedSteps']
        execution.steps_detail = result.get('steps', [])
        execution.finished_at = timezone.now()
        if execution.started_at:
            execution.duration = (execution.finished_at - execution.started_at).total_seconds()
        execution.save()
        _send_progress_update(execution.id, result['status'], 100,
                              f"重录完成: {result['passedSteps']}/{result['totalSteps']} 通过")
    except Exception as e:
        logger.error(f'[Task] 单步重录失败(记录 {execution_id}): {e}', exc_info=True)
        if execution:
            execution.refresh_from_db()
            execution.status = 'error'
            execution.error_message = str(e)[-2000:]
            execution.finished_at = timezone.now()
            if execution.started_at:
                execution.duration = (execution.finished_at - execution.started_at).total_seconds()
            execution.save()
            _send_progress_update(execution.id, 'error', execution.progress or 0, f'单步重录异常: {e}')
    finally:
        if device:
            try:
                device.refresh_from_db()
                device.unlock()
            except Exception as e:
                logger.error(f'[Task] 解锁设备失败: {e}')

    return execution.status if execution else 'error'


@shared_task(bind=True, max_retries=0)
def rerun_else_task(self, execution_id, replay_index, branch_step_index):
    """整组补录 else：在 else 态(条件不满足)页面上只重录分支头 else 槽 + 该分支 else 组子步骤。

    不启动/不清理应用（skip_launch=True），尊重用户手动准备的 else 态页面；
    成功后仅合并写回该分支的 else_* 槽与 else 组叶子步骤，if 槽与其他步骤保持不变。
    """
    from .models import MidsceneExecutionRecord

    execution = None
    device = None
    try:
        execution = MidsceneExecutionRecord.objects.get(id=execution_id)
        midscene_case = execution.midscene_case
        if not midscene_case:
            raise ValueError('执行记录没有关联的测试用例')
        if execution.status in ('stopped', 'stopping'):
            if execution.status == 'stopping':
                execution.status = 'stopped'
                execution.finished_at = timezone.now()
                execution.save(update_fields=['status', 'finished_at'])
            logger.info(f'[Task] 补录else执行 {execution_id} 已在启动前被停止，跳过')
            return 'stopped'
        device = execution.device
        if not device:
            raise ValueError('没有选择执行设备')
        model_config = midscene_case.ai_model_config
        if not model_config or not model_config.api_key:
            raise ValueError('未配置 AI 模型或 API Key')

        # 解析分支头与其 else 组下标，用于写回合并范围
        from .midscene_runner import parse_ai_prompt
        steps = parse_ai_prompt(midscene_case.ai_prompt)
        if branch_step_index < 0 or branch_step_index >= len(steps):
            raise ValueError('分支头步骤越界')
        head = steps[branch_step_index]
        if head.get('type') != 'branch':
            raise ValueError('目标步骤不是分支头')
        else_indices = head.get('else_children', [])
        if not else_indices:
            raise ValueError('该分支没有 else 组子步骤')

        device.lock(execution.executed_by)
        execution.status = 'running'
        execution.started_at = timezone.now()
        execution.save(update_fields=['status', 'started_at'])
        _send_progress_update(execution.id, 'running', 0,
                              f'补录else：步骤 {branch_step_index + 1}（请保持设备处于else态页面）')

        def on_progress(step, total, data):
            msg_type = data.get('type', '')
            if msg_type == 'step_start':
                execution.refresh_from_db()
                execution.progress = data.get('progress', 0)
                execution.save(update_fields=['progress'])
                _send_progress_update(execution.id, 'running', data.get('progress', 0),
                                      f"步骤 {step}/{total}: {data.get('instruction', '')}")
            elif msg_type == 'step_done':
                execution.refresh_from_db()
                execution.progress = data.get('progress', 0)
                execution.steps_detail = execution.steps_detail or []
                execution.steps_detail.append({
                    'step': step,
                    'instruction': data.get('instruction', ''),
                    'status': data.get('status', 'failed'),
                    'screenshot': data.get('screenshot', ''),
                    'aiReasoning': data.get('aiReasoning', []),
                    'error': data.get('error', ''),
                    'action': data.get('action', ''),
                    'anomalies': data.get('anomalies', []),
                    'query_data': data.get('query_data', ''),
                    'assert_passed': data.get('assert_passed'),
                    'complete_message': data.get('complete_message', ''),
                })
                execution.passed_steps = sum(
                    1 for s in execution.steps_detail if s['status'] == 'passed')
                execution.failed_steps = sum(
                    1 for s in execution.steps_detail if s['status'] == 'failed')
                execution.save()
                _send_progress_update(execution.id, 'running', data.get('progress', 0),
                                      f"步骤 {step}/{total}: {data.get('instruction', '')}")

        result = run_midscene_test(
            ai_prompt=midscene_case.ai_prompt, device=device, model_config=model_config,
            execution_record=execution, progress_callback=on_progress,
            record_mode=True, replay_mode=False, clear_app_data=False,
            skip_launch=True, rerun_else_slot=branch_step_index,
        )

        # 取分支头 else 槽 + else 组子步骤录制结果，合并写回（保留 if 槽与其他步骤）
        rec_steps = (result.get('replay_data') or {}).get('steps') or []
        head_rec = rec_steps[branch_step_index] if 0 <= branch_step_index < len(rec_steps) else None
        else_leaf_recs = {}
        for ci in else_indices:
            if 0 <= ci < len(rec_steps) and rec_steps[ci] is not None:
                else_leaf_recs[ci] = rec_steps[ci]
        wrote_back = False
        if head_rec is not None and isinstance(head_rec, dict):
            midscene_case.refresh_from_db()
            raw = midscene_case.replay_data
            entries = raw if isinstance(raw, list) else ([raw] if isinstance(raw, dict) else [])
            if isinstance(raw, dict):
                raw = [raw]
            if isinstance(raw, list) and 0 <= replay_index < len(raw):
                entry = raw[replay_index]
                if isinstance(entry, dict) and isinstance(entry.get('steps'), list) \
                        and 0 <= branch_step_index < len(entry['steps']):
                    existing_head = entry['steps'][branch_step_index]
                    if isinstance(existing_head, dict):
                        # 合并：只更新 else_* 槽，保留 if 槽（branch_entered/act_before_hash/after_hash）
                        for k in ('else_entered', 'else_act_before_hash', 'else_after_hash'):
                            if k in head_rec:
                                existing_head[k] = head_rec[k]
                        existing_head.setdefault('else_entered', False)
                        entry['steps'][branch_step_index] = existing_head
                    # 替换 else 组子步骤录制数据（仅存在的 item）
                    for ci, leaf in else_leaf_recs.items():
                        if 0 <= ci < len(entry['steps']):
                            entry['steps'][ci] = leaf
                    midscene_case.replay_data = raw
                    midscene_case.save(update_fields=['replay_data'])
                    wrote_back = True
        if not wrote_back:
            raise ValueError('补录目标脚本不存在或已被删除，未写回')

        execution.refresh_from_db()
        execution.status = result['status']
        execution.progress = 100
        execution.total_steps = result['totalSteps']
        execution.passed_steps = result['passedSteps']
        execution.failed_steps = result['failedSteps']
        execution.steps_detail = result.get('steps', [])
        execution.finished_at = timezone.now()
        if execution.started_at:
            execution.duration = (execution.finished_at - execution.started_at).total_seconds()
        execution.save()
        _send_progress_update(execution.id, result['status'], 100,
                              f"补录else完成: {result['passedSteps']}/{result['totalSteps']} 通过")
    except Exception as e:
        logger.error(f'[Task] 补录else失败(记录 {execution_id}): {e}', exc_info=True)
        if execution:
            execution.refresh_from_db()
            execution.status = 'error'
            execution.error_message = str(e)[-2000:]
            execution.finished_at = timezone.now()
            if execution.started_at:
                execution.duration = (execution.finished_at - execution.started_at).total_seconds()
            execution.save()
            _send_progress_update(execution.id, 'error', execution.progress or 0, f'补录else异常: {e}')
    finally:
        if device:
            try:
                device.refresh_from_db()
                device.unlock()
            except Exception as e:
                logger.error(f'[Task] 解锁设备失败: {e}')

    return execution.status if execution else 'error'


def _resolve_replay_index(device, item):
    """编排项回放索引：fixed 用 item.replay_index；auto 按执行设备挑最匹配录制，无匹配回退最新。"""
    if item.replay_mode == 'fixed':
        return item.replay_index
    existing = item.case.replay_data
    if isinstance(existing, dict):
        existing = [existing]
    if existing:
        try:
            # 延迟导入避免与 views 循环依赖
            from .views_midscene import _pick_best_replay
            pick = _pick_best_replay(device, existing)
            if pick and pick.get('recommended_index') is not None:
                return pick['recommended_index']
        except Exception as e:
            logger.warning(f'[Task] 编排项回放匹配失败({e})，回退最新录制')
    return item.replay_index


@shared_task(bind=True, max_retries=0)
def execute_midscene_sequence_task(self, run_id, install_package_id=None):
    """顺序执行一条用例编排：每项复用 run_midscene_test，串行推进并复用设备状态。"""
    from .models import (MidsceneSequenceRun, MidsceneExecutionRecord, MidsceneAppPackage)
    from .midscene_runner import run_midscene_test, parse_ai_prompt

    run = None
    device = None
    try:
        run = MidsceneSequenceRun.objects.select_related('sequence', 'device').get(id=run_id)
        sequence = run.sequence
        device = run.device
        if not device:
            raise ValueError('没有选择执行设备')
        items = list(sequence.items.select_related('case').order_by('order'))
        if not items:
            raise ValueError('编排没有用例')

        if run.status in ('stopped', 'stopping'):
            if run.status == 'stopping':
                run.status = 'stopped'
                run.finished_at = timezone.now()
                run.save(update_fields=['status', 'finished_at'])
            logger.info(f'[Task] 编排运行 {run_id} 已在启动前被停止，跳过')
            return 'stopped'

        device.lock(run.executed_by)
        run.status = 'running'
        run.started_at = timezone.now()
        run.save(update_fields=['status', 'started_at'])
        _send_progress_update_run(run.id, 'running', 5, '开始执行...')

        # 链级 install_package_id 作为首项未指定包时的默认包，在循环内按项处理

        n_items = len(items)
        done_items = 0
        run_total_steps = run.total_steps or sum(
            len(parse_ai_prompt(it.case.ai_prompt)) for it in items)
        any_failed = False

        def _update_run_progress():
            run.refresh_from_db()
            run.progress = int(done_items / n_items * 100) if n_items else 100
            run.save(update_fields=['progress'])

        for idx, it in enumerate(items):
            run.refresh_from_db()
            if run.status in ('stopping', 'stopped'):
                if run.status == 'stopping':
                    run.status = 'stopped'
                    run.finished_at = timezone.now()
                    run.save(update_fields=['status', 'finished_at'])
                logger.info(f'[Task] 编排在项 {idx + 1} 前停止')
                return 'stopped'

            case = it.case
            child = None
            try:
                child = MidsceneExecutionRecord.objects.create(
                    midscene_case=case, case_name=case.name, device=device,
                    platform=device.platform, status='running', auto_plan=False,
                    total_steps=len(parse_ai_prompt(case.ai_prompt)),
                    executed_by=run.executed_by, sequence_run=run,
                    started_at=timezone.now(),
                )
                replay_index = _resolve_replay_index(device, it)
                model_config = case.ai_model_config
                if not model_config or not model_config.api_key:
                    raise ValueError('未配置 AI 模型或 API Key')
                # 项级安装包：有包则覆盖安装并启动；无包沿用 clear_relaunch 决定清/启
                item_pkg = None
                if it.install_package_id:
                    item_pkg = MidsceneAppPackage.objects.filter(id=it.install_package_id).first()
                    if not item_pkg:
                        raise ValueError(f'编排项 {idx + 1} 的安装包不存在或已被删除')
                elif idx == 0 and install_package_id:
                    item_pkg = MidsceneAppPackage.objects.filter(id=install_package_id).first()
                    if not item_pkg:
                        raise ValueError('安装包不存在或已被删除')

                app_package_override = ''
                if item_pkg:
                    _send_progress_update_run(run.id, 'running', 5,
                                              f'安装 {item_pkg.name or item_pkg.package_name}...')
                    ok, log, err = run_package_install(item_pkg, device, {'overwrite': True})
                    if not ok:
                        raise ValueError(f'安装包安装失败: {err}')
                    app_package_override = item_pkg.package_name or ''
                    clear_app_data = bool(it.clear_relaunch)
                    skip_launch = False  # 装完要启动新包
                else:
                    clear_app_data = bool(it.clear_relaunch)
                    skip_launch = not it.clear_relaunch

                def on_progress(step, total_s, data):
                    msg_type = data.get('type', '')
                    if msg_type == 'step_start':
                        child.refresh_from_db()
                        child.progress = data.get('progress', 0)
                        child.save(update_fields=['progress'])
                        _send_progress_update(child.id, 'running', data.get('progress', 0),
                                              f"步骤 {step}/{total_s}: {data.get('instruction', '')}")
                    elif msg_type == 'step_done':
                        child.refresh_from_db()
                        child.progress = data.get('progress', 0)
                        child.steps_detail = child.steps_detail or []
                        child.steps_detail.append({
                            'step': step,
                            'instruction': data.get('instruction', ''),
                            'status': data.get('status', 'failed'),
                            'screenshot': data.get('screenshot', ''),
                            'aiReasoning': data.get('aiReasoning', []),
                            'error': data.get('error', ''),
                            'action': data.get('action', ''),
                            'anomalies': data.get('anomalies', []),
                            'query_data': data.get('query_data', ''),
                            'assert_passed': data.get('assert_passed'),
                            'complete_message': data.get('complete_message', ''),
                        })
                        child.passed_steps = sum(
                            1 for s in child.steps_detail if s['status'] == 'passed')
                        child.failed_steps = sum(
                            1 for s in child.steps_detail if s['status'] == 'failed')
                        child.save()
                        _send_progress_update(child.id, 'running', data.get('progress', 0),
                                              f"步骤 {step}/{total_s}: {data.get('instruction', '')}")

                result = run_midscene_test(
                    ai_prompt=case.ai_prompt, device=device, model_config=model_config,
                    execution_record=child, progress_callback=on_progress,
                    record_mode=False, replay_mode=True, replay_index=replay_index,
                    clear_app_data=clear_app_data, app_package_override=app_package_override,
                    skip_launch=skip_launch,
                )
                # 与单用例执行一致：把 runner 返回的结果状态写回子执行记录
                if result:
                    child.refresh_from_db()
                    child.status = result.get('status', child.status)
                    child.total_steps = result.get('totalSteps', child.total_steps)
                    child.passed_steps = result.get('passedSteps', child.passed_steps)
                    child.failed_steps = result.get('failedSteps', child.failed_steps)
                    if result.get('steps'):
                        child.steps_detail = result['steps']
                    child.save()
            except Exception as e:
                logger.error(f'[Task] 编排项 {idx + 1} 执行失败: {e}', exc_info=True)
                if child:
                    child.refresh_from_db()
                    child.status = 'error'
                    child.error_message = str(e)
                    child.finished_at = timezone.now()
                    if child.started_at:
                        child.duration = (child.finished_at - child.started_at).total_seconds()
                    child.save()
                result = {'status': 'error', 'totalSteps': 0, 'passedSteps': 0,
                          'failedSteps': 0, 'steps': []}

            child.refresh_from_db()
            child.finished_at = timezone.now()
            if child.started_at:
                child.duration = (child.finished_at - child.started_at).total_seconds()
            child.save(update_fields=['status', 'finished_at', 'duration'])
            done_items += 1
            _update_run_progress()

            status = child.status
            # 停止：无论如何都中止，剩余项标 skipped
            if status == 'stopped':
                for j in range(idx + 1, n_items):
                    it2 = items[j]
                    MidsceneExecutionRecord.objects.create(
                        midscene_case=it2.case, case_name=it2.case.name, device=device,
                        platform=device.platform, status='skipped', auto_plan=False,
                        total_steps=len(parse_ai_prompt(it2.case.ai_prompt)),
                        executed_by=run.executed_by, sequence_run=run,
                        started_at=timezone.now(), finished_at=timezone.now(),
                    )
                run.refresh_from_db()
                run.status = 'stopped'
                run.finished_at = timezone.now()
                run.save(update_fields=['status', 'finished_at'])
                break
            if status != 'passed':
                any_failed = True
                # break_on_fail 且非停止：中止并把剩余项标 skipped
                if it.break_on_fail:
                    for j in range(idx + 1, n_items):
                        it2 = items[j]
                        MidsceneExecutionRecord.objects.create(
                            midscene_case=it2.case, case_name=it2.case.name, device=device,
                            platform=device.platform, status='skipped', auto_plan=False,
                            total_steps=len(parse_ai_prompt(it2.case.ai_prompt)),
                            executed_by=run.executed_by, sequence_run=run,
                            started_at=timezone.now(), finished_at=timezone.now(),
                        )
                    run.refresh_from_db()
                    run.status = 'failed'
                    run.finished_at = timezone.now()
                    run.save(update_fields=['status', 'finished_at'])
                    break
                # break_on_fail=False：继续下一项
        else:
            run.refresh_from_db()
            run.status = 'passed' if not any_failed else 'failed'
            run.finished_at = timezone.now()
            run.save(update_fields=['status', 'finished_at'])

        run.refresh_from_db()
        childs = MidsceneExecutionRecord.objects.filter(sequence_run=run)
        run.total_steps = sum(c.total_steps for c in childs if c.status != 'skipped')
        run.passed_steps = sum(c.passed_steps for c in childs if c.status != 'skipped')
        run.failed_steps = sum(c.failed_steps for c in childs if c.status != 'skipped')
        if run.started_at and run.finished_at:
            run.duration = (run.finished_at - run.started_at).total_seconds()
        run.progress = 100 if run.status in ('passed', 'failed', 'stopped', 'error') else run.progress
        run.save()

        if run.status == 'passed':
            _send_progress_update_run(run.id, 'passed', 100,
                                      f"编排完成: {run.passed_steps}/{run.total_steps} 通过")
        else:
            _send_progress_update_run(run.id, run.status, run.progress or 0, '编排执行结束')

    except Exception as e:
        logger.error(f'Midscene 编排执行失败: {e}', exc_info=True)
        if run:
            run.refresh_from_db()
            run.status = 'error'
            run.error_message = str(e)
            run.finished_at = timezone.now()
            if run.started_at:
                run.duration = (run.finished_at - run.started_at).total_seconds()
            run.save()
            _send_progress_update_run(run.id, 'error', run.progress or 0, f'编排异常: {e}')

    finally:
        if device:
            try:
                device.refresh_from_db()
                device.unlock()
            except Exception as e:
                logger.error(f'[Task] 解锁设备失败: {e}')

    return run.status if run else 'error'


@shared_task(bind=True, max_retries=0)
def install_app_package_task(self, install_id):
    """异步安装安装包到单台设备（Android adb install / iOS tidevice install），安装期间锁定设备防冲突。"""
    from .models import MidsceneAppInstallRecord

    record = MidsceneAppInstallRecord.objects.select_related('package', 'device').get(id=install_id)
    device = record.device
    if not device:
        record.status = 'failed'
        record.error_message = '设备不存在'
        record.finished_at = timezone.now()
        record.save(update_fields=['status', 'error_message', 'finished_at'])
        return 'failed'

    locked_by_us = False
    try:
        device.lock(record.created_by)
        locked_by_us = True
        record.status = 'running'
        record.started_at = timezone.now()
        record.log = ''
        record.error_message = ''
        record.save(update_fields=['status', 'started_at', 'log', 'error_message'])

        pkg = record.package
        opts = record.options or {}
        start = time.time()
        ok, log, err = run_package_install(pkg, device, opts)
        record.log = log[-2000:]
        if ok:
            record.status = 'success'
            record.error_message = ''
        else:
            record.status = 'failed'
            record.error_message = err
            logger.error(f'[Install] 安装失败(设备 {device.device_id}): {err}')
    except Exception as e:
        logger.error(f'[Install] 安装异常(记录 {install_id}): {e}', exc_info=True)
        record.status = 'failed'
        record.error_message = str(e)[-500:]
    finally:
        record.finished_at = timezone.now()
        if record.started_at:
            record.duration = (record.finished_at - record.started_at).total_seconds()
        record.save(update_fields=['status', 'log', 'error_message', 'finished_at', 'duration'])
        if device and locked_by_us:
            try:
                device.refresh_from_db()
                device.unlock()
            except Exception as e:
                logger.error(f'[Install] 解锁设备失败: {e}')

    return record.status
