# -*- coding: utf-8 -*-
"""两阶段定位：规划模型描述目标元素 -> locate 模型返回中心坐标。

对齐 Midscene 的 TaskBuilder（createLocateTask）：规划模型只负责"描述元素"，
坐标由专门的 locate 提示词基于截图计算。移动端纯截图视觉识别，不引入
DOM/无障碍树。

容错策略：
  - locate 输出缺失/越界/解析失败 -> 重试 1 次；
  - 重试仍失败且规划输出带直接坐标 -> 降级用直接坐标；
  - 都没有 -> 抛 LocateError，由引擎反馈给规划模型重规划。
"""

import json
import re
import logging
import io

from .actions import INTERACTIVE_ACTIONS, has_direct_coords, locate_fields_for
from .prompts import (
    LOCATE_SYSTEM_PROMPT, build_locate_user_prompt,
    REGION_SYSTEM_PROMPT, build_region_user_prompt,
)

logger = logging.getLogger(__name__)


class LocateError(RuntimeError):
    pass


def _tolerant_json_fix(raw):
    fixed = raw
    # 未加引号的 key（locate: "x" / locate = "x"）-> "locate":"x"
    fixed = re.sub(r'(^|[,{]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*[:=]\s*', r'\1"\2":', fixed)
    # 单引号值 -> 双引号；尾逗号
    fixed = re.sub(r'"\s*:\s*\'([^\']*)\'', r'": "\1"', fixed)
    fixed = re.sub(r',\s*([}\]])', r'\1', fixed)
    return fixed


def _parse_locate_json(raw):
    """从 locate 模型输出里解析 {x_pct, y_pct}，0-100 百分比，容错返回 None。"""
    if not raw:
        return None
    candidates = re.findall(r'\{[^{}]*\}', raw) or [raw]
    for chunk in candidates:
        fixed = _tolerant_json_fix(chunk)
        variants = [chunk, fixed, f'{{{fixed}}}']
        for text in variants:
            try:
                data = json.loads(text)
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            x_pct = data.get('x_pct')
            y_pct = data.get('y_pct')
            try:
                x_pct = float(x_pct)
                y_pct = float(y_pct)
            except (TypeError, ValueError):
                continue
            if not (0 <= x_pct <= 100 and 0 <= y_pct <= 100):
                continue
            return {'x_pct': x_pct, 'y_pct': y_pct, 'reasoning': str(data.get('reasoning', ''))[:200]}
    return None


def _parse_region_json(raw):
    """从区域定位输出解析 {x_pct,y_pct,w_pct,h_pct}（区域左上角+宽高百分比），容错返回 None。"""
    if not raw:
        return None
    candidates = re.findall(r'\{[^{}]*\}', raw) or [raw]
    for chunk in candidates:
        fixed = _tolerant_json_fix(chunk)
        for text in (chunk, fixed, f'{{{fixed}}}'):
            try:
                data = json.loads(text)
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            try:
                x_pct = float(data.get('x_pct'))
                y_pct = float(data.get('y_pct'))
                w_pct = float(data.get('w_pct'))
                h_pct = float(data.get('h_pct'))
            except (TypeError, ValueError):
                continue
            if not (0 <= x_pct <= 100 and 0 <= y_pct <= 100
                    and 1 <= w_pct <= 100 and 1 <= h_pct <= 100):
                continue
            return {
                'x_pct': x_pct, 'y_pct': y_pct, 'w_pct': w_pct, 'h_pct': h_pct,
                'reasoning': str(data.get('reasoning', ''))[:200],
            }
    return None


def _locate_once(target_desc, png, model_config, width, height, context, call_vlm_fn):
    """单次 locate 调用，返回 {'x_pct','y_pct','reasoning'} 或抛 LocateError。"""
    system_prompt = LOCATE_SYSTEM_PROMPT.replace('{width}', str(width)).replace('{height}', str(height))
    if context:
        system_prompt = system_prompt.replace('{context}', f'全局提示: {context}')
    else:
        system_prompt = system_prompt.replace('{context}', '')
    raw = call_vlm_fn(
        png,
        build_locate_user_prompt(target_desc),
        model_config,
        width=width,
        height=height,
        context=context,
        system_prompt=system_prompt,
        return_raw=True,
    )
    logger.info(f'[Locate] 目标={target_desc[:100]}, 响应={str(raw)[:300]}')
    result = _parse_locate_json(raw)
    if not result:
        raise LocateError(f'locate 模型输出无法解析: {str(raw)[:200]}')
    return result


def _locate_region_once(target_desc, png, model_config, width, height, context, call_vlm_fn):
    """单次区域定位调用，返回 {'x_pct','y_pct','w_pct','h_pct','reasoning'} 或抛 LocateError。"""
    system_prompt = REGION_SYSTEM_PROMPT.replace('{width}', str(width)).replace('{height}', str(height))
    if context:
        system_prompt = system_prompt.replace('{context}', f'全局提示: {context}')
    else:
        system_prompt = system_prompt.replace('{context}', '')
    raw = call_vlm_fn(
        png,
        build_region_user_prompt(target_desc),
        model_config,
        width=width,
        height=height,
        context=context,
        system_prompt=system_prompt,
        return_raw=True,
    )
    logger.info(f'[DeepLocate] 区域 目标={target_desc[:100]}, 响应={str(raw)[:300]}')
    result = _parse_region_json(raw)
    if not result:
        raise LocateError(f'区域定位模型输出无法解析: {str(raw)[:200]}')
    return result


def _crop_and_resize(png_bytes, region, width, height, max_side=1024, min_side=64):
    """按区域百分比裁剪原图并放大到最长边 max_side（保持比例）。
    返回 (crop_png, src_rect, resize_wh)；src_rect 为原图像素区域 {'x','y','w','h'}。"""
    from PIL import Image
    img = Image.open(io.BytesIO(png_bytes)).convert('RGB')
    rx = region['x_pct'] / 100.0 * width
    ry = region['y_pct'] / 100.0 * height
    rw = region['w_pct'] / 100.0 * width
    rh = region['h_pct'] / 100.0 * height
    x0 = max(0, int(rx))
    y0 = max(0, int(ry))
    x1 = min(width, int(rx + rw))
    y1 = min(height, int(ry + rh))
    # 最小尺寸不足时围绕区域中心扩展
    if x1 - x0 < min_side or y1 - y0 < min_side:
        cx = (x0 + x1) // 2
        cy = (y0 + y1) // 2
        hw = max(min_side // 2, (x1 - x0) // 2)
        hh = max(min_side // 2, (y1 - y0) // 2)
        x0 = max(0, cx - hw)
        x1 = min(width, cx + hw)
        y0 = max(0, cy - hh)
        y1 = min(height, cy + hh)
    if x1 <= x0 or y1 <= y0:
        raise LocateError(f'深度定位：裁剪区域无效 (x:{x0}-{x1}, y:{y0}-{y1})')
    crop = img.crop((x0, y0, x1, y1))
    cw, ch = crop.size
    scale = max_side / max(cw, ch)
    if scale < 1.0:
        crop = crop.resize((max(1, int(round(cw * scale))), max(1, int(round(ch * scale)))),
                           Image.LANCZOS)
    buf = io.BytesIO()
    crop.save(buf, format='PNG')
    return buf.getvalue(), {'x': x0, 'y': y0, 'w': x1 - x0, 'h': y1 - y0}, crop.size


def deep_locate_element(target_desc, png, model_config, width, height, context='',
                        call_vlm_fn=None, crop_saver=None):
    """深度定位：区域定位 -> 裁剪放大 -> 精确定位，返回原图百分比坐标。
    crop_saver（可选）：接收裁剪 PNG 字节，返回保存后的 URL，写入 deep_locate.crop_url。"""
    call_vlm_fn = call_vlm_fn or _default_call_vlm()
    region = _locate_region_once(target_desc, png, model_config, width, height, context, call_vlm_fn)
    crop_png, src_rect, resize_wh = _crop_and_resize(png, region, width, height)
    crop_url = ''
    if crop_saver is not None:
        try:
            crop_url = crop_saver(crop_png) or ''
        except Exception as e:
            logger.warning(f'[DeepLocate] 裁剪图保存失败: {e}')
    loc = _locate_once(target_desc, crop_png, model_config, resize_wh[0], resize_wh[1],
                       context, call_vlm_fn)
    abs_x = src_rect['x'] + loc['x_pct'] / 100.0 * src_rect['w']
    abs_y = src_rect['y'] + loc['y_pct'] / 100.0 * src_rect['h']
    return {
        'x_pct': abs_x / width * 100.0,
        'y_pct': abs_y / height * 100.0,
        'reasoning': loc.get('reasoning', ''),
        'deep_locate': {
            'source_rect': src_rect,
            'resized': list(resize_wh),
            'crop_url': crop_url,
        },
    }


def locate_element(target_desc, png, model_config, width, height, context='',
                   call_vlm_fn=None, retries=1, info=None):
    """带重试的 locate：失败自动重试 retries 次，仍失败抛 LocateError。
    info（可选 dict）回写 {'retries': n, 'error': last_error}，供 anomaly 采集。"""
    call_vlm_fn = call_vlm_fn or _default_call_vlm()
    last_err = None
    for attempt in range(retries + 1):
        try:
            result = _locate_once(target_desc, png, model_config, width, height, context, call_vlm_fn)
            if info is not None:
                info.update({'retries': attempt, 'error': ''})
            return result
        except Exception as e:
            from ..midscene_runner import ExecutionStopped  # 局部导入避免循环依赖
            if isinstance(e, ExecutionStopped):
                raise  # 用户停止：不重试、不降级，直接向上传递
            last_err = e
            if attempt < retries:
                logger.warning(f'[Locate] 第{attempt + 1}次失败，重试: {e}')
    if info is not None:
        info.update({'retries': retries, 'error': str(last_err)[:300]})
    raise LocateError(f'定位目标失败（已重试 {retries} 次）: {target_desc[:100]}，错误: {last_err}')


def _default_call_vlm():
    from ..midscene_runner import call_vlm
    return call_vlm


def resolve_action_coords(action, png, model_config, width, height, context='',
                          use_locate=True, call_vlm_fn=None, use_deep_locate='off',
                          crop_saver=None):
    """为交互动作补齐像素坐标。

    返回 (ok, action, error_msg, info)：
      - use_locate 且动作带 locate 描述 -> 逐字段 locate 填充坐标；
      - use_deep_locate 控制深度定位：off=不启用；auto=normal 失败自动升级裁剪放大；
        on=直接走裁剪放大，失败回退 normal；
      - locate 失败/无描述 -> 若已有直接坐标则使用；
      - 都没有 -> (False, action, error)。
    info 携带定位过程信息：{'locate': {'retries', 'error', 'fallback', 'deep_locate'}}。
    """
    call_vlm_fn = call_vlm_fn or _default_call_vlm()
    action = dict(action)
    info = {}
    if action.get('action') not in INTERACTIVE_ACTIONS:
        return True, action, '', info

    fields = locate_fields_for(action)
    if use_locate and fields:
        try:
            locate_info = {}
            for locate_key, coord_pair in fields:
                desc = str(action.get(locate_key, '')).strip()
                if not desc:
                    continue
                loc = _locate_field(desc, png, model_config, width, height, context,
                                    call_vlm_fn, use_deep_locate, crop_saver, locate_info)
                x = int(round(loc['x_pct'] / 100.0 * width))
                y = int(round(loc['y_pct'] / 100.0 * height))
                action[coord_pair[0]] = max(0, min(width, x))
                action[coord_pair[1]] = max(0, min(height, y))
            if all(
                action.get(c) is not None
                for pair in _coord_pairs_for(action.get('action')) for c in pair
            ):
                info['locate'] = locate_info
                info['locate']['mode'] = use_deep_locate
                return True, action, '', info
        except LocateError as e:
            logger.warning(f'[Locate] locate 失败，检查是否可降级直接坐标: {e}')
            info['locate'] = {'retries': locate_info.get('retries', 1),
                              'error': str(e)[:300], 'fallback': False}

    if has_direct_coords(action):
        loc = info.setdefault('locate', {})
        loc['fallback'] = True
        return True, action, '', info
    loc = info.setdefault('locate', {})
    loc['fallback'] = False
    return False, action, '无法确定动作坐标：locate 失败且没有直接坐标，请让规划模型改用 x_pct/y_pct 或更准确的元素描述', info


def _locate_field(desc, png, model_config, width, height, context, call_vlm_fn,
                  use_deep_locate, crop_saver, locate_info):
    """单个 locate 字段的定位，按 use_deep_locate 语义执行，返回坐标结果（含原图百分比）。"""
    if use_deep_locate == 'on':
        # 直接深度定位；失败回退 normal（含同图重试）
        try:
            loc = deep_locate_element(desc, png, model_config, width, height,
                                      context, call_vlm_fn, crop_saver=crop_saver)
            locate_info['deep_locate'] = loc['deep_locate']
            return loc
        except LocateError:
            loc = locate_element(desc, png, model_config, width, height, context,
                                 call_vlm_fn=call_vlm_fn, info=locate_info)
            return loc
    if use_deep_locate == 'auto':
        # normal 失败后自动升级一次裁剪放大
        try:
            return locate_element(desc, png, model_config, width, height, context,
                                  call_vlm_fn=call_vlm_fn, info=locate_info)
        except LocateError as normal_err:
            try:
                loc = deep_locate_element(desc, png, model_config, width, height,
                                          context, call_vlm_fn, crop_saver=crop_saver)
                locate_info['deep_locate'] = loc['deep_locate']
                locate_info['retries'] = max(locate_info.get('retries', 0), 1)
                locate_info['error'] = ''
                return loc
            except LocateError as deep_err:
                raise LocateError(f'{normal_err}；深度定位也失败: {deep_err}') from deep_err
    return locate_element(desc, png, model_config, width, height, context,
                          call_vlm_fn=call_vlm_fn, info=locate_info)


def _coord_pairs_for(action_type):
    from .actions import _COORD_PAIRS
    return _COORD_PAIRS.get(action_type, ())
