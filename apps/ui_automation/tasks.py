# -*- coding: utf-8 -*-
"""
Midscene AI 移动端自动化 - Celery 异步任务
纯 Python Runner，不依赖 Node.js Sidecar
"""
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)

from .midscene_runner import run_midscene_test


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
def execute_midscene_task(self, execution_id):
    """
    异步执行 Midscene 测试任务（纯 Python Runner）。
    """
    from .models import MidsceneExecutionRecord

    execution = None
    device = None

    try:
        execution = MidsceneExecutionRecord.objects.get(id=execution_id)
        midscene_case = execution.midscene_case

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
        )

        # ---- 保存结果 ----
        execution.refresh_from_db()
        execution.status = result['status']
        execution.finished_at = timezone.now()
        if execution.started_at:
            execution.duration = (execution.finished_at - execution.started_at).total_seconds()
        execution.progress = 100
        execution.total_steps = result['totalSteps']
        execution.passed_steps = result['passedSteps']
        execution.failed_steps = result['failedSteps']
        execution.save()

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
