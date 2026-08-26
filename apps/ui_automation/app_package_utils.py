# -*- coding: utf-8 -*-
"""安装包元信息解析工具（APK / IPA）

- Android: 优先 aapt dump badging（自动发现 PATH / ANDROID_HOME / 常见 SDK 路径），
  解析失败时用文件名启发式兜底，包名可手动补填。
- iOS: 直接读 IPA 内 Payload/*.app/Info.plist（plistlib 支持二进制 plist）。
"""
import hashlib
import logging
import os
import platform as sys_platform
import re
import shutil
import subprocess
import zipfile
import plistlib

logger = logging.getLogger(__name__)

_SUBPROCESS_KWARGS = {}
if sys_platform.system() == 'Windows':
    _SUBPROCESS_KWARGS['creationflags'] = subprocess.CREATE_NO_WINDOW

_SDK_HINTS = [
    'D:/androidsdk',
    'D:/Android/Sdk',
    'D:/Android/sdk',
    'C:/Android/Sdk',
    'C:/Users/%USERNAME%/AppData/Local/Android/Sdk',
]


def compute_md5(path):
    """计算文件 MD5"""
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def find_aapt():
    """查找 aapt 可执行文件，找不到返回 None"""
    candidates = []
    # 1. PATH
    for name in ('aapt', 'aapt.exe'):
        p = shutil.which(name)
        if p:
            return p
    # 2. 环境变量
    for env_key in ('ANDROID_HOME', 'ANDROID_SDK_ROOT', 'ANDROID_SDK'):
        sdk = os.environ.get(env_key, '')
        if sdk:
            candidates.append(sdk)
    # 3. 常见路径
    candidates += [p.replace('%USERNAME%', os.environ.get('USERNAME', '')) for p in _SDK_HINTS]
    seen = set()
    for sdk in candidates:
        sdk = sdk.strip()
        if not sdk or sdk in seen:
            continue
        seen.add(sdk)
        build_tools = os.path.join(sdk, 'build-tools')
        if not os.path.isdir(build_tools):
            continue
        try:
            versions = sorted(os.listdir(build_tools), reverse=True)
        except OSError:
            continue
        for v in versions:
            for name in ('aapt.exe', 'aapt'):
                p = os.path.join(build_tools, v, name)
                if os.path.isfile(p):
                    return p
    return None


def _aapt_badging(aapt_path, apk_path):
    """aapt dump badging 输出原始文本，失败抛异常"""
    r = subprocess.run([aapt_path, 'dump', 'badging', apk_path],
                       capture_output=True, text=True, timeout=60,
                       encoding='utf-8', errors='replace', **_SUBPROCESS_KWARGS)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[:300] or r.stdout[:300])
    return r.stdout


def _parse_aapt_output(output):
    """从 aapt badging 输出提取 package/versionName/versionCode"""
    info = {}
    m = re.search(r"package:\s+name='([^']+)'\s+versionCode='([^']*)'\s+versionName='([^']*)'", output)
    if m:
        info['package_name'] = m.group(1)
        info['version_code'] = m.group(2)
        info['version_name'] = m.group(3)
    if not info.get('package_name'):
        m = re.search(r"package:\s+name='([^']+)'", output)
        if m:
            info['package_name'] = m.group(1)
    return info


def _infer_from_filename(filename):
    """文件名启发式兜底：xxx_v1.2.3.apk / xxx-1.2.3(4).ipa 等"""
    info = {}
    base = os.path.splitext(os.path.basename(filename or ''))[0]
    # 版本名：v1.2.3 / 1.2.3 / 1.2.3(4)
    m = re.search(r'[vV]?(\d+(?:\.\d+){1,3})(?:[\(\-_](\d+)\)?)?', base)
    if m:
        info['version_name'] = m.group(1)
        if m.group(2):
            info['version_code'] = m.group(2)
    return info


def parse_apk(path, filename=''):
    """解析 APK，返回 {'package_name','version_name','version_code'}（可缺字段）"""
    info = _infer_from_filename(filename or path)
    aapt = find_aapt()
    if not aapt:
        logger.warning('[Package] 未找到 aapt，APK 元信息使用文件名兜底')
        return info
    try:
        output = _aapt_badging(aapt, path)
        parsed = _parse_aapt_output(output)
        info.update({k: v for k, v in parsed.items() if v})
        logger.info('[Package] aapt 解析成功: %s', parsed)
    except Exception as e:
        logger.warning('[Package] aapt 解析失败，使用文件名兜底: %s', e)
    return info


def parse_ipa(path, filename=''):
    """解析 IPA 内的 Info.plist，返回 {'package_name','version_name','version_code'}"""
    info = _infer_from_filename(filename or path)
    try:
        with zipfile.ZipFile(path) as zf:
            plist_names = [n for n in zf.namelist()
                           if n.endswith('.app/Info.plist') and not n.startswith('__MACOSX')]
            if not plist_names:
                logger.warning('[Package] IPA 中未找到 Info.plist')
                return info
            # 取路径最短的那个（主 App）
            plist_names.sort(key=len)
            with zf.open(plist_names[0]) as f:
                data = plistlib.load(f)
        mapping = {
            'package_name': ('CFBundleIdentifier',),
            'version_name': ('CFBundleShortVersionString',),
            'version_code': ('CFBundleVersion',),
        }
        for key, plist_keys in mapping.items():
            for pk in plist_keys:
                v = data.get(pk)
                if v:
                    info[key] = str(v)
                    break
        logger.info('[Package] IPA Info.plist 解析成功: %s', info)
    except Exception as e:
        logger.warning('[Package] IPA 解析失败，使用文件名兜底: %s', e)
    return info


def parse_package_file(path, platform, filename=''):
    """按平台解析安装包元信息"""
    if platform == 'ios':
        return parse_ipa(path, filename)
    return parse_apk(path, filename)
