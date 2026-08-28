# -*- coding: utf-8 -*-
"""工具合集 - Celery 异步任务"""
import traceback
from datetime import datetime, timedelta

from celery import shared_task
from django.utils import timezone

from .models import PushCheckRun, ToolboxConfig, SyncCheckConfig, SyncCheckRun, ReplyCheckConfig, ReplyCheckRun
from .push_check_engine import run_push_check_engine
from . import sync_check_engine
from .sync_check_engine import run_sync_check_engine
from . import reply_check_engine


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
        'require_push_activity': cfg_obj.require_push_activity,
        'interval_minutes': cfg_obj.interval_minutes,
        'deadline_time': cfg_obj.deadline_time,
        'mail_subject': cfg_obj.mail_subject,
        'mail_body_keyword': cfg_obj.mail_body_keyword,
        'extract_mode': cfg_obj.extract_mode,
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
    config = _build_sync_config()
    state = _build_sync_state(run)
    sync_check_engine.configure(config, state)
    config['has_push_today'] = _has_push_today()
    try:
        result = run_sync_check_engine(force=force, config=config, state=state)
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
        _notify_sync_check(run, cfg_obj.enable_dingtalk_notify)
    except Exception as exc:
        run.status = 'fail'
        run.log = ((run.log + '\n') if run.log else '') + traceback.format_exc()
        run.checked_at = timezone.now()
        run.save()
        _notify_sync_check(run, cfg_obj.enable_dingtalk_notify)
    SyncCheckConfig.objects.filter(pk=cfg_obj.pk).update(last_check_at=timezone.now())


def _has_push_today():
    """当天是否有推送活动：存在当天的推送对比运行记录。"""
    now = timezone.localtime()
    day_start = timezone.make_aware(datetime.combine(now.date(), datetime.min.time()))
    day_end = day_start + timedelta(days=1)
    return PushCheckRun.objects.filter(started_at__gte=day_start, started_at__lt=day_end).exists()


def _notify_sync_check(run, enable):
    """异常终态（fail/timeout）时推送钉钉告警；同一天相同异常状态只推送一次。"""
    status = run.status or ''
    if status not in ('fail', 'timeout'):
        # 回到非异常状态，清空已推送标记，允许之后再次提醒
        if run.notify_sent_status:
            run.notify_sent_status = ''
            run.save(update_fields=['notify_sent_status'])
        return
    if not enable or run.notify_sent_status == status:
        return

    lines = [
        '## 同步确认异常提醒',
        '',
        '- 日期: {}'.format(run.date),
        '- 状态: {}'.format(run.get_status_display()),
    ]
    if run.mail_subject:
        lines.append('- 邮件: {}'.format(run.mail_subject))
    if run.mail_uid:
        lines.append('- 邮件UID: {}'.format(run.mail_uid))
    if run.diffs:
        lines.append('')
        lines.append('**差异（{}）:**'.format(len(run.diffs)))
        for d in run.diffs[:10]:
            lines.append('- {}'.format(d))
        if len(run.diffs) > 10:
            lines.append('- ... 共 {} 项'.format(len(run.diffs)))
    lines.append('')
    lines.append('请到 TestHub → 工具合集 → 同步确认 查看详情。')

    from apps.core.notifications import send_dingtalk_markdown
    results = send_dingtalk_markdown('同步确认异常提醒', '\n'.join(lines))
    ok = sum(1 for r in results if r.get('ok'))
    fail = len(results) - ok

    run.notify_sent_status = status
    run.save(update_fields=['notify_sent_status'])
    note = '钉钉通知: 成功 {} / 失败 {}'.format(ok, fail)
    run.log = ((run.log + '\n') if run.log else '') + note
    run.save(update_fields=['log'])


@shared_task(bind=True, max_retries=0)
def run_sync_check_tick(self):
    """Celery beat 每分钟触发；内部按 interval_minutes + last_check_at 节流。"""
    cfg_obj = SyncCheckConfig.get_singleton()
    if not cfg_obj.enabled:
        return
    now = timezone.now()
    if cfg_obj.last_check_at and (now - cfg_obj.last_check_at).total_seconds() < cfg_obj.interval_minutes * 60:
        return
    # 当天已闭环（通过/不一致/超时）后不再自动触发，避免反复空跑
    if SyncCheckRun.objects.filter(date=timezone.localdate(),
                                   status__in=('ok', 'fail', 'timeout')).exists():
        return
    _execute_sync_check(force=False)


@shared_task(bind=True, max_retries=0)
def run_sync_check(self, force=False):
    """手动触发一次同步确认检查（force=true 忽略当天已处理标记）。"""
    _execute_sync_check(force=force)


def _build_reply_config():
    """组装配置回复提醒引擎配置（IMAP 复用 ToolboxConfig）。"""
    rc = ReplyCheckConfig.get_singleton()
    toolbox = ToolboxConfig.get_singleton()
    return {
        'imap': {
            'host': toolbox.imap_host,
            'port': toolbox.imap_port,
            'user': toolbox.imap_user,
            'password': toolbox.imap_password,
            'timeout': toolbox.imap_timeout,
        },
        'qc_recipient_keywords': rc.qc_recipient_keywords,
        'body_keyword': rc.body_keyword,
        'title_keywords': rc.title_keywords,
        'ad_keyword': rc.ad_keyword,
        'notify_threshold_minutes': rc.notify_threshold_minutes,
        'enabled': rc.enabled,
        'interval_minutes': rc.interval_minutes,
    }


def _execute_reply_check(force=False):
    """执行一次配置回复检查并持久化当天记录（tick 与手动触发共用）。"""
    rc = ReplyCheckConfig.get_singleton()
    today = timezone.localdate()
    run, _ = ReplyCheckRun.objects.get_or_create(date=today, defaults={})
    config = _build_reply_config()
    state = {
        'unreplied': run.unresolved or [],
        'actionable': [],
        'notified_keys': run.notified_keys or [],
    }
    old_log = run.log or ''
    try:
        result = reply_check_engine.run_reply_check_engine(force=force, config=config, state=state)
        summary = result.get('summary') or {}
        run.unreplied_count = int(summary.get('unreplied_count') or 0)
        run.ad_unreplied_count = int(summary.get('ad_unreplied_count') or 0)
        run.unresolved = result.get('unreplied') or []
        run.log = (old_log + '\n' if old_log else '') + result['log']
        run.checked_at = timezone.now()
        run.save()
        _notify_reply_check(run, rc.enable_dingtalk_notify)
    except Exception as exc:
        run.log = (old_log + '\n' if old_log else '') + traceback.format_exc()
        run.checked_at = timezone.now()
        run.save()
    ReplyCheckConfig.objects.filter(pk=rc.pk).update(last_check_at=timezone.now())


def _notify_reply_check(run, enable):
    """把当天新出现的未回复线程聚合推送钉钉；每线程每天只提醒一次。"""
    if not enable:
        return
    notified = set(run.notified_keys or [])
    new_items = [x for x in (run.unresolved or [])
                 if x.get('actionable') and x.get('key') not in notified]
    if not new_items:
        return
    lines = ['## 配置回复提醒', '']
    for it in new_items:
        tag = '广告' if it.get('ad') else '配置'
        lines.append('- [{}] {}'.format(tag, it.get('subject', '')))
        if it.get('sender'):
            lines.append('  - 发件人: {}'.format(it['sender']))
        if it.get('send_time'):
            lines.append('  - 发件时间: {}'.format(it['send_time']))
        lines.append('  - 状态: 未收到回复')
    lines.append('')
    lines.append('请到 TestHub → 工具合集 → 配置回复提醒 查看详情。')

    from apps.core.notifications import send_dingtalk_markdown
    results = send_dingtalk_markdown('配置回复提醒', '\n'.join(lines))
    ok = sum(1 for r in results if r.get('ok'))
    fail = len(results) - ok
    if ok > 0:
        keys = notified | {x['key'] for x in new_items if x.get('key')}
        run.notified_keys = sorted(keys)
        run.save(update_fields=['notified_keys'])
    note = '钉钉通知: 成功 {} / 失败 {}（新增 {} 条）'.format(ok, fail, len(new_items))
    run.log = ((run.log + '\n') if run.log else '') + note
    run.save(update_fields=['log'])


@shared_task(bind=True, max_retries=0)
def run_reply_check_tick(self):
    """Celery beat 每分钟触发；按 interval_minutes + last_check_at 节流。"""
    rc = ReplyCheckConfig.get_singleton()
    if not rc.enabled:
        return
    now = timezone.now()
    if rc.last_check_at and (now - rc.last_check_at).total_seconds() < rc.interval_minutes * 60:
        return
    _execute_reply_check(force=False)


@shared_task(bind=True, max_retries=0)
def run_reply_check(self, force=False):
    """手动触发一次配置回复检查（force=true 立即重查最新邮件）。"""
    _execute_reply_check(force=force)
