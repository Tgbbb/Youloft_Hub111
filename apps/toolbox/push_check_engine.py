# -*- coding: utf-8 -*-
"""
推送邮件监听 + 自动对比 + 自动改时间（由 E:\\daily_check\\watch_push_python\\watch_push.py 移植）

逻辑：
  1. IMAP 找最新的（任意发件人）PUSH + 测试需求 + 非回复邮件
  2. 对比已处理过的邮件（状态存 ToolboxConfig 表），新邮件才处理
  3. 解析 → 对比后台
  4. 通过 → 自动改 taskFireTime = 当前时间-1分钟（立即触发）
  5. 有问题 → 输出问题清单（不修改，等待人工确认）

依赖：仅 Python 标准库（3.8+）。
OCR：需要本机安装 Tesseract-OCR（命令行 tesseract），并确保 tessdata/
     目录包含 chi_sim.traineddata（已随模块附带）。
"""
import email
import email.header
import email.utils
import imaplib
import json
import os
import re
import ssl
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from urllib import parse as up
from urllib.request import Request, urlopen

# Windows 控制台/重定向到文件时统一用 UTF-8，避免 GBK 编码报错（如 '❌'）
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TESSDATA_DIR = os.path.join(BASE_DIR, 'tessdata')

# ============ 引擎配置（由 Celery 任务从 ToolboxConfig 表注入）============
DEFAULT_CONFIG = {
    'imap': {
        'host': 'imap.qiye.aliyun.com',
        'port': 993,
        'user': '',
        'password': '',
        'timeout': 20,
    },
    'backend': {
        'host': '192.168.1.110',
        'port': 8015,
    },
}

_CFG = None
_STATE = None
_log_lines = []
_last_ok = True
_last_summary = {}


def configure(config, state):
    """由运行入口注入配置与已处理状态（来源：ToolboxConfig 表）"""
    global _CFG, _STATE
    _CFG = config or {}
    _STATE = dict(state or {})


def get_config():
    return _CFG or DEFAULT_CONFIG


def load_state():
    if _STATE is not None:
        return _STATE
    return {'lastDate': None, 'lastUid': None, 'processed': [], 'problems': 0}


def save_state(s):
    global _STATE
    _STATE = dict(s or {})


def log(*args):
    """日志收集器：去除 ANSI 颜色码，保存为纯文本运行日志"""
    text = ' '.join(str(a) for a in args)
    text = re.sub(r'\x1b\[[0-9;]*m', '', text)
    _log_lines.append(text)

CLIENT_MAP = {'0': 'iOS', '0,1': 'Android', '2': '鸿蒙', '0,1,2': 'iOS、安卓、鸿蒙'}
# 后台推送目标多选框映射（推导）：0=主包(万年历), 1=黄历, 2=鸿蒙(客户端标识)
APP_MAP = {'0': '万年历', '1': '黄历', '2': '鸿蒙'}
# 版本类别数值映射：1=all，7=不向对应平台推送
ANDROID_VERSION_MAP = {'1': 'all', '7': '不向安卓推送'}
IOS_VERSION_MAP = {'1': 'all', '7': '不向iOS推送'}

# 地区编码映射（后台 citys 字段，多个用逗号分隔）
CITY_MAP = {
    '10101': '北京', '10102': '上海', '10103': '天津', '10104': '重庆',
    '10105': '黑龙江', '10106': '吉林', '10107': '辽宁', '10108': '内蒙古',
    '10109': '河北', '10110': '山西', '10111': '陕西', '10112': '山东',
    '10113': '新疆', '10114': '西藏', '10115': '青海', '10116': '甘肃',
    '10117': '宁夏', '10118': '河南', '10119': '江苏', '10120': '湖北',
    '10121': '浙江', '10122': '安徽', '10123': '福建', '10124': '江西',
    '10125': '湖南', '10126': '贵州', '10127': '四川', '10128': '广东',
    '10129': '云南', '10130': '广西', '10131': '海南', '10132': '香港',
    '10133': '澳门', '10134': '台湾',
}

# 星座/标签编码映射（后台 checkItem 字段，多个用逗号分隔）
ZODIAC_MAP = {
    'pre_aries': '白羊座', 'pre_taurus': '金牛座', 'pre_gemini': '双子座',
    'pre_cancer': '巨蟹座', 'pre_leo': '狮子座', 'pre_virgo': '处女座',
    'pre_libra': '天秤座', 'pre_scorpio': '天蝎座', 'pre_sagittarius': '射手座',
    'pre_capricorn': '摩羯座', 'pre_aquarius': '水瓶座', 'pre_pisces': '双鱼座',
    'pre_unknown': '未知星座',
}


def decode_citys(citys_str):
    if not citys_str:
        return ''
    return '、'.join(CITY_MAP.get(c.strip(), c.strip()) for c in citys_str.split(','))


def decode_check_item(check_str):
    if not check_str:
        return ''
    return '、'.join(ZODIAC_MAP.get(c.strip(), c.strip()) for c in check_str.split(','))


# 推送目标的显示名称：0=主包、1=黄历、2=鸿蒙
TARGET_NAME = {'0': '主包', '1': '黄历', '2': '鸿蒙'}


def target_names(targets):
    names = '、'.join(TARGET_NAME.get(t, t) for t in (targets or []))
    return names or '(未配置)'


# 后台记录的展示标识：优先用后台界面可见的「上报id」(taskId)，无则退回内部 id
def rec_label(r):
    return f"上报id={r['taskId']}" if r and r.get('taskId') else f"id={r['id']}"


# ANSI 颜色（Windows 10+ CMD/PowerShell、VS Code 终端均支持）
_R = '\x1b[31m'; _G = '\x1b[32m'; _Y = '\x1b[33m'; _C = '\x1b[36m'
_D = '\x1b[90m'; _B = '\x1b[1m'; _X = '\x1b[0m'


def _use_color():
    # 输出被重定向（如 run.bat 写入 run_log.txt）时去掉颜色，日志更干净
    if os.environ.get('WATCH_PUSH_NO_COLOR'):
        return False
    return sys.stdout.isatty()


if not _use_color():
    _R = _G = _Y = _C = _D = _B = _X = ''
# 根据邮件行（客户端 + 推送app）推导后台应勾选的推送目标（pushTarget）
# 规则：
#   iOS   + 万年历       → 主包(0)
#   安卓  + 万年历、黄历 → 主包(0)、黄历(1)
#   鸿蒙  + 万年历       → 鸿蒙(2)  ← 鸿蒙端勾的是「鸿蒙」而不是「主包」
def infer_expect_push_target(client, mail_app):
    c = (client or '').strip()
    app_str = re.sub(r'[、,，\s]', '', mail_app or '')
    if c == '鸿蒙':
        return ['2']
    targets = []
    if '万年历' in app_str:
        targets.append('0')  # 主包 = 万年历
    if '黄历' in app_str:
        targets.append('1')  # 黄历
    return sorted(dict.fromkeys(targets))


# 根据推送目标中勾选的 app 组合，推断期望的安卓/iOS 版本类别
# 规则来自业务配置：
#   仅主包(0) → 安卓=不向安卓推送(7)，iOS=all(1)
#   主包+黄历(0,1) → 安卓=all(1)，iOS=不向iOS推送(7)
#   仅鸿蒙(2) → 安卓=all(1)，iOS=不向iOS推送(7)
#   三端(0,1,2) → 安卓=all(1)，iOS=all(1)
_VERSION_RULES = {
    '0':     {'android': '7', 'ios': '1'},
    '0,1':   {'android': '1', 'ios': '7'},
    '2':     {'android': '1', 'ios': '7'},
    '0,1,2': {'android': '1', 'ios': '1'},
}


def infer_version_category(push_target):
    sorted_key = ','.join(sorted(x for x in (push_target or '').split(',') if x))
    return _VERSION_RULES.get(sorted_key)


# 统一客户端名称：邮件解析可能是 iOS/Android/鸿蒙（中英混杂），统一成标准名用于比较
def norm_client(c):
    s = (c or '').strip().lower()
    if 'ios' in s or '苹果' in s:
        return 'iOS'
    if '安卓' in s or 'android' in s:
        return '安卓'
    if '鸿蒙' in s or 'harmony' in s:
        return '鸿蒙'
    return s


# 根据后台记录的 pushTarget（推送目标勾选组合）反推这条记录属于哪个客户端。
# 后台记录没有「客户端」字段，唯一能定位身份的就是推送目标组合：
#   0(主包) → iOS；0,1(主包+黄历) → 安卓；2(鸿蒙) → 鸿蒙
# 返回 'iOS' | '安卓' | '鸿蒙' | '三端' | '异常' | None
def infer_client_from_push_target(push_target):
    sorted_key = ','.join(sorted(x for x in (push_target or '').split(',') if x))
    mapping = {'0': 'iOS', '0,1': '安卓', '2': '鸿蒙', '0,1,2': '三端', '1': '异常'}
    if sorted_key == '':
        return None
    return mapping.get(sorted_key, '异常')


# 标题归一化：忽略标点/空白（含全角空格、引号、括号）
_TITLE_STRIP_RE = re.compile(r'[，,。.!！?？、；;：:\u201c\u201d\u2018\u2019"\'（）()\s]')


def normalize_title(s):
    return _TITLE_STRIP_RE.sub('', s or '')


def _find_key(url):
    m = re.search(r'key=(\d+)', url or '')
    return m.group(1) if m else ''


def extract_url(line):
    m = re.search(r'https?://\S+', line or '')
    if not m:
        return ''
    url = m.group(0)
    after = (line or '')[m.end():]
    suffix = re.match(r'^\s*<https?://[^>]*>\s*(\[[^\]]+\](?:&[^=\s]+=\[[^\]]+\])*)', after)
    if suffix:
        url += suffix.group(1)
    return url


# HTML 实体解码
def decode_html_entities(s):
    return ((s or '')
            .replace('&ldquo;', '\u201c').replace('&rdquo;', '\u201d')
            .replace('&quot;', '"').replace('&amp;', '&')
            .replace('&nbsp;', ' ').replace('&#39;', "'")
            .replace('&lt;', '<').replace('&gt;', '>'))
# 从邮件 HTML 中解析表格：标题/描述/类型/链接是独立单元格，不会被纯文本合并
# 返回 [{ date, title, body, rest, type, platforms: [{time, client, app, region, url, key}] }]
def parse_schedule_html(html):
    pushes = []
    trs = re.findall(r'<tr[^>]*>[\s\S]*?</tr>', html or '')
    if len(trs) < 2:
        return pushes

    rows = []
    for tr in trs:
        tds = re.findall(r'<td[^>]*>[\s\S]*?</td>', tr)
        cells = []
        for td in tds:
            txt = decode_html_entities(re.sub(r'<[^>]+>', '', td))
            txt = re.sub(r'\s+', '', txt).strip()
            rowspan = 1
            colspan = 1
            rm = re.search(r'rowspan="(\d+)"', td)
            cm = re.search(r'colspan="(\d+)"', td)
            if rm:
                rowspan = int(rm.group(1))
            if cm:
                colspan = int(cm.group(1))
            cells.append({'txt': txt, 'rowspan': rowspan, 'colspan': colspan})
        rows.append(cells)

    # rowspan 展开：把每行展开成完整的列数组（被 rowspan 占用的列继承上一行的值）
    def expand(cells, span_map):
        out = []
        ci = 0
        for c in cells:
            while span_map.get(ci) and span_map[ci]['remaining'] > 0:
                out.append(span_map[ci]['txt'])
                span_map[ci]['remaining'] -= 1
                ci += 1
            out.append(c['txt'])
            if c['rowspan'] > 1:
                span_map[ci] = {'txt': c['txt'], 'remaining': c['rowspan'] - 1}
            ci += max(1, c['colspan'])
        while span_map.get(ci) and span_map[ci]['remaining'] > 0:
            out.append(span_map[ci]['txt'])
            span_map[ci]['remaining'] -= 1
            ci += 1
        return out

    header_cols = expand(rows[0], {})

    def col_idx(name):
        for i, c in enumerate(header_cols):
            if name in c:
                return i
        return -1

    i_date = col_idx('日期')
    i_time = col_idx('时间')
    i_client = col_idx('客户端')
    i_app = col_idx('推送App')
    i_region = col_idx('推送地区')
    i_type = col_idx('类型')
    i_title = col_idx('标题')
    i_body = col_idx('描述')
    i_link = col_idx('链接')
    # 没有完整表格 → 走纯文本逻辑
    if i_title < 0 or i_link < 0 or i_time < 0:
        return pushes

    span_map = {}
    current = None
    for r in range(1, len(rows)):
        cols = expand(rows[r], span_map)

        def get_col(i):
            return cols[i] if 0 <= i < len(cols) else ''

        time_ = get_col(i_time)
        if not re.match(r'^\d{1,2}:\d{2}$', time_):
            continue  # 只处理带时间的排期行
        date = get_col(i_date)
        client = get_col(i_client)
        app = get_col(i_app)
        region = get_col(i_region) or get_col(i_region + 1)
        type_ = get_col(i_type)
        title = get_col(i_title)
        body = get_col(i_body)
        url = get_col(i_link)
        key = _find_key(url)

        # 日期变化 → 新的一批推送（同封邮件里可能有多天）
        if not current or (date and date != current['date']):
            # rest 是后台搜索的主要线索：标题 → 描述 → 类型，标题为空时也有内容可搜
            rest = title or body or type_ or ''
            current = {
                'date': date or (current['date'] if current else '') or '',
                'rest': rest, 'title': title, 'body': body, 'type': type_,
                'platforms': [],
            }
            pushes.append(current)
        current['platforms'].append({
            'time': time_, 'client': client, 'app': app,
            'region': region, 'url': url, 'key': key,
        })
    return pushes


def parse_schedule(text, html):
    # 优先用 HTML 表格（标题/描述/类型/链接是独立单元格，纯文本会粘成一行）
    from_html = parse_schedule_html(html)
    if from_html:
        return from_html

    # 回退：纯文本解析（无 HTML 或解析失败时）
    pushes = []
    current = None
    for raw_line in (text or '').split('\n'):
        line = raw_line.strip()
        if not line:
            continue
        is_date_row = bool(re.match(r'^\d{1,2}/\d{1,2}', line))
        is_time_row = bool(re.match(r'^\d{1,2}:\d{2}', line))
        if not is_date_row and not is_time_row:
            continue
        url = extract_url(line)
        cleaned = re.sub(r'<https:[^>]+>', lambda m: m.group(0)[1:-1], line)
        http_idx = cleaned.find('http')
        before = cleaned[:http_idx] if http_idx >= 0 else cleaned[:-1]
        if is_date_row:
            m = re.match(r'^(\d{1,2}/\d{1,2})([一二三四五六日天])(\d{1,2}:\d{2})(iOS|Android|鸿蒙)(万年历、黄历|万年历|黄历)?(all)?(.+)$', before)
            if not m:
                continue
            key = _find_key(url)
            current = {'date': m.group(1), 'rest': m.group(7), 'title': m.group(7), 'platforms': []}
            pushes.append(current)
            current['platforms'].append({
                'time': m.group(3), 'client': m.group(4), 'app': m.group(5) or '',
                'region': m.group(6) or '', 'url': url, 'key': key,
            })
        elif current:
            m = re.match(r'^(\d{1,2}:\d{2})(iOS|Android|鸿蒙)(万年历、黄历|万年历|黄历)?', before)
            if not m:
                continue
            key = _find_key(url)
            current['platforms'].append({
                'time': m.group(1), 'client': m.group(2),
                'app': m.group(3) or current['platforms'][0]['app'],
                'region': current['platforms'][0]['region'],
                'url': url, 'key': key,
            })
    return pushes
def num_status(r):
    """把后台记录的 taskStatus 统一转成数字（后台可能是字符串也可能是数字）"""
    s = r.get('taskStatus') if r else None
    if s in (None, ''):
        return -999
    try:
        return int(s)
    except (TypeError, ValueError):
        return -999


# ============ 3. 后台查询 ============
def get_cookie():
    cfg = get_config() or {}
    c = (cfg.get('push_cookie') or '').strip()
    # cookie 的 key 带日期（TaskControlYYYYMMDD=...），后台按当天日期认；
    # usercheck 校验码是固定的，因此只需把日期段刷新成今天即可（README: Cookie 有效期约1天）
    if c:
        today = datetime.now().strftime('%Y%m%d')
        c = re.sub(r'TaskControl\d{8}', 'TaskControl' + today, c, count=1)
    return c


# 把一个原始关键词扩展成多个候选搜索词（后台 LIKE 模糊匹配，长标题搜不到 → 用短前缀重试）
_SEARCH_PREFIX_STRIP = re.compile(
    r'^(常规|末伏（提前）|农历七月初一|七夕（提前）|立秋躲秋|中伏至|大暑将至|'
    r'世界肝炎日|8月入秋|春节|元宵|清明|端午|中秋|重阳|冬至|腊八|劳动节|国庆)'
)


def build_search_candidates(keyword):
    cleaned = _SEARCH_PREFIX_STRIP.sub('', str(keyword or '')).strip()
    if not cleaned:
        return []
    head_clean = re.sub(r'^[^\u4e00-\u9fa5A-Za-z0-9]+', '', cleaned)
    first_seg_m = re.match(r'^[\u4e00-\u9fa5A-Za-z0-9]{2,8}', head_clean)
    first_seg = first_seg_m.group(0) if first_seg_m else ''
    out = []
    if first_seg:
        out.append(first_seg)
    for l in (10, 20, 30):
        s = head_clean[:l]
        if len(s) >= 4 and s not in out:
            out.append(s)
    # 单字 OCR 误识容错：追加开头 2~3 字前缀，避免「身体有恙」搜不到「身体有癌」
    for l in (3, 2):
        s = head_clean[:l]
        if len(s) >= 2 and s not in out:
            out.append(s)
    if not out:
        out.append(cleaned[:30])
    return out


# 支持多来源搜索：传数组，把每个来源（标题/描述/key…）都展开成候选词，
# 按顺序依次尝试，只要有一个候选词能命中后台记录就算成功。
# 这样即使邮件标题有误（OCR 错字/空格/标点），也能靠描述、key 等其他线索定位到后台记录。
def search_push(sources):
    if not isinstance(sources, (list, tuple)):
        sources = [sources]
    kw_list = []
    for s in sources:
        kw_list.extend(build_search_candidates(s))
    candidates = []
    for kw in kw_list:
        if kw and kw not in candidates:
            candidates.append(kw)
    if not candidates:
        return None

    backend = get_config()['backend']
    for kw in candidates:
        body = up.urlencode({
            'taskTitle': kw, 'taskStatus': '-9', 'pageIndex': '1',
            'pageSize': '30', 'sortField': 'name',
        }).encode('utf-8')
        req = Request(
            'http://%s:%d/Push_Android_Operate/SearchPush_Android_Operate?_t=%d'
            % (backend['host'], int(backend['port']), int(time.time() * 1000)),
            data=body, method='POST',
            headers={
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Cookie': get_cookie(), 'Cache-Control': 'no-cache',
            })
        try:
            with urlopen(req, timeout=30) as resp:
                data = resp.read().decode('utf-8', errors='replace')
            j = json.loads(data)
            if (j.get('succ') and j.get('record') and j['record'].get('records')
                    and len(j['record']['records']) > 0):
                return j
        except Exception:
            continue  # 短词搜不到或出错 → 换下一个候选词
    return None


# ============ 4. 修改时间 ============
def edit_time(rec, new_time):
    def g(*keys, default=''):
        for k in keys:
            if rec.get(k) is not None:
                return rec[k]
        return default

    body = (
        'id=' + str(g('id')) +
        '&taskName=' + up.quote(str(g('taskName'))) +
        '&taskTitle=' + up.quote(str(g('taskTitle'))) +
        '&taskBody=' + up.quote(str(g('taskBody'))) +
        '&url=' + up.quote(str(g('url'))) +
        '&versionType=' + str(g('versionType')) +
        '&versionValues=' + str(g('versionValues')) +
        '&versionTypeIOS=' + str(g('versionTypeIOS')) +
        '&versionValuesIOS=' + str(g('versionValuesIOS')) +
        '&inQueue=' + str(g('inQueue')) +
        '&taskFireTime=' + up.quote(new_time).replace('%20', '+') +
        '&icon=' + up.quote(str(g('icon'))) +
        '&citys=' + str(g('citys')) +
        '&checkItem=' + str(g('checkItem')) +
        '&pushTarget=' + up.quote(str(g('pushTarget')))
    )
    backend = get_config()['backend']
    req = Request(
        'http://%s:%d/Push_Android_Operate/EditPush_Android_Operate'
        % (backend['host'], int(backend['port'])),
        data=body.encode('utf-8'), method='POST',
        headers={
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Cookie': get_cookie(),
        })
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode('utf-8', errors='replace'))
    except Exception:
        return None
# ============ 邮件工具 ============
def decode_mime_words(s):
    """解码 RFC2047 编码的词（如 =?utf-8?B?...?=）"""
    if not s:
        return ''
    try:
        parts = email.header.decode_header(s)
        out = []
        for text, charset in parts:
            if isinstance(text, bytes):
                out.append(text.decode(charset or 'utf-8', errors='replace'))
            else:
                out.append(text)
        return ''.join(out)
    except Exception:
        return s


def get_text_and_html(msg):
    """提取邮件正文 text/plain 与 text/html（与 mailparser 的 text/html 字段对应）"""
    text = ''
    html = ''
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == 'text/plain' and not text:
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or 'utf-8'
                text = payload.decode(charset, errors='replace') if payload else ''
            elif ctype == 'text/html' and not html:
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or 'utf-8'
                html = payload.decode(charset, errors='replace') if payload else ''
    else:
        ctype = msg.get_content_type()
        charset = msg.get_content_charset() or 'utf-8'
        payload = msg.get_payload(decode=True)
        if ctype == 'text/plain':
            text = payload.decode(charset, errors='replace') if payload else ''
        elif ctype == 'text/html':
            html = payload.decode(charset, errors='replace') if payload else ''
    return text, html


def _looks_like_image(payload):
    """按文件头魔数识别图片（兼容部分客户端把图片标成 application/octet-stream）。"""
    if not payload:
        return False
    if payload.startswith(b'\x89PNG\r\n\x1a\n'):
        return True
    if payload.startswith(b'\xff\xd8\xff'):
        return True
    if payload.startswith((b'GIF87a', b'GIF89a')):
        return True
    if payload.startswith(b'BM'):
        return True
    if payload.startswith(b'RIFF') and payload[8:12] == b'WEBP':
        return True
    return False


def get_image_attachments(msg):
    atts = []
    for part in msg.walk():
        ctype = part.get_content_type()
        if ctype and ctype.startswith('image'):
            payload = part.get_payload(decode=True) or b''
            atts.append({'content': payload, 'size': len(payload), 'contentType': ctype})
        elif ctype == 'application/octet-stream':
            payload = part.get_payload(decode=True) or b''
            if _looks_like_image(payload):
                atts.append({'content': payload, 'size': len(payload), 'contentType': ctype})
    return atts


_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
           'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

IMAP_SINCE_DAYS = 2  # 搜最近 2 天


def find_latest_push_email():
    """IMAP 找最新一封 PUSH + 测试需求 + 非回复邮件（任意发件人）"""
    since = datetime.now(timezone.utc) - timedelta(days=IMAP_SINCE_DAYS)
    since_str = '%02d-%s-%d' % (since.day, _MONTHS[since.month - 1], since.year)
    cfg = get_config()
    imap_cfg = cfg['imap']
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

        # 批量取头部（含 UID），按主题筛选候选
        # 注意：imaplib 的 fetch 需要逗号分隔的序号字符串（如 b'1,2,3'），不能传列表
        candidates = []
        fetch_set = b','.join(seqs)
        typ, msg_data = imap.fetch(fetch_set, '(UID BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])')
        if typ == 'OK':
            for item in msg_data:
                if not isinstance(item, tuple):
                    continue
                meta = item[0].decode('utf-8', 'replace')
                um = re.search(r'UID (\d+)', meta)
                if not um:
                    continue
                uid = int(um.group(1))
                header_bytes = item[1] or b''
                msg = email.message_from_bytes(header_bytes)
                subject = decode_mime_words(msg.get('Subject', ''))
                # 发件人不限定（喻坪、唐铬彬等都可），只按主题识别
                if 'PUSH' in subject and '测试需求' in subject and '回复' not in subject:
                    candidates.append((uid, subject))

        if not candidates:
            return None
        latest_uid = max(candidates, key=lambda x: x[0])[0]

        typ, msg_data = imap.uid('fetch', str(latest_uid), '(RFC822)')
        if typ != 'OK' or not msg_data or not isinstance(msg_data[0], tuple):
            return None
        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)

        date_str = msg.get('Date', '')
        parsed_date = email.utils.parsedate_to_datetime(date_str) if date_str else datetime.now(timezone.utc)
        # 与 JS 版 toISOString() 相同格式，便于 state 兼容
        iso = parsed_date.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')

        text, html = get_text_and_html(msg)
        return {
            'uid': latest_uid,
            'date': iso,
            'subject': decode_mime_words(msg.get('Subject', '')),
            'text': text,
            'html': html,
            'attachments': get_image_attachments(msg),
        }
    finally:
        try:
            imap.logout()
        except Exception:
            pass


# ============ OCR（图片附件）============
def find_tesseract():
    cfg = get_config() or {}
    p = (cfg.get('tesseract_path') or '').strip().strip('"')
    if p and os.path.exists(p):
        return p
    p = os.environ.get('TESSERACT_PATH') or ''
    if p and os.path.exists(p):
        return p
    from shutil import which
    p = which('tesseract')
    if p:
        return p
    for cand in (r'C:\Program Files\Tesseract-OCR\tesseract.exe',
                 r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
                 r'E:\ocr\tesseract.exe'):
        if os.path.exists(cand):
            return cand
    return None


def ocr_image(image_bytes):
    """调用本机 Tesseract 识别图片，返回全文（失败返回 None）"""
    tesseract = find_tesseract()
    if not tesseract:
        return None
    tmp = None
    try:
        data = image_bytes
        # 预处理：放大 2x + 灰度 + 增强对比度，显著提升小字号表格/截图的识别率
        try:
            from PIL import Image, ImageEnhance
            import io as _io
            img = Image.open(_io.BytesIO(image_bytes))
            if img.width * img.height <= 2000000:
                img = img.convert('L')
                img = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)
                img = ImageEnhance.Contrast(img).enhance(1.6)
                buf = _io.BytesIO()
                img.save(buf, format='PNG')
                data = buf.getvalue()
        except Exception:
            data = image_bytes
        fd, tmp = tempfile.mkstemp(suffix='.png')
        os.close(fd)
        with open(tmp, 'wb') as f:
            f.write(data)
        cmd = [tesseract, tmp, 'stdout', '--tessdata-dir', TESSDATA_DIR, '-l', 'chi_sim']
        proc = subprocess.run(cmd, capture_output=True, timeout=120)
        return proc.stdout.decode('utf-8', errors='replace')
    except Exception:
        return None
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except Exception:
                pass


def ocr_extract_field(text, start_keywords, stop_keywords):
    """OCR 通用字段提取：支持多种关键字变体，按 stopKeywords 截断"""
    for sk in start_keywords:
        s = text.find(sk)
        if s < 0:
            continue
        content_start = s + len(sk)
        end = len(text)
        for ek in stop_keywords:
            ei = text.find(ek, content_start)
            if ei >= 0 and ei < end:
                end = ei
        val = text[content_start:end]
        val = re.sub(r'^[：:""\u201c\u201d\u2018\u2019`\']\s*', '', val)
        val = re.sub(r'[""\u201c\u201d\u2018\u2019]', '', val).strip()
        if val:
            return val
    return ''


def ocr_extract(text):
    """把 OCR 原文解析成一个推送条目（无 http 关键字则返回 None）"""
    raw = re.sub(r'[ \t]+', ' ', text or '')
    raw = re.sub(r'\n\s*\n', '\n', raw).strip()
    # 提取用：去掉所有空白（OCR 逐字带空格，必须去除才能匹配「标题」等关键字）
    compact = re.sub(r'\s+', '', raw)
    if 'http' not in compact:
        return None

    # URL：从 https:// 开始，截断到第一个中文字符（避免空格导致过早截断）
    url = ''
    https_idx = compact.find('https://')
    if https_idx >= 0:
        rest = compact[https_idx:]
        cn_m = re.search(r'[\u4e00-\u9fa5]', rest)
        cn_idx = cn_m.start() if cn_m else -1
        url = rest[:cn_idx].strip() if cn_idx > 0 else rest.strip()

    # 字段提取（支持简体/繁体/常见 OCR 误识变体）
    client = ocr_extract_field(compact, ['客户端', '客戶端'], ['推送地区', '地区', '标题', '标題', '描述'])
    region = ocr_extract_field(compact, ['推送地区', '地区'], ['标题', '标題', '描述', '链接'])
    title = ocr_extract_field(compact, ['标题', '标題'], ['描述', '链接', '推送app', 'app'])
    body = ocr_extract_field(compact, ['描述'], ['链接', 'https://', '标题'])

    # key 直接在全文搜，不依赖 URL 是否截断正确
    key_m = re.search(r'key=(\d+)', compact)
    key = key_m.group(1) if key_m else ''

    # 备用：如果标题仍为空，在地区之后、描述之前暴力抓一段
    final_title = title
    if not final_title:
        region_idx = compact.find('地区') if compact.find('地区') >= 0 else compact.find('推送地区')
        desc_idx = compact.find('描述')
        if region_idx >= 0 and desc_idx > region_idx:
            skip = 4 if compact.find('推送地区') == region_idx else 2
            final_title = re.sub(r'^[：:\s]+', '', compact[region_idx + skip:desc_idx]).strip()
    # 再备用：如果标题还是空，把整个文本里最长的中文句子当作标题（去掉已知字段关键字）
    if not final_title:
        cn_parts = re.split(r'[，,。!！?？\s]+', compact)
        candidates = [p for p in cn_parts if re.search(r'[\u4e00-\u9fa5]{4,}', p)]
        exclude = ['客户端', '推送地区', '标题', '描述', '链接', '推送app', 'app']
        candidates = [p for p in candidates if not any(e in p for e in exclude)]
        if candidates:
            final_title = candidates[0]

    final_client = re.sub(r'[，,""\u201c\u201d]', '、', client) if client else 'iOS、安卓、鸿蒙'
    final_region = re.sub(r'[""\u201c\u201d]', '', region or 'all').strip()

    return {
        'raw': raw,
        'url': url, 'key': key,
        'title': final_title, 'body': body,
        'client': final_client, 'region': final_region,
    }
# ============ 主流程 ============
def main(force=False):
    global _last_ok
    log('%s[%s] 检查推送邮件...%s' % (_D, datetime.now().strftime('%Y/%m/%d %H:%M:%S'), _X))

    cfg = get_config()
    if not cfg['imap'].get('user') or not cfg['imap'].get('password'):
        log('   %s✖ 未配置 IMAP 账号密码（imap.user / imap.password），请在配置页填写后重试%s' % (_R, _X))
        _last_ok = False
        _last_summary.update({'message': '未配置 IMAP 账号密码', 'email_subject': '',
                              'problems': 0, 'edited': 0, 'skipped': 0})
        return

    email_data = find_latest_push_email()
    if not email_data:
        log('   %sℹ 最近2天无新推送邮件%s' % (_D, _X))
        _last_summary.update({'message': '最近2天无新推送邮件', 'email_subject': '',
                              'problems': 0, 'edited': 0, 'skipped': 0})
        return

    # 已处理过则跳过（--force 可强制重查，方便反复查看比对结果）
    # 判断依据：优先用 uid（邮箱内唯一递增，连发邮件时间戳相同也不会误判）；
    # 旧版本 state 只有 lastDate 时退化为按日期判断（升级后首次运行自动写入 lastUid）
    state = load_state()
    if state.get('lastUid') is not None:
        already_processed = (state['lastUid'] == email_data['uid'])
    else:
        already_processed = (state.get('lastDate') == email_data['date'])
    if not force and already_processed:
        log('   %sℹ 邮件 %s (uid=%s) 已处理过，跳过（加 --force 可强制重查）%s'
              % (_D, email_data['subject'], email_data['uid'], _X))
        _last_summary.update({'message': '邮件已处理过，已跳过（可勾选强制重查）',
                              'email_subject': email_data['subject'],
                              'problems': 0, 'edited': 0, 'skipped': 0})
        return
    if force:
        log('   %s↻ --force 模式：忽略已处理记录，强制重查%s' % (_C, _X))

    log('   %s►%s 发现新邮件: %s (%s)' % (_C, _X, email_data['subject'], email_data['date']))

    pushes = parse_schedule(email_data['text'], email_data['html'])
    if len(pushes) == 0 and email_data['attachments']:
        # 正文无表格 → OCR 图片附件
        log('   %s↻ 正文无表格，OCR 图片附件...%s' % (_D, _X))
        for att in email_data['attachments']:
            if att['size'] < 5000:
                continue  # 跳过小图标
            try:
                text = ocr_image(att['content'])
                if text is None:
                    log('   %s✖ OCR 不可用（未找到 tesseract，或识别失败）%s' % (_R, _X))
                    break
                parsed = ocr_extract(text)
                if parsed is None:
                    continue
                # 输出完整 OCR 原文供调试
                log('   %sOCR 原文:%s' % (_D, _X))
                for ln in parsed['raw'].split('\n'):
                    log('   ' + ln)
                log('   %sOCR 解析:%s 标题=%s' % (_D, _X, parsed['title'] or '(未识别)'))
                log('   %sOCR 解析:%s 描述=%s' % (_D, _X, parsed['body'] or '(未识别)'))
                log('   %sOCR 解析:%s 链接key=%s' % (_D, _X, parsed['key'] or '(未识别)'))
                log('   %sOCR 解析:%s 客户端=%s' % (_D, _X, parsed['client']))
                log('   %sOCR 解析:%s 地区=%s' % (_D, _X, parsed['region']))
                pushes.append({
                    'date': 'OCR',
                    'title': parsed['title'],
                    'body': parsed['body'],
                    'rest': parsed['title'] or parsed['body'] or parsed['key'] or '',
                    'platforms': [{
                        'time': '00:00', 'client': parsed['client'], 'app': '',
                        'region': parsed['region'], 'url': parsed['url'], 'key': parsed['key'],
                    }],
                })
            except Exception as e:
                log('   %s✖ OCR 单附件失败:%s %s' % (_R, _X, e))
    if len(pushes) == 0:
        log('   %s✖ 解析失败（含OCR），请人工查看%s' % (_R, _X))
        state['lastDate'] = email_data['date']
        state['lastUid'] = email_data['uid']
        save_state(state)
        _last_ok = False
        _last_summary.update({'message': '解析失败（含OCR），请人工查看',
                              'email_subject': email_data['subject'],
                              'problems': 0, 'edited': 0, 'skipped': 0})
        return
    log('   %s▸ 解析到 %d 条推送%s' % (_D, len(pushes), _X))

    # 对比
    problems = 0
    skip_count = 0  # 内容通过但状态非待推送而被跳过的记录数
    to_edit = []
    problem_list = []  # 收集所有问题，末尾统一汇总

    for push_idx, p in enumerate(pushes, start=1):
        log('\n   %s─────────────────────────────────────────%s' % (_C, _X))
        log('   %s►%s %s推送 #%d%s  |  %s' % (_C, _X, _B, push_idx, _X, p['date']))
        log('   %s─────────────────────────────────────────%s' % (_C, _X))

        # 先打印邮件侧（解析出来的内容）
        log('   %s▸ 邮件解析结果%s' % (_D, _X))
        if p.get('type'):
            log('      类型 : %s' % p['type'])
        log('      标题 : %s' % (p.get('title') or '(未识别)'))
        log('      描述 : %s' % (p.get('body') or p.get('desc') or '(未识别)'))
        if p.get('platforms'):
            max_client = max([len(pl['client']) for pl in p['platforms']] + [6])
            max_app = max([len(pl.get('app') or '(未识别)') for pl in p['platforms']] + [10])
            for plat in p['platforms']:
                k = _find_key(plat.get('url') or '')
                a = (plat.get('app') or '(未识别)').ljust(max_app)
                r = (plat.get('region') or 'all').ljust(4)
                c = plat.get('client', '').ljust(max_client)
                log('      %s[%s]%s  app:%s  地区:%s  key:%s  →  %s'
                      % (_D, c, _X, a, r, k or '(未识别)', plat.get('url')))

        # 多来源搜索：标题 → 描述 → key，任意一个能命中后台记录即可。
        # 标题有错（OCR 错字/空格/标点差异）也能靠其他线索定位到后台记录。
        search_sources = [p.get('title') or p.get('rest'), p.get('body') or p.get('desc')]
        first_key = p['platforms'][0].get('key')
        if first_key:
            search_sources.append(first_key)
        result = search_push(search_sources)
        matches = []
        if result and result.get('succ'):
            # 保留所有状态的记录进行匹配和对比（不只是待推送）。
            # 但匹配时「待推送」记录优先：同一推送可能因重复配置存在多条记录
            # （旧记录已执行 + 新记录待推送），只有待推送的才是当前真正要处理的那条，
            # 不能因为旧记录排前面就被它抢先匹配。
            all_recs = result['record']['records']
            pending = [r for r in all_recs if num_status(r) == 0]
            others = [r for r in all_recs if num_status(r) != 0]
            matches = pending + others
            if pending and others:
                log('      %sℹ 后台命中 %d 条待推送 + %d 条其他状态，优先匹配待推送%s'
                      % (_D, len(pending), len(others), _X))

        # 不打印后台待执行记录列表，只对比邮件里实际有的推送

        if len(matches) == 0:
            total_returned = len(result['record']['records']) if result and result.get('record') else 0
            mail_title = p.get('title') or p.get('rest') or '(邮件侧未解析到标题)'
            mail_key = p['platforms'][0].get('key') or '(未识别)'

            log('\n      %s✖ 问题：后台未找到该推送%s' % (_R, _X))
            log('         邮件标题：%s' % mail_title)
            log('         邮件描述：%s' % (p.get('body') or p.get('desc') or '(未识别)'))
            log('         邮件key  ：%s' % mail_key)
            log('         已尝试搜索：%s' % ' / '.join([s for s in search_sources if s]))
            log('         后台搜索结果：%d 条' % total_returned)
            if total_returned > 0 and result and result.get('record') and result['record'].get('records'):
                # 只列出最相似的一条供参考，不罗列全部待执行
                best = result['record']['records'][0]
                bk = _find_key(best.get('url') or '')
                log('         后台最相似记录：标题「%s」 key:%s' % (best.get('taskTitle'), bk))

            msg = '推送 #%d: 后台未找到匹配记录（邮件标题「%s」 key=%s）' % (push_idx, mail_title, mail_key)
            problem_list.append(msg)
            problems += 1
            continue

        # 版本类别（versionType/versionTypeIOS）是后台每条记录独立的字段，
        # 在下面每个平台行内按「该行期望的推送目标」单独推断检查

        used_ids = set()  # 已检查过的后台记录 id（无论是否匹配成功，都不让其他行重复检查）
        for plat in p['platforms']:
            email_key = plat.get('key') or _find_key(plat.get('url') or '')
            want_client = norm_client(plat.get('client', ''))
            # 匹配范围：只查「待推送」记录。已执行记录不参与匹配——
            # 因为旧的已执行记录内容是正确的，如果 fallback 到它，会掩盖
            # 「今天该客户端未配置待推送记录」的问题。
            pending_recs = [r for r in matches if num_status(r) == 0 and r['id'] not in used_ids]
            other_recs = [r for r in matches if num_status(r) != 0 and r['id'] not in used_ids]
            ptitle = p.get('title')

            def title_eq(r):
                return bool(ptitle) and normalize_title(r.get('taskTitle') or '') == normalize_title(ptitle)

            def title_like(r):
                n_mail = normalize_title(ptitle)
                n_back = normalize_title(r.get('taskTitle') or '')
                return bool(ptitle) and (n_back in n_mail or n_mail in n_back)

            def find_first(recs, pred):
                for r in recs:
                    if pred(r):
                        return r
                return None

            matched = None
            diag_msgs = []  # 匹配过程中的诊断信息

            # 步骤1: 待推送记录中按 key 精确匹配
            if email_key and not matched:
                by_key = find_first(pending_recs, lambda r: ('key=%s' % email_key) in (r.get('url') or ''))
                if by_key:
                    used_ids.add(by_key['id'])
                    guess = infer_client_from_push_target(by_key.get('pushTarget'))
                    if guess == want_client:
                        matched = by_key
                    else:
                        diag_msgs.append(
                            '找到待推送记录(%s)但推送目标=「%s」→ 属于【%s】而非【%s】——疑似把 %s 配成了 %s'
                            % (rec_label(by_key),
                               target_names([x for x in (by_key.get('pushTarget') or '').split(',') if x]),
                               guess or '未知', want_client, want_client, guess or '其他端'))

            # 步骤2: 待推送记录中按身份匹配（pushTarget 反推客户端）
            if not matched:
                by_identity = find_first(
                    pending_recs, lambda r: infer_client_from_push_target(r.get('pushTarget')) == want_client)
                if by_identity:
                    used_ids.add(by_identity['id'])
                    matched = by_identity
                    if email_key:
                        back_key = _find_key(by_identity.get('url') or '')
                        if back_key != email_key:
                            diag_msgs.append('找到待推送记录(%s)但 key 不一致 → 邮件:%s 后台:%s'
                                             % (rec_label(by_identity), email_key, back_key))

            # 步骤3: 待推送记录中按标题兜底匹配
            if not matched:
                by_title = find_first(pending_recs, lambda r: title_eq(r) or title_like(r))
                if by_title:
                    used_ids.add(by_title['id'])
                    guess = infer_client_from_push_target(by_title.get('pushTarget'))
                    if guess == want_client:
                        matched = by_title
                        if email_key:
                            back_key = _find_key(by_title.get('url') or '')
                            if back_key != email_key:
                                diag_msgs.append('标题匹配到记录(%s)但 key 不一致 → 邮件:%s 后台:%s'
                                                 % (rec_label(by_title), email_key, back_key))
                    else:
                        diag_msgs.append(
                            '找到待推送记录(%s)但推送目标=「%s」→ 属于【%s】而非【%s】——疑似把 %s 配成了 %s'
                            % (rec_label(by_title),
                               target_names([x for x in (by_title.get('pushTarget') or '').split(',') if x]),
                               guess or '未知', want_client, want_client, guess or '其他端'))

            # 输出诊断信息（匹配成功前发现的异常）——去重，同一条异常只报一次
            for m in dict.fromkeys(diag_msgs):
                log('      %s▲ [%s] %s%s' % (_Y, plat.get('client') or '', m, _X))

            # 未找到待推送记录 → 明确报错，同时列出已执行旧记录和现有待推送记录供参考
            if not matched:
                old_rec = find_first(
                    other_recs, lambda r: infer_client_from_push_target(r.get('pushTarget')) == want_client)
                if old_rec:
                    old_key = _find_key(old_rec.get('url') or '')
                    log('      %s✖ [%s] 未找到待推送记录（找到已执行旧记录 %s, key=%s）——请确认今天是否已配置%s'
                          % (_R, plat.get('client') or '', rec_label(old_rec), old_key, _X))
                else:
                    log('      %s✖ [%s] 未找到待推送记录——请确认今天是否已配置%s'
                          % (_R, plat.get('client') or '', _X))
                if pending_recs:
                    log('         %s后台现有待推送记录:%s' % (_D, _X))
                    for r in pending_recs:
                        rk = _find_key(r.get('url') or '')
                        guess = infer_client_from_push_target(r.get('pushTarget'))
                        log('           %s- %s%s 推送目标=「%s」 key=%s → 属于【%s】'
                              % (_D, _X, rec_label(r),
                                 target_names([x for x in (r.get('pushTarget') or '').split(',') if x]),
                                 rk, guess or '未知'))
                problem_list.append('[%s] 未找到待推送记录——请确认今天是否已配置' % (plat.get('client') or ''))
                problems += 1
                continue
            # 逐项对比，直接列出差异
            issues = []
            back_key = _find_key(matched.get('url') or '')
            skip_edit = False  # 状态非待推送 → 内容检查照做，但禁止修改该记录

            # 0. 状态检查（仅警告，不阻断：可能之前已执行过、今天重新配置，仍需对比内容检查）
            st = num_status(matched)
            if st != 0:
                status_map = {'0': '待推送', '1': '已推送/已执行', '-1': '已过期', '-2': '已取消'}
                log('      %s▲ [%s] 后台状态不是待推送（当前状态：%s）——仅提醒，继续检查内容%s'
                      % (_Y, plat.get('client') or '', status_map.get(str(st), str(st)), _X))
                skip_edit = True

            # 1. 标题对比：先看实质文字差异（归一化忽略标点/空白），再看格式差异（首尾空格、标点）
            if ptitle:
                mail_title_raw = ptitle.strip()
                back_title_raw = (matched.get('taskTitle') or '').strip()
                n_mail = normalize_title(mail_title_raw)
                n_back = normalize_title(back_title_raw)
                if n_mail != n_back:
                    # 实质文字差异
                    if n_mail in n_back:
                        # 后台标题包含完整邮件标题 → 后台多了字
                        idx = n_back.index(n_mail)
                        extra = n_back[:idx] + n_back[idx + len(n_mail):]
                        issues.append('标题不一致 → 邮件:「%s」 后台:「%s」（后台多了「%s」）'
                                      % (mail_title_raw, back_title_raw, extra))
                    elif n_back in n_mail:
                        # 邮件标题包含完整后台标题 → 邮件多了字
                        idx = n_mail.index(n_back)
                        extra = n_mail[:idx] + n_mail[idx + len(n_back):]
                        issues.append('标题不一致 → 邮件:「%s」 后台:「%s」（邮件多了「%s」）'
                                      % (mail_title_raw, back_title_raw, extra))
                    elif n_mail in n_back:
                        # 后台标题包含完整邮件标题 → 后台多了字
                        idx = n_back.index(n_mail)
                        extra = n_back[:idx] + n_back[idx + len(n_mail):]
                        issues.append('标题不一致 → 邮件:「%s」 后台:「%s」（后台多了「%s」）'
                                      % (mail_title_raw, back_title_raw, extra))
                    else:
                        issues.append('标题不一致 → 邮件:「%s」 后台:「%s」' % (mail_title_raw, back_title_raw))
                elif (matched.get('taskTitle') or '') != ptitle:
                    # 归一化后文字相同、但原始串不同 → 格式差异（首尾空格/标点）
                    # 邮件侧标题解析时已去除所有空白，因此这里的差异基本都来自后台
                    if mail_title_raw == back_title_raw:
                        # 仅首尾空格差异（trim 后内容完全一致）
                        lead_b = len(re.match(r'^\s*', matched.get('taskTitle') or '').group(0))
                        tail_b = len(re.search(r'\s*$', matched.get('taskTitle') or '').group(0))
                        issues.append('标题格式差异（仅空格）→ 邮件:「%s」 后台:「%s」〔后台前后多余空格 %d 个〕'
                                      % (ptitle, matched.get('taskTitle') or '', lead_b + tail_b))
                    else:
                        issues.append('标题格式差异（空格/标点）→ 邮件:「%s」 后台:「%s」〔文字相同，仅空格或标点不同〕'
                                      % (ptitle, matched.get('taskTitle') or ''))

            # 2. 描述对比（邮件描述 vs 后台 taskBody）——保留原始标点，不 normalize，确保 "？" 等差异能被检出
            mail_body = (p.get('body') or p.get('desc') or '').strip()
            back_body = (matched.get('taskBody') or '').strip()
            if mail_body and back_body and mail_body != back_body:
                # 若差异只是尾部数字差异（OCR 常把末尾标点误识成数字），归为 OCR 误差
                if re.sub(r'\d+$', '', mail_body) == back_body or re.sub(r'\d+$', '', back_body) == mail_body:
                    log('      %s▲ [%s] 描述疑似OCR误差 → 邮件:「%s」 后台:「%s」（以标题匹配为准）%s'
                          % (_Y, plat.get('client') or '', mail_body, back_body, _X))
                else:
                    # 计算具体差异（前后缀）
                    diff_info = ''
                    if back_body.startswith(mail_body) and len(back_body) > len(mail_body):
                        diff_info = '（后台多了「%s」）' % back_body[len(mail_body):]
                    elif mail_body.startswith(back_body) and len(mail_body) > len(back_body):
                        diff_info = '（邮件多了「%s」）' % mail_body[len(back_body):]
                    issues.append('描述不一致 → 邮件:「%s」 后台:「%s」%s' % (mail_body, back_body, diff_info))

            # 2.1 后台描述前后空白检测（粘贴时常带入空格/制表符）
            back_body_raw = matched.get('taskBody') or ''
            if back_body_raw != back_body_raw.strip():
                lead_n = len(re.match(r'^\s*', back_body_raw).group(0))
                tail_n = len(re.search(r'\s*$', back_body_raw).group(0))
                issues.append('描述前后有多余空白（前 %d 个 / 后 %d 个）→ 后台:「%s」'
                              % (lead_n, tail_n, back_body_raw.strip()))

            # 3. 推送目标对比：邮件行(客户端+app) → 期望 pushTarget，与后台实际勾选对比
            expect_targets = infer_expect_push_target(plat.get('client', ''), plat.get('app', ''))
            actual_targets = sorted([x for x in (matched.get('pushTarget') or '').split(',') if x])
            if expect_targets and ','.join(expect_targets) != ','.join(actual_targets):
                issues.append('推送目标不一致 → 邮件期望:「%s」 后台:「%s」'
                              % (target_names(expect_targets), target_names(actual_targets)))

            # 3.5 版本类别对比（安卓版本类别 / iOS版本类别）——每条后台记录独立检查：
            # 后台 iOS/安卓/鸿蒙 是三条独立记录，各自有独立的 versionType/versionTypeIOS，
            # 不能按整封邮件的并集来查。期望值来自「该行邮件内容推导的推送目标」（用户规则）：
            #   主包 → 安卓=不向安卓推送(7)、iOS=all(1)
            #   主包+黄历 → 安卓=all(1)、iOS=不向iOS推送(7)
            #   鸿蒙 → 安卓=all(1)、iOS=不向iOS推送(7)
            row_expect_targets = infer_expect_push_target(plat.get('client', ''), plat.get('app', ''))
            rule_source = ','.join(row_expect_targets) if row_expect_targets else ','.join(actual_targets)
            ver_rule = infer_version_category(rule_source)
            if ver_rule:
                back_android = str(matched.get('versionType') or '')
                back_ios = str(matched.get('versionTypeIOS') or '')
                if back_android != ver_rule['android']:
                    issues.append('安卓版本类别不一致 → 期望:安卓版本类别=「%s」 后台:安卓版本类别=「%s」'
                                  % (ANDROID_VERSION_MAP.get(ver_rule['android'], ver_rule['android']),
                                     ANDROID_VERSION_MAP.get(back_android, back_android)))
                if back_ios != ver_rule['ios']:
                    issues.append('iOS版本类别不一致 → 期望:iOS版本类别=「%s」 后台:iOS版本类别=「%s」'
                                  % (IOS_VERSION_MAP.get(ver_rule['ios'], ver_rule['ios']),
                                     IOS_VERSION_MAP.get(back_ios, back_ios)))
            # 4. key 对比（OCR 常把 &参数 误识为数字粘到 key 后，如 34519&loc → 3451981，需容错）
            if email_key and back_key and email_key != back_key:
                if email_key.startswith(back_key) or back_key.startswith(email_key):
                    log('      %s▲ [%s] 链接key疑似OCR误差 → 邮件:%s 后台:%s（以标题匹配为准）%s'
                          % (_Y, plat.get('client') or '', email_key, back_key, _X))
                else:
                    # 带身份信息帮助定位：该后台记录的推送目标反推是哪端
                    id_guess = infer_client_from_push_target(matched.get('pushTarget'))
                    id_hint = ''
                    if id_guess and id_guess != norm_client(plat.get('client', '')):
                        id_hint = ('（该记录推送目标=「%s」→ 属【%s】，确认是否把 %s 的 key 填到了 %s）'
                                   % (target_names(actual_targets), id_guess, id_guess,
                                      norm_client(plat.get('client', ''))))
                    issues.append('链接key不一致 → 邮件:%s 后台:%s%s' % (email_key, back_key, id_hint))

            # 4.1 完整链接对比（key 只是 url 的一部分，域名/路径/参数也可能配错）
            mail_url = (plat.get('url') or '').strip()
            back_url = (matched.get('url') or '').strip()
            if mail_url and back_url and mail_url != back_url:
                try:
                    mu = up.urlparse(mail_url)
                    bu = up.urlparse(back_url)
                    url_diffs = []
                    if mu.hostname != bu.hostname:
                        url_diffs.append('域名不同 → 邮件:%s 后台:%s' % (mu.hostname, bu.hostname))
                    if mu.path != bu.path:
                        url_diffs.append('路径不同 → 邮件:%s 后台:%s' % (mu.path, bu.path))
                    mp = up.parse_qsl(mu.query, keep_blank_values=True)
                    bp = up.parse_qsl(bu.query, keep_blank_values=True)

                    def qs_get(pairs, key):
                        for k, v in pairs:
                            if k == key:
                                return v
                        return None

                    def qs_has(pairs, key):
                        return any(k == key for k, _ in pairs)

                    for k, v in mp:
                        if not qs_has(bp, k):
                            url_diffs.append('参数缺失 → 后台缺少「%s=%s」' % (k, v))
                        elif qs_get(bp, k) != v:
                            url_diffs.append('参数值不同 → %s:邮件=「%s」 后台=「%s」' % (k, v, qs_get(bp, k)))
                    for k, v in bp:
                        if not qs_has(mp, k):
                            url_diffs.append('参数多余 → 后台多了「%s=%s」' % (k, v))
                    if url_diffs:
                        issues.append('链接url不一致（%s）' % '；'.join(url_diffs))
                    else:
                        # 域名/路径/参数全一致但字符串不同 → 可能是参数顺序或编码差异，只提醒
                        log('      %s▲ [%s] 链接url有细微差异（参数顺序/编码）→ 以key为准%s'
                              % (_Y, plat.get('client') or '', _X))
                except Exception:
                    issues.append('链接url不一致 → 邮件:「%s」 后台:「%s」' % (mail_url, back_url))

            # 4.2 后台链接前后空白检测（粘贴时常带制表符/空格，会导致跳转链接异常）
            back_url_raw = matched.get('url') or ''
            if back_url_raw != back_url_raw.strip():
                lead_m = re.match(r'^\s*', back_url_raw).group(0)
                tail_n = len(re.search(r'\s*$', back_url_raw).group(0))
                lead_kind = '制表符' if '\t' in lead_m else '空格'
                issues.append('后台链接前后有多余空白（前 %s%d 个 / 后 %d 个）→ 链接:「%s」'
                              % (lead_kind, len(lead_m), tail_n, back_url_raw.strip()))

            # 5. 地区对比（邮件"推送地区" vs 后台 citys）
            mail_region = (plat.get('region') or '').strip()
            back_citys = (matched.get('citys') or '').strip()
            back_region_text = decode_citys(back_citys) or '(未配置/全国)'
            # 邮件地区为 all 或空 = 全国推送，后台 citys 应为空
            if mail_region.lower() == 'all' or not mail_region:
                if back_citys:
                    issues.append('地区不一致 → 邮件:全国(all) 后台:「%s」〔后台限制了地区〕' % back_region_text)
            else:
                # 邮件有具体地区要求时，简单归一化比较
                n_mail_reg = re.sub(r'[、,\s]', '', mail_region)
                n_back_reg = re.sub(r'[、,\s]', '', back_region_text)
                if n_mail_reg != n_back_reg and n_mail_reg != back_citys:
                    issues.append('地区不一致 → 邮件:「%s」 后台:「%s」' % (mail_region, back_region_text))

            # 6. 星座/标签对比（后台 checkItem）
            # 邮件表格无星座列 → 默认不限制星座，后台 checkItem 应为空
            back_check_item = (matched.get('checkItem') or '').strip()
            if back_check_item:
                back_zodiac_text = decode_check_item(back_check_item)
                issues.append('星座/标签不一致 → 邮件:未限制 后台:「%s」〔后台限制了星座/标签〕' % back_zodiac_text)

            if issues:
                for i in issues:
                    log('      %s✖ [%s] %s%s' % (_R, plat.get('client') or '', i, _X))
                    problem_list.append('[%s] %s' % (plat.get('client') or '', i))
                    problems += 1  # 每个子问题单独计数
            else:
                log('      %s✔ [%s] 通过%s' % (_G, plat.get('client') or '', _X))
                if skip_edit:
                    skip_count += 1
                    log('      %s→ [%s] 内容通过，但状态不是待推送，跳过修改（不修改已执行/过期/取消的记录）%s'
                          % (_D, plat.get('client') or '', _X))
                else:
                    to_edit.append({'rec': matched})

    if problems > 0:
        log('\n   %s─────────────────────────────────────────%s' % (_Y, _X))
        log('   %s▲ 发现 %d 处问题，不修改，请人工确认：%s' % (_Y, problems, _X))
        log('   %s─────────────────────────────────────────%s' % (_Y, _X))
        for i, p_item in enumerate(problem_list, start=1):
            log('   %s%2d.%s %s' % (_Y, i, _X, p_item))
        # 记录状态（标记问题邮件）
        state['lastDate'] = email_data['date']
        state['lastUid'] = email_data['uid']
        state['problems'] = problems
        save_state(state)
        _last_ok = False
        _last_summary.update({'message': '发现 %d 处问题，不修改，请人工确认' % problems,
                              'email_subject': email_data['subject'],
                              'problems': problems, 'edited': 0, 'skipped': skip_count})
        return

    if len(to_edit) == 0:
        log('   %s▲ 无待修改的推送%s%s' % (_Y, _X,
              '%s（%d 条内容通过但状态非待推送，已跳过修改）%s' % (_D, skip_count, _X) if skip_count > 0 else ''))
        state['lastDate'] = email_data['date']
        state['lastUid'] = email_data['uid']
        save_state(state)
        _last_summary.update({'message': '无待修改的推送' + ('（%d 条内容通过但状态非待推送，已跳过修改）' % skip_count if skip_count else ''),
                              'email_subject': email_data['subject'],
                              'problems': 0, 'edited': 0, 'skipped': skip_count})
        return

    # 全通过 → 自动改时间 = 当前时间-1分钟
    now = datetime.now() - timedelta(minutes=1)
    new_time = now.strftime('%Y-%m-%d %H:%M:00')
    log('\n   %s✔ 对比全部通过，自动修改 %d 条 → %s%s' % (_G, len(to_edit), new_time, _X))
    if skip_count > 0:
        log('   %s→ 另有 %d 条内容通过但状态非待推送，已跳过修改%s' % (_D, skip_count, _X))
    for t in to_edit:
        r = edit_time(t['rec'], new_time)
        ok = bool(r and r.get('Success'))
        log('      %s%s%s %s (id:%s)' % (_G if ok else _R, '✔' if ok else '✖', _X,
                                           t['rec'].get('taskTitle'), t['rec'].get('id')))
    state['lastDate'] = email_data['date']
    state['lastUid'] = email_data['uid']
    state['problems'] = 0
    save_state(state)
    log('   %s✔ 完成%s' % (_G, _X))
    _last_summary.update({'message': '对比全部通过，自动修改 %d 条推送时间' % len(to_edit),
                          'email_subject': email_data['subject'],
                          'problems': 0, 'edited': len(to_edit), 'skipped': skip_count})


def run_push_check_engine(force=False, config=None, state=None):
    """由 Celery 任务调用的入口：配置与状态来自数据库，返回结构化结果。"""
    global _last_ok, _last_summary
    _log_lines.clear()
    configure(config, state)
    _last_ok = True
    _last_summary = {'message': '', 'email_subject': '',
                     'problems': 0, 'edited': 0, 'skipped': 0}
    try:
        main(force=force)
    except Exception as exc:
        log('❌ %s' % exc)
        _last_ok = False
        _last_summary['message'] = str(exc)
    return {
        'ok': _last_ok,
        'summary': _last_summary,
        'log': '\n'.join(_log_lines),
        'state': dict(load_state()),
    }
