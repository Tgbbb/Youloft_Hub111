"""需求分析 Celery 异步任务"""
import logging
from celery import shared_task
from django.utils import timezone
from apps.requirement_analysis.models import ModaoImport

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=0)
def import_from_modao_task(self, import_id: int, url: str, auth_token: str):
    """异步执行墨刀导入，更新 ModaoImport 状态和进度"""
    record = ModaoImport.objects.get(id=import_id)
    record.status = 'importing'
    record.progress = 5
    record.celery_task_id = self.request.id or ''
    record.save(update_fields=['status', 'progress', 'celery_task_id'])

    try:
        from apps.requirement_analysis.models import AIModelService

        # 进度跟踪（不在 async 回调里写 DB，避免 sync/async 冲突）
        progress_state = {'current': 0, 'total': 1}

        def on_progress(current: int, total: int, message: str = ''):
            progress_state['current'] = current
            progress_state['total'] = total
            if message:
                logger.info(f'[Modao] {message}')

        # 在独立 event loop 中运行 async 代码
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                AIModelService.import_from_modao(
                    url=url,
                    auth_token=auth_token,
                    progress_callback=on_progress,
                )
            )
        finally:
            loop.close()

        record.title = result.get('title', record.title)
        record.data = {
            'canvases': result.get('canvases', []),
            'import_id': result.get('import_id', ''),
        }
        record.status = 'completed'
        record.progress = 100
        record.save(update_fields=['title', 'data', 'status', 'progress'])
        logger.info(f'[Modao] 异步导入完成: import_id={import_id}, {len(result.get("canvases", []))}画布')

    except Exception as exc:
        record.status = 'failed'
        record.progress = 100
        record.error_message = str(exc)[:1000]
        record.save(update_fields=['status', 'progress', 'error_message'])
        logger.error(f'[Modao] 异步导入失败: import_id={import_id}, error={exc}')
        raise
