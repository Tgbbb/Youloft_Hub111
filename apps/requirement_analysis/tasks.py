"""需求分析 Celery 异步任务"""
import logging
import os
import re
import shutil
import threading
import uuid
import urllib.parse
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from apps.requirement_analysis.models import AxureImport, ModaoImport, PrdImport

logger = logging.getLogger(__name__)

STAGE_BASE_PROGRESS = {'prepare': 5, 'login': 15, 'list': 25}


def _cleanup_failed_import_screenshots(import_id: str):
    """导入失败/中断时清理本次截图目录，避免残留孤儿文件"""
    if not import_id or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', import_id):
        return
    root = os.path.realpath(os.path.join(settings.MEDIA_ROOT, 'modao_screenshots'))
    target = os.path.realpath(os.path.join(root, import_id))
    if target.startswith(root + os.sep) and os.path.isdir(target):
        shutil.rmtree(target, ignore_errors=True)
        logger.info(f'[Modao] 导入失败，已清理截图目录: {target}')


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
    # 截图目录 id（12 位 hex），与数据库主键 import_id 参数区分开，避免遮蔽
    screenshot_dir_id = uuid.uuid4().hex[:12]

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
                rec = ModaoImport.objects.get(pk=record.id)
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
                    import_id=screenshot_dir_id,
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
        logger.info(f'[Modao] 异步导入完成: import_id={screenshot_dir_id}, {len(result.get("canvases", []))}画布')

    except Exception as exc:
        stop_event.set()
        persist_thread.join(timeout=2)
        _cleanup_failed_import_screenshots(screenshot_dir_id)
        record.status = 'failed'
        record.stage = 'failed'
        record.error_message = str(exc)[:1000]
        detail = build_detail()
        detail['stage'] = 'failed'
        detail['message'] = str(exc)[:1000]
        record.progress_detail = detail
        record.save(update_fields=['status', 'stage', 'error_message', 'progress_detail'])
        logger.error(f'[Modao] 异步导入失败: import_id={screenshot_dir_id}, error={exc}')
        raise


def _cleanup_failed_axure_screenshots(import_id: str):
    """Axure 导入失败/中断时清理本次下载的图片目录"""
    if not import_id or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', import_id):
        return
    root = os.path.realpath(os.path.join(settings.MEDIA_ROOT, 'axure_screenshots'))
    target = os.path.realpath(os.path.join(root, import_id))
    if target.startswith(root + os.sep) and os.path.isdir(target):
        shutil.rmtree(target, ignore_errors=True)
        logger.info(f'[Axure] 导入失败，已清理截图目录: {target}')


def _cleanup_failed_prd_screenshots(import_id: str):
    """PRD 导入失败/中断时清理本次下载的图片目录"""
    if not import_id or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', import_id):
        return
    root = os.path.realpath(os.path.join(settings.MEDIA_ROOT, 'prd_screenshots'))
    target = os.path.realpath(os.path.join(root, import_id))
    if target.startswith(root + os.sep) and os.path.isdir(target):
        shutil.rmtree(target, ignore_errors=True)
        logger.info(f'[PRD] 导入失败，已清理截图目录: {target}')


def _axure_abs(parsed, rel: str):
    """把页面相对路径安全拼成 entry 同源绝对 URL；非法返回 None。
    入口路径可能已 URL 编码（如 %20），先 unquote 再统一 quote，避免双重编码。"""
    rel_clean = (rel or '').split('#')[0].split('?')[0].replace('\\', '/').strip('/')
    if not rel_clean or rel_clean.startswith(('//', 'http:', 'https:', 'data:')):
        return None
    segs = rel_clean.split('/')
    if '..' in segs or any(not s for s in segs):
        return None
    raw_path = parsed.path.rstrip('/')
    if parsed.path.endswith('/'):
        # 目录型入口（如 .../xxx/），目录本身就是 base
        base = raw_path
    else:
        # 文件型入口（如 .../xxx/index.html），去掉文件名
        base = raw_path.rsplit('/', 1)[0] if '/' in raw_path else ''
    joined = (base + '/' + rel_clean).lstrip('/')
    quoted = urllib.parse.quote(
        urllib.parse.unquote(joined), safe='/:@&=+$,;~*()!'
    )
    return f'{parsed.scheme}://{parsed.netloc}/' + quoted


def _axure_fetch(url: str) -> bytes:
    import urllib.request
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        final = urllib.parse.urlparse(r.geturl())
        if final.scheme not in ('http', 'https'):
            raise ValueError('子请求被重定向到非 http(s)，已拒绝')
        return r.read()


def _axure_launch_kwargs() -> dict:
    """查找本机可用的 Chrome/Chromium 启动参数（系统 Chrome 或 ms-playwright 缓存）"""
    chrome_paths = [
        r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
        os.path.expanduser(r'~\AppData\Local\Google\Chrome\Application\chrome.exe'),
    ]
    import glob
    chrome_paths += glob.glob(
        os.path.expandvars(r'%LOCALAPPDATA%\ms-playwright\chromium-*\chrome-win64\chrome.exe')
    )
    chrome_paths += glob.glob(
        os.path.expandvars(r'%LOCALAPPDATA%\ms-playwright\chromium_headless_shell-*\chrome-headless-shell-win64\chrome-headless-shell.exe')
    )
    chrome_path = next((p for p in chrome_paths if os.path.exists(p)), None)
    launch_args = {'headless': True, 'args': ['--no-sandbox', '--disable-gpu']}
    if chrome_path:
        launch_args['executable_path'] = chrome_path
    return launch_args


def _fetch_axure_sitemap(url: str, progress_callback=None) -> tuple:
    """打开 Axure 入口页，从 $axure.document.sitemap 提取页面树。返回 (root_nodes, title)"""
    import asyncio
    from playwright.async_api import async_playwright

    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        raise ValueError('仅支持 http/https 的 Axure 原型链接')

    async def run():
        async with async_playwright() as p:
            browser = await p.chromium.launch(**_axure_launch_kwargs())
            try:
                page = await browser.new_page()
                await page.goto(url, wait_until='networkidle', timeout=90000)
                roots = await page.evaluate(
                    """() => {
                        const walk = (ns) => (ns || []).map(n => ({
                            id: n.id, pageName: n.pageName, url: n.url,
                            type: n.type, children: walk(n.children)
                        }));
                        const sitemap = window.$axure && $axure.document && $axure.document.sitemap;
                        return walk((sitemap && sitemap.rootNodes) || []);
                    }"""
                )
                return roots or []
            finally:
                await browser.close()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        roots = loop.run_until_complete(run())
    finally:
        loop.close()

    if not roots:
        raise ValueError('链接不是有效的 Axure 原型包（未找到 $axure.document.sitemap 页面列表）')
    title = ''
    for n in roots:
        if n.get('pageName'):
            title = n['pageName']
            break
    logger.info(f'[Axure] 解析到页面树: {len(roots)} 个根节点, title={title}')
    return roots, title


def _walk_axure_nodes(nodes, folder: str, out: list):
    """把 sitemap 树拍平成画布列表（Folder 无 url 只做分组；页面带子页时子页以父子路径分组）"""
    for n in nodes or []:
        if not isinstance(n, dict):
            continue
        name = (n.get('pageName') or '').strip() or (n.get('url') or '未命名')
        url = (n.get('url') or '').strip()
        children = n.get('children') or []
        if url:
            out.append({'name': name, 'folder': folder, 'url': url})
            child_folder = f'{folder}/{name}' if folder else name
            _walk_axure_nodes(children, child_folder, out)
        else:
            child_folder = f'{folder}/{name}' if folder else name
            _walk_axure_nodes(children, child_folder, out)


def _convert_svgs_to_png(items: list) -> dict:
    """用 Chromium 把 SVG bytes 渲染为 PNG。items: [(name, svg_bytes)] →
    返回 {name: (png_bytes, width, height)}（仅成功项）"""
    import base64 as _b64
    from playwright.sync_api import sync_playwright

    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(**_axure_launch_kwargs())
        try:
            page = browser.new_page()
            for name, data in items:
                try:
                    b64 = _b64.b64encode(data).decode()
                    html_doc = (
                        '<html><head><style>html,body{margin:0;padding:0;overflow:hidden}'
                        'img{display:block}</style></head>'
                        f'<body><img id="s" src="data:image/svg+xml;base64,{b64}"></body></html>'
                    )
                    page.set_content(html_doc, timeout=15000)
                    dims = page.evaluate(
                        '() => { const i = document.getElementById("s"); '
                        'const r = i.getBoundingClientRect(); '
                        'return {w: Math.max(1, Math.round(r.width)), h: Math.max(1, Math.round(r.height))}; }'
                    )
                    if not dims or dims.get('w', 0) <= 0 or dims.get('h', 0) <= 0:
                        continue
                    shot = page.screenshot(clip={
                        'x': 0, 'y': 0,
                        'width': dims['w'] + 2,
                        'height': dims['h'] + 2,
                    })
                    results[name] = (shot, dims['w'], dims['h'])
                except Exception as exc:
                    logger.warning(f'[Axure] SVG 转 PNG 失败 {name}: {exc}')
        finally:
            try:
                browser.close()
            except Exception:
                pass
    return results


def _extract_axure_page(parsed, page: dict, img_dir: str) -> dict:
    """提取单个 Axure 页面：原生文字（坐标排序）+ UI 图片组件（下载落盘）"""
    from io import BytesIO
    from bs4 import BeautifulSoup
    from PIL import Image

    page_url = _axure_abs(parsed, page['url'])
    if not page_url:
        raise ValueError('页面 URL 非法')
    html = _axure_fetch(page_url).decode('utf-8-sig', 'ignore')
    soup = BeautifulSoup(html, 'html.parser')

    # 1) 原生文字：div.text 非空且未隐藏
    text_items = []
    for div in soup.select('div.text'):
        style = div.get('style', '') or ''
        if 'display:none' in style or 'visibility: hidden' in style:
            continue
        txt = ' '.join(div.get_text(' ', strip=True).split())
        if not txt:
            continue
        sid = div.get('id', '') or ''
        m = re.match(r'^(u\d+)_text$', sid)
        parent_sid = m.group(1) if m else sid
        text_items.append((parent_sid, txt))

    # 2) 坐标排序：styles.css 中 #uXX { left/top }
    css_pos = {}
    body_width = 0
    try:
        css_rel = f"files/{page['url'].rsplit('.', 1)[0]}/styles.css"
        css_url = _axure_abs(parsed, css_rel)
        if css_url:
            css = _axure_fetch(css_url).decode('utf-8-sig', 'ignore')
            for m in re.finditer(r'#(u\d+)\s*\{([^}]*)\}', css):
                left = re.search(r'left:\s*(-?\d+)px', m.group(2))
                top = re.search(r'top:\s*(-?\d+)px', m.group(2))
                if left and top:
                    css_pos[m.group(1)] = (int(left.group(1)), int(top.group(1)))
            bm = re.search(r'body\s*\{([^}]*)\}', css)
            if bm:
                wm = re.search(r'width:\s*(\d+)px', bm.group(1))
                if wm:
                    body_width = int(wm.group(1))
    except Exception:
        logger.info(f'[Axure] 页面「{page["name"]}」未获取到样式坐标，按 DOM 顺序')

    ordered = sorted(
        text_items,
        key=lambda it: (
            css_pos.get(it[0], (10 ** 9, 10 ** 9))[1],
            css_pos.get(it[0], (0, 10 ** 9))[0],
        ),
    )
    texts = {'body': [t for _, t in ordered], 'sticky': []}

    # 3) UI 图片组件：img.img[src]，下载后过滤小图（表格底图/装饰）；SVG 转 PNG 保留
    screenshots = []
    svg_items = []
    os.makedirs(img_dir, exist_ok=True)
    page_slug = re.sub(r'[^\w\u4e00-\u9fff-]+', '_', page['url'].rsplit('.', 1)[0]) or 'page'
    seen = set()
    for img in soup.select('img.img[src]'):
        src = (img.get('src') or '').strip()
        if not src or 'transparent.gif' in src:
            continue
        img_url = _axure_abs(parsed, src)
        if not img_url:
            continue
        raw_name = src.rsplit('/', 1)[-1]
        fname = f'{page_slug}_{raw_name}'
        if fname in seen:
            continue
        seen.add(fname)
        data = b''
        try:
            data = _axure_fetch(img_url)
            img_obj = Image.open(BytesIO(data))
            w, h = img_obj.size
            if w < 60 or h < 60:
                logger.info(f'[Axure] 过滤装饰小图 {fname}: {w}x{h}')
                continue
            with open(os.path.join(img_dir, fname), 'wb') as f:
                f.write(data)
            screenshots.append({
                'url': f'{settings.MEDIA_URL}axure_screenshots/{os.path.basename(img_dir)}/{fname}',
                'width': w,
                'height': h,
            })
        except Exception as exc:
            head = data[:256].lower()
            if fname.lower().endswith('.svg') or b'<svg' in head:
                svg_items.append((fname, data))
                continue
            logger.warning(f'[Axure] 图片下载/解析失败 {fname}: {exc}')

    if svg_items:
        converted = _convert_svgs_to_png(svg_items)
        for fname, (png_data, w, h) in converted.items():
            if w < 60 or h < 60:
                logger.info(f'[Axure] 过滤 SVG 装饰小图 {fname}: {w}x{h}')
                continue
            out_name = fname.rsplit('.', 1)[0] + '.png'
            with open(os.path.join(img_dir, out_name), 'wb') as f:
                f.write(png_data)
            screenshots.append({
                'url': f'{settings.MEDIA_URL}axure_screenshots/{os.path.basename(img_dir)}/{out_name}',
                'width': w,
                'height': h,
            })

    return {
        'name': page['name'],
        'folder': page.get('folder', ''),
        'texts': texts,
        'screenshots': screenshots,
        'width': body_width,
        'height': 0,
    }


def _prd_extract_module_text(mod):
    """提取单个 requirement-module 的正文：概述 + page-names + 各 doc-section（标题/小标题/条目/表格）"""
    parts = []

    heading = mod.select_one('.module-heading')
    if heading:
        h = heading.select_one('.module-title')
        if h:
            parts.append('【模块】' + h.get_text(' ', strip=True))
        # 概述/负责人等
        overview = heading.get_text(' ', strip=True)
        if overview:
            parts.append(overview)

    for pn in mod.select('.page-name'):
        t = pn.get_text(' ', strip=True)
        if t:
            parts.append('涉及页面：' + t)

    headings = ('h2', 'h3', 'h4', 'h5', 'h6')
    for sec in mod.select('.doc-section'):
        # 按文档顺序输出大标题/小标题/条目/表格单元格，保留原文的分组语义
        for el in sec.find_all(headings + ('p', 'li', 'td')):
            name = el.name
            # 嵌在表格单元格里的节点交给 td 统一输出，避免重复
            if name != 'td' and el.find_parent('td') is not None:
                continue
            if name == 'td':
                t = ' '.join(el.get_text(' ', strip=True).split())
                if t:
                    parts.append('· ' + t)
                continue
            # 含块级子节点的 li 跳过，交给内层节点输出
            if name == 'li' and el.find(['p', 'ul', 'ol', 'li']) is not None:
                continue
            t = ' '.join(el.get_text(' ', strip=True).split())
            if not t:
                continue
            if name in headings:
                # 原标题已带【】/● 标记时保留原样，避免出现【【说明】】这种双层括号
                parts.append(t if t[0] in '【●◆■' else '【' + t + '】')
            else:
                # 去掉行首箭头/项目符号，减少噪音
                parts.append(re.sub(r'^[➢►▶▸▪•·※★\-–—]+\s*', '', t) or t)

    # 去重保序
    seen = set()
    out = []
    for t in parts:
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def _extract_prd_document(html_path: str, img_dir: str, progress_callback=None) -> dict:
    """解析单文件 HTML PRD：返回 {'title', 'modules', 'pages', 'version_info'}。
    pages: [{name, folder(模块名), texts, screenshots}]，模块正文只挂在该模块最后一张原型图上。"""
    from bs4 import BeautifulSoup
    from PIL import Image
    from io import BytesIO
    import base64 as _b64

    with open(html_path, 'rb') as f:
        html = f.read().decode('utf-8', 'ignore')
    soup = BeautifulSoup(html, 'html.parser')

    title = (soup.title.get_text(strip=True) if soup.title else '') or 'PRD文档'
    version_info = {}
    vp = soup.select_one('.version-panel')
    if vp:
        version_info['text'] = vp.get_text(' ', strip=True)[:2000]
        for card in vp.select('.detail-card'):
            t = card.get_text(' ', strip=True)
            if t:
                version_info.setdefault('details', []).append(t[:500])

    # 模块正文（按 data-module-article 键）
    modules = {}
    for mod in soup.select('.requirement-module[data-module-article]'):
        key = mod.get('data-module-article')
        heading = mod.select_one('.module-title')
        name = key
        if heading:
            owner = heading.select_one('.owner-tag')
            if owner:
                owner.extract()
            name = heading.get_text(' ', strip=True) or key
        modules[key] = {'name': name, 'texts': {'body': _prd_extract_module_text(mod), 'sticky': []}}

    for _mk, _mv in modules.items():
        logger.info(f'[PRD] 模块「{_mv["name"]}」提取正文 {len(_mv["texts"]["body"])} 条')

    # 原型页：prototype-item 与模块、内嵌 base64 图片
    os.makedirs(img_dir, exist_ok=True)
    pages = []
    failed = 0
    for item in soup.select('.prototype-group .prototype-item'):
        pid = item.get('id', '')
        name_el = item.select_one('.prototype-title')
        name = name_el.get_text(' ', strip=True) if name_el else pid
        img_el = item.select_one('.prototype-frame img[src^="data:image/"]')
        if not img_el:
            failed += 1
            pages.append({'name': name, 'folder': '', 'texts': {'body': [], 'sticky': []},
                          'screenshots': [], 'width': 0, 'height': 0})
            continue
        src = img_el.get('src', '')
        try:
            header, b64 = src.split(',', 1)
            raw = _b64.b64decode(b64, validate=True)
            img = Image.open(BytesIO(raw))
            w, h = img.size
            fname = (pid or ('p_%02d' % (len(pages) + 1))) + '.png'
            with open(os.path.join(img_dir, fname), 'wb') as f:
                f.write(raw)
            pages.append({'name': name, 'folder': '', 'texts': {'body': [], 'sticky': []},
                          'screenshots': [{'url': f'{settings.MEDIA_URL}prd_screenshots/{os.path.basename(img_dir)}/{fname}',
                                           'width': w, 'height': h}],
                          'width': w, 'height': h})
        except Exception as exc:
            failed += 1
            logger.warning(f'[PRD] 原型页 {name} 图片解码失败: {exc}')
            pages.append({'name': name, 'folder': '', 'texts': {'body': [], 'sticky': []},
                          'screenshots': [], 'width': 0, 'height': 0})

    # 通过侧边栏链接把每页指派到模块（data-module-id），再挂正文到模块最后一张原型图
    page_module = {}
    for a in soup.select('a[data-prototype][data-module-id]'):
        pid = (a.get('data-prototype') or '').strip()
        mid = (a.get('data-module-id') or '').strip()
        if pid and mid:
            page_module[pid] = mid

    # prototype-item id 形如 prototype-XX
    by_id = {p_item.get('id', ''): idx for idx, p_item in enumerate(soup.select('.prototype-group .prototype-item'))}
    module_page_idx = {}
    for pid, mid in page_module.items():
        if pid in by_id and mid in modules:
            module_page_idx.setdefault(mid, []).append(by_id[pid])
    for mid, idxs in module_page_idx.items():
        for idx in idxs:
            if 0 <= idx < len(pages):
                pages[idx]['folder'] = modules[mid]['name']
        if idxs and modules.get(mid):
            last_idx = max(idxs)
            if 0 <= last_idx < len(pages):
                pages[last_idx]['texts'] = modules[mid]['texts']
                logger.info(
                    f'[PRD] 模块「{modules[mid]["name"]}」正文挂载到画布「{pages[last_idx]["name"]}」'
                )

    return {'title': title, 'modules': modules, 'pages': pages, 'version_info': version_info,
            'failed': failed}


@shared_task(bind=True, max_retries=0)
def import_prd_task(self, record_id: int, url: str):
    """异步执行单文件 HTML PRD 导入：下载 → 解析模块正文与原型图 → 落盘"""
    import threading
    import tempfile
    import urllib.request

    record = PrdImport.objects.get(id=record_id)
    record.status = 'importing'
    record.stage = 'prepare'
    record.progress = 5
    record.progress_detail = {
        'stage': 'prepare',
        'message': '任务已开始，正在准备下载…',
        'current': 0,
        'total': 1,
        'canvases': [],
    }
    record.celery_task_id = getattr(getattr(self, 'request', None), 'id', '') or ''
    record.save(update_fields=['status', 'stage', 'progress', 'progress_detail', 'celery_task_id'])
    dir_id = uuid.uuid4().hex[:12]

    progress_state = {
        'current': 0,
        'total': 1,
        'stage': 'prepare',
        'message': '任务已开始，正在准备下载…',
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

    def on_progress(current, total, message='', stage=None, canvas_index=None,
                    canvas_name=None, canvas_status=None):
        progress_state['current'] = current
        progress_state['total'] = total
        if stage:
            progress_state['stage'] = stage
        if message:
            progress_state['message'] = message
            logger.info(f'[PRD] {message}')
        if canvas_index is not None:
            entry = next((c for c in progress_state['canvases'] if c.get('index') == canvas_index), None)
            if entry is None:
                entry = {'index': canvas_index, 'name': canvas_name or f'页面{canvas_index}',
                         'status': 'pending', 'message': ''}
                progress_state['canvases'].append(entry)
            if canvas_name:
                entry['name'] = canvas_name
            if canvas_status:
                entry['status'] = canvas_status
            if message and canvas_status in ('done', 'failed'):
                entry['message'] = message

    def persist_progress():
        last_snapshot = None
        while not stop_event.wait(0.5):
            try:
                rec = PrdImport.objects.get(pk=record.id)
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
            except PrdImport.DoesNotExist:
                return
            except Exception as exc:
                logger.warning(f'[PRD] 进度写库失败: {exc}')

    persist_thread = threading.Thread(target=persist_progress, daemon=True)
    persist_thread.start()

    tmp_path = None
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc:
            raise ValueError('仅支持 http/https 的 PRD 文档链接')

        on_progress(0, 1, '正在下载文档…', stage='list')
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as tmp:
            tmp_path = tmp.name
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=120) as resp:
                final_host = urllib.parse.urlparse(resp.geturl()).hostname
                if final_host and final_host != parsed.hostname:
                    raise ValueError('文档被重定向到其他主机，已拒绝')
                total = 0
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > 500 * 1024 * 1024:
                        raise ValueError('文档超过 500MB 上限')
                    tmp.write(chunk)

        on_progress(0, 1, '正在解析模块与原型图…', stage='canvas')
        img_dir = os.path.join(settings.MEDIA_ROOT, 'prd_screenshots', dir_id)
        result = _extract_prd_document(tmp_path, img_dir, on_progress)
        pages = result.get('pages', [])
        if not pages:
            raise ValueError('未找到模块结构或原型页，请确认是单文件 HTML PRD 文档')

        for i, p in enumerate(pages, 1):
            n_img = len(p.get('screenshots') or [])
            n_text = len((p.get('texts') or {}).get('body') or [])
            on_progress(i, len(pages), f'{p["name"]} 完成（文字{n_text} 图{n_img}）', stage='canvas',
                        canvas_index=i, canvas_name=p.get('name') or f'页面{i}',
                        canvas_status='failed' if not n_img else 'done')

        record.title = result.get('title') or record.title
        record.data = {
            'import_id': dir_id,
            'pages': pages,
            'modules': result.get('modules', {}),
            'version_info': result.get('version_info', {}),
        }
        record.status = 'completed'
        record.stage = 'done'
        record.progress = 100
        detail = build_detail()
        detail['stage'] = 'done'
        detail['message'] = f'导入完成: {len(pages)} 个原型页'
        record.progress_detail = detail
        record.save(update_fields=['title', 'data', 'status', 'stage', 'progress', 'progress_detail'])
        logger.info(f'[PRD] 异步导入完成: import_id={dir_id}, {len(pages)}原型页, 失败{result.get("failed", 0)}')

    except Exception as exc:
        stop_event.set()
        persist_thread.join(timeout=2)
        _cleanup_failed_prd_screenshots(dir_id)
        record.status = 'failed'
        record.stage = 'failed'
        record.error_message = str(exc)[:1000]
        detail = build_detail()
        detail['stage'] = 'failed'
        detail['message'] = str(exc)[:1000]
        record.progress_detail = detail
        record.save(update_fields=['status', 'stage', 'error_message', 'progress_detail'])
        logger.error(f'[PRD] 异步导入失败: import_id={dir_id}, error={exc}')
        raise
    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except Exception:
                pass


@shared_task(bind=True, max_retries=0)
def import_axure_task(self, record_id: int, url: str):
    """异步执行 Axure 原型导入：页面树 → 每页文字+图片 → 落库"""
    import threading

    record = AxureImport.objects.get(id=record_id)
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
    record.celery_task_id = getattr(getattr(self, 'request', None), 'id', '') or ''
    record.save(update_fields=['status', 'stage', 'progress', 'progress_detail', 'celery_task_id'])
    dir_id = uuid.uuid4().hex[:12]

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

    def on_progress(current, total, message='', stage=None, canvas_index=None,
                    canvas_name=None, canvas_status=None):
        progress_state['current'] = current
        progress_state['total'] = total
        if stage:
            progress_state['stage'] = stage
        if message:
            progress_state['message'] = message
            logger.info(f'[Axure] {message}')
        if canvas_index is not None:
            entry = next((c for c in progress_state['canvases'] if c.get('index') == canvas_index), None)
            if entry is None:
                entry = {'index': canvas_index, 'name': canvas_name or f'画布{canvas_index}',
                         'status': 'pending', 'message': ''}
                progress_state['canvases'].append(entry)
            if canvas_name:
                entry['name'] = canvas_name
            if canvas_status:
                entry['status'] = canvas_status
            if message and canvas_status in ('done', 'failed'):
                entry['message'] = message

    def persist_progress():
        last_snapshot = None
        while not stop_event.wait(0.5):
            try:
                rec = AxureImport.objects.get(pk=record.id)
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
            except AxureImport.DoesNotExist:
                return
            except Exception as exc:
                logger.warning(f'[Axure] 进度写库失败: {exc}')

    persist_thread = threading.Thread(target=persist_progress, daemon=True)
    persist_thread.start()

    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc:
            raise ValueError('仅支持 http/https 的 Axure 原型链接')

        on_progress(0, 1, '正在解析页面列表…', stage='list')
        roots, title = _fetch_axure_sitemap(url, on_progress)
        pages = []
        _walk_axure_nodes(roots, '', pages)
        if not pages:
            raise ValueError('未找到任何页面')

        results = []
        failed = set()
        img_dir = os.path.join(settings.MEDIA_ROOT, 'axure_screenshots', dir_id)
        total = len(pages)
        for i, p in enumerate(pages, 1):
            on_progress(i, total, f'导入画布 {i}/{total}: {p["name"]}', stage='canvas',
                        canvas_index=i, canvas_name=p['name'], canvas_status='pending')
            try:
                page_data = _extract_axure_page(parsed, p, img_dir)
                results.append(page_data)
                n_img = len(page_data.get('screenshots') or [])
                n_text = len((page_data.get('texts') or {}).get('body') or [])
                on_progress(i, total, f'{p["name"]} 完成（文字{n_text} 图{n_img}）', stage='canvas',
                            canvas_index=i, canvas_name=p['name'], canvas_status='done')
            except Exception as exc:
                failed.add(p['name'])
                logger.error(f'[Axure] 画布 {p["name"]} 导入失败: {exc}')
                results.append({
                    'name': p['name'], 'folder': p.get('folder', ''),
                    'texts': {'body': [], 'sticky': []}, 'screenshots': [],
                    'width': 0, 'height': 0,
                })
                on_progress(i, total, f'{p["name"]} 失败: {str(exc)[:120]}', stage='canvas',
                            canvas_index=i, canvas_name=p['name'], canvas_status='failed')

        if len(failed) >= total:
            raise ValueError(f'所有页面导入失败（{len(failed)}/{total}）')

        record.title = title or record.title
        record.data = {'import_id': dir_id, 'pages': results}
        record.status = 'completed'
        record.stage = 'done'
        record.progress = 100
        detail = build_detail()
        detail['stage'] = 'done'
        detail['message'] = f'导入完成: {len(results)} 个画布'
        record.progress_detail = detail
        record.save(update_fields=['title', 'data', 'status', 'stage', 'progress', 'progress_detail'])
        logger.info(f'[Axure] 异步导入完成: import_id={dir_id}, {len(results)}画布, 失败{len(failed)}')

    except Exception as exc:
        stop_event.set()
        persist_thread.join(timeout=2)
        _cleanup_failed_axure_screenshots(dir_id)
        record.status = 'failed'
        record.stage = 'failed'
        record.error_message = str(exc)[:1000]
        detail = build_detail()
        detail['stage'] = 'failed'
        detail['message'] = str(exc)[:1000]
        record.progress_detail = detail
        record.save(update_fields=['status', 'stage', 'error_message', 'progress_detail'])
        logger.error(f'[Axure] 异步导入失败: import_id={dir_id}, error={exc}')
        raise
