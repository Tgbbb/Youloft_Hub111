"""需求分析 Celery 异步任务"""
import logging
import threading
from celery import shared_task
from django.utils import timezone
from apps.requirement_analysis.models import ModaoImport

logger = logging.getLogger(__name__)

STAGE_BASE_PROGRESS = {'prepare': 5, 'login': 15, 'list': 25}


def _calc_progress(stage: str, current: int, total: int) -> int:
    """把阶段/画布进度映射为 0-100 的百分比"""
    if stage == 'done':
        return 100
    if stage == 'canvas' and total > 0:
        return min(95, 25 + int(70 * current / total))
    return STAGE_BASE_PROGRESS.get(stage, 25)


@shared_task(bind=True, max_retries=0)
def import_from_modao_task(self, import_id: int, url: str, auth_token: str):
    """异步执行墨刀导入，更新 ModaoImport 状态和进度"""
    record = ModaoImport.objects.get(id=import_id)
    record.status = 'importing'
    record.stage = 'prepare'
    record.progress = 5
    record.progress_detail = {
        'stage': 'prepare',
        'message': '任务已开始，正在准备浏览器…',
        'current': 0,
        'total': 1,
        'canvases': [],
    }
    record.celery_task_id = self.request.id or ''
    record.save(update_fields=['status', 'stage', 'progress', 'progress_detail', 'celery_task_id'])

    # 进度状态维护在内存，由后台线程节流写库（避免 async 回调里操作 ORM）
    progress_state = {
        'current': 0,
        'total': 1,
        'stage': 'prepare',
        'message': '任务已开始，正在准备浏览器…',
        'canvases': [],
    }
    stop_event = threading.Event()

    def build_detail():
        return {
            'stage': progress_state.get('stage', ''),
            'message': progress_state.get('message', ''),
            'current': progress_state.get('current', 0),
            'total': progress_state.get('total', 1),
            'canvases': list(progress_state.get('canvases', [])),
        }

    def on_progress(current: int, total: int, message: str = '', stage: str = None,
                    canvas_index: int = None, canvas_name: str = None, canvas_status: str = None):
        progress_state['current'] = current
        progress_state['total'] = total
        if stage:
            progress_state['stage'] = stage
        if message:
            progress_state['message'] = message
            logger.info(f'[Modao] {message}')
        if canvas_index is not None:
            entry = next((c for c in progress_state['canvases'] if c.get('index') == canvas_index), None)
            if entry is None:
                entry = {
                    'index': canvas_index,
                    'name': canvas_name or f'画布{canvas_index}',
                    'status': 'pending',
                    'message': '',
                }
                progress_state['canvases'].append(entry)
            if canvas_name:
                entry['name'] = canvas_name
            if canvas_status:
                entry['status'] = canvas_status
            if message and canvas_status in ('done', 'failed'):
                entry['message'] = message

    def persist_progress():
        """后台线程：节流把内存进度写入 DB"""
        last_snapshot = None
        while not stop_event.wait(0.5):
            try:
                rec = ModaoImport.objects.get(pk=import_id)
                canvases = progress_state.get('canvases', [])
                snapshot = (
                    progress_state.get('stage'),
                    progress_state.get('current', 0),
                    progress_state.get('total', 1),
                    progress_state.get('message', ''),
                    tuple((c.get('index'), c.get('status')) for c in canvases),
                )
                if snapshot == last_snapshot:
                    continue
                last_snapshot = snapshot
                rec.stage = progress_state.get('stage', '')
                rec.progress = _calc_progress(
                    rec.stage, progress_state.get('current', 0), progress_state.get('total', 1)
                )
                rec.progress_detail = build_detail()
                rec.save(update_fields=['stage', 'progress', 'progress_detail'])
            except ModaoImport.DoesNotExist:
                return
            except Exception as exc:
                logger.warning(f'[Modao] 进度写库失败: {exc}')

    persist_thread = threading.Thread(target=persist_progress, daemon=True)
    persist_thread.start()

    try:
        from apps.requirement_analysis.models import AIModelService

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
            stop_event.set()
            persist_thread.join(timeout=2)

        record.title = result.get('title', record.title)
        record.data = {
            'canvases': result.get('canvases', []),
            'import_id': result.get('import_id', ''),
        }
        record.status = 'completed'
        record.stage = 'done'
        record.progress = 100
        detail = build_detail()
        detail['stage'] = 'done'
        detail['message'] = f'导入完成: {len(result.get("canvases", []))} 个画布'
        record.progress_detail = detail
        record.save(update_fields=['title', 'data', 'status', 'stage', 'progress', 'progress_detail'])
        logger.info(f'[Modao] 异步导入完成: import_id={import_id}, {len(result.get("canvases", []))}画布')

    except Exception as exc:
        stop_event.set()
        persist_thread.join(timeout=2)
        record.status = 'failed'
        record.stage = 'failed'
        record.error_message = str(exc)[:1000]
        detail = build_detail()
        detail['stage'] = 'failed'
        detail['message'] = str(exc)[:1000]
        record.progress_detail = detail
        record.save(update_fields=['status', 'stage', 'error_message', 'progress_detail'])
        logger.error(f'[Modao] 异步导入失败: import_id={import_id}, error={exc}')
        raise
