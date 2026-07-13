# -*- coding: utf-8 -*-
"""
iOS 设备操作 — 通过 WebDriverAgent (WDA) REST API
Android 用 ADB 命令，iOS 用 WDA HTTP 请求。上层 VLM 逻辑完全相同。
"""
import logging
import time
import requests as http
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)


class IOSDevice:
    """iOS 设备操作封装，通过 WDA 的 HTTP API 控制设备"""

    def __init__(self, wda_host='localhost', wda_port=8100, bundle_id=''):
        self.wda_host = wda_host
        self.wda_port = wda_port
        self.bundle_id = bundle_id
        self.base_url = f'http://{wda_host}:{wda_port}'
        self.session_id = None
        self._screen_size = None
        self._connected = False

    # ---- 连接管理 ----

    def connect(self):
        """连接 WDA，获取或创建 session"""
        try:
            # 检查 WDA 状态
            status = http.get(f'{self.base_url}/status', timeout=10)
            if status.status_code != 200:
                raise RuntimeError(f'WDA 状态异常: {status.status_code}')

            # 获取或创建 session
            sessions = http.get(f'{self.base_url}/sessions', timeout=10).json()
            val = sessions.get('value', [])
            # val 可能是 [{"id":"xxx"}] 或 {"sessionId":"xxx"} 或 []
            if isinstance(val, list) and len(val) > 0:
                self.session_id = val[0].get('id')
            elif isinstance(val, dict) and val.get('sessionId'):
                self.session_id = val['sessionId']
            else:
                resp = http.post(f'{self.base_url}/session', json={
                    'capabilities': {}
                }, timeout=30).json()
                self.session_id = resp.get('sessionId')
                logger.info(f'[iOS] 创建新 session: {self.session_id}')

            if not self.session_id:
                raise RuntimeError('无法创建 WDA session')

            # 获取屏幕尺寸
            size_resp = http.get(
                f'{self.base_url}/session/{self.session_id}/window/size',
                timeout=10
            ).json()
            w = size_resp['value']['width']
            h = size_resp['value']['height']
            self._screen_size = (w, h)

            self._connected = True
            logger.info(f'[iOS] WDA 已连接: {self.wda_host}:{self.wda_port}, 屏幕={w}x{h}')
            return True

        except RequestException as e:
            raise RuntimeError(
                f'无法连接 WDA ({self.base_url})。请确保:\n'
                f'1. iPhone 已通过 USB 连接\n'
                f'2. tidevice relay 8100 8100 正在运行\n'
                f'3. WDA 正在 iPhone 上运行\n'
                f'错误: {e}'
            )

    def disconnect(self):
        """断开 WDA session"""
        try:
            if self.session_id:
                http.delete(f'{self.base_url}/session/{self.session_id}', timeout=5)
        except Exception:
            pass
        self._connected = False

    @property
    def connected(self):
        return self._connected

    @property
    def screen_size(self):
        return self._screen_size or (375, 812)  # iPhone X 默认

    # ---- 截图 ----

    def screenshot(self):
        """截取屏幕，返回 PNG 二进制数据"""
        import base64, json
        try:
            resp = http.get(f'{self.base_url}/screenshot', timeout=15)
            if resp.status_code != 200:
                raise RuntimeError(f'WDA截图失败 HTTP {resp.status_code}: {resp.text[:200]}')
            data = resp.json()
            if 'value' not in data:
                raise RuntimeError(f'WDA截图返回异常: {json.dumps(data) if isinstance(data, dict) else data}')
            return base64.b64decode(data['value'])
        except RequestException as e:
            raise RuntimeError(f'WDA截图连接失败(base_url={self.base_url}): {e}')

    def _ensure_session(self):
        """确保 session 有效"""
        if not self.session_id:
            self.connect()

    # ---- 触摸操作 ----

    def tap(self, x, y):
        """点击坐标 — 新版 WDA 6.x+ 用 /wda/tap，降级 /wda/tap/0"""
        self._ensure_session()
        x, y = int(x), int(y)
        logger.info(f'[iOS] tap {x} {y}')
        # 新版端点（WDA 6.x+）
        try:
            resp = http.post(
                f'{self.base_url}/session/{self.session_id}/wda/tap',
                json={'x': x, 'y': y},
                timeout=10
            )
            if resp.status_code == 200:
                return
        except Exception:
            pass
        # 降级旧版端点
        http.post(
            f'{self.base_url}/session/{self.session_id}/wda/tap/0',
            json={'x': x, 'y': y},
            timeout=10
        )

    def long_press(self, x, y, duration=2.0):
        """长按坐标（WDA 单位是秒）"""
        self._ensure_session()
        x, y = int(x), int(y)
        logger.info(f'[iOS] long_press {x} {y} {duration}s')
        http.post(
            f'{self.base_url}/session/{self.session_id}/wda/touchAndHold',
            json={'x': x, 'y': y, 'duration': duration},
            timeout=10
        )

    def swipe(self, x1, y1, x2, y2, duration=0.3):
        """滑动"""
        logger.info(f'[iOS] swipe ({x1},{y1}) → ({x2},{y2})')
        http.post(
            f'{self.base_url}/session/{self.session_id}/wda/dragfromtoforduration',
            json={
                'fromX': int(x1), 'fromY': int(y1),
                'toX': int(x2), 'toY': int(y2),
                'duration': duration,
            },
            timeout=10
        )

    # ---- 文本输入 ----

    def input_text(self, text):
        """输入文本（先点当前焦点元素，再通过 WDA keys 输入）"""
        logger.info(f'[iOS] input "{text}"')
        http.post(
            f'{self.base_url}/session/{self.session_id}/wda/keys',
            json={'value': [text]},
            timeout=10
        )

    # ---- 系统操作 ----

    def home(self):
        """按 Home 键"""
        logger.info('[iOS] home')
        http.post(
            f'{self.base_url}/session/{self.session_id}/wda/pressButton',
            json={'name': 'home'},
            timeout=10
        )

    def app_switcher(self):
        """打开多任务"""
        logger.info('[iOS] app switcher')
        w, h = self.screen_size
        # 从底部向上滑动触发多任务
        self.swipe(w // 2, h - 10, w // 2, h // 4, duration=0.8)

    # ---- 应用管理 ----

    def launch_app(self, bundle_id=None):
        """启动应用并激活前台"""
        bid = bundle_id or self.bundle_id
        if not bid:
            raise ValueError('未指定 Bundle ID')
        logger.info(f'[iOS] launch {bid}')
        try:
            http.post(
                f'{self.base_url}/session/{self.session_id}/wda/apps/launch',
                json={'bundleId': bid},
                timeout=15
            )
        except Exception as e:
            logger.warning(f'[iOS] launch 失败: {e}，尝试 activate')
        # iOS 17+ 需要额外激活
        try:
            http.post(
                f'{self.base_url}/session/{self.session_id}/wda/apps/activate',
                json={'bundleId': bid},
                timeout=5
            )
        except Exception:
            pass
        time.sleep(3)

    def terminate_app(self, bundle_id=None):
        """关闭应用"""
        bid = bundle_id or self.bundle_id
        if not bid:
            return
        logger.info(f'[iOS] terminate {bid}')
        try:
            http.post(
                f'{self.base_url}/session/{self.session_id}/wda/apps/terminate',
                json={'bundleId': bid},
                timeout=10
            )
        except Exception:
            pass

    def is_app_running(self, bundle_id=None):
        """检查应用是否在运行（通过尝试获取 app 状态）"""
        bid = bundle_id or self.bundle_id
        if not bid:
            return False
        try:
            resp = http.get(
                f'{self.base_url}/session/{self.session_id}/wda/apps/state',
                params={'bundleId': bid},
                timeout=5
            )
            return resp.json().get('value', {}).get('state', 0) == 4  # 4=running
        except Exception:
            return False

    # ---- 兼容接口（对接 runner） ----

    def execute_action(self, action):
        """执行 VLM 返回的动作（统一入口）"""
        t = action.get('action', '')

        if t in ('tap', 'click'):
            self.tap(action['x'], action['y'])
        elif t == 'long_press':
            self.long_press(action['x'], action['y'], action.get('duration', 2))
        elif t == 'swipe':
            self.swipe(action['x1'], action['y1'], action['x2'], action['y2'])
        elif t == 'input':
            self.input_text(action['text'])
        elif t == 'back':
            # iOS 没有全局 back 键，用左滑手势模拟
            w, h = self.screen_size
            self.swipe(20, h // 2, w - 20, h // 2)
        elif t == 'home':
            self.home()
        elif t == 'wait' or t == 'done':
            pass
        else:
            logger.warning(f'[iOS] 未知动作: {t}')
