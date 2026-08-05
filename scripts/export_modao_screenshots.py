#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
墨刀画布截图导出脚本（独立版）

与 TestHub 中 AIModelService.import_from_modao 的截图逻辑保持一致：
  - Playwright 无头 Chrome + device_scale_factor=4 超采样截图
  - 隐藏墨刀 UI、画布缩放归一化到 100%、包围盒裁剪
  - PIL 背景裁剪 + 长边压缩 + JPEG(q92, 无二次采样) 落盘
  - 输出 canvases.json 清单（画布名 / 文件名 / 尺寸 / 状态）

用法（推荐）:
    1. 填写脚本同目录下的 config.ini（url / cookie 或 cookie_file / out）
    2. 直接运行: python export_modao_screenshots.py

也可用命令行参数覆盖配置:
    python export_modao_screenshots.py --url "https://modao.cc/proto/xxxxx" ^
        --cookie "xxx=yyy; aaa=bbb" --out D:/tmp/modao_shots

依赖:
    pip install playwright pillow
    优先使用本机 Chrome（无需 playwright install chromium）；
    找不到时回退到 playwright 自带的 chromium。
"""

import argparse
import asyncio
import base64
import configparser
import io
import json
import logging
import os
import sys

logger = logging.getLogger("modao_export")


# ---------------------------------------------------------------------------
# 截图输出控制（与 models.py 一致）
# ---------------------------------------------------------------------------
TARGET_LONG_EDGE = 4096   # 目标长边：控制模型输入大小与 token 成本
MAX_EDGE = 25000          # 原始像素上限：防 OOM


# ---------------------------------------------------------------------------
# 墨刀页面 JS 辅助（与 models.py 中的常量一致）
# ---------------------------------------------------------------------------
_MODAO_BOUNDS_JS = '''() => {
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    let count = 0;
    const vw = window.innerWidth;
    const hasScreen = document.querySelector('.mb-screen') !== null;
    document.querySelectorAll('.widget, [id^="text-dom-"], .wImage, [class*="draft"]').forEach(w => {
        const b = w.getBoundingClientRect();
        if (b.width <= 0 || b.height <= 0) return;
        // 优先只统计当前画布容器(.mb-screen)内的元素，天然排除左右侧边栏/面板；
        // 旧版页面无该容器时，退化为按右侧 15% 视口宽度过滤
        if (hasScreen && !w.closest('.mb-screen')) return;
        if (!hasScreen && b.left > vw * 0.85) return;
        count++;
        minX = Math.min(minX, b.left);
        minY = Math.min(minY, b.top);
        maxX = Math.max(maxX, b.right);
        maxY = Math.max(maxY, b.bottom);
    });
    if (count === 0) return null;
    return {x: minX, y: minY, w: maxX - minX, h: maxY - minY, count};
}'''

_MODAO_REPOSITION_JS = '''(arg) => {
    const fit = arg.fit, padX = arg.padX, padY = arg.padY;
    const za = document.querySelector('.zoom-area');
    if (!za) return null;
    const grabBounds = () => {
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        let count = 0;
        const hasScreen = document.querySelector('.mb-screen') !== null;
        document.querySelectorAll('.widget, [id^="text-dom-"], .wImage, [class*="draft"]').forEach(w => {
            const b = w.getBoundingClientRect();
            if (b.width <= 0 || b.height <= 0) return;
            if (hasScreen && !w.closest('.mb-screen')) return;
            count++;
            minX = Math.min(minX, b.left);
            minY = Math.min(minY, b.top);
            maxX = Math.max(maxX, b.right);
            maxY = Math.max(maxY, b.bottom);
        });
        if (count === 0) return null;
        return {x: minX, y: minY, w: maxX - minX, h: maxY - minY, count};
    };
    const m = (getComputedStyle(za).transform || '').match(/^matrix\\(([^)]+)\\)$/);
    if (!m) return null;
    const p = m[1].split(',').map(Number);
    let e = p[4], f = p[5];
    za.style.transform = `matrix(${fit}, 0, 0, ${fit}, ${e}, ${f})`;
    let b = grabBounds();
    if (!b) return null;
    for (let i = 0; i < 8; i++) {
        const dx = padX - b.x, dy = padY - b.y;
        if (Math.abs(dx) < 0.6 && Math.abs(dy) < 0.6) break;
        e += dx;
        f += dy;
        za.style.transform = `matrix(${fit}, 0, 0, ${fit}, ${e}, ${f})`;
        b = grabBounds();
    }
    return {x: b.x, y: b.y, w: b.w, h: b.h, count: b.count};
}'''

_MODAO_REVERT_ZOOM_JS = '''() => {
    const st = window.__modaoZoomState;
    if (st) {
        if (st.isZoom) st.el.style.zoom = st.originalZoom;
        else st.el.style.transform = st.originalTransform;
        delete window.__modaoZoomState;
    }
}'''

_MODAO_HIDE_UI_JS = '''() => {
    const selectors = [
        '#fixed-area, .fixed_area, [class*="StyledSignUpPrompt"]',
        '.ruler, .rulerH, .rulerV, #mb-ruler, [class*="Ruler"], [class*="StyledRulerContainer"]',
        '[class*="ToolBar"], [class*="toolbar-left"], [class*="toolbar"], [class*="StyledToolbar"]',
        '[class*="comment"], [class*="annotation"], [class*="note-panel"], [class*="right-panel"]',
        '[class*="thumbnail"], [class*="status-bar"], [class*="bottom-bar"]',
        '[class*="LeftSidePanel"], [class*="left-panel"], [class*="LeftPane"], [class*="CanvasListPanel"], [class*="ScreenList"], .canvas-scroll-list, .toggleable-zone',
    ];
    const saved = window.__modaoHiddenUI || [];
    document.querySelectorAll(selectors.join(',')).forEach(el => {
        if (el.style.display !== 'none') {
            saved.push({el, display: el.style.display});
            el.style.display = 'none';
        }
    });
    window.__modaoHiddenUI = saved;
    return saved.length;
}'''

_MODAO_RESTORE_UI_JS = '''() => {
    const saved = window.__modaoHiddenUI || [];
    for (const item of saved) {
        item.el.style.display = item.display;
    }
    window.__modaoHiddenUI = [];
    return saved.length;
}'''

_MODAO_EXPAND_ALL_JS = '''() => {
    let n = 0;
    // 每次只点第一个折叠的 expander，避免 DOM 重建后句柄失效
    for (let guard = 0; guard < 10; guard++) {
        let a = null;
        const all = document.querySelectorAll('a.expander');
        for (const el of all) {
            const svg = el.querySelector('svg');
            // 注意：svg.className 是 SVGAnimatedString，String() 为 "[object SVGAnimatedString]"，
            // 必须用 getAttribute('class') 判断 is-collapse/is-expand
            if (svg && /is-collapse/.test(svg.getAttribute('class') || '')) { a = el; break; }
        }
        if (!a) break;
        a.click();
        n++;
    }
    return n;
}'''

_MODAO_ACTIVE_CID_JS = '''() => {
    const active = document.querySelector('li.rn-content-item.active, [class*="rn-list-item"].active');
    if (!active) return null;
    const li = active.closest('li');
    return li ? (li.getAttribute('data-cid') || null) : null;
}'''

_MODAO_NORMALIZE_ZOOM_JS = '''() => {
    const grabBounds = () => {
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        let count = 0;
        const vw = window.innerWidth;
        document.querySelectorAll('.widget, [id^="text-dom-"], .wImage, [class*="draft"]').forEach(w => {
            const b = w.getBoundingClientRect();
            if (b.width <= 0 || b.height <= 0) return;
            if (b.left > vw * 0.85) return; // 跳过右侧面板元素
            count++;
            minX = Math.min(minX, b.left);
            minY = Math.min(minY, b.top);
            maxX = Math.max(maxX, b.right);
            maxY = Math.max(maxY, b.bottom);
        });
        if (count === 0) return null;
        return {x: minX, y: minY, w: maxX - minX, h: maxY - minY, count};
    };

    const before = grabBounds();
    if (!before) return null;

    // 向上查找画布缩放的来源（transform scale 或 CSS zoom）
    const findZoomSource = (el) => {
        let node = el;
        while (node && node !== document.body) {
            const cs = getComputedStyle(node);
            const m = cs.transform.match(/^matrix\\(([^)]+)\\)$/);
            if (m) {
                const p = m[1].split(',').map(Number);
                const sx = Math.hypot(p[0], p[1]);
                if (sx > 0.05 && Math.abs(sx - 1) > 0.02) return {el: node, scale: sx};
            }
            const z = parseFloat(cs.zoom);
            if (Number.isFinite(z) && z > 0.05 && Math.abs(z - 1) > 0.02) return {el: node, scale: z, isZoom: true};
            node = node.parentElement;
        }
        return null;
    };

    const sample = document.querySelectorAll('.widget, [id^="text-dom-"], .wImage');
    let source = null;
    for (const w of Array.from(sample).slice(0, 20)) {
        source = findZoomSource(w);
        if (source) break;
    }
    if (!source || source.scale >= 0.9) {
        return {x: before.x, y: before.y, w: before.w, h: before.h, count: before.count,
                scale: source ? source.scale : 1, normalized: false};
    }
    try {
        if (source.isZoom) {
            window.__modaoZoomState = {el: source.el, isZoom: true, originalZoom: source.el.style.zoom};
            source.el.style.zoom = String(1 / source.scale);
        } else {
            window.__modaoZoomState = {el: source.el, isZoom: false, originalTransform: source.el.style.transform};
            const cur = getComputedStyle(source.el).transform;
            source.el.style.transform = (cur && cur !== 'none' ? cur + ' ' : '') +
                'scale(' + (1 / source.scale).toFixed(6) + ')';
        }
        return {x: before.x, y: before.y, w: before.w, h: before.h, count: before.count,
                scale: source.scale, normalized: true};
    } catch (e) {
        return {x: before.x, y: before.y, w: before.w, h: before.h, count: before.count,
                scale: source.scale, normalized: false};
    }
}'''


# ---------------------------------------------------------------------------
# PIL 后处理：内存保护 → 背景裁剪 → 目标长边降采样 → 高质量 JPEG
# ---------------------------------------------------------------------------
def process_screenshot(screenshot_bytes, target_long_edge=TARGET_LONG_EDGE):
    """输入原始 PNG 字节，返回 (jpeg_bytes, width, height)；PIL 不可用则原样返回。"""
    try:
        from PIL import Image
    except ImportError:
        logger.warning("Pillow 未安装，跳过图片后处理（保留原始截图）")
        img = Image.open(io.BytesIO(screenshot_bytes))
        return screenshot_bytes, img.size[0], img.size[1]

    img = Image.open(io.BytesIO(screenshot_bytes))
    # 内存保护：原始像素超上限时先等比压到上限
    if max(img.size) > MAX_EDGE:
        ratio = MAX_EDGE / max(img.size)
        img = img.resize((max(1, int(img.width * ratio)), max(1, int(img.height * ratio))), Image.LANCZOS)

    gray = img.convert('L')
    arr = gray.load()
    pw, ph = img.size

    # 从四角采样实际背景色
    corners = []
    for cx, cy in [(5, 5), (pw - 6, 5), (5, ph - 6), (pw - 6, ph - 6)]:
        sample = [arr[cx + dx, cy + dy] for dx in (-2, 0, 2) for dy in (-2, 0, 2)]
        sample.sort()
        corners.append(sample[len(sample) // 2])
    bg_level = sum(corners) // len(corners)
    threshold = min(bg_level + 10, 252)

    def is_bg(x, y):
        return arr[x, y] >= threshold

    top = 0
    while top < ph and all(is_bg(x, top) for x in range(pw)):
        top += 1
    bottom = ph - 1
    while bottom > top and all(is_bg(x, bottom) for x in range(pw)):
        bottom -= 1
    left = 0
    while left < pw and all(is_bg(left, y) for y in range(top, bottom + 1)):
        left += 1
    right = pw - 1
    while right > left and all(is_bg(right, y) for y in range(top, bottom + 1)):
        right -= 1

    crop_pad = 5
    crop = (max(0, left - crop_pad), max(0, top - crop_pad),
            min(pw, right + 1 + crop_pad), min(ph, bottom + 1 + crop_pad))
    if crop[0] > 0 or crop[1] > 0 or crop[2] < pw or crop[3] < ph:
        img = img.crop(crop)

    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')

    # 统一缩放到目标长边：控制模型输入大小与 token 成本
    long_edge = max(img.size)
    if long_edge > target_long_edge:
        ratio = target_long_edge / long_edge
        img = img.resize((max(1, int(img.width * ratio)), max(1, int(img.height * ratio))), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=92, subsampling=0)
    return buf.getvalue(), img.width, img.height


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def find_system_chrome():
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
    ]
    return next((p for p in candidates if os.path.exists(p)), None)


def parse_cookies(cookie_str):
    """把 'k=v; k2=v2' 解析为 playwright cookie 列表（域名 .modao.cc）。"""
    cookies = []
    if cookie_str and '=' in cookie_str:
        for pair in cookie_str.split(';'):
            pair = pair.strip()
            if '=' in pair:
                k, v = pair.split('=', 1)
                cookies.append({
                    'name': k.strip(),
                    'value': v.strip(),
                    'domain': '.modao.cc',
                    'path': '/',
                })
    return cookies


async def export_modao_screenshots(url, auth_token, out_dir,
                                   target_long_edge=TARGET_LONG_EDGE,
                                   device_scale_factor=4,
                                   headful=False):
    """遍历墨刀画布并截图保存到 out_dir，返回结果 dict。"""
    from playwright.async_api import async_playwright

    os.makedirs(out_dir, exist_ok=True)
    result = {'title': '', 'canvases': [], 'out_dir': out_dir}

    chrome_path = find_system_chrome()
    logger.info("使用 Chrome: %s", chrome_path or "playwright 自带 chromium")

    async with async_playwright() as p:
        launch_args = {'headless': not headful, 'args': ['--no-sandbox', '--disable-gpu']}
        if chrome_path:
            launch_args['executable_path'] = chrome_path
        browser = await p.chromium.launch(**launch_args)
        try:
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1200},
                device_scale_factor=device_scale_factor,
                locale='zh-CN',
            )
            page = await context.new_page()

            # 注入 Cookie（先设 cookie 再导航，避免预访问导致重定向）
            cookies = parse_cookies(auth_token)
            if cookies:
                await context.add_cookies(cookies)
                logger.info("已注入 %d 个 cookie", len(cookies))

            await page.goto(url, wait_until='domcontentloaded', timeout=60000)
            await page.wait_for_timeout(3000)  # 等待页面稳定（可能触发 JS 跳转）
            result['title'] = await page.title()
            logger.info("页面标题: %s", result['title'])

            # Cookie 过期检测
            if result['title'] == '墨刀':
                raise Exception('Cookie已失效：页面标题为"墨刀"，请重新获取Cookie')
            current_url = page.url
            if 'workspace' in current_url or 'login' in current_url:
                raise Exception(f'Cookie已失效：页面被重定向到 {current_url}，请重新获取Cookie')

            # 等侧边栏渲染
            try:
                await page.wait_for_selector('li.rn-content-item', timeout=15000)
            except Exception:
                logger.warning("等待画布列表超时，当前URL: %s", page.url)
                await page.wait_for_timeout(5000)

            all_items = await page.query_selector_all('li.rn-content-item')
            logger.info("发现 %d 个侧边栏项，正在过滤非画布...", len(all_items))

            # 过滤：只保留真正的页面画布(target-type=6)，排除图层/热区(target-type=2)。
            # 只记录 data-cid，不缓存元素句柄——折叠/展开会重建侧边栏 DOM，句柄会失效
            canvas_cids = []
            for item in all_items:
                target_type = await item.evaluate(
                    'el => el.querySelector("[data-interactive-target-type]")?.getAttribute("data-interactive-target-type") || ""'
                )
                if target_type == '6':
                    cid = await item.get_attribute('data-cid')
                    canvas_cids.append(cid)
                else:
                    name_el = await item.query_selector('.editable-span')
                    name = (await name_el.inner_text()).strip() if name_el else '(空)'
                    logger.info("跳过非画布项: %s (target-type=%s)", name, target_type)

            canvas_count = len(canvas_cids)
            logger.info("过滤后 %d 个画布", canvas_count)
            if canvas_count == 0:
                raise Exception('Cookie已失效或页面无权限：未找到画布，请检查Cookie是否正确（F12→Network→请求头→Cookie整行复制）')

            async def _locate_canvas_item(cid):
                for it in await page.query_selector_all('li.rn-content-item'):
                    if await it.get_attribute('data-cid') == cid:
                        return it
                return None

            for i, cid in enumerate(canvas_cids):
                name = f'画布{i + 1}'
                try:
                    # 每次处理前确保子页面树全部展开（防止上一张父级画布折叠后子页不可见）
                    await page.evaluate(_MODAO_EXPAND_ALL_JS)
                    await page.wait_for_timeout(400)
                    item = await _locate_canvas_item(cid)
                    if item is None:
                        raise Exception('画布项在侧边栏中不可见，无法定位')
                    name_el = await item.query_selector('.editable-span')
                    name = (await name_el.inner_text()).strip() if name_el else f'画布{i + 1}'
                    logger.info("[%d/%d] 正在处理画布: %s", i + 1, canvas_count, name)

                    # 点击行内文字（或行本身）。不要点击 li 中心：
                    # li 里嵌套着子页面行，点 li 中心会落到子页上，导致父级画布
                    # （如 单人模式设置页）跳到其第一个子页面（倒计时页），截图重复。
                    async def click_row():
                        item = await _locate_canvas_item(cid)
                        if item is None:
                            return None
                        row = await item.query_selector('div[data-interactive-target-type]') or item
                        click_el = await row.query_selector('.editable-span') or row
                        await click_el.scroll_into_view_if_needed()
                        await page.wait_for_timeout(300)
                        await click_el.click()
                        await page.wait_for_timeout(1500)
                        return item

                    item = await click_row()
                    if item is None:
                        raise Exception('画布项在侧边栏中不可见，无法定位')

                    # 校验是否真的激活了目标画布（父级画布可能跳到第一个子页面）
                    active_cid = await page.evaluate(_MODAO_ACTIVE_CID_JS)
                    if active_cid and active_cid != cid:
                        logger.warning("[%d/%d][%s] 点击后激活了 %s（父级画布跳到子页），折叠后重试…",
                                       i + 1, canvas_count, name, active_cid)
                        try:
                            await item.evaluate(
                                'el => { const a = el.querySelector("a.expander"); if (a) a.click(); }'
                            )
                            await page.wait_for_timeout(500)
                        except Exception:
                            pass
                        item = await click_row()
                        if item is None:
                            raise Exception('折叠后画布项不可见，无法定位')
                        active_cid = await page.evaluate(_MODAO_ACTIVE_CID_JS)
                        if active_cid and active_cid != cid:
                            raise Exception(f'画布点击后未切换（激活了 {active_cid}），已跳过')

                    # 隐藏墨刀 UI（顶栏/标尺/左侧页面树/右侧面板等），截图后恢复
                    await page.evaluate(_MODAO_HIDE_UI_JS)
                    await page.wait_for_timeout(1000)

                    # 计算可见 widget 包围盒，并尝试把大画布恢复为 100% 缩放（提升文字清晰度）
                    try:
                        zoom_probe = await page.evaluate(_MODAO_NORMALIZE_ZOOM_JS)
                    except Exception as e:
                        logger.warning("缩放探测失败，按原缩放截图: %s", e)
                        zoom_probe = None

                    if zoom_probe and zoom_probe.get('normalized'):
                        await page.wait_for_timeout(600)
                        logger.info("[%d/%d] 画布缩放已恢复100%: scale=%.3f",
                                    i + 1, canvas_count, zoom_probe['scale'])
                    elif zoom_probe and zoom_probe.get('scale', 1) < 0.9:
                        logger.warning("[%d/%d] 检测到画布缩放 %.3f 但归一化失败，使用原缩放截图",
                                       i + 1, canvas_count, zoom_probe['scale'])

                    # 归一化后计算包围盒
                    try:
                        bounds = await page.evaluate(_MODAO_BOUNDS_JS)
                    except Exception as e:
                        logger.warning("包围盒计算失败: %s", e)
                        bounds = zoom_probe

                    # 视口扩展：包围盒超出视口时扩大视口，确保完整截图（避免只截到视口内部分）
                    if bounds and (bounds['w'] > 1900 or bounds['h'] > 1200):
                        try:
                            new_w = min(max(int(bounds['w']) + 40, 1280), 4096)
                            new_h = min(max(int(bounds['h']) + 40, 900), 4096)
                            vs = page.viewport_size or {}
                            if new_w != vs.get('width') or new_h != vs.get('height'):
                                await page.set_viewport_size({'width': new_w, 'height': new_h})
                                await page.wait_for_timeout(500)
                                bounds = await page.evaluate(_MODAO_BOUNDS_JS)
                        except Exception as e:
                            logger.warning("视口扩展失败: %s", e)

                    # 重定位 + 适配缩放：把画布左上角对齐到 (pad,pad)，必要时等比缩小到视口内。
                    vs = page.viewport_size or {}
                    if bounds and (bounds['x'] < 0 or bounds['y'] < 0
                                   or bounds['x'] + bounds['w'] + 20 > vs.get('width', 1920)
                                   or bounds['y'] + bounds['h'] + 20 > vs.get('height', 1200)):
                        try:
                            pad_align = 10
                            vw_cur = max(vs.get('width', 1920), 1)
                            vh_cur = max(vs.get('height', 1200), 1)
                            fit = min(1.0,
                                      (vw_cur - pad_align * 2 - 4) / max(bounds['w'], 1),
                                      (vh_cur - pad_align * 2 - 4) / max(bounds['h'], 1))
                            fit = max(fit, 0.01)
                            reposition = await page.evaluate(
                                _MODAO_REPOSITION_JS,
                                {'fit': fit, 'padX': pad_align, 'padY': pad_align},
                            )
                            if reposition:
                                await page.wait_for_timeout(300)
                                bounds = await page.evaluate(_MODAO_BOUNDS_JS)
                                logger.info("[%d/%d] 画布已重定位: fit=%.4f, bounds=(%.0f,%.0f,%.0fx%.0f)",
                                            i + 1, canvas_count, fit,
                                            bounds['x'], bounds['y'], bounds['w'], bounds['h'])
                        except Exception as e:
                            logger.warning("画布重定位失败: %s", e)

                    # 仍超出视口（重定位失败等极端情况）：回退原缩放状态，避免截取部分内容
                    vs = page.viewport_size or {}
                    if bounds and (bounds['w'] > vs.get('width', 1920) + 5 or bounds['h'] > vs.get('height', 1200) + 5
                                   or bounds['x'] < -0.5 or bounds['y'] < -0.5):
                        try:
                            await page.evaluate(_MODAO_REVERT_ZOOM_JS)
                            await page.wait_for_timeout(400)
                            bounds = await page.evaluate(_MODAO_BOUNDS_JS)
                            logger.warning("[%d/%d] 画布超出视口上限，已回退原缩放截图", i + 1, canvas_count)
                        except Exception as e:
                            logger.warning("回退缩放失败: %s", e)

                    # 截图前等待字体加载完成，避免 fallback 字体导致的模糊/缺字
                    try:
                        await page.evaluate(
                            'document.fonts ? Promise.race([document.fonts.ready, new Promise(r => setTimeout(r, 2000))]) : true'
                        )
                    except Exception:
                        pass

                    logger.info("[%d/%d] 正在截图: %s", i + 1, canvas_count, name)
                    if bounds:
                        pad = 10
                        clip_region = {
                            'x': max(0, bounds['x'] - pad),
                            'y': max(0, bounds['y'] - pad),
                            'width': min(bounds['w'] + pad * 2, 12000),
                            'height': min(bounds['h'] + pad * 2, 12000),
                        }
                        # 输出像素超 8192 长边时，Chrome 普通截图可能失败，改用 CDP 截图
                        longest_css = max(clip_region['width'], clip_region['height'])
                        try:
                            if longest_css * device_scale_factor > 8192:
                                cdp = await context.new_cdp_session(page)
                                shot = await cdp.send('Page.captureScreenshot', {
                                    'format': 'png',
                                    'clip': {
                                        'x': clip_region['x'], 'y': clip_region['y'],
                                        'width': clip_region['width'], 'height': clip_region['height'],
                                        'scale': 1,
                                    },
                                    'captureBeyondViewport': False,
                                })
                                screenshot_bytes = base64.b64decode(shot['data'])
                                logger.info("[%d/%d] 大图截图走CDP: %.0fx%.0f",
                                            i + 1, canvas_count, clip_region['width'], clip_region['height'])
                            else:
                                screenshot_bytes = await page.screenshot(clip=clip_region, type='png')
                        except Exception as e:
                            logger.warning("截图异常，回退普通截图: %s", e)
                            screenshot_bytes = await page.screenshot(clip=clip_region, type='png')
                    else:
                        screenshot_bytes = await page.screenshot(type='png', full_page=True)

                    # PIL 后处理：内存保护 → 背景裁剪 → 目标长边降采样 → 高质量 JPEG
                    screenshot_bytes, final_w, final_h = process_screenshot(
                        screenshot_bytes, target_long_edge=target_long_edge
                    )

                    filename = f'{i:02d}.jpg'
                    filepath = os.path.join(out_dir, filename)
                    with open(filepath, 'wb') as f:
                        f.write(screenshot_bytes)

                    result['canvases'].append({
                        'index': i + 1,
                        'name': name,
                        'file': filename,
                        'width': final_w,
                        'height': final_h,
                        'status': 'done',
                        'error': '',
                    })
                    logger.info("[%d/%d] %s 截图完成 (%dx%d, %.0fKB)",
                                i + 1, canvas_count, name, final_w, final_h,
                                len(screenshot_bytes) / 1024)
                except Exception as ex:
                    logger.error("[%d/%d] 画布提取失败: %s", i + 1, canvas_count, ex)
                    result['canvases'].append({
                        'index': i + 1,
                        'name': name,
                        'file': '',
                        'width': 0,
                        'height': 0,
                        'status': 'failed',
                        'error': str(ex),
                    })
                finally:
                    # 恢复被隐藏的 UI（顶栏/左侧页面树等），确保下一个画布能正常点击
                    try:
                        await page.evaluate(_MODAO_RESTORE_UI_JS)
                    except Exception:
                        pass
        finally:
            await browser.close()

    # 写清单
    manifest_path = os.path.join(out_dir, 'canvases.json')
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    ok = sum(1 for c in result['canvases'] if c['status'] == 'done')
    failed = len(result['canvases']) - ok
    logger.info("导入完成: %d 个画布成功, %d 个失败, 清单: %s", ok, failed, manifest_path)
    return result


def load_config(path):
    """读取 config.ini 的 [modao] 段；文件不存在或键为空时返回 None。"""
    cfg = {
        'url': None,
        'cookie': None,
        'cookie_file': None,
        'out': None,
        'target_long_edge': None,
        'scale_factor': None,
        'headful': None,
    }
    if not os.path.exists(path):
        return cfg
    parser = configparser.ConfigParser()
    parser.read(path, encoding='utf-8')
    if not parser.has_section('modao'):
        return cfg
    sec = parser['modao']
    for key in cfg:
        value = sec.get(key, '').strip()
        if value:
            cfg[key] = value
    return cfg


def main():
    parser = argparse.ArgumentParser(description="墨刀画布截图导出（独立脚本）")
    parser.add_argument('--config', default=None,
                        help='配置文件路径（默认：脚本同目录 config.ini）')
    parser.add_argument('--url', help='墨刀原型页面 URL（不填则读取配置文件）')
    parser.add_argument('--cookie', help='墨刀 Cookie 字符串（不填则读取配置文件）')
    parser.add_argument('--cookie-file', help='从文件读取 Cookie 字符串（不填则读取配置文件）')
    parser.add_argument('--out', help='截图输出目录（不填则读取配置文件）')
    parser.add_argument('--target-long-edge', type=int, help='输出 JPEG 目标长边像素（默认 4096）')
    parser.add_argument('--scale-factor', type=float, help='浏览器 device_scale_factor 超采样倍数（默认 4）')
    parser.add_argument('--headful', action='store_true', help='有头模式（调试用，默认无头）')
    parser.add_argument('--verbose', action='store_true', help='输出 DEBUG 级别日志')
    args = parser.parse_args()

    # 配置文件默认放在脚本同目录
    config_path = args.config or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'config.ini'
    )
    cfg = load_config(config_path)
    if not os.path.exists(config_path):
        logger.warning("未找到配置文件: %s，将使用命令行参数/默认值", config_path)

    url = args.url or cfg['url']
    if not url:
        parser.error('缺少墨刀 URL：请在 config.ini 中填写 url，或用 --url 传入')

    cookie = args.cookie or cfg['cookie'] or ''
    cookie_file = args.cookie_file or cfg['cookie_file'] or ''
    if cookie_file:
        # 相对路径按配置文件所在目录解析（cookie.txt 与 config.ini 放一起最省事）
        if not os.path.isabs(cookie_file):
            cookie_file = os.path.join(os.path.dirname(config_path), cookie_file)
        if not os.path.exists(cookie_file):
            parser.error(f'Cookie 文件不存在: {cookie_file}')
        with open(cookie_file, 'r', encoding='utf-8') as f:
            cookie = f.read().strip()
    if not cookie:
        parser.error('缺少 Cookie：请在 config.ini 中填写 cookie / cookie_file，或用 --cookie / --cookie-file 传入')

    out = args.out or cfg['out'] or 'modao_screenshots'
    target_long_edge = args.target_long_edge or int(cfg['target_long_edge'] or TARGET_LONG_EDGE)
    scale_factor = args.scale_factor or float(cfg['scale_factor'] or 4)
    headful = args.headful or (cfg['headful'] or '').lower() in ('1', 'true', 'yes', 'on')

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='[%(asctime)s] %(levelname)s %(message)s',
        datefmt='%H:%M:%S',
    )

    logger.info("URL: %s", url)
    logger.info("输出目录: %s", out)
    logger.info("参数: target_long_edge=%d, scale_factor=%g, headful=%s",
                target_long_edge, scale_factor, headful)

    try:
        result = asyncio.run(export_modao_screenshots(
            url=url,
            auth_token=cookie,
            out_dir=out,
            target_long_edge=target_long_edge,
            device_scale_factor=scale_factor,
            headful=headful,
        ))
        sys.exit(0 if result['canvases'] and all(c['status'] == 'done' for c in result['canvases']) else 1)
    except Exception as e:
        logger.error("导出失败: %s", e)
        sys.exit(1)


if __name__ == '__main__':
    main()
