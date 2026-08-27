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

# 上报ID 用于切分表格数据行（后台配置截图每行以上报ID 开头，uuid 末尾字符 OCR 可能误识）
_UUID_RE = re.compile(
    r'[0-9a-fA-FlI]{8}-[0-9a-fA-FlI]{4,5}-[0-9a-fA-FlI]{4,5}-[0-9a-fA-FlI]{4}-[0-9a-fA-FlI]{10,}',
    re.I)
_TARGET_HINT = ('主包', '黄历', '鸿蒙')
_TARGET_CODE = {'主包': '0', '黄历': '1', '鸿蒙': '2'}


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


def _find_email_by_headers(subject_predicate, body_keyword=None):
    """IMAP 找当天最新一封满足标题判定、可选正文关键词的邮件。"""
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
                if subject_predicate(subject):
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
        if body_keyword and body_keyword not in plain_text:
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


def find_sync_email(subject_keyword, body_keyword):
    """IMAP 找当天最新一封标题含 subject_keyword、正文含 body_keyword 的邮件。"""
    return _find_email_by_headers(lambda s: subject_keyword in s, body_keyword)


def ocr_extract_sync_rows(text):
    """把 OCR 原文按上报ID 切分成表格数据行（每行含该条推送的完整字段）。"""
    raw = re.sub(r'[ \t]+', ' ', text or '')
    raw = re.sub(r'\n\s*\n', '\n', raw).strip()
    compact = re.sub(r'\s+', '', raw)
    matches = list(_UUID_RE.finditer(compact))
    rows = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(compact)
        rows.append({
            'uid': m.group(0),
            'compact': compact[start:end],
        })
    return {'raw': raw, 'rows': rows}


def _norm_ocr_versions(text):
    """把 OCR 常见的 iOS 误识归一化（I0S / 1OS / 10S / IO0S 等 → iOS）。"""
    text = text or ''
    for v in ('IO0S', 'IOOS', 'I00S', 'I0OS', '1O0S', '1OOS',
              'I0S', '1OS', '10S', 'IOS', 'IoS', 'Ios', 'l0S', 'loS'):
        text = text.replace(v, 'iOS')
    return text


def _backend_version_text(value, platform):
    """后台版本代码转显示文本：1=all，7=不向该端推送。"""
    v = str(value or '').strip()
    if v == '7':
        return '不向%s推送' % ('安卓' if platform == '安卓' else 'iOS')
    if v == '1':
        return 'all'
    return ''


_TARGET_WINDOW = 60  # 只在行首窗口里识别目标词，避免把内容里的相似字误当目标


def _search_source_cut(text):
    """返回标题起点：行首窗口内最后一个命中目标词（含轻度误识）的结束位置。"""
    window = text[:_TARGET_WINDOW]
    last_end = -1
    for word in _TARGET_HINT:
        start = 0
        while True:
            i = window.find(word, start)
            if i == -1:
                break
            last_end = max(last_end, i + len(word))
            start = i + 1
        # 轻度误识：等长、首字符相同、相似 ≥0.5（如 鸿菜→鸿蒙、主苕→主包）
        for i in range(len(window) - len(word) + 1):
            seg = window[i:i + len(word)]
            if seg == word or seg[0] != word[0]:
                continue
            from difflib import SequenceMatcher
            if SequenceMatcher(None, word, seg).ratio() >= 0.5:
                last_end = max(last_end, i + len(word))
    return last_end


def _extract_search_source(row_compact):
    """从行文本提取搜索源：目标词（含误识）之后的标题/内容段。"""
    text = _norm_ocr_versions(_UUID_RE.sub('', row_compact or ''))
    text = re.sub(r'^[^0-9\u4e00-\u9fa5]+', '', text)  # 去掉开头粘连的 uuid 尾部误识字符
    cut = _search_source_cut(text)
    return text[cut:] if cut != -1 else text


def _extract_target_codes(row_compact):
    """从行文本提取目标词对应的后台代码集合。"""
    codes = set()
    for word, code in _TARGET_CODE.items():
        if word in row_compact:
            codes.add(code)
    return codes


def _pick_backend_record(records, target_codes):
    """在候选后台记录中选与邮件行推送目标交集最大的那条；完全相等直接命中。"""
    if not records:
        return None
    target_codes = target_codes or set()
    best = None
    best_score = None
    for r in records:
        back = set(x for x in str(r.get('pushTarget') or '').split(',') if x)
        if back == target_codes:
            return r
        score = (len(back & target_codes),
                 -(len(back | target_codes) - len(back & target_codes)))
        if best_score is None or score > best_score:
            best_score = score
            best = r
    return best


def _fuzzy_contains(needle, haystack, min_ratio=0.72):
    """容错包含匹配：归一化子串命中，或允许少量 OCR 误识（含单字变多字）。"""
    n = pce.normalize_title(needle or '').lower()
    h = pce.normalize_title(haystack or '').lower()
    if not n or not h:
        return False
    if n in h:
        return True
    if len(n) >= 6:
        from difflib import SequenceMatcher
        best = 0.0
        for w in range(max(4, len(n) - 3), len(n) + 4):
            for i in range(len(h) - w + 1):
                ratio = SequenceMatcher(None, n, h[i:i + w]).ratio()
                if ratio > best:
                    best = ratio
        return best >= min_ratio
    return False


def compare_with_backend(rows):
    """按行 × 后台记录反向包含校验：后台记录字段应都能在对应 OCR 行文本中找到。"""
    diffs = []
    matched_records = []
    for idx, row in enumerate(rows, start=1):
        row_compact = _norm_ocr_versions(row['compact'])
        search_source = _extract_search_source(row_compact)
        result = pce.search_push([search_source]) if search_source else None
        records = ((result or {}).get('record') or {}).get('records') or []
        target_codes = _extract_target_codes(row_compact)
        matched = None
        if records:
            if target_codes:
                # 按推送目标交集最大选对应记录（同标题会命中多条不同目标）
                matched = _pick_backend_record(records, target_codes)
            else:
                # 行内没有可识别的目标词 → 按标题子串选第一条
                for r in records:
                    t = pce.normalize_title(r.get('taskTitle') or '').lower()
                    if t and t in pce.normalize_title(row_compact).lower():
                        matched = r
                        break
                if matched is None:
                    matched = records[0]
        if matched is None:
            diffs.append('第 %d 条推送（上报ID=%s）：后台未找到匹配记录' % (idx, row['uid']))
            log('✖ 推送 #%d (uid=%s): 未找到匹配记录' % (idx, row['uid']))
            continue
        matched_records.append(matched)
        log('▶ 推送 #%d (uid=%s): 匹配后台记录 id=%s（目标=%s）'
            % (idx, row['uid'], matched.get('id') or matched.get('taskId') or '',
               matched.get('pushTarget') or ''))

        # 标题
        back_title = matched.get('taskTitle') or ''
        if _fuzzy_contains(back_title, row_compact):
            log('  ✓ 标题: %s' % back_title)
        else:
            log('  ✗ 标题: 邮件行未包含「%s」' % back_title)
            diffs.append('第 %d 条推送标题不一致 → 邮件行未包含后台标题:「%s」'
                         % (idx, back_title))
        # 推送内容
        back_body = matched.get('taskBody') or ''
        if _fuzzy_contains(back_body, row_compact):
            log('  ✓ 内容: %s' % back_body)
        else:
            log('  ✗ 内容: 邮件行未包含「%s」' % back_body)
            diffs.append('第 %d 条推送内容不一致 → 邮件行未包含后台内容:「%s」'
                         % (idx, back_body))
        # 推送目标：集合相等校验（缺/多都报）
        back_codes = set(x for x in str(matched.get('pushTarget') or '').split(',') if x)
        for code in sorted(back_codes | target_codes):
            word = pce.TARGET_NAME.get(code)
            if not word:
                continue
            if code in back_codes and code in target_codes:
                log('  ✓ 目标: %s' % word)
            elif code in back_codes:
                log('  ✗ 目标: 缺少「%s」' % word)
                diffs.append('第 %d 条推送目标缺少「%s」（后台:%s）'
                             % (idx, word, pce.target_names([code])))
            else:
                log('  ✗ 目标: 多出「%s」' % word)
                diffs.append('第 %d 条推送目标多出「%s」（邮件:%s）'
                             % (idx, word, pce.target_names([code])))
        # 安卓版本
        back_android = _backend_version_text(matched.get('versionType'), '安卓')
        if back_android and back_android in row_compact:
            log('  ✓ 安卓版本: %s' % back_android)
        elif back_android:
            log('  ✗ 安卓版本: 邮件行未包含「%s」' % back_android)
            diffs.append('第 %d 条安卓版本不一致 → 邮件行未包含:「%s」' % (idx, back_android))
        # IOS版本
        back_ios = _backend_version_text(matched.get('versionTypeIOS'), 'IOS')
        if back_ios and back_ios in row_compact:
            log('  ✓ iOS版本: %s' % back_ios)
        elif back_ios:
            log('  ✗ iOS版本: 邮件行未包含「%s」' % back_ios)
            diffs.append('第 %d 条IOS版本不一致 → 邮件行未包含:「%s」' % (idx, back_ios))

    return {'matched': matched_records, 'diffs': diffs}


_VISION_PROMPT = (
    "你是表格识别助手。下面是一张「推送后台配置」表格截图。"
    "请逐行读取每一条推送，输出严格的 JSON 数组；每个元素是一个对象，字段为："
    "uid(上报ID, 字符串)、name(推送名称)、target(推送目标, 如'主包'/'黄历'/'鸿蒙'或其组合)、"
    "title(推送标题)、body(推送内容)、android(安卓版本, 如'all'/'不向安卓推送')、"
    "ios(IOS版本, 如'all'/'不向IOS推送')、time(推送时间)、status(推送状态)。"
    "只输出 JSON 数组本身，不要 Markdown 代码块，不要额外说明；看不清的字段填空字符串。"
)


def _strip_code_fence(text):
    text = (text or '').strip()
    fence = re.match(r'^```[a-zA-Z]*\s*', text)
    if fence:
        text = text[fence.end():].strip()
    return re.sub(r'\s*```\s*$', '', text).strip()


def _pick(item, *keys):
    for k in keys:
        v = item.get(k)
        if v not in (None, ''):
            return str(v)
    return ''


def _parse_vision_rows(text):
    """解析视觉模型返回的 JSON 数组为行字典列表；失败返回 None。"""
    import json
    text = _strip_code_fence(text)
    try:
        data = json.loads(text)
    except Exception:
        return None
    if isinstance(data, dict):
        data = data.get('rows') or data.get('data') or []
    if not isinstance(data, list):
        return None
    rows = []
    for item in data:
        if not isinstance(item, dict):
            continue
        rows.append({
            'uid': _pick(item, 'uid', 'uuid', 'id'),
            'name': _pick(item, 'name'),
            'target': _pick(item, 'target', 'pushTarget', 'targets'),
            'title': _pick(item, 'title', 'pushTitle'),
            'body': _pick(item, 'body', 'content', 'pushBody'),
            'android': _pick(item, 'android', 'androidVersion', 'versionType'),
            'ios': _pick(item, 'ios', 'iOS', 'iosVersion', 'versionTypeIOS'),
            'time': _pick(item, 'time', 'pushTime'),
            'status': _pick(item, 'status', 'pushStatus'),
        })
    return rows


def _vision_rows_to_parsed(vrows):
    """把视觉结构化行转成下游统一的 {uid, compact} 结构。"""
    out = []
    for r in vrows:
        parts = [r['name'] or '', r['target'] or '', r['title'] or '',
                 r['body'] or '', r['android'] or '', r['ios'] or '']
        compact = _norm_ocr_versions(re.sub(r'\s+', '', ''.join(parts)))
        out.append({
            'uid': r['uid'] or '', 'compact': compact,
            'name': r['name'], 'target': r['target'], 'title': r['title'],
            'body': r['body'], 'android': r['android'], 'ios': r['ios'],
        })
    return {'raw': '', 'rows': out}


def extract_rows_vision(image_bytes):
    """复用 TestHub Agent 配置的视觉模型从截图提取推送配置行；失败返回 None（调用方回退 OCR）。"""
    try:
        from apps.assistant import sdk_runtime
        from openai import OpenAI
    except Exception:
        return None
    try:
        cfg = sdk_runtime.load_llm_config()
        if not cfg.get('api_key'):
            return None
        import base64
        b64 = base64.b64encode(image_bytes).decode('utf-8')
        base_url = (cfg.get('base_url') or '').rstrip('/') or None
        client = OpenAI(api_key=cfg['api_key'], base_url=base_url, timeout=30, max_retries=0)
        resp = client.chat.completions.create(
            model=cfg['model'],
            messages=[{
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': _VISION_PROMPT},
                    {'type': 'image_url',
                     'image_url': {'url': 'data:image/png;base64,' + b64}},
                ],
            }],
            temperature=0,
        )
        text = (resp.choices[0].message.content) or ''
        rows = _parse_vision_rows(text)
        return _vision_rows_to_parsed(rows) if rows else None
    except Exception as exc:
        log('视觉模型提取失败，回退 OCR：%s' % exc)
        return None


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

    log('[%s] 同步确认检查...' % now.strftime('%Y/%m/%d %H:%M:%S'))

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

    if cfg.get('require_push_activity', True) and not cfg.get('has_push_today', False):
        state.update({'status': 'pending', 'checked_at': now.isoformat()})
        save_state(state)
        log('ℹ 当天无推送对比运行记录，跳过监听，不报超时')
        _last_summary.update({'status': 'pending', 'message': '当天无推送活动，跳过监听'})
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
        if cfg.get('extract_mode') == 'vision_fallback':
            parsed = extract_rows_vision(att['content'])
            if parsed and parsed['rows']:
                log('视觉模型提取到 %d 条推送记录' % len(parsed['rows']))
            else:
                parsed = None
        if parsed is None:
            ocr_text = pce.ocr_image(att['content'])
            if ocr_text:
                parsed = ocr_extract_sync_rows(ocr_text)
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

    rows = parsed['rows']
    if not rows:
        state.update({
            'done': True, 'status': 'fail',
            'mail_uid': email_data['uid'], 'mail_subject': email_data['subject'],
            'checked_at': now.isoformat(),
        })
        save_state(state)
        log('✖ 已收到邮件但 OCR 未解析出推送配置行（图片内容与预期表格结构不符）')
        _last_ok = False
        _last_summary.update({
            'status': 'fail', 'message': '已收到邮件但 OCR 未解析出推送配置行',
            'mail_uid': email_data['uid'], 'mail_subject': email_data['subject'],
        })
        return

    log('OCR 解析到 %d 条推送记录' % len(rows))
    cmp = compare_with_backend(rows)
    diffs = cmp['diffs']
    matched = cmp.get('matched')

    state.update({
        'done': True,
        'status': 'ok' if not diffs else 'fail',
        'mail_uid': email_data['uid'],
        'mail_subject': email_data['subject'],
        'parsed_fields': {'rows': [{'uid': r['uid'], 'compact': r['compact']} for r in rows]},
        'backend_record': matched or [],
        'diffs': diffs,
        'checked_at': now.isoformat(),
    })
    save_state(state)
    _last_summary.update({
        'status': state['status'],
        'mail_uid': email_data['uid'],
        'mail_subject': email_data['subject'],
        'parsed_fields': {'rows': [{'uid': r['uid'], 'compact': r['compact']} for r in rows]},
        'backend_record': matched or [],
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
