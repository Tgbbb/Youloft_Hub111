# -*- coding: utf-8 -*-
"""工具合集 - Celery 异步任务"""
import traceback

from celery import shared_task
from django.utils import timezone

from .models import PushCheckRun, ToolboxConfig, SyncCheckConfig, SyncCheckRun
from .push_check_engine import run_push_check_engine
from .sync_check_engine import run_sync_check_engine


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


def _build_sync_config():
    """组装同步确认引擎配置（IMAP/后台复用 ToolboxConfig）。"""
    cfg_obj = SyncCheckConfig.get_singleton()
    toolbox = ToolboxConfig.get_singleton()
    return {
        'imap': {
            'host': toolbox.imap_host,
            'port': toolbox.imap_port,
            'user': toolbox.imap_user,
            'password': toolbox.imap_password,
            'timeout': toolbox.imap_timeout,
        },
        'backend': {
            'host': toolbox.backend_host,
            'port': toolbox.backend_port,
        },
        'push_cookie': toolbox.push_cookie,
        'tesseract_path': toolbox.tesseract_path,
        'enabled': cfg_obj.enabled,
        'interval_minutes': cfg_obj.interval_minutes,
        'deadline_time': cfg_obj.deadline_time,
        'mail_subject': cfg_obj.mail_subject,
        'mail_body_keyword': cfg_obj.mail_body_keyword,
    }


def _build_sync_state(run):
    return {
        'done': run.status in ('ok', 'fail', 'timeout'),
        'status': run.status,
        'mail_uid': run.mail_uid,
        'mail_subject': run.mail_subject,
        'parsed_fields': run.parsed_fields or {},
        'backend_record': run.backend_record or {},
        'diffs': run.diffs or [],
        'checked_at': run.checked_at.isoformat() if run.checked_at else None,
    }


def _execute_sync_check(force=False):
    """执行一次同步确认检查并持久化当天记录（tick 与手动触发共用）。"""
    cfg_obj = SyncCheckConfig.get_singleton()
    today = timezone.localdate()
    run, _ = SyncCheckRun.objects.get_or_create(date=today, defaults={'status': 'pending'})
    try:
        result = run_sync_check_engine(force=force, config=_build_sync_config(), state=_build_sync_state(run))
        es = result.get('state') or {}
        run.status = es.get('status') or ('ok' if result['ok'] else 'fail')
        run.mail_uid = es.get('mail_uid')
        run.mail_subject = es.get('mail_subject') or ''
        run.parsed_fields = es.get('parsed_fields') or {}
        run.backend_record = es.get('backend_record') or {}
        run.diffs = es.get('diffs') or []
        run.log = ((run.log + '\n') if run.log else '') + result['log']
        run.checked_at = timezone.now()
        run.save()
    except Exception as exc:
        run.status = 'fail'
        run.log = ((run.log + '\n') if run.log else '') + traceback.format_exc()
        run.checked_at = timezone.now()
        run.save()
    SyncCheckConfig.objects.filter(pk=cfg_obj.pk).update(last_check_at=timezone.now())


@shared_task(bind=True, max_retries=0)
def run_sync_check_tick(self):
    """Celery beat 每分钟触发；内部按 interval_minutes + last_check_at 节流。"""
    cfg_obj = SyncCheckConfig.get_singleton()
    if not cfg_obj.enabled:
        return
    now = timezone.now()
    if cfg_obj.last_check_at and (now - cfg_obj.last_check_at).total_seconds() < cfg_obj.interval_minutes * 60:
        return
    _execute_sync_check(force=False)


@shared_task(bind=True, max_retries=0)
def run_sync_check(self, force=False):
    """手动触发一次同步确认检查（force=true 忽略当天已处理标记）。"""
    _execute_sync_check(force=force)
