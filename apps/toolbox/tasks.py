# -*- coding: utf-8 -*-
"""工具合集 - Celery 异步任务"""
import traceback

from celery import shared_task
from django.utils import timezone

from .models import PushCheckRun, ToolboxConfig
from .push_check_engine import run_push_check_engine


@shared_task(bind=True, max_retries=0)
def run_push_check(self, run_id):
    run = PushCheckRun.objects.filter(id=run_id).first()
    if run is None:
        return
    run.status = 'running'
    run.save(update_fields=['status'])

    cfg_obj = ToolboxConfig.get_singleton()
    config = {
        'imap': {
            'host': cfg_obj.imap_host,
            'port': cfg_obj.imap_port,
            'user': cfg_obj.imap_user,
            'password': cfg_obj.imap_password,
            'timeout': cfg_obj.imap_timeout,
        },
        'backend': {
            'host': cfg_obj.backend_host,
            'port': cfg_obj.backend_port,
        },
        'push_cookie': cfg_obj.push_cookie,
        'tesseract_path': cfg_obj.tesseract_path,
    }
    state = {
        'lastDate': cfg_obj.last_date or '',
        'lastUid': cfg_obj.last_uid,
        'problems': cfg_obj.last_problems,
    }

    try:
        result = run_push_check_engine(force=run.force, config=config, state=state)
        run.status = 'success' if result['ok'] else 'failed'
        run.log = result['log']
        run.summary = result['summary'] or {}

        engine_state = result.get('state') or {}
        if engine_state.get('lastUid') is not None:
            cfg_obj.last_uid = engine_state['lastUid']
        if engine_state.get('lastDate'):
            cfg_obj.last_date = engine_state['lastDate']
        cfg_obj.last_problems = int(engine_state.get('problems') or 0)
        cfg_obj.save(update_fields=['last_uid', 'last_date', 'last_problems', 'updated_at'])
    except Exception as exc:
        run.status = 'failed'
        run.log = (run.log or '') + '\n' + traceback.format_exc()
        run.summary = {'message': str(exc)}

    run.finished_at = timezone.now()
    run.save(update_fields=['status', 'log', 'summary', 'finished_at'])
