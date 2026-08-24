# -*- coding: utf-8 -*-
"""同步确认引擎：监听「已同步至线上」回复邮件，OCR 图片配置并与推送后台对比。

复用 push_check_engine 的 IMAP/OCR/后台查询工具函数，独立实现：
  1. 当天标题/正文关键词匹配的邮件搜索
  2. 图片 OCR 五字段提取（推送目标/推送标题/推送内容/安卓版本/IOS版本）
  3. 与推送后台实时记录逐字段归一化对比（只读，不修改后台）
"""

import email
import imaplib
import re
import ssl
from datetime import datetime, timezone

from . import push_check_engine as pce

_STATE = None
_log_lines = []
_last_ok = True
_last_summary = {}

# 五字段提取顺序：每个字段用 start 关键字定位、stop 关键字截断（compact 文本已去空白）
_SYNC_FIELD_SPECS = [
    ('push_target', ['推送目标'], ['推送标题', '标题', '推送内容', '内容', '安卓版本', 'IOS版本', 'iOS版本', '推送链接']),
    ('title', ['推送标题', '标题'], ['推送内容', '内容', '安卓版本', 'IOS版本', 'iOS版本', '推送目标', '推送链接']),
    ('content', ['推送内容', '内容'], ['安卓版本', 'IOS版本', 'iOS版本', '推送目标', '推送标题', '推送链接']),
    ('android_version', ['安卓版本'], ['IOS版本', 'iOS版本', '推送目标', '推送标题', '推送内容', '推送链接']),
    ('ios_version', ['IOS版本', 'iOS版本'], ['推送目标', '推送标题', '推送内容', '安卓版本', '推送链接']),
]

# 推送目标显示名 → 后台代码集合（后台 pushTarget：0=主包/万年历, 1=黄历, 2=鸿蒙）
_TARGET_ALIASES = [
    ('主包', '0'), ('万年历', '0'), ('黄历', '1'), ('鸿蒙', '2'),
    ('iOS', '0'), ('苹果', '0'), ('安卓', '0,1'), ('Android', '0,1'),
]


def configure(config, state):
    """由调用方注入配置与已处理状态（配置同时写入 push_check_engine 供后台查询复用）。"""
    global _STATE
    base = {
        'done': False, 'status': 'pending', 'mail_uid': None, 'mail_subject': '',
        'parsed_fields': {}, 'backend_record': {}, 'diffs': [], 'checked_at': None,
    }
    base.update(state or {})
    _STATE = base
    pce.configure(config, state or {})


def load_state():
    return _STATE if _STATE is not None else {
        'done': False, 'status': 'pending', 'mail_uid': None, 'mail_subject': '',
        'parsed_fields': {}, 'backend_record': {}, 'diffs': [], 'checked_at': None,
    }


def save_state(s):
    global _STATE
    _STATE = dict(s or {})


def log(*args):
    text = ' '.join(str(a) for a in args)
    text = re.sub(r'\x1b\[[0-9;]*m', '', text)
    _log_lines.append(text)


def find_sync_email(subject_keyword, body_keyword):
    """IMAP 找当天最新一封标题含 subject_keyword、正文含 body_keyword 的邮件。"""
    cfg = pce.get_config()
    imap_cfg = cfg['imap']
    now = datetime.now()
    since_str = '%02d-%s-%d' % (now.day, pce._MONTHS[now.month - 1], now.year)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    imap = imaplib.IMAP4_SSL(imap_cfg['host'], imap_cfg['port'],
                             ssl_context=ctx, timeout=int(imap_cfg.get('timeout', 20)))
    try:
        imap.login(imap_cfg['user'], imap_cfg['password'])
        imap.select('INBOX', readonly=True)
        typ, data = imap.search(None, '(SINCE "%s")' % since_str)
        if typ != 'OK':
            return None
        seqs = data[0].split()
        if not seqs:
            return None

        candidates = []
        fetch_set = b','.join(seqs)
        typ, msg_data = imap.fetch(fetch_set, '(UID BODY.PEEK[HEADER.FIELDS (SUBJECT DATE)])')
        if typ == 'OK':
            for item in msg_data:
                if not isinstance(item, tuple):
                    continue
                meta = item[0].decode('utf-8', 'replace')
                um = re.search(r'UID (\d+)', meta)
                if not um:
                    continue
                uid = int(um.group(1))
                header = email.message_from_bytes(item[1] or b'')
                subject = pce.decode_mime_words(header.get('Subject', ''))
                if subject_keyword in subject:
                    candidates.append((uid, subject))
        if not candidates:
            return None

        latest_uid = max(candidates, key=lambda x: x[0])[0]
        typ, msg_data = imap.uid('fetch', str(latest_uid), '(RFC822)')
        if typ != 'OK' or not msg_data or not isinstance(msg_data[0], tuple):
            return None
        msg = email.message_from_bytes(msg_data[0][1])

        date_str = msg.get('Date', '')
        parsed_date = email.utils.parsedate_to_datetime(date_str) if date_str else datetime.now(timezone.utc)
        iso = parsed_date.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
        text, html = pce.get_text_and_html(msg)
        plain_text = (text or '') + re.sub(r'<[^>]+>', '', html or '')
        if body_keyword not in plain_text:
            return None
        return {
            'uid': latest_uid,
            'date': iso,
            'subject': pce.decode_mime_words(msg.get('Subject', '')),
            'text': text,
            'html': html,
            'attachments': pce.get_image_attachments(msg),
        }
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def ocr_extract_sync_fields(text):
    """把 OCR 原文解析成五字段（compact 文本定位，兼容 OCR 空格/换行干扰）。"""
    raw = re.sub(r'[ \t]+', ' ', text or '')
    raw = re.sub(r'\n\s*\n', '\n', raw).strip()
    compact = re.sub(r'\s+', '', raw)
    fields = {}
    for key, starts, stops in _SYNC_FIELD_SPECS:
        fields[key] = pce.ocr_extract_field(compact, starts, stops)
    return {'raw': raw, 'fields': fields}


def norm_push_target(value):
    """推送目标显示名 → 后台代码集合字符串（如 '0,1'）；识别不到返回原文。"""
    s = (value or '').strip()
    if not s:
        return ''
    codes = set()
    for word, code in _TARGET_ALIASES:
        if word in s:
            for c in code.split(','):
                codes.add(c)
    if codes:
        return ','.join(sorted(codes))
    return s


def norm_version(value):
    """版本类别归一化：1=all，7=不向该端推送。"""
    s = str(value or '').strip()
    if '不向' in s:
        return '7'
    if s.lower() in ('all', '全部'):
        return '1'
    if s in ('1', '7'):
        return s
    return s


def compare_with_backend(fields):
    """OCR 五字段 vs 推送后台记录，返回 {'matched': record|None, 'diffs': [...]}。"""
    diffs = []
    title = (fields.get('title') or '').strip()
    content = (fields.get('content') or '').strip()
    sources = [s for s in (title, content) if s]
    result = pce.search_push(sources) if sources else None
    if not result or not result.get('succ'):
        return {'matched': None, 'diffs': ['后台未找到匹配记录（标题/内容未命中）']}
    records = (result.get('record') or {}).get('records') or []
    if not records:
        return {'matched': None, 'diffs': ['后台未找到匹配记录']}

    matched = None
    if title:
        for r in records:
            if pce.normalize_title(r.get('taskTitle') or '') == pce.normalize_title(title):
                matched = r
                break
    if matched is None:
        matched = records[0]

    # 1. 推送目标
    ocr_target = norm_push_target(fields.get('push_target') or '')
    back_raw = str(matched.get('pushTarget') or '')
    back_target = ','.join(sorted(x for x in back_raw.split(',') if x))
    if not ocr_target:
        diffs.append('推送目标未识别')
    elif ocr_target != back_target:
        diffs.append('推送目标不一致 → 邮件:「%s」 后台:「%s」'
                     % (fields.get('push_target'), pce.target_names(back_raw.split(',')) or '(未配置)'))

    # 2. 推送标题
    back_title = (matched.get('taskTitle') or '').strip()
    if not title:
        diffs.append('推送标题未识别')
    elif pce.normalize_title(title) != pce.normalize_title(back_title):
        diffs.append('推送标题不一致 → 邮件:「%s」 后台:「%s」' % (title, back_title))

    # 3. 推送内容
    back_content = (matched.get('taskBody') or '').strip()
    if not content:
        diffs.append('推送内容未识别')
    elif pce.normalize_title(content) != pce.normalize_title(back_content):
        diffs.append('推送内容不一致 → 邮件:「%s」 后台:「%s」' % (content, back_content))

    # 4. 安卓版本
    ocr_android = norm_version(fields.get('android_version') or '')
    back_android = norm_version(matched.get('versionType'))
    if not ocr_android:
        diffs.append('安卓版本未识别')
    elif ocr_android != back_android:
        diffs.append('安卓版本不一致 → 邮件:「%s」 后台:「%s」'
                     % (fields.get('android_version'), pce.ANDROID_VERSION_MAP.get(back_android, back_android)))

    # 5. IOS版本
    ocr_ios = norm_version(fields.get('ios_version') or '')
    back_ios = norm_version(matched.get('versionTypeIOS'))
    if not ocr_ios:
        diffs.append('IOS版本未识别')
    elif ocr_ios != back_ios:
        diffs.append('IOS版本不一致 → 邮件:「%s」 后台:「%s」'
                     % (fields.get('ios_version'), pce.IOS_VERSION_MAP.get(back_ios, back_ios)))

    return {'matched': matched, 'diffs': diffs}


def main(force=False):
    global _last_ok
    cfg = pce.get_config()
    state = load_state()
    now = datetime.now()
    today = now.date()

    deadline_str = cfg.get('deadline_time') or '18:30'
    try:
        deadline = datetime.combine(today, datetime.strptime(deadline_str, '%H:%M').time())
    except Exception:
        deadline_str = '18:30'
        deadline = datetime.combine(today, datetime.strptime(deadline_str, '%H:%M').time())

    log('%s[%s] 同步确认检查...%s' % ('', now.strftime('%Y/%m/%d %H:%M:%S'), ''))

    if state.get('done') and not force:
        log('ℹ 当天已处理（%s），跳过；勾选强制重新对比可重查' % (state.get('status') or ''))
        _last_summary.update({
            'status': state.get('status') or 'ok',
            'message': '当天已处理，跳过',
            'mail_uid': state.get('mail_uid'),
            'mail_subject': state.get('mail_subject') or '',
            'parsed_fields': state.get('parsed_fields') or {},
            'backend_record': state.get('backend_record') or {},
            'diffs': state.get('diffs') or [],
        })
        return

    if now >= deadline and not state.get('done'):
        state.update({'done': True, 'status': 'timeout', 'checked_at': now.isoformat()})
        save_state(state)
        log('✖ 已到截止时间 %s，仍未收到「已同步至线上」邮件 → 超时异常' % deadline_str)
        _last_ok = False
        _last_summary.update({'status': 'timeout', 'message': '截止 %s 前未收到已同步邮件' % deadline_str})
        return

    subject_keyword = cfg.get('mail_subject') or '回复：【测试需求】关于常规PUSH的测试需求'
    body_keyword = cfg.get('mail_body_keyword') or '已同步至线上'
    log('▸ 监听当天已同步邮件（标题含「%s」，截止 %s）...' % (subject_keyword, deadline_str))

    email_data = find_sync_email(subject_keyword, body_keyword)
    if not email_data:
        state.update({'status': 'pending', 'checked_at': now.isoformat()})
        save_state(state)
        log('ℹ 未发现已同步邮件')
        _last_summary.update({'status': 'pending', 'message': '尚未收到已同步邮件'})
        return

    log('► 发现邮件: %s (uid=%s)' % (email_data['subject'], email_data['uid']))
    parsed = None
    atts = [a for a in email_data['attachments'] if a['size'] >= 5000]
    if atts:
        att = max(atts, key=lambda a: a['size'])
        ocr_text = pce.ocr_image(att['content'])
        if ocr_text:
            parsed = ocr_extract_sync_fields(ocr_text)
    if parsed is None:
        state.update({
            'done': True, 'status': 'fail',
            'mail_uid': email_data['uid'], 'mail_subject': email_data['subject'],
            'checked_at': now.isoformat(),
        })
        save_state(state)
        log('✖ 已收到邮件但未解析出配置图片（无图片附件或 OCR 失败）')
        _last_ok = False
        _last_summary.update({
            'status': 'fail', 'message': '已收到邮件但未解析出配置图片',
            'mail_uid': email_data['uid'], 'mail_subject': email_data['subject'],
        })
        return

    fields = parsed['fields']
    log('OCR 解析: 推送目标=%s 标题=%s 内容=%s 安卓=%s IOS=%s'
        % (fields.get('push_target'), fields.get('title'), fields.get('content'),
           fields.get('android_version'), fields.get('ios_version')))
    cmp = compare_with_backend(fields)
    diffs = cmp['diffs']
    matched = cmp.get('matched')

    state.update({
        'done': True,
        'status': 'ok' if not diffs else 'fail',
        'mail_uid': email_data['uid'],
        'mail_subject': email_data['subject'],
        'parsed_fields': fields,
        'backend_record': matched or {},
        'diffs': diffs,
        'checked_at': now.isoformat(),
    })
    save_state(state)
    _last_summary.update({
        'status': state['status'],
        'mail_uid': email_data['uid'],
        'mail_subject': email_data['subject'],
        'parsed_fields': fields,
        'backend_record': matched or {},
        'diffs': diffs,
    })
    if diffs:
        _last_ok = False
        _last_summary['message'] = '对比不一致（%d 项）' % len(diffs)
        for d in diffs:
            log('✖ ' + d)
    else:
        _last_summary['message'] = '对比全部通过'
        log('✔ 对比全部通过')


def run_sync_check_engine(force=False, config=None, state=None):
    """由 Celery 任务/手动触发调用：返回结构化结果，state 由调用方持久化。"""
    global _last_ok, _last_summary
    _log_lines.clear()
    configure(config, state)
    _last_ok = True
    _last_summary = {
        'status': 'pending', 'message': '', 'mail_uid': None, 'mail_subject': '',
        'parsed_fields': {}, 'backend_record': {}, 'diffs': [], 'problems': 0,
    }
    try:
        main(force=force)
    except Exception as exc:
        log('❌ %s' % exc)
        _last_ok = False
        _last_summary['status'] = 'fail'
        _last_summary['message'] = str(exc)
    return {
        'ok': _last_ok,
        'summary': _last_summary,
        'log': '\n'.join(_log_lines),
        'state': dict(load_state()),
    }
