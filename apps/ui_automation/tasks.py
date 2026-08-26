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


@shared_task(bind=True, max_retries=0)
def execute_midscene_task(self, execution_id, record_mode=False, replay_mode=False,
                          replay_index=0, clear_app_data=False, install_package_id=None):
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
        if not model_config or not model_config.api_key:
            raise ValueError('未配置 AI 模型或 API Key')

        # 锁定设备
        device.lock(execution.executed_by)

        # 更新状态
        execution.status = 'running'
        execution.started_at = timezone.now()
        execution.save(update_fields=['status', 'started_at'])

        _send_progress_update(execution.id, 'running', 5, '开始执行...')

        # ---- 执行前安装：选了安装包则装包 + 强制清数据，失败则整个执行失败 ----
        app_package_override = ''
        if install_package_id:
            from .models import MidsceneAppPackage
            install_pkg = MidsceneAppPackage.objects.filter(id=install_package_id).first()
            if not install_pkg:
                raise ValueError('安装包不存在或已被删除')
            if device.platform != 'android':
                raise ValueError('iOS 设备暂不支持自动安装')
            _send_progress_update(execution.id, 'running', 5,
                                  f'安装 {install_pkg.name or install_pkg.package_name}...')
            logger.info(f'[Task] 执行前安装: {install_pkg.name or install_pkg.package_name} -> {device.device_id}')
            ok, log, err = run_apk_install(install_pkg, device, {'overwrite': True})
            if not ok:
                logger.error(f'[Task] 执行前安装失败(记录 {execution_id}): {err}')
                raise ValueError(f'安装包安装失败: {err}')
            logger.info(f'[Task] 安装完成: {install_pkg.name or install_pkg.package_name} '
                        f'({install_pkg.package_name})')
            app_package_override = install_pkg.package_name or ''
            clear_app_data = True  # 选了包强制清数据

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
def install_app_package_task(self, install_id):
    """异步安装 APK 到单台设备（adb install），安装期间锁定设备防冲突。"""
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
        ok, log, err = run_apk_install(pkg, device, opts)
        record.log = log[-2000:]
        if ok:
            record.status = 'success'
            record.error_message = ''
        else:
            record.status = 'failed'
            record.error_message = err
            logger.error(f'[Install] adb install 失败(设备 {device.device_id}): {err}')
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
