# -*- coding: utf-8 -*-
"""配置回复提醒引擎：监听当天「品管部」配置邮件，找出未回复线程并判定是否需要提醒。

复用 push_check_engine 的 IMAP/解析工具函数，独立实现：
  1. 当天邮件筛选：收件人含品管部 + 正文含请QC检查 + 标题含 配置/广告/测试需求
  2. 日期过滤：标题/正文中出现 M.D 或 M.D-M.D 且不覆盖今天 → 视为非当天配置，跳过
  3. 同主题回复判定：同归一化主题分组内存在更晚邮件 → 已回复；否则未回复
  4. 未回复判定：广告 → 立即提醒；非广告 → 发件时间超过阈值才提醒
"""

import email
import imaplib
import re
import ssl
from datetime import date as _date, datetime

from . import push_check_engine as pce

_log_lines = []
_last_ok = True
_last_summary = {}
_last_state = {}
_CFG = {}

# 日期格式：8.28 或 8.28-8.29（可能带空格/破折号）
_RANGE_RE = re.compile(r'(\d{1,2})\.(\d{1,2})\s*[-—~]\s*(\d{1,2})\.(\d{1,2})')
_SINGLE_RE = re.compile(r'(?<![\d.])(\d{1,2})\.(\d{1,2})(?![\d.])')

# 回复前缀（中文/英文），用于归一化主题分组
_CN_REPLY = r'(?:[【\[]?(?:回复|答复|转发)[】\]]?\s*[:：]?\s*)'
_ASCII_REPLY = r'(?:[【\[]?(?:Re|RE|Fwd|FW|Forward)[】\]]?\s*[:：]\s*)'
_REPLY_PREFIX_RE = re.compile(r'^\s*(?:%s|%s)+' % (_CN_REPLY, _ASCII_REPLY), re.I)

# 邮件正文出现这些词，视为已闭合/验证回复，不应再作为未回复请求
_VERIFIED_KEYWORDS = ('已验证', '已核实', '已确认', '已检查', '验证完成')


def configure(config, state):
    """由调用方注入配置与已处理状态。"""
    global _CFG
    _CFG = config or {}
    pce.configure(config or {}, state or {})


def get_config():
    return _CFG or pce.get_config()


def load_state():
    return dict(_last_state) if _last_state else {}


def save_state(s):
    global _last_state
    _last_state = dict(s or {})


def log(*args):
    text = ' '.join(str(a) for a in args)
    text = re.sub(r'\x1b\[[0-9;]*m', '', text)
    _log_lines.append(text)


def _to_local(dt):
    """转成 naive 本地时间，便于比较。"""
    if dt is None:
        return datetime.now()
    if dt.tzinfo is not None:
        dt = dt.astimezone()
        dt = dt.replace(tzinfo=None)
    return dt


def _parse_message_date(msg):
    raw = msg.get('Date', '')
    if not raw:
        return datetime.now()
    try:
        return _to_local(email.utils.parsedate_to_datetime(raw))
    except Exception:
        return datetime.now()


def _extract_sender(msg):
    return pce.decode_mime_words(msg.get('From', '')).strip() or '未知发件人'


def _recipient_match(msg, keywords):
    """To/CC/Delivered-To 的显示名或地址包含任一关键字即命中。"""
    if not keywords:
        return False
    raw = ' '.join(msg.get_all('To', []) + msg.get_all('Cc', []) +
                   msg.get_all('Delivered-To', []))
    decoded = pce.decode_mime_words(raw).lower()
    return any(kw.strip().lower() in decoded for kw in keywords if kw.strip())


def _subject_match(subject, keywords):
    if not keywords:
        return False
    subj = pce.decode_mime_words(subject or '').lower()
    return any(kw.strip().lower() in subj for kw in keywords if kw.strip())


def _body_match(body, keywords):
    """正文命中任一关键字即匹配（逗号分隔）。"""
    if not keywords:
        return False
    hay = body or ''
    return any(kw.strip() in hay for kw in keywords if kw.strip())


def _strip_script_style(html):
    """去掉 HTML 中 <style>/<script> 内部内容，避免 CSS/JS 小数被误判为日期。"""
    return re.sub(r'<(style|script)[^>]*>.*?</\1>', '', html or '',
                  flags=re.I | re.S)


def _is_verified_text(text):
    """正文含验证/关闭标记 → 该邮件是验证/确认回复，而非未回复请求。"""
    lowered = _primary_body(text or '').lower()
    return any(kw.lower() in lowered for kw in _VERIFIED_KEYWORDS)


# 引用/转发历史的边界（内嵌邮件头或分隔线），用于只取当前邮件正文首部
_QUOTE_BOUNDARY_RE = re.compile(
    r'^[ \t]*(主\s*题\s*[:：]|发件人\s*[:：]|收件人\s*[:：]|-{3,}|_{3,}|═{3,})',
    re.I | re.M)


def _primary_body(text):
    """截取正文首部（当前邮件自身内容），避开被引用/转发的旧邮件历史。"""
    if not text:
        return ''
    m = _QUOTE_BOUNDARY_RE.search(text)
    if m:
        return text[:m.start()].strip()
    # 无明确引用边界时回退取前 300 字，避免长引用把正文首尾淹没
    return text[:300].strip() or text.strip()


def normalize_subject(s):
    """归一化主题：去回复前缀、压缩空白、小写。保留标题内日期以区分不同配置。"""
    s = pce.decode_mime_words(s or '')
    s = _REPLY_PREFIX_RE.sub('', s)
    return re.sub(r'\s+', ' ', s).strip().lower()


def _parse_date_specs(text):
    """解析 M.D 单日期与 M.D-M.D 日期范围。"""
    specs = []
    text = text or ''

    def valid(m, d):
        return 1 <= m <= 12 and 1 <= d <= 31

    for m in _RANGE_RE.finditer(text):
        m1, d1, m2, d2 = (int(m.group(1)), int(m.group(2)),
                          int(m.group(3)), int(m.group(4)))
        if valid(m1, d1) and valid(m2, d2):
            specs.append(('range', m1, d1, m2, d2))
    masked = _RANGE_RE.sub(' ' * 16, text)
    for m in _SINGLE_RE.finditer(masked):
        mo, dy = int(m.group(1)), int(m.group(2))
        if valid(mo, dy):
            specs.append(('single', mo, dy))
    return specs


def _date_spec_cover_today(spec, today):
    """判断解析出的日期/范围是否覆盖今天。"""
    if spec[0] == 'single':
        _, month, day = spec
        return (month, day) == (today.month, today.day)
    _, m1, d1, m2, d2 = spec
    year = today.year
    try:
        start = _date(year, m1, d1)
        end = _date(year, m2, d2)
        if end < start:
            end = end.replace(year=year + 1)
    except ValueError:
        return False
    return start <= today <= end


def _has_nontoday_date(text, today):
    """标题/正文存在任一不覆盖今天的日期 → 判为非当天配置。"""
    for spec in _parse_date_specs(text):
        if not _date_spec_cover_today(spec, today):
            return True
    return False


def _fetch_today_records(imap_cfg):
    """IMAP 拉取当天全部邮件头（UID/Subject/Date/From/To/Cc）。"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    imap = imaplib.IMAP4_SSL(
        imap_cfg['host'], imap_cfg['port'],
        ssl_context=ctx, timeout=int(imap_cfg.get('timeout', 20)))
    try:
        imap.login(imap_cfg.get('user', ''), imap_cfg.get('password', ''))
        imap.select('INBOX', readonly=True)
        now = datetime.now()
        since_str = '%02d-%s-%d' % (now.day, pce._MONTHS[now.month - 1], now.year)
        typ, data = imap.search(None, '(SINCE "%s")' % since_str)
        if typ != 'OK':
            return [], imap
        seqs = data[0].split()
        if not seqs:
            return [], imap
        records = []
        fetch_set = b','.join(seqs)
        typ, msg_data = imap.fetch(
            fetch_set, '(UID BODY.PEEK[HEADER.FIELDS (SUBJECT DATE FROM TO CC)])')
        if typ == 'OK':
            for item in msg_data:
                if not isinstance(item, tuple):
                    continue
                meta = item[0].decode('utf-8', 'replace')
                um = re.search(r'UID (\d+)', meta)
                if not um:
                    continue
                header = email.message_from_bytes(item[1] or b'')
                rec_date = _parse_message_date(header)
                records.append({
                    'uid': int(um.group(1)),
                    'subject': pce.decode_mime_words(header.get('Subject', '')),
                    'date_dt': rec_date,
                    'sender': _extract_sender(header),
                    'header': header,
                })
        return records, imap
    except Exception:
        try:
            imap.logout()
        except Exception:
            pass
        raise


def _fetch_msg(imap, uid):
    """按 UID 拉取一封完整邮件。"""
    typ, data = imap.uid('fetch', str(uid), '(RFC822)')
    if typ != 'OK' or not data or not isinstance(data[0], tuple):
        return None
    return email.message_from_bytes(data[0][1])


def run_reply_check_engine(force=False, config=None, state=None):
    """执行一次配置回复检查，返回结构化结果。"""
    global _last_ok, _last_summary, _last_state
    configure(config or {}, state or {})
    cfg = get_config()
    _log_lines[:] = []
    imap_cfg = cfg['imap']
    qc_kw = [k for k in (cfg.get('qc_recipient_keywords') or '').split(',') if k.strip()]
    body_kw_list = [k for k in (cfg.get('body_keyword') or '').split(',') if k.strip()]
    title_kw = [k for k in (cfg.get('title_keywords') or '').split(',') if k.strip()]
    ad_kw_list = [k for k in (cfg.get('ad_keyword') or '').split(',') if k.strip()]
    threshold_min = int(cfg.get('notify_threshold_minutes') or 30)
    now = datetime.now()
    today = now.date()

    log('配置回复检查...')
    log('筛选规则: 收件人含%s / 正文含%s / 标题含%s' % (
        '或'.join(qc_kw) or '(未设置)',
        '或'.join(body_kw_list) or '(未设置)',
        '或'.join(title_kw) or '(未设置)'))

    records, imap = _fetch_today_records(imap_cfg)
    try:
        log('当天邮件 %d 封' % len(records))
        candidates = []
        for rec in records:
            if not _subject_match(rec['subject'], title_kw):
                continue
            if not _recipient_match(rec['header'], qc_kw):
                continue
            msg = _fetch_msg(imap, rec['uid'])
            if msg is None:
                continue
            text, html = pce.get_text_and_html(msg)
            # 去掉 <style>/<script> 内的 CSS/JS，避免把 line-height:1.5、0.5em 等小数误判为日期
            html_clean = _strip_script_style(html)
            body = (text or '') + re.sub(r'<[^>]+>', '', html_clean)
            if not _body_match(body, body_kw_list):
                continue
            searchable = (rec['subject'] or '') + '\n' + body
            if _has_nontoday_date(searchable, today):
                log('跳过(非当天日期): %s' % rec['subject'])
                continue
            subj_lower = pce.decode_mime_words(rec['subject']).lower()
            rec['ad'] = bool(ad_kw_list) and any(
                kw.lower() in subj_lower for kw in ad_kw_list)
            rec['body'] = body
            candidates.append(rec)

        # 全部邮件按归一化主题记录发送时间，用于「更晚同主题」判定
        subject_times = {}
        for rec in records:
            k = normalize_subject(rec['subject'])
            subject_times.setdefault(k, []).append(rec['date_dt'])

        # 按归一化主题分组，取组内最早匹配邮件作为该线程代表；
        # 只要组内存在更晚的邮件（如「已验证」回复），线程即视为已回复。
        # 避免把后续回复邮件里被引用的「请QC检查」误判为新的未回复请求。
        group_reps = {}
        for rec in candidates:
            key = normalize_subject(rec['subject'])
            rep = group_reps.get(key)
            if rep is None or (rec['date_dt'] and (not rep['date_dt'] or rec['date_dt'] < rep['date_dt'])):
                group_reps[key] = rec

        unresolved = []
        actionable = []
        for key, rep in group_reps.items():
            if _is_verified_text(rep.get('body', '')):
                log('已回复(验证邮件): %s' % rep['subject'])
                continue
            later = any(
                dt.replace(tzinfo=None) > rep['date_dt'].replace(tzinfo=None)
                for dt in subject_times.get(key, [])) if rep['date_dt'] else False
            if later:
                log('已回复(存在更晚同主题): %s' % rep['subject'])
                continue
            is_ad = rep['ad']
            elapsed = ((now - rep['date_dt'].replace(tzinfo=None)).total_seconds() / 60.0
                       if rep['date_dt'] else 0.0)
            is_actionable = is_ad or elapsed >= threshold_min
            item = {
                'subject': rep['subject'],
                'sender': rep['sender'],
                'send_time': rep['date_dt'].isoformat() if rep['date_dt'] else '',
                'ad': is_ad,
                'is_replied': False,
                'key': key,
                'actionable': is_actionable,
                'elapsed_minutes': round(elapsed, 1),
            }
            unresolved.append(item)
            if is_actionable:
                actionable.append(item)
            log('未回复%s: %s' % ('[广告]' if is_ad else '', rep['subject']))

        summary = {
            'email_count': len(records),
            'candidate_count': len(candidates),
            'unreplied_count': len(unresolved),
            'ad_unreplied_count': sum(1 for x in unresolved if x['ad']),
            'actionable_count': len(actionable),
        }
        _last_ok = True
        _last_summary = summary
        _last_state = dict(state or {})
        _last_state.update({
            'unreplied': unresolved,
            'actionable': actionable,
            'checked_at': now.isoformat(),
        })
        save_state(_last_state)
        log('未回复 %d 封（广告 %d 封）' % (
            summary['unreplied_count'], summary['ad_unreplied_count']))
        return {'ok': True, 'log': '\n'.join(_log_lines), 'summary': summary,
                'state': _last_state, 'unreplied': unresolved, 'actionable': actionable}
    finally:
        try:
            imap.logout()
        except Exception:
            pass
