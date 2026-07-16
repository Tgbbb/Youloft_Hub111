# -*- coding: utf-8 -*-
"""
Midscene AI 移动端自动化 - 纯 Python Runner
核心循环: 截图(ADB) → VLM 看图 → 返回动作 → ADB 执行 → 循环

智能规划模式 (aiAct):
  VLM 携带总目标，持续决策下一步 → 执行 → 截图 → 再决策 → 直到 done
  不是预拆解，而是每步实时决策。Midscene 文档证实了这一点。
"""
import os
import re
import json
import base64
import logging
import subprocess
import time
import platform as sys_platform
import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

_SUBPROCESS_KWARGS = {}
if sys_platform.system() == 'Windows':
    _SUBPROCESS_KWARGS['creationflags'] = subprocess.CREATE_NO_WINDOW


# ============================================================
# 步骤解析
# ============================================================

def parse_ai_prompt(ai_prompt):
    steps = []
    for line in ai_prompt.strip().split('\n'):
        line = line.strip()
        if not line: continue
        line = re.sub(r'^(\d+[\.\)、]\s*)', '', line)
        line = re.sub(r'^[-*•]\s*', '', line)
        if line: steps.append({'instruction': line})
    return steps


# ============================================================
# ADB
# ============================================================

def _adb(device_id, *args, timeout=15):
    cmd = ['adb', '-s', device_id] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          encoding='utf-8', errors='replace', **_SUBPROCESS_KWARGS)

def adb_execute(device_id, action):
    t = action.get('action', '')
    if t in ('tap', 'click'):
        _adb(device_id, 'shell', 'input', 'tap', str(int(float(action.get('x',0)))), str(int(float(action.get('y',0)))))
    elif t == 'swipe':
        _adb(device_id, 'shell', 'input', 'swipe', str(int(float(action.get('x1',0)))), str(int(float(action.get('y1',0)))),
             str(int(float(action.get('x2',0)))), str(int(float(action.get('y2',0)))), str(action.get('duration',300)))
    elif t == 'input':
        _adb(device_id, 'shell', 'input', 'text', action.get('text','').replace(' ','%s').replace('&','\\&'))
    elif t == 'back':    _adb(device_id, 'shell', 'input', 'keyevent', 'KEYCODE_BACK')
    elif t == 'home':    _adb(device_id, 'shell', 'input', 'keyevent', 'KEYCODE_HOME')
    elif t == 'long_press':
        x, y, d = int(float(action.get('x',0))), int(float(action.get('y',0))), action.get('duration',2000)
        _adb(device_id, 'shell', 'input', 'swipe', str(x), str(y), str(x), str(y), str(d))
    elif t == 'launch':
        _adb(device_id, 'shell', 'monkey', '-p', action.get('package',''), '1')

def adb_screenshot(device_id):
    result = subprocess.run(['adb','-s',device_id,'exec-out','screencap','-p'], capture_output=True, timeout=15, **_SUBPROCESS_KWARGS)
    if result.returncode != 0 or not result.stdout: raise RuntimeError('截图失败')
    return result.stdout

def adb_get_screen_size(device_id):
    r = _adb(device_id, 'shell', 'wm', 'size')
    m = re.search(r'(\d+)x(\d+)', r.stdout)
    return (int(m.group(1)), int(m.group(2))) if m else (1080,1920)

def grant_permissions(device_id, package):
    for p in ['android.permission.CAMERA','android.permission.READ_EXTERNAL_STORAGE',
              'android.permission.WRITE_EXTERNAL_STORAGE','android.permission.ACCESS_FINE_LOCATION',
              'android.permission.ACCESS_COARSE_LOCATION','android.permission.READ_PHONE_STATE',
              'android.permission.RECORD_AUDIO','android.permission.READ_CONTACTS','android.permission.POST_NOTIFICATIONS']:
        try: _adb(device_id, 'shell', 'pm', 'grant', package, p, timeout=5)
        except: pass


# ============================================================
# 截图压缩 + 保存
# ============================================================

def _compress_png(png_bytes):
    try:
        from PIL import Image; import io
        img = Image.open(io.BytesIO(png_bytes)); img = img.resize((405,900), Image.LANCZOS)
        buf = io.BytesIO(); img.save(buf, format='PNG'); return buf.getvalue()
    except: return png_bytes

def _phash(png_bytes):
    """感知哈希：8x8灰度图 → 64位指纹"""
    try:
        from PIL import Image; import io
        img = Image.open(io.BytesIO(png_bytes)).convert('L').resize((8, 8), Image.LANCZOS)
        pixels = list(img.getdata())
        avg = sum(pixels) / 64
        return sum((1 << i) for i, v in enumerate(pixels) if v > avg)
    except: return 0

def _is_same_page(png1, png2):
    """比较两张截图的感知哈希，汉明距离 < 5 判定为同一页"""
    h1 = _phash(png1)
    h2 = _phash(png2)
    if h1 == 0 or h2 == 0:
        return False  # pHash 失败时不误判
    return (h1 ^ h2).bit_count() < 3

def save_screenshot(png_bytes, execution_id, step_num):
    d = os.path.join(settings.MEDIA_ROOT, 'midscene', str(execution_id))
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, f'step_{step_num}.png')
    with open(p, 'wb') as f: f.write(png_bytes)
    return f'{settings.MEDIA_URL}midscene/{execution_id}/step_{step_num}.png'


# ============================================================
# VLM
# ============================================================

VLM_SYSTEM_PROMPT = """你是移动端自动化测试助手。观察手机截图，精确找出操作目标位置。

截图分辨率: {width}x{height} 像素
{context}

响应（一行JSON）：
{"action":"tap","x_pct":50,"y_pct":25,"step_status":"done","reasoning":"..."}
{"action":"long_press","x_pct":50,"y_pct":25,"duration":2000,"step_status":"done","reasoning":"..."}
{"action":"input","text":"hello","step_status":"done","reasoning":"..."}
{"action":"swipe","x1_pct":50,"y1_pct":80,"x2_pct":50,"y2_pct":30,"step_status":"done","reasoning":"..."}
{"action":"back","step_status":"done","reasoning":"..."}
{"action":"wait","step_status":"in_progress","reasoning":"页面加载中，等待..."}
{"action":"assert","passed":true,"reasoning":"..."}
{"action":"query","data":"提取的数据","reasoning":"..."}
{"action":"done","reasoning":"..."}

step_status 说明：
- "done": 动作直接完成了当前步骤指令，可以进入下一步
- "in_progress": 动作是在处理弹窗/渠道选择/权限请求等障碍（需根据全局提示处理），步骤尚未完成，仍需继续

规则：
- 指令含"验证/检查/确认/断言"→用assert，看图判断passed=true/false
- 指令含"提取/获取/查询"→用query，data字段放提取结果
- 如果界面加载完毕但找不到目标→用swipe滑动查找。绝对不要猜坐标
- 如果界面还在加载/动画/过渡中→用wait等待
- x_pct/y_pct必须是0到100之间的数字（如62表示62%，不要用625这样的三位数）
- x_pct: 从左到右的百分比位置（0=最左，50=中间，100=最右）
- y_pct: 从上到下的百分比位置（0=最上，50=中间，100=最下）
- 智能规划模式下：每次只返回一个操作。完成后返回done。
- 逐行模式下：只返回动作JSON，不要返回done。单行指令只做一个动作。"""

def _parse_vlm_response(content):
    logger.info(f'[VLM] 原始响应(前500字符): {content[:500]}')
    for line in content.strip().split('\n'):
        line = line.strip()
        if not line or not line.startswith('{'): continue
        # 修复常见 VLM JSON 错误
        line = re.sub(r'([,\{])\s*([a-z_]+)="([^"]*)"', r'\1"\2":"\3"', line)
        line = re.sub(r'([,\{])\s*([a-z_]+)=(\d+)', r'\1"\2":\3', line)
        line = re.sub(r'"x"\s*:\s*(\d+),(\d+)\s*,', r'"x":\1,"y":\2,', line)
        # 修复 y_pct="623  → "y_pct":"623" (VLM 常见格式错误)
        line = re.sub(r'([a-z_]+)="(\d+)([,}\]])', r'"\1":"\2"\3', line)
        # 修复 y_pct="   → "y_pct":0 (空值)
        line = re.sub(r'([a-z_]+)="([,}\]])', r'"\1":0\2', line)
        # 修复 VLM 误输出 ] 而非 } 或 ,  (如 y_pct":590]  → y_pct":590,)
        line = re.sub(r'(\d+)\]\s*"', r'\1,"', line)
        try:
            r = json.loads(line)
            if isinstance(r, dict) and 'action' in r: return r
        except: continue
    # 正则兜底
    am = re.search(r'"action"\s*:\s*"([^"]+)"', content)
    if am:
        return {'action': am.group(1),
                'x': int(re.search(r'"x"\s*:\s*(\d+)', content).group(1)) if re.search(r'"x"\s*:\s*(\d+)', content) else 0,
                'y': int(re.search(r'"y"\s*:\s*(\d+)', content).group(1)) if re.search(r'"y"\s*:\s*(\d+)', content) else 0,
                'text': (re.search(r'"text"\s*:\s*"([^"]*)"', content) or re.search(r'"text"\s*:\s*"([^"]*)', content) or [None,''])[1],
                'reasoning': (re.search(r'"reasoning"\s*:\s*"([^"]*)"', content) or [None,''])[1] or '',
                'step_status': (re.search(r'"step_status"\s*:\s*"([^"]+)"', content) or [None,'done'])[1]}
    raise ValueError(f'无法解析 VLM 响应: {content[:300]}')


def call_vlm(png_bytes, instruction, model_config, width=1080, height=1920, context=''):
    png_bytes = _compress_png(png_bytes)
    logger.info(f'[VLM] 截图已压缩: {len(png_bytes)} bytes (405x900)')
    b64 = base64.b64encode(png_bytes).decode('utf-8')
    ctx = f'全局提示: {context}' if context else ''
    system_prompt = (VLM_SYSTEM_PROMPT
                     .replace('{width}', str(width)).replace('{height}', str(height))
                     .replace('{context}', ctx))
    base_url = model_config.base_url if hasattr(model_config, 'base_url') else model_config.get('base_url','')
    api_key = model_config.api_key if hasattr(model_config, 'api_key') else model_config.get('api_key','')
    model_name = model_config.model_name if hasattr(model_config, 'model_name') else model_config.get('model_name','')
    if not api_key: raise ValueError('VLM API Key 未配置')
    api_url = base_url.rstrip('/')
    if not api_url.endswith('/v1'): api_url += '/v1'
    api_url += '/chat/completions'
    logger.info(f'[VLM] 调用模型 {model_name}: {instruction}')
    last_error = None
    for attempt in range(3):
        try:
            with httpx.Client(timeout=180.0) as client:
                r = client.post(api_url, headers={'Authorization': f'Bearer {api_key}','Content-Type':'application/json'},
                                json={'model':model_name, 'messages':[
                                    {'role':'system','content':system_prompt},
                                    {'role':'user','content':[
                                        {'type':'image_url','image_url':{'url':f'data:image/png;base64,{b64}'}},
                                        {'type':'text','text':instruction}]}],
                                      'max_tokens':1024,'temperature':0.1})
                r.raise_for_status()
            break
        except Exception as e:
            last_error = e
            if attempt < 2:
                logger.warning(f'[VLM] 第{attempt+1}次超时，重试...')
                time.sleep(3)
    else:
        raise last_error
    content = r.json()['choices'][0]['message']['content']
    logger.info(f'[VLM] 响应: {content[:200]}')
    return _parse_vlm_response(content)


# ============================================================
# 主执行逻辑
# ============================================================

def run_midscene_test(ai_prompt, device, model_config, execution_record, progress_callback=None):
    steps = parse_ai_prompt(ai_prompt)
    if not steps: raise ValueError('ai_prompt 中没有有效的测试步骤')

    platform = device.platform
    mc = execution_record.midscene_case
    ai_context = (mc.ai_act_context if mc and mc.ai_act_context else '')

    # ---- 平台初始化 ----
    ios_dev = None
    device_id = None
    if platform == 'android':
        device_id = device.adb_serial
        if not device_id: raise ValueError('Android 设备标识无效')
    elif platform == 'ios':
        from .ios_device import IOSDevice
        wda_host = (device.wda_host or 'localhost:8100').replace('http://','').replace('https://','').rstrip('/')
        host, port_str = wda_host.rsplit(':', 1) if ':' in wda_host else (wda_host, '8100')
        port = int(port_str)
        ios_bundle = (mc.app_package if mc and mc.app_package
                      else (mc.project.default_app_package if mc and mc.project else ''))
        ios_dev = IOSDevice(host, int(port), ios_bundle)
        ios_dev.connect()
        device_id = device.tidevice_udid or device.device_id
    else:
        raise ValueError(f'不支持的平台: {platform}')

    logger.info(f'[Runner] 开始执行: {execution_record.id}, 平台={platform}, 设备={device_id}, 步骤数={len(steps)}')

    # ---- 获取分辨率 ----
    if platform == 'android':
        width, height = adb_get_screen_size(device_id)
    else:
        width, height = ios_dev.screen_size
    logger.info(f'[Runner] 屏幕分辨率: {width}x{height}')

    # ---- 启动应用 ----
    if platform == 'android':
        # Android: 用例包名 → 项目Android包名
        app_pkg = (mc.app_package if mc and mc.app_package
                   else (mc.project.default_app_package if mc and mc.project else ''))
        if app_pkg:
            grant_permissions(device_id, app_pkg)
            _adb(device_id, 'shell', 'monkey', '-p', app_pkg, '-c', 'android.intent.category.LAUNCHER', '1', timeout=10)
            time.sleep(2)
    elif platform == 'ios':
        # iOS: 用例包名 → 项目iOS Bundle ID
        ios_bid = (mc.app_package if mc and mc.app_package
                   else (mc.project.default_ios_bundle_id if mc and mc.project else ''))
        if ios_bid:
            ios_dev.bundle_id = ios_bid
            ios_dev.launch_app()
            # iOS 17+ 必须激活应用到前台，否则 WDA tap 会被蒙层挡住
            import requests as _req
            try:
                _req.post(f'http://{host}:{port}/session/{ios_dev.session_id}/wda/apps/activate',
                          json={'bundleId': ios_bid}, timeout=5)
            except Exception: pass
            time.sleep(1)

    # ---- 智能规划模式 ----
    auto_plan = getattr(execution_record, 'auto_plan', False)
    if auto_plan and steps:
        full_goal = ai_prompt.replace('\n', '，')
        logger.info(f'[Runner] aiAct 模式: VLM 持续决策，总目标={full_goal[:80]}...')
        steps = [{'instruction': full_goal}]  # 合并为一个任务

    # ---- 逐步执行 ----
    results = []
    prev_png = None  # 跨步骤持久化，检测步骤间页面变化
    step_retry_count = {}  # 每个步骤的回退计数，防止无限循环
    step_idx = 0
    while step_idx < len(steps):
        step = steps[step_idx]
        instruction = step['instruction']
        is_ai_act = auto_plan  # 智能规划模式 VLM 自己决定 done

        if re.match(r'^打开.*(?:com\.|应用|app|APP)', instruction) and app_package:
            results.append({'step':step_idx+1,'instruction':instruction,'status':'passed',
                            'screenshot':'','aiReasoning':['ADB启动'],'action':'launch'})
            step_idx += 1; continue

        logger.info(f'[Runner] 步骤 {step_idx+1}/{len(steps)}: {instruction}')

        if progress_callback:
            progress_callback(step_idx+1, len(steps), {'type':'step_start','step':step_idx+1,'total':len(steps),
                                                 'instruction':instruction,'progress':int(step_idx/len(steps)*100)})

        reasonings = []
        max_turns = 20 if is_ai_act else 8
        screenshot_url = ''
        last_action = ''
        # 重复动作检测（每步独立）
        last_action_fp = ''
        repeat_count = 0

        try:
            for turn in range(max_turns):
                # 检查是否被用户停止
                execution_record.refresh_from_db()
                if execution_record.status == 'stopped':
                    results.append({'step':step_idx+1,'instruction':instruction,'status':'stopped',
                                    'screenshot':'','aiReasoning':reasonings,'action':'stopped'})
                    step_idx += 1; break
                # 截图（分平台）
                png = ios_dev.screenshot() if ios_dev else adb_screenshot(device_id)

                # 页面未变检测
                page_unchanged = False
                if prev_png is not None and _is_same_page(prev_png, png):
                    if turn == 0 and step_idx > 0:
                        # 新步骤开头页面与上一步结束时一样 → 上一步操作未生效
                        retries = step_retry_count.get(step_idx - 1, 0)
                        if retries < 1:
                            # 移除上一条无效结果，退回重试一次
                            step_retry_count[step_idx - 1] = retries + 1
                            logger.warning(f'[Runner] 新步骤页面未变，上一步操作可能未生效，退回步骤 {step_idx} 重试')
                            if results:
                                results.pop()
                            reasonings = []
                            step_idx -= 1
                            instruction = steps[step_idx]['instruction']
                            prev_png = png
                            continue
                        else:
                            # 已重试过，不再回退，继续当前步骤
                            logger.info(f'[Runner] 上一步已重试过，不再回退')
                    page_unchanged = True
                    logger.info(f'[Runner] 步骤 {step_idx+1} 页面未变化')
                prev_png = png

                # aiAct 模式: 参照 Midscene conversationHistory 机制
                if is_ai_act and reasonings:
                    # 只保留最近3步的简洁描述（避免 prompt 膨胀）
                    hist_items = []
                    for r in reasonings[-3:]:
                        if '] ' in r:
                            txt = r.split('] ', 1)[1]
                            # 去掉冗长推理，只留核心动作
                            txt = re.sub(r'根据(总目标|用户指令|当前步骤).*?(需要|这是|点击)', r'\2', txt)
                            hist_items.append(txt[:60])
                    hist_text = '\n'.join(f'- {h}' for h in hist_items)
                    prompt = (
                        f'总目标: {instruction}\n'
                        f'最近操作: {hist_text}\n'
                        f'注意：如果用户给的是具体步骤，逐条执行，不多做也不少做。'
                        f'全部完成后返回 done，否则执行下一步。'
                    )
                elif is_ai_act:
                    # 第一步：要求 VLM 自己拆解并执行
                    prompt = (
                        f'你需要完成以下任务:\n{instruction}\n\n'
                        f'观察截图，执行第一个操作。完成后逐步继续。'
                        f'注意：如果用户给的是具体步骤，逐条执行，不多做也不少做。'
                        f'全部完成后返回 done。'
                    )
                else:
                    # 条件步骤检测
                    is_conditional = instruction.startswith('如果') or instruction.startswith('若')
                    # 构建本步骤已有的操作历史
                    history_text = ''
                    if reasonings:
                        recent = [r.split('] ', 1)[1] if '] ' in r else r for r in reasonings[-3:]]
                        history_text = '\n'.join(f'第{turn-len(recent)+j+1}次: {r[:80]}' for j, r in enumerate(recent))
                        history_text = f'\n你本轮已执行的操作:\n{history_text}\n请基于以上历史判断下一步，不要重复已做过的操作。'
                    conditional_hint = ''
                    if is_conditional:
                        conditional_hint = '这是一个条件步骤：如果截图中能看到目标就点击，看不到就直接返回 done 跳过。'
                    prompt = (
                        f'当前步骤({step_idx+1}/{len(steps)}): {instruction}\n'
                        f'{conditional_hint}'
                        f'如果当前截图与步骤目标无关（如弹窗、渠道选择页），'
                        f'请根据「全局提示」处理，step_status 填 "in_progress"。'
                        f'只有当你的动作直接执行了这条步骤指令时，step_status 填 "done"。'
                        f'{history_text}'
                    )

                if page_unchanged:
                    prompt += '\n上一次操作后页面未变化，请自行判断是否需要重试或调整。'
                action = call_vlm(png, prompt, model_config, width, height, ai_context)

                # 百分比→像素
                for coord in ('x','y','x1','y1','x2','y2'):
                    pk = f'{coord}_pct'
                    if pk in action and coord not in action:
                        v = float(action[pk])
                        ref = width if coord.startswith('x') else height
                        # 0-100 → 百分比；>100可能是遗漏小数点(如625=62.5%)→除以10
                        pct = v / 10.0 if v > 100 else v
                        action[coord] = int(pct/100.0*ref)

                t = action.get('action','done')
                reason = action.get('reasoning','')
                reasonings.append(f'[轮{turn+1}] {reason}')
                prev_action = last_action
                last_action = t

                # 重复动作检测：连续3次相同操作且页面未变 → 卡死
                action_fp = f"{t}_{action.get('x_pct','')}_{action.get('y_pct','')}"
                if action_fp == last_action_fp and t in ('tap', 'click'):
                    repeat_count += 1
                else:
                    last_action_fp = action_fp
                    repeat_count = 0
                if repeat_count >= 2:
                    raise RuntimeError(f'连续{repeat_count+1}次重复{t}: ({action.get("x_pct","")},{action.get("y_pct","")})，操作无效，页面可能卡死或元素不可点击')

                # 1. 按类型执行
                if t == 'done': screenshot_url = save_screenshot(png, execution_record.id, step_idx+1); break
                if t == 'wait': time.sleep(3); continue  # 加载中等待
                if t == 'swipe':
                    if ios_dev: ios_dev.execute_action(action)
                    else: adb_execute(device_id, action)
                elif t == 'assert':
                    if not action.get('passed',True): raise AssertionError(f'断言失败: {reason}')
                    if is_ai_act and prev_action == 'assert':
                        reasonings.append('[Done] 连续断言通过，任务完成')
                        screenshot_url = save_screenshot(png, execution_record.id, step_idx+1); break
                    if not is_ai_act: screenshot_url = save_screenshot(png, execution_record.id, step_idx+1); break
                elif t == 'query':
                    logger.info(f'[Runner] 提取: {str(action.get("data",""))[:200]}')
                    if not is_ai_act: screenshot_url = save_screenshot(png, execution_record.id, step_idx+1); break
                else:  # tap/click/long_press/input/back
                    if ios_dev: ios_dev.execute_action(action)
                    else: adb_execute(device_id, action)

                # 2. 按动作类型等待
                w = {'tap':2,'click':2,'long_press':0.5,'back':0.5,
                     'input':0.2,'swipe':0.3,'wait':0,'assert':0,'query':0,'done':0}.get(t,0.5)
                if w: time.sleep(w)

                # 3. aiAct 继续循环；逐行模式按 step_status 决定是否结束本轮
                if is_ai_act: continue
                step_status = action.get('step_status', 'done')
                if step_status == 'in_progress':
                    logger.info(f'[Runner] 步骤 {step_idx+1} 处理障碍中，继续...')
                    continue
                # step_status == 'done': 步骤完成
                screenshot_url = save_screenshot(png, execution_record.id, step_idx+1); break
            else:
                raise RuntimeError(f'达到最大轮次({max_turns})')

            results.append({'step':step_idx+1,'instruction':instruction,'status':'passed',
                            'screenshot':screenshot_url,'aiReasoning':reasonings,'action':last_action})

            if progress_callback:
                progress_callback(step_idx+1, len(steps), {'type':'step_done','step':step_idx+1,'total':len(steps),
                                                     'instruction':instruction,'status':'passed',
                                                     'screenshot':screenshot_url,'aiReasoning':reasonings,
                                                     'progress':int((step_idx+1)/len(steps)*100)})
            logger.info(f'[Runner] 步骤 {step_idx+1} 通过: {reasonings[-1] if reasonings else ""}')
            step_idx += 1

        except Exception as e:
            logger.error(f'[Runner] 步骤 {step_idx+1} 失败: {e}')
            su = ''; png = None
            try:
                png = ios_dev.screenshot() if ios_dev else adb_screenshot(device_id)
                su = save_screenshot(png, execution_record.id, step_idx+1)
            except: pass
            results.append({'step':step_idx+1,'instruction':instruction,'status':'failed',
                            'error':str(e),'screenshot':su,'aiReasoning':reasonings})
            step_idx += 1

    # 清理 iOS 连接
    if ios_dev:
        try: ios_dev.disconnect()
        except: pass

    total = len(results); passed = sum(1 for r in results if r['status']=='passed')
    failed = sum(1 for r in results if r['status']=='failed')
    logger.info(f'[Runner] 执行完成: {passed}/{total} 通过')
    return {'totalSteps':total,'passedSteps':passed,'failedSteps':failed,'steps':results,
            'status':'passed' if failed==0 else 'failed'}
