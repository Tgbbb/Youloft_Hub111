# -*- coding: utf-8 -*-
"""
Midscene AI 移动端自动化 - API 视图
"""
import logging
import os
import subprocess
import platform as sys_platform
from django.utils import timezone
from django.db import models as db_models
from django.db import transaction
from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.views import APIView

from .models import (
    MidsceneProject, MidsceneDevice, MidsceneCase, MidsceneCaseFolder,
    MidsceneExecutionRecord, MidsceneAppPackage, MidsceneAppInstallRecord,
    MidsceneGlobalConfig, MidsceneSequence, MidsceneSequenceRun,
)
from .serializers_midscene import (
    MidsceneProjectSerializer,
    MidsceneDeviceSerializer,
    MidsceneDeviceSimpleSerializer,
    MidsceneCaseSerializer,
    MidsceneCaseCreateSerializer,
    MidsceneCaseFolderSerializer,
    MidsceneExecutionRecordSerializer,
    MidsceneAppPackageSerializer,
    MidsceneAppInstallRecordSerializer,
    MidsceneGlobalConfigSerializer,
    MidsceneSequenceSerializer,
    MidsceneSequenceCreateSerializer,
    MidsceneSequenceRunSerializer,
    MidsceneSequenceRunDetailSerializer,
)

logger = logging.getLogger(__name__)


def _fmt_resolution(res):
    """把录制条目里的 resolution 规范为 'WxH' 字符串，兼容 dict/str/None。"""
    if not res:
        return ''
    if isinstance(res, str):
        return res.strip().lower().replace(' ', '')
    try:
        w = res.get('width')
        h = res.get('height')
    except AttributeError:
        return ''
    if not w or not h:
        return ''
    return f'{int(w)}x{int(h)}'


def _read_device_resolution(device):
    """读取当前设备实测分辨率（'WxH' 字符串），失败返回 None。
    Android 走 screencap 实测；iOS 走 WDA 截图像素尺寸（与录制存的口径一致）。"""
    if device.platform == 'android':
        try:
            from .midscene_runner import adb_get_screen_size
            w, h = adb_get_screen_size(device.adb_serial)
            return f'{w}x{h}'
        except Exception as e:
            logger.warning(f'[ReplayMatch] 读取 Android 分辨率失败: {e}')
    elif device.platform == 'ios':
        try:
            from .ios_device import IOSDevice
            from .midscene_runner import png_size
            wda_host = (device.wda_host or 'localhost:8100').replace('http://', '').replace('https://', '').rstrip('/')
            host, port_str = wda_host.rsplit(':', 1) if ':' in wda_host else (wda_host, '8100')
            ios = IOSDevice(host, int(port_str))
            ios.connect()
            try:
                size = png_size(ios.screenshot())
            finally:
                ios.disconnect()
            if size:
                return f'{size[0]}x{size[1]}'
        except Exception as e:
            logger.warning(f'[ReplayMatch] 读取 iOS 分辨率失败: {e}')
    return None


def _match_device_replay(device, existing, replay_index):
    """单台设备的回放脚本匹配检查（不依赖 request）。

    device: MidsceneDevice；existing: 录制条目列表；replay_index: 当前选中索引。
    返回匹配结果 dict（与单设备 replay_match 接口返回结构一致）；
    existing 非列表或索引越界时返回 None。
    """
    if not isinstance(existing, list) or replay_index < 0 or replay_index >= len(existing):
        return None
    selected = existing[replay_index] or {}
    rec_dev = selected.get('device') or {}
    rec_res_str = _fmt_resolution(rec_dev.get('resolution'))
    cur_res_str = _read_device_resolution(device)

    cur_platform = device.platform
    cur_model = (device.name or '').strip()
    rec_platform = str(rec_dev.get('platform', '') or '')
    rec_model = str(rec_dev.get('name', '') or '').strip()

    # 匹配等级：分辨率一致优先于型号一致；取不到分辨率 → unknown 不阻塞
    if rec_platform and rec_platform != cur_platform:
        level = 'platform_mismatch'
    elif not rec_res_str or not cur_res_str:
        level = 'unknown'
    elif rec_res_str == cur_res_str:
        level = 'exact' if (cur_model and rec_model and cur_model == rec_model) else 'ok'
    else:
        level = 'resolution_mismatch'

    # 候选：平台一致 + 分辨率一致的其他条目（型号一致优先）
    candidates = []
    for i, entry in enumerate(existing):
        if i == replay_index or not entry:
            continue
        e_dev = entry.get('device') or {}
        if str(e_dev.get('platform', '') or '') != cur_platform:
            continue
        e_res_str = _fmt_resolution(e_dev.get('resolution'))
        if not e_res_str or not cur_res_str or e_res_str != cur_res_str:
            continue
        candidates.append({
            'index': i,
            'name': entry.get('name', ''),
            'device': e_dev,
        })
    candidates.sort(key=lambda c: 0 if (c['device'].get('name') or '').strip() == cur_model else 1)

    return {
        'match_level': level,
        'current_device': {
            'platform': cur_platform,
            'model': cur_model,
            'resolution': cur_res_str,
        },
        'selected': {
            'index': replay_index,
            'name': selected.get('name', ''),
            'device': rec_dev,
        },
        'matching': candidates,
    }


def _pick_best_replay(device, existing):
    """为该设备从全部录制条目中独立挑最匹配的一条（不锚定当前选中索引）。

    匹配优先级：平台一致 → 分辨率一致 → 型号一致（列表靠前=最新优先）。
    existing 非列表时返回 None；否则始终返回 dict：
      match_level: exact/ok/unknown/no_match
      recommended_index: 最匹配条目索引（no_match/无法推荐时为 None）
      recommended_name, has_match, current_device
    """
    if not isinstance(existing, list):
        return None
    cur_platform = device.platform
    cur_model = (device.name or '').strip()
    cur_res_str = _read_device_resolution(device)

    same_platform = [
        (i, entry) for i, entry in enumerate(existing)
        if entry and str((entry.get('device') or {}).get('platform', '') or '') == cur_platform
    ]
    if not same_platform:
        return {
            'match_level': 'no_match',
            'recommended_index': None,
            'recommended_name': '',
            'has_match': False,
            'current_device': {
                'platform': cur_platform,
                'model': cur_model,
                'resolution': cur_res_str,
            },
        }

    # 分辨率可比时优先分辨率一致（型号一致再优先）；列表顺序即最新优先
    scored = []
    if cur_res_str:
        for i, entry in same_platform:
            e_res_str = _fmt_resolution((entry.get('device') or {}).get('resolution'))
            if e_res_str:
                scored.append((i, entry, e_res_str))
    if scored:
        res_matched = [x for x in scored if x[2] == cur_res_str]
        pool = res_matched if res_matched else scored
        pool.sort(key=lambda x: 0 if str((x[1].get('device') or {}).get('name') or '').strip() == cur_model else 1)
        i, entry, e_res_str = pool[0]
        if res_matched:
            rec_model = str((entry.get('device') or {}).get('name') or '').strip()
            level = 'exact' if (cur_model and rec_model and rec_model == cur_model) else 'ok'
        else:
            level = 'no_match'
        recommended_index = i if level != 'no_match' else None
    else:
        # 分辨率信息不足：取最新同平台条目兜底，unknown 不阻塞
        i, entry = same_platform[0]
        level = 'unknown'
        recommended_index = i

    return {
        'match_level': level,
        'recommended_index': recommended_index,
        'recommended_name': entry.get('name', '') if recommended_index is not None else '',
        'has_match': level != 'no_match',
        'current_device': {
            'platform': cur_platform,
            'model': cur_model,
            'resolution': cur_res_str,
        },
    }


class MidsceneProjectViewSet(viewsets.ModelViewSet):
    """Midscene 移动端测试项目"""
    queryset = MidsceneProject.objects.all()
    serializer_class = MidsceneProjectSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'updated_at', 'name']

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(
            db_models.Q(owner=self.request.user) |
            db_models.Q(members=self.request.user)
        ).distinct()

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class MidsceneDeviceViewSet(viewsets.ModelViewSet):
    """Midscene 设备管理（Android + iOS）"""
    queryset = MidsceneDevice.objects.all()
    serializer_class = MidsceneDeviceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['platform', 'status']
    search_fields = ['name', 'device_id']
    ordering_fields = ['platform', 'status', 'created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return MidsceneDeviceSerializer
        return super().get_serializer_class()

    @action(detail=False, methods=['get'])
    def simple_list(self, request):
        """返回简化设备列表（用于下拉选择）"""
        devices = self.get_queryset().filter(status__in=['online', 'available'])
        serializer = MidsceneDeviceSimpleSerializer(devices, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='connect_network')
    def connect_network(self, request):
        """通过 WiFi ADB 连接局域网 Android 设备"""
        ip = request.data.get('ip', '').strip()
        port = request.data.get('port', 5555)

        if not ip:
            return Response({'error': '请输入设备 IP 地址'}, status=400)

        target = f'{ip}:{port}'
        kwargs = {}
        if sys_platform.system() == 'Windows':
            kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

        result = subprocess.run(
            ['adb', 'connect', target],
            capture_output=True, text=True, timeout=10, **kwargs
        )
        output = (result.stdout + result.stderr).strip()

        if 'connected' in output.lower():
            # 获取设备属性
            name = ''
            version = ''
            try:
                info = subprocess.run(
                    ['adb', '-s', target, 'shell', 'getprop', 'ro.product.model'],
                    capture_output=True, text=True, timeout=5, **kwargs
                )
                if info.returncode == 0:
                    name = info.stdout.strip()
                ver = subprocess.run(
                    ['adb', '-s', target, 'shell', 'getprop', 'ro.build.version.release'],
                    capture_output=True, text=True, timeout=5, **kwargs
                )
                if ver.returncode == 0:
                    version = ver.stdout.strip()
            except Exception:
                pass

            device, _ = MidsceneDevice.objects.update_or_create(
                device_id=target,
                defaults={
                    'platform': 'android',
                    'status': 'available',
                    'adb_serial': target,
                    'name': name or target,
                    'android_version': version,
                    'ip_address': ip,
                    'port': port,
                }
            )
            from .serializers_midscene import MidsceneDeviceSimpleSerializer
            return Response({
                'success': True,
                'message': f'已连接到 {target}',
                'device': MidsceneDeviceSimpleSerializer(device).data,
            })
        else:
            return Response({
                'success': False,
                'message': f'连接失败: {output}',
            }, status=400)

    @action(detail=True, methods=['post'], url_path='disconnect_network')
    def disconnect_network(self, request, pk=None):
        """断开 WiFi ADB 连接"""
        device = self.get_object()
        target = f'{device.ip_address}:{device.port}' if device.ip_address else device.device_id

        kwargs = {}
        if sys_platform.system() == 'Windows':
            kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

        subprocess.run(['adb', 'disconnect', target], capture_output=True, timeout=5, **kwargs)
        device.status = 'offline'
        device.save(update_fields=['status'])
        return Response({'success': True, 'message': f'已断开 {target}'})

    @action(detail=False, methods=['post'])
    def discover_android(self, request):
        """发现 Android 设备（ADB）"""
        adb_path = request.data.get('adb_path', 'adb')
        try:
            kwargs = {}
            if sys_platform.system() == 'Windows':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

            result = subprocess.run(
                [adb_path, 'devices', '-l'],
                capture_output=True, text=True, timeout=10, **kwargs
            )
            lines = result.stdout.strip().split('\n')[1:]
            discovered = []
            for line in lines:
                line = line.strip()
                if not line or 'offline' in line:
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    device_id = parts[0]
                    status = 'available' if parts[1] == 'device' else 'offline'

                    # 更新或创建
                    device, created = MidsceneDevice.objects.update_or_create(
                        device_id=device_id,
                        defaults={
                            'platform': 'android',
                            'status': status,
                            'adb_serial': device_id,
                            'name': '',
                        }
                    )
                    # 尝试获取设备名称
                    try:
                        info = subprocess.run(
                            [adb_path, '-s', device_id, 'shell', 'getprop', 'ro.product.model'],
                            capture_output=True, text=True, timeout=5, **kwargs
                        )
                        if info.returncode == 0 and info.stdout.strip():
                            device.name = info.stdout.strip()
                        ver = subprocess.run(
                            [adb_path, '-s', device_id, 'shell', 'getprop', 'ro.build.version.release'],
                            capture_output=True, text=True, timeout=5, **kwargs
                        )
                        if ver.returncode == 0 and ver.stdout.strip():
                            device.android_version = ver.stdout.strip()
                        device.save(update_fields=['name', 'android_version'])
                    except Exception:
                        pass

                    discovered.append(device_id)

            # 把不在线的旧设备标记为 offline
            MidsceneDevice.objects.filter(platform='android').exclude(
                device_id__in=discovered
            ).update(status='offline')

            return Response({
                'message': f'发现 {len(discovered)} 台 Android 设备',
                'devices': discovered,
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['post'])
    def discover_ios(self, request):
        """发现 iOS 设备（go-ios / tidevice）"""
        import subprocess
        import platform as sys_platform
        import json as json_module

        tool = request.data.get('tool_path', '')
        wda_host = request.data.get('wda_host', '')

        # 自动检测工具路径
        if not tool:
            candidates = [
                r'E:\iOS相关\go-ios-win\ios.exe',  # Windows go-ios
                'ios', 'tidevice',
            ]
            for c in candidates:
                if os.path.exists(c) or subprocess.run(['where', c] if sys_platform.system() == 'Windows' else ['which', c],
                                        capture_output=True, timeout=3).returncode == 0:
                    tool = c; break

        if not tool:
            return Response({'error': '找不到 iOS 工具。请安装 go-ios 或 tidevice'}, status=500)

        try:
            kwargs = {}
            if sys_platform.system() == 'Windows':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

            is_go_ios = 'ios.exe' in tool or tool.endswith('ios')
            discovered = []

            if is_go_ios:
                # go-ios: 输出 JSON
                result = subprocess.run([tool, 'list'], capture_output=True, text=True,
                                        timeout=10, **kwargs)
                for line in result.stdout.strip().split('\n'):
                    try:
                        data = json_module.loads(line)
                        if 'deviceList' in data:
                            for udid in data['deviceList']:
                                device, _ = MidsceneDevice.objects.update_or_create(
                                    device_id=udid,
                                    defaults={
                                        'platform': 'ios',
                                        'status': 'available',
                                        'tidevice_udid': udid,
                                        'name': f'iPhone ({udid[:12]}...)',
                                        'wda_host': wda_host or '127.0.0.1:8100',
                                    }
                                )
                                discovered.append(udid)
                    except json_module.JSONDecodeError:
                        pass
            else:
                # tidevice: 纯文本输出
                result = subprocess.run([tool, 'list'], capture_output=True, text=True,
                                        timeout=10, **kwargs)
                for line in result.stdout.strip().split('\n'):
                    parts = line.strip().split()
                    if parts:
                        udid = parts[0]
                        name = ' '.join(parts[1:]) if len(parts) > 1 else f'iPhone ({udid[:12]}...)'
                        device, _ = MidsceneDevice.objects.update_or_create(
                            device_id=udid,
                            defaults={
                                'platform': 'ios',
                                'status': 'available',
                                'tidevice_udid': udid,
                                'name': name,
                                'wda_host': wda_host or '127.0.0.1:8100',
                            }
                        )
                        discovered.append(udid)

            return Response({
                'message': f'发现 {len(discovered)} 台 iOS 设备',
                'devices': discovered,
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=True, methods=['post'])
    def lock(self, request, pk=None):
        """锁定设备"""
        device = self.get_object()
        try:
            device.lock(request.user)
            return Response({'status': 'locked'})
        except ValueError as e:
            return Response({'error': str(e)}, status=409)

    @action(detail=True, methods=['post'])
    def unlock(self, request, pk=None):
        """解锁设备"""
        device = self.get_object()
        device.unlock()
        return Response({'status': 'unlocked'})

    @action(detail=True, methods=['get'])
    def test_wda(self, request, pk=None):
        """测试 WDA 连通性"""
        device = self.get_object()
        host = request.query_params.get('host', device.wda_host or 'localhost:8100')
        # 去掉协议前缀和尾部斜杠
        host = host.replace('http://', '').replace('https://', '').rstrip('/')
        try:
            import requests as req
            resp = req.get(f'http://{host}/status', timeout=5)
            ok = resp.status_code == 200
            if ok:
                device.status = 'online'
                device.save(update_fields=['status'])
            return Response({'ok': ok, 'data': resp.json() if ok else {}})
        except Exception as e:
            device.status = 'offline'
            device.save(update_fields=['status'])
            return Response({'ok': False, 'error': str(e)})

    @action(detail=True, methods=['post'])
    def screenshot(self, request, pk=None):
        """获取设备实时截图（Base64）"""
        device = self.get_object()
        import subprocess
        import platform as sys_platform
        import base64

        kwargs = {}
        if sys_platform.system() == 'Windows':
            kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

        try:
            if device.platform == 'android':
                adb_path = request.data.get('adb_path', 'adb')
                result = subprocess.run(
                    [adb_path, '-s', device.adb_serial, 'exec-out', 'screencap', '-p'],
                    capture_output=True, timeout=10, **kwargs
                )
                if result.returncode == 0:
                    b64 = base64.b64encode(result.stdout).decode('utf-8')
                    return Response({'screenshot': f'data:image/png;base64,{b64}'})
            elif device.platform == 'ios':
                # iOS 用 WDA 截图
                import requests as req
                wda_url = f'http://{device.wda_host}/screenshot'
                resp = req.get(wda_url, timeout=10)
                if resp.status_code == 200:
                    b64 = base64.b64encode(resp.content).decode('utf-8')
                    return Response({'screenshot': f'data:image/png;base64,{b64}'})

            return Response({'error': '截图失败'}, status=500)
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class MidsceneRecordSessionViewSet(viewsets.GenericViewSet):
    """真机手操录制会话（Android getevent 采集 -> 动作脚本预览/保存）。"""
    permission_classes = [IsAuthenticated]

    def _get_device(self, device_id):
        try:
            device = MidsceneDevice.objects.get(id=int(device_id))
        except (TypeError, ValueError, MidsceneDevice.DoesNotExist):
            return None
        return device

    @action(detail=False, methods=['post'])
    def start(self, request):
        """锁设备并启动 getevent 采集，返回 session_id。"""
        device_id = request.data.get('device_id')
        device = self._get_device(device_id)
        if not device:
            return Response({'error': '设备不存在'}, status=404)
        if device.platform != 'android':
            return Response({'error': '真机手操录制 v1 仅支持 Android 设备'}, status=400)
        if device.status == 'locked' and device.locked_by != request.user:
            return Response({'error': f'设备已被 {device.locked_by.username} 锁定'}, status=409)
        if device.status in ('offline',):
            return Response({'error': f'设备 {device.name or device.device_id} 不在线'}, status=400)
        busy = MidsceneExecutionRecord.objects.filter(
            device=device, status__in=['pending', 'running'],
        ).exists()
        if busy:
            return Response({'error': f'设备 {device.name or device.device_id} 正在执行中，请等待完成后再发起'}, status=409)
        try:
            from .manual_recorder import start_session
            session_id = start_session(device, request.user)
        except ValueError as e:
            return Response({'error': str(e)}, status=409)
        except Exception as e:
            logger.error(f'[ManualRecorder] 启动录制失败: {e}', exc_info=True)
            return Response({'error': f'启动录制失败: {e}'}, status=500)
        return Response({
            'session_id': session_id,
            'device_id': device.id,
            'device_name': device.name or device.device_id,
            'started_at': timezone.now().isoformat(),
            'message': '录制已开始，请在手机上操作（抬起停顿 1.5 秒自动切分为一步）',
        })

    @action(detail=True, methods=['post'])
    def stop(self, request, pk=None):
        """停止采集、解析动作脚本并返回预览（数据缓存 30 分钟供保存）。"""
        try:
            from .manual_recorder import stop_session
            steps, size = stop_session(pk)
        except KeyError:
            return Response({'error': '录制会话不存在或已结束，请重新开始录制'}, status=404)
        except ValueError as e:
            return Response({'error': str(e)}, status=400)
        except Exception as e:
            logger.error(f'[ManualRecorder] 停止录制失败: {e}', exc_info=True)
            return Response({'error': f'停止录制失败: {e}'}, status=500)
        return Response({
            'session_id': pk,
            'steps': steps,
            'step_count': len(steps),
            'resolution': {'width': size['width'], 'height': size['height']},
            'message': f'录制已停止，共解析 {len(steps)} 步',
        })

    @action(detail=True, methods=['post'])
    def save(self, request, pk=None):
        """把已停止的录制保存为独立用例（绑定项目）。

        入参：name / project_id（必选）。生成 ai_prompt 占位步骤 + replay_data
        单条目（mode='manual'），脚本库按该标记聚合；不再支持追加到现有用例。
        """
        try:
            from .manual_recorder import get_stopped_preview, build_replay_data, discard_stopped
            preview = get_stopped_preview(pk)
        except KeyError:
            return Response({'error': '录制会话不存在或已过期，请重新录制'}, status=404)
        steps = preview['steps']
        if not steps:
            return Response({'error': '没有解析到任何动作步骤，请重新录制'}, status=400)
        try:
            device = MidsceneDevice.objects.get(id=preview['device_id'])
        except MidsceneDevice.DoesNotExist:
            return Response({'error': '录制设备不存在'}, status=404)

        case_id = request.data.get('case_id')
        name = str(request.data.get('name', '')).strip()
        entry = build_replay_data(steps, device, preview['width'], preview['height'], name=name)
        device_name = device.name or device.device_id
        entry['name'] = name or f"手操录制 {timezone.now().strftime('%m-%d %H:%M')} [{device_name}]"

        if case_id not in (None, '', 0, '0'):
            return Response({'error': '手操录制已改为独立用例保存，不再追加到现有用例'}, status=400)

        project_id = request.data.get('project_id')
        if project_id in (None, '', 'null'):
            return Response({'error': '请选择所属项目'}, status=400)
        try:
            project_id = int(project_id)
        except (TypeError, ValueError):
            return Response({'error': '无效的项目 ID'}, status=400)

        # 占位 ai_prompt 每步一行，回放/直放都按 replay_data 执行
        ai_prompt = '\n'.join(f'步骤 {i+1}' for i in range(len(steps)))
        midscene_case = MidsceneCase.objects.create(
            name=name or f"手操录制 {timezone.now().strftime('%m-%d %H:%M')} [{device_name}]",
            ai_prompt=ai_prompt,
            project_id=project_id,
            replay_data=[entry],
            created_by=request.user,
        )
        discard_stopped(pk)
        return Response({
            'case_id': midscene_case.id,
            'case_name': midscene_case.name,
            'replay_index': 0,
            'step_count': len(steps),
            'message': f'已新建用例「{midscene_case.name}」（回放脚本 #0）',
        })

    @action(detail=False, methods=['get'])
    def scripts(self, request):
        """手操脚本库：聚合 replay_data 中含 mode=='manual' 条目的用例。

        查询参数 project（可选）：按项目过滤。返回每条 manual 条目的
        entry_index 供执行/重命名/删除定位；历史"追加到普通用例"的数据
        同样列出（兼容旧保存方式）。latest_result 为该用例最近一次执行。
        """
        qs = MidsceneCase.objects.all()
        project_id = request.query_params.get('project')
        if project_id not in (None, '', 'null'):
            try:
                qs = qs.filter(project_id=int(project_id))
            except (TypeError, ValueError):
                return Response({'error': '无效的项目 ID'}, status=400)
        results = []
        for case in qs:
            raw = case.replay_data
            entries = raw if isinstance(raw, list) else ([raw] if isinstance(raw, dict) else [])
            for idx, entry in enumerate(entries):
                if not isinstance(entry, dict) or entry.get('mode') != 'manual':
                    continue
                dev = entry.get('device') or {}
                res = dev.get('resolution') if isinstance(dev, dict) else None
                steps = entry.get('steps')
                latest = case.execution_records.first()
                results.append({
                    'case_id': case.id,
                    'entry_index': idx,
                    'name': entry.get('name') or case.name,
                    'project': case.project.name if case.project else '',
                    'project_id': case.project_id,
                    'device': (dev or {}).get('name') or '',
                    'platform': (dev or {}).get('platform') or 'android',
                    'resolution': {
                        'width': res.get('width') if isinstance(res, dict) else None,
                        'height': res.get('height') if isinstance(res, dict) else None,
                    } if isinstance(res, dict) else None,
                    'step_count': len(steps) if isinstance(steps, list) else 0,
                    'entry_count': len(entries),
                    'recorded_at': entry.get('recorded_at') or case.updated_at.isoformat(),
                    'latest_result': {
                        'status': latest.status,
                        'pass_rate': latest.pass_rate,
                        'finished_at': latest.finished_at,
                    } if latest else None,
                })
        results.sort(key=lambda r: str(r['recorded_at'] or ''), reverse=True)
        return Response(results)


class MidsceneCaseViewSet(viewsets.ModelViewSet):
    """Midscene AI 用例"""
    queryset = MidsceneCase.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['project']
    search_fields = ['name', 'ai_prompt']
    ordering_fields = ['created_at', 'updated_at', 'name']

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return MidsceneCaseCreateSerializer
        return MidsceneCaseSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['get'], url_path='replay_match')
    def replay_match(self, request, pk=None):
        """回放前设备匹配检查（只读，不创建执行）。
        返回选中录制条目与当前设备（型号=设备名、平台、分辨率）的匹配等级，
        以及用例内更匹配的候选条目，供前端提示切换脚本/重新录制。
        adb/WDA 读不到分辨率时降级为 unknown，不阻塞执行。"""
        midscene_case = self.get_object()
        device_id = request.query_params.get('device_id')
        try:
            replay_index = int(request.query_params.get('replay_index', 0) or 0)
        except (TypeError, ValueError):
            return Response({'error': '无效的录制索引'}, status=400)
        if not device_id:
            return Response({'error': '请选择执行设备'}, status=400)
        try:
            device = MidsceneDevice.objects.get(id=device_id)
        except MidsceneDevice.DoesNotExist:
            return Response({'error': '设备不存在'}, status=404)

        existing = midscene_case.replay_data
        if isinstance(existing, dict):
            existing = [existing]
        result = _match_device_replay(device, existing, replay_index)
        if result is None:
            return Response({'error': '无效的录制索引'}, status=400)
        return Response(result)

    @action(detail=True, methods=['post'], url_path='replay_match_batch')
    def replay_match_batch(self, request, pk=None):
        """多设备回放前批量匹配检查：每台设备独立挑自己的最优脚本。

        入参 {devices: [id...], replay_index}。当前选中的 replay_index 只作为
        兜底与对比基准：每台设备从全部录制条目里挑最匹配的一条
        （平台+分辨率+型号），返回 recommended_index / needs_switch；
        adb/WDA 读不到分辨率时该台降级 unknown 不阻塞。
        """
        midscene_case = self.get_object()
        devices = request.data.get('devices') or []
        try:
            replay_index = int(request.data.get('replay_index', 0) or 0)
        except (TypeError, ValueError):
            return Response({'error': '无效的录制索引'}, status=400)
        if not devices:
            return Response({'error': '请选择执行设备'}, status=400)

        existing = midscene_case.replay_data
        if isinstance(existing, dict):
            existing = [existing]
        if not isinstance(existing, list) or replay_index < 0 or replay_index >= len(existing):
            return Response({'error': '无效的录制索引'}, status=400)

        results = []
        for did in devices:
            try:
                device = MidsceneDevice.objects.get(id=did)
            except MidsceneDevice.DoesNotExist:
                results.append({'device_id': did, 'error': '设备不存在'})
                continue
            pick = _pick_best_replay(device, existing)
            if pick is None:
                res = {'error': '无效的录制索引'}
            else:
                selected = existing[replay_index] or {}
                recommended_index = pick['recommended_index']
                res = {
                    'match_level': pick['match_level'],
                    'current_index': replay_index,
                    'current_name': selected.get('name', ''),
                    'recommended_index': recommended_index if recommended_index is not None else replay_index,
                    'recommended_name': pick['recommended_name'] or selected.get('name', ''),
                    'needs_switch': recommended_index is not None and recommended_index != replay_index,
                    'has_match': pick['has_match'],
                    'current_device': pick['current_device'],
                }
            results.append({
                'device_id': device.id,
                'device_name': device.name or device.device_id,
                **res,
            })
        return Response({'results': results})

    @action(detail=True, methods=['post'])
    def clear_replay(self, request, pk=None):
        """清除录制数据"""
        midscene_case = self.get_object()
        midscene_case.replay_data = None
        midscene_case.save(update_fields=['replay_data'])
        return Response({'message': '录制数据已清除'})

    @action(detail=True, methods=['post'], url_path='delete_replay')
    def delete_replay(self, request, pk=None):
        """删除指定录制条目"""
        midscene_case = self.get_object()
        index = request.data.get('index', 0)
        existing = midscene_case.replay_data
        if isinstance(existing, dict):
            existing = [existing]
        if not isinstance(existing, list) or index >= len(existing):
            return Response({'error': '无效的索引'}, status=400)
        existing.pop(index)
        midscene_case.replay_data = existing if existing else None
        midscene_case.save(update_fields=['replay_data'])
        return Response({'message': '已删除', 'replay_data': midscene_case.replay_data})

    @action(detail=True, methods=['post'], url_path='rename_replay')
    def rename_replay(self, request, pk=None):
        """重命名指定录制条目"""
        midscene_case = self.get_object()
        index = request.data.get('index', 0)
        try:
            index = int(index)
        except (TypeError, ValueError):
            return Response({'error': '无效的索引'}, status=400)
        name = str(request.data.get('name', '')).strip()
        if not name:
            return Response({'error': '名称不能为空'}, status=400)
        existing = midscene_case.replay_data
        if isinstance(existing, dict):
            existing = [existing]
        if not isinstance(existing, list) or index < 0 or index >= len(existing):
            return Response({'error': '无效的索引'}, status=400)
        existing[index]['name'] = name
        midscene_case.save(update_fields=['replay_data'])
        return Response({'message': '已重命名', 'replay_data': midscene_case.replay_data})

    @action(detail=True, methods=['post'], url_path='rerun_step')
    def rerun_step(self, request, pk=None):
        """单步重录：在用户手动准备好的页面上只录制目标步骤，并写回对应回放脚本。

        入参：replay_index（目标脚本）/ step_index（步骤序号，从 0 起）/ device_id。
        创建一条新的执行记录并投递 rerun_step_task；不启动不清理应用，尊重手动页面状态。
        """
        midscene_case = self.get_object()
        from .midscene_runner import parse_ai_prompt
        try:
            step_index = int(request.data.get('step_index'))
            replay_index = int(request.data.get('replay_index', 0))
            device_id = int(request.data.get('device_id'))
        except (TypeError, ValueError):
            return Response({'error': '参数无效: step_index/replay_index/device_id 必须为整数'}, status=400)

        steps = parse_ai_prompt(midscene_case.ai_prompt)
        if step_index < 0 or step_index >= len(steps):
            return Response({'error': f'步骤索引越界（共 {len(steps)} 步）'}, status=400)
        if steps[step_index].get('type') == 'branch':
            return Response({'error': '暂不支持重录分支头步骤，请重录其子步骤或整条脚本'}, status=400)

        raw = midscene_case.replay_data
        entries = raw if isinstance(raw, list) else ([raw] if isinstance(raw, dict) else [])
        if replay_index < 0 or replay_index >= len(entries):
            return Response({'error': '回放脚本不存在'}, status=400)
        entry_steps = entries[replay_index].get('steps') if isinstance(entries[replay_index], dict) else None
        if not isinstance(entry_steps, list) or step_index >= len(entry_steps):
            return Response({'error': f'脚本步骤索引越界（共 {len(entry_steps) if isinstance(entry_steps, list) else 0} 步）'}, status=400)

        with transaction.atomic():
            try:
                device = MidsceneDevice.objects.select_for_update().get(id=device_id)
            except MidsceneDevice.DoesNotExist:
                return Response({'error': '设备不存在'}, status=404)
            if device.status == 'locked' and device.locked_by != request.user:
                return Response({'error': f'设备已被 {device.locked_by.username} 锁定'}, status=409)
            if device.status in ('offline',):
                return Response({'error': f'设备 {device.name or device.device_id} 不在线'}, status=400)
            busy = MidsceneExecutionRecord.objects.filter(
                device=device, status__in=['pending', 'running'],
            ).exists()
            if busy:
                return Response({'error': f'设备 {device.name or device.device_id} 正在执行中，请等待完成后再发起'}, status=409)

            execution = MidsceneExecutionRecord.objects.create(
                midscene_case=midscene_case, case_name=midscene_case.name,
                device=device, platform=device.platform, status='pending',
                auto_plan=False, total_steps=len(steps), executed_by=request.user,
                model_config_snapshot={
                    'name': midscene_case.ai_model_config.name if midscene_case.ai_model_config else '',
                    'model_type': midscene_case.ai_model_config.model_type if midscene_case.ai_model_config else '',
                    'model_name': midscene_case.ai_model_config.model_name if midscene_case.ai_model_config else '',
                } if midscene_case.ai_model_config else {},
            )

        from .tasks import rerun_step_task
        task = rerun_step_task.delay(execution.id, replay_index, step_index)
        execution.task_id = task.id
        execution.save(update_fields=['task_id'])
        return Response({'execution_id': execution.id, 'task_id': task.id, 'status': 'pending'})

    @action(detail=True, methods=['post'], url_path='rerun_else')
    def rerun_else(self, request, pk=None):
        """整组补录 else：在 else 态(条件不满足)页面上只重录分支头 else 槽 + 该分支 else 组子步骤。

        入参：replay_index（目标脚本）/ branch_step_index（分支头步骤序号，从 0 起）/ device_id。
        创建一条新的执行记录并投递 rerun_else_task；不启动不清理应用，尊重手动 else 态页面。
        """
        midscene_case = self.get_object()
        from .midscene_runner import parse_ai_prompt
        try:
            branch_step_index = int(request.data.get('branch_step_index'))
            replay_index = int(request.data.get('replay_index', 0))
            device_id = int(request.data.get('device_id'))
        except (TypeError, ValueError):
            return Response({'error': '参数无效: branch_step_index/replay_index/device_id 必须为整数'}, status=400)

        steps = parse_ai_prompt(midscene_case.ai_prompt)
        if branch_step_index < 0 or branch_step_index >= len(steps):
            return Response({'error': f'分支头步骤索引越界（共 {len(steps)} 步）'}, status=400)
        head = steps[branch_step_index]
        if head.get('type') != 'branch':
            return Response({'error': '目标步骤不是分支头，无法补录 else'}, status=400)
        else_indices = head.get('else_children', [])
        if not else_indices:
            return Response({'error': '该分支没有 else 组子步骤，无法补录'}, status=400)

        raw = midscene_case.replay_data
        entries = raw if isinstance(raw, list) else ([raw] if isinstance(raw, dict) else [])
        if replay_index < 0 or replay_index >= len(entries):
            return Response({'error': '回放脚本不存在'}, status=400)
        entry_steps = entries[replay_index].get('steps') if isinstance(entries[replay_index], dict) else None
        if not isinstance(entry_steps, list) or branch_step_index >= len(entry_steps):
            return Response({'error': '脚本分支头索引越界'}, status=400)

        with transaction.atomic():
            try:
                device = MidsceneDevice.objects.select_for_update().get(id=device_id)
            except MidsceneDevice.DoesNotExist:
                return Response({'error': '设备不存在'}, status=404)
            if device.status == 'locked' and device.locked_by != request.user:
                return Response({'error': f'设备已被 {device.locked_by.username} 锁定'}, status=409)
            if device.status in ('offline',):
                return Response({'error': f'设备 {device.name or device.device_id} 不在线'}, status=400)
            busy = MidsceneExecutionRecord.objects.filter(
                device=device, status__in=['pending', 'running'],
            ).exists()
            if busy:
                return Response({'error': f'设备 {device.name or device.device_id} 正在执行中，请等待完成后再发起'}, status=409)

            execution = MidsceneExecutionRecord.objects.create(
                midscene_case=midscene_case, case_name=midscene_case.name,
                device=device, platform=device.platform, status='pending',
                auto_plan=False, total_steps=len(steps), executed_by=request.user,
                model_config_snapshot={
                    'name': midscene_case.ai_model_config.name if midscene_case.ai_model_config else '',
                    'model_type': midscene_case.ai_model_config.model_type if midscene_case.ai_model_config else '',
                    'model_name': midscene_case.ai_model_config.model_name if midscene_case.ai_model_config else '',
                } if midscene_case.ai_model_config else {},
            )

        from .tasks import rerun_else_task
        task = rerun_else_task.delay(execution.id, replay_index, branch_step_index)
        execution.task_id = task.id
        execution.save(update_fields=['task_id'])
        return Response({'execution_id': execution.id, 'task_id': task.id, 'status': 'pending'})

    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        """执行 Midscene 用例"""
        midscene_case = self.get_object()
        auto_plan = request.data.get('auto_plan', False)
        record_mode = request.data.get('record', False)
        replay_mode = request.data.get('replay', False)
        clear_app_data = request.data.get('clear_app_data', False)
        script_replay = bool(request.data.get('script_replay', False))
        if script_replay:
            if not replay_mode:
                return Response({'error': '纯动作直放需要开启回放模式'}, status=400)
            auto_plan = False

        # 安装包（可选）：选了执行前覆盖安装并清数据；包平台需与设备平台一致
        install_package_id = request.data.get('install_package_id')
        if install_package_id in (None, '', 0, '0', 'null'):
            install_package_id = None
        else:
            try:
                install_package_id = int(install_package_id)
            except (TypeError, ValueError):
                return Response({'error': '无效的安装包 ID'}, status=400)
            install_pkg_obj = MidsceneAppPackage.objects.filter(id=install_package_id).first()
            if not install_pkg_obj:
                return Response({'error': '安装包不存在或已被删除'}, status=400)

        # 解析设备请求：兼容单设备 device_id 与多设备 devices 数组
        try:
            default_replay_index = int(request.data.get('replay_index', 0) or 0)
        except (TypeError, ValueError):
            return Response({'error': '无效的录制索引'}, status=400)
        use_batch = 'devices' in request.data
        if use_batch:
            devices = request.data.get('devices') or []
            if not devices:
                return Response({'error': '请选择执行设备'}, status=400)
            requests = []
            for d in devices:
                if isinstance(d, dict):
                    did = d.get('device_id')
                    try:
                        ridx = int(d.get('replay_index', default_replay_index) or default_replay_index)
                    except (TypeError, ValueError):
                        return Response({'error': '无效的录制索引'}, status=400)
                else:
                    did = d
                    ridx = default_replay_index
                try:
                    did = int(did)
                except (TypeError, ValueError):
                    return Response({'error': f'无效的设备 ID: {did}'}, status=400)
                requests.append((did, ridx))
        else:
            device_id = request.data.get('device_id')
            if not device_id:
                return Response({'error': '请选择执行设备'}, status=400)
            try:
                requests = [(int(device_id), default_replay_index)]
            except (TypeError, ValueError):
                return Response({'error': '无效的设备 ID'}, status=400)

        # 同一设备互斥：事务内按 id 排序锁设备行（避免多请求锁序不同死锁），
        # 校验无 pending/running 任务后才创建；失败设备带 error 不阻断其余。
        # Celery 任务在事务提交后再投递，避免 worker 抢先执行读不到记录。
        from .midscene_runner import parse_ai_prompt
        if script_replay:
            raw = midscene_case.replay_data
            entries = raw if isinstance(raw, list) else ([raw] if isinstance(raw, dict) else [])
            if not entries or default_replay_index >= len(entries):
                return Response({'error': '无效的录制索引'}, status=400)
            entry = entries[default_replay_index] if isinstance(entries[default_replay_index], dict) else {}
            entry_steps = entry.get('steps') if isinstance(entry, dict) else None
            if not isinstance(entry_steps, list) or not entry_steps:
                return Response({'error': '回放脚本没有有效的步骤'}, status=400)
            steps = entry_steps
        else:
            steps = parse_ai_prompt(midscene_case.ai_prompt)
        created = []
        failed = []
        with transaction.atomic():
            for did, ridx in sorted(requests, key=lambda x: x[0]):
                try:
                    device = MidsceneDevice.objects.select_for_update().get(id=did)
                except MidsceneDevice.DoesNotExist:
                    failed.append({'device_id': did, 'status': 404, 'error': '设备不存在'})
                    continue

                if device.status == 'locked' and device.locked_by != request.user:
                    failed.append({'device_id': did, 'status': 409,
                                   'error': f'设备已被 {device.locked_by.username} 锁定'})
                    continue
                if device.status in ('offline',):
                    failed.append({'device_id': did, 'status': 400,
                                   'error': f'设备 {device.name or device.device_id} 不在线'})
                    continue
                if install_package_id and install_pkg_obj.platform != device.platform:
                    failed.append({'device_id': did, 'status': 400,
                                   'error': f'安装包平台与设备 {device.name or device.device_id} 不匹配（{install_pkg_obj.get_platform_display()} 包）'})
                    continue
                busy = MidsceneExecutionRecord.objects.filter(
                    device=device, status__in=['pending', 'running'],
                ).exists()
                if busy:
                    failed.append({
                        'device_id': did,
                        'status': 409,
                        'error': f'设备 {device.name or device.device_id} 正在执行中，请等待完成后再发起',
                    })
                    continue

                execution = MidsceneExecutionRecord.objects.create(
                    midscene_case=midscene_case,
                    case_name=midscene_case.name,
                    device=device,
                    platform=device.platform,
                    status='pending',
                    auto_plan=auto_plan,
                    total_steps=len(steps),
                    executed_by=request.user,
                    model_config_snapshot={
                        'name': midscene_case.ai_model_config.name if midscene_case.ai_model_config else '',
                        'model_type': midscene_case.ai_model_config.model_type if midscene_case.ai_model_config else '',
                        'model_name': midscene_case.ai_model_config.model_name if midscene_case.ai_model_config else '',
                    } if midscene_case.ai_model_config else {},
                )
                created.append((execution, ridx))

        # 事务提交后投递任务（record/replay 参数各设备一致，replay_index 可逐台指定）
        from .tasks import execute_midscene_task
        results = []
        for execution, ridx in created:
            task = execute_midscene_task.delay(
                execution.id, record_mode=record_mode, replay_mode=replay_mode,
                replay_index=ridx, clear_app_data=clear_app_data,
                install_package_id=install_package_id,
                script_replay=script_replay,
            )
            execution.task_id = task.id
            execution.save(update_fields=['task_id'])
            results.append({
                'execution_id': execution.id,
                'task_id': task.id,
                'device_id': execution.device_id,
                'replay_index': ridx,
            })

        if not use_batch:
            # 单设备旧格式：返回原结构（失败时保持原错误语义）
            if not results:
                err = failed[0] if failed else {'error': '创建执行失败'}
                return Response(err, status=err.get('status', 400))
            return Response({'execution_id': results[0]['execution_id'], 'task_id': results[0]['task_id'],
                             'status': 'pending'})

        return Response({
            'executions': results,
            'failed': failed,
            'status': 'pending',
        })

    @action(detail=False, methods=['post'])
    def generate_steps(self, request):
        """AI 生成详细测试步骤（从简要描述展开）"""
        description = request.data.get('description', '')
        if not description:
            return Response({'error': '请输入测试描述'}, status=400)

        # 使用 AI 展开
        from apps.requirement_analysis.views import AIModelConfig
        config_id = request.data.get('model_config_id')

        try:
            if config_id:
                config = AIModelConfig.objects.get(id=config_id, is_active=True)
            else:
                config = AIModelConfig.objects.filter(
                    role='app_automation_vision', is_active=True
                ).first()

            if not config:
                return Response({'error': '没有可用的 VLM 模型配置'}, status=400)

            # 构造 prompt
            prompt = f"""你是一个移动端测试专家。请将以下测试场景描述展开为详细的、可执行的测试步骤。
每行一个步骤，用自然语言描述具体操作。注意：
1. 步骤要足够具体，AI 能直接执行（如"点击底部'我的'按钮"而不是"进入我的页面"）
2. 包括必要的等待步骤
3. 包括验证步骤（如"验证页面显示'登录成功'"）

场景描述：
{description}

请直接输出步骤列表，每行一个步骤，以序号开头："""

            import requests as req
            import json

            headers = {
                'Authorization': f'Bearer {config.api_key}',
                'Content-Type': 'application/json',
            }
            resp = req.post(
                f'{config.base_url}/chat/completions',
                json={
                    'model': config.model_name,
                    'messages': [{'role': 'user', 'content': prompt}],
                    'max_tokens': config.max_tokens,
                    'temperature': config.temperature,
                },
                headers=headers,
                timeout=30,
            )

            if resp.status_code == 200:
                data = resp.json()
                content = data['choices'][0]['message']['content']
                return Response({'steps': content})
            else:
                return Response({'error': f'AI 调用失败: {resp.status_code}'}, status=500)

        except Exception as e:
            logger.error(f'AI 生成步骤失败: {e}')
            return Response({'error': str(e)}, status=500)


class MidsceneCaseFolderViewSet(viewsets.ModelViewSet):
    """Midscene 用例文件夹"""
    queryset = MidsceneCaseFolder.objects.all()
    serializer_class = MidsceneCaseFolderSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['project', 'parent_folder']
    search_fields = ['name']
    ordering_fields = ['name', 'created_at']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        accessible = MidsceneProject.objects.filter(
            db_models.Q(owner=user) | db_models.Q(members=user)
        ).distinct()
        return qs.filter(
            db_models.Q(project__in=accessible) |
            db_models.Q(project__isnull=True)
        ).select_related('project')

    def perform_create(self, serializer):
        project = serializer.validated_data.get('project')
        if project is not None:
            if not MidsceneProject.objects.filter(
                db_models.Q(owner=self.request.user) |
                db_models.Q(members=self.request.user),
                id=project.id,
            ).exists():
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied('无权在此项目下创建文件夹')
        serializer.save(created_by=self.request.user)


class MidsceneExecutionRecordViewSet(viewsets.ReadOnlyModelViewSet, mixins.DestroyModelMixin):
    """Midscene 执行记录"""
    queryset = MidsceneExecutionRecord.objects.all()
    serializer_class = MidsceneExecutionRecordSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'platform']
    search_fields = ['case_name']

    def get_queryset(self):
        qs = super().get_queryset()
        project_id = self.request.query_params.get('project')
        if project_id:
            qs = qs.filter(midscene_case__project_id=project_id)
        return qs
    ordering_fields = ['created_at', 'status']

    @action(detail=False, methods=['post'], url_path='batch_delete')
    def batch_delete(self, request):
        """批量删除执行记录"""
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': '请选择要删除的记录'}, status=400)
        deleted, _ = MidsceneExecutionRecord.objects.filter(id__in=ids).delete()
        return Response({'message': f'已删除 {deleted} 条记录'})

    @action(detail=True, methods=['post'])
    def stop(self, request, pk=None):
        """停止执行：pending 直接停止；running 置 stopping，由 worker 确认后转 stopped。

        threads 池下 revoke(terminate=True) 无法杀线程，真正停止靠执行链路
        轮询检查 status；置 stopping 后前端显示「停止中」，等 worker 确认再转 stopped，
        避免用户误以为设备已经停了。"""
        execution = self.get_object()
        if execution.status not in ('pending', 'running'):
            return Response({'error': '任务不在执行中'}, status=400)

        # 撤销 Celery 任务
        if execution.task_id:
            from celery import current_app
            current_app.control.revoke(execution.task_id, terminate=True)

        if execution.status == 'pending':
            # 尚未开始：直接停止，无需等 worker 确认
            execution.status = 'stopped'
            execution.finished_at = timezone.now()
            execution.save(update_fields=['status', 'finished_at'])
            return Response({'status': 'stopped'})

        # 执行中：先置 stopping，worker 下一轮检查到后真正收尾
        execution.status = 'stopping'
        execution.save(update_fields=['status'])
        return Response({'status': 'stopping'})

    @action(detail=True, methods=['get'], url_path='report')
    def report(self, request, pk=None):
        """获取 HTML 测试报告（懒生成：首次访问生成并写 report_path，之后直接复用）。

        参数 force=1 可强制重新生成。
        """
        execution = self.get_object()
        force = str(request.query_params.get('force', '')).lower() in ('1', 'true', 'yes')
        try:
            from .midscene_report import generate_report_file
            report_path = generate_report_file(execution, force=force)
            return Response({'url': report_path, 'status': execution.status})
        except Exception as e:
            logger.error(f'[Report] 生成测试报告失败: {e}', exc_info=True)
            return Response({'error': f'生成报告失败: {e}'}, status=500)


class MidsceneAppPackageViewSet(viewsets.ModelViewSet):
    """Midscene 安装包管理（APK/IPA 上传、删除、一键安装）"""
    queryset = MidsceneAppPackage.objects.all()
    serializer_class = MidsceneAppPackageSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['platform', 'package_name']
    search_fields = ['name', 'package_name', 'version_name']
    ordering_fields = ['created_at', 'updated_at', 'file_size']

    def create(self, request, *args, **kwargs):
        """上传安装包：自动识别平台、解析包名/版本、MD5 去重。"""
        upload = request.FILES.get('file')
        if not upload:
            return Response({'error': '请选择要上传的安装包文件'}, status=400)

        filename = (upload.name or '').strip()
        ext = os.path.splitext(filename)[1].lower()
        platform_map = {'.apk': 'android', '.ipa': 'ios'}
        platform = platform_map.get(ext)
        if not platform:
            return Response({'error': f'不支持的文件类型: {ext or "未知"}，仅支持 .apk / .ipa'}, status=400)

        from .app_package_utils import compute_md5, parse_package_file

        # 先落盘（Django 写入 media），再从文件解析元信息
        instance = MidsceneAppPackage(
            name=request.data.get('name', '').strip() or os.path.splitext(filename)[0],
            platform=platform,
            file=upload,
            description=request.data.get('description', '').strip(),
            created_by=request.user,
        )
        instance.save()

        try:
            path = instance.file.path
            instance.file_size = os.path.getsize(path)
            instance.md5 = compute_md5(path)
            info = parse_package_file(path, platform, filename)
            instance.package_name = info.get('package_name', '')
            instance.version_name = info.get('version_name', '')
            instance.version_code = info.get('version_code', '')
            if not instance.package_name and not request.data.get('name'):
                instance.name = os.path.splitext(filename)[0]
            instance.save()
        except Exception as e:
            logger.error(f'[Package] 安装包解析失败: {e}', exc_info=True)
            file_name = instance.file.name
            instance.delete()
            if file_name:
                try:
                    instance.file.storage.delete(file_name)
                except Exception:
                    pass
            return Response({'error': f'安装包解析失败: {e}'}, status=400)

        # 同包名同版本去重（解析出包名后才检查）
        if instance.package_name and instance.version_code:
            dup = MidsceneAppPackage.objects.filter(
                platform=platform,
                package_name=instance.package_name,
                version_code=instance.version_code,
            ).exclude(id=instance.id).first()
            if dup:
                file_name = instance.file.name
                instance.delete()
                if file_name:
                    try:
                        instance.file.storage.delete(file_name)
                    except Exception:
                        pass
                return Response({
                    'error': f'已存在相同包名和版本: {dup.name} ({dup.version_name})，无需重复上传',
                    'existing_id': dup.id,
                }, status=400)

        serializer = self.get_serializer(instance)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance):
        file_name = instance.file.name
        super().perform_destroy(instance)
        if file_name:
            try:
                instance.file.storage.delete(file_name)
            except Exception:
                logger.warning(f'[Package] 删除安装包文件失败: {file_name}')

    @action(detail=True, methods=['post'], url_path='install')
    def install(self, request, pk=None):
        """一键安装到指定设备（每设备一个安装任务，异步执行）。"""
        pkg = self.get_object()
        # 包平台需与设备平台一致（Android 装 apk / iOS 装 ipa）

        device_ids = request.data.get('device_ids') or request.data.get('devices')
        if not device_ids:
            return Response({'error': '请选择安装设备'}, status=400)
        if isinstance(device_ids, (str, int)):
            device_ids = [device_ids]
        try:
            device_ids = sorted({int(x) for x in device_ids})
        except (TypeError, ValueError):
            return Response({'error': '无效的设备 ID'}, status=400)

        options = {
            'overwrite': bool(request.data.get('overwrite', True)),
            'downgrade': bool(request.data.get('downgrade', False)),
            'launch': bool(request.data.get('launch', False)),
        }

        # 与执行共用互斥：设备在线、未被他人锁定、无 pending/running 任务
        created = []
        failed = []
        with transaction.atomic():
            for did in device_ids:
                try:
                    device = MidsceneDevice.objects.select_for_update().get(id=did)
                except MidsceneDevice.DoesNotExist:
                    failed.append({'device_id': did, 'error': '设备不存在'})
                    continue
                if device.status == 'locked' and device.locked_by != request.user:
                    failed.append({'device_id': did,
                                   'error': f'设备已被 {device.locked_by.username} 锁定'})
                    continue
                if device.status in ('offline',):
                    failed.append({'device_id': did,
                                   'error': f'设备 {device.name or device.device_id} 不在线'})
                    continue
                if pkg.platform != device.platform:
                    failed.append({'device_id': did,
                                   'error': f'安装包平台与设备不匹配（{pkg.get_platform_display()} 包 -> {device.get_platform_display()} 设备）'})
                    continue
                busy = (
                    MidsceneExecutionRecord.objects.filter(
                        device=device, status__in=['pending', 'running', 'stopping']
                    ).exists()
                    or MidsceneAppInstallRecord.objects.filter(
                        device=device, status__in=['pending', 'running']
                    ).exists()
                )
                if busy:
                    failed.append({'device_id': did,
                                   'error': f'设备 {device.name or device.device_id} 正在执行任务，请等待完成'})
                    continue
                record = MidsceneAppInstallRecord.objects.create(
                    package=pkg, device=device, status='pending',
                    options=options, created_by=request.user,
                )
                created.append(record)

        # 事务提交后投递任务
        from .tasks import install_app_package_task
        results = []
        for record in created:
            task = install_app_package_task.delay(record.id)
            record.task_id = task.id
            record.save(update_fields=['task_id'])
            results.append({
                'install_id': record.id,
                'task_id': task.id,
                'device_id': record.device_id,
            })

        return Response({
            'installs': results,
            'failed': failed,
            'message': f'已提交 {len(results)} 台设备安装，{len(failed)} 台失败',
        })


class MidsceneAppInstallRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """Midscene 安装记录（只读，前端轮询进度）"""
    queryset = MidsceneAppInstallRecord.objects.all()
    serializer_class = MidsceneAppInstallRecordSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['package', 'device', 'status']
    ordering_fields = ['created_at', 'status', 'duration']


class MidsceneConfigView(APIView):
    """Midscene 全局引擎配置（单例）：GET 读当前配置与生效值，PUT 保存（改完立即生效）。"""
    permission_classes = [IsAuthenticated]

    def _payload(self, cfg):
        from .midscene_ai.engine import resolve_locate_switches
        eff_locate, eff_deep = resolve_locate_switches()
        return {
            'config': MidsceneGlobalConfigSerializer(cfg).data,
            'effective': {
                'use_locate': eff_locate,
                'use_deep_locate': eff_deep,
            },
            'defaults': {
                'use_locate': True,
                'use_deep_locate': 'auto',
            },
        }

    def get(self, request):
        cfg = MidsceneGlobalConfig.get_singleton()
        return Response(self._payload(cfg))

    def put(self, request):
        cfg = MidsceneGlobalConfig.get_singleton()
        if 'use_locate' in request.data:
            v = request.data.get('use_locate')
            if isinstance(v, str):
                low = v.strip().lower()
                if low in ('true', '1', 'yes', 'on'):
                    cfg.use_locate = True
                elif low in ('false', '0', 'no', 'off'):
                    cfg.use_locate = False
                elif low in ('', 'null', 'none'):
                    cfg.use_locate = None
                else:
                    return Response({'error': 'use_locate 仅支持 true/false/不覆盖'}, status=400)
            else:
                cfg.use_locate = v
        if 'use_deep_locate' in request.data:
            deep = str(request.data.get('use_deep_locate', '')).strip().lower()
            if deep not in ('', 'off', 'auto', 'on'):
                return Response({'error': 'use_deep_locate 仅支持 off/auto/on/不覆盖'}, status=400)
            cfg.use_deep_locate = deep
        cfg.updated_by = request.user
        cfg.save()
        return Response(self._payload(cfg))


class MidsceneSequenceViewSet(viewsets.ModelViewSet):
    """Midscene 用例编排：有序串联多个用例，单设备一次执行。"""
    queryset = MidsceneSequence.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['project', 'folder']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'updated_at', 'name']

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return MidsceneSequenceCreateSerializer
        return MidsceneSequenceSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['get'], url_path='match_summary')
    def sequence_match(self, request, pk=None):
        """跑链前按执行设备逐项返回将用的录制与匹配等级（只读，不阻塞）。"""
        sequence = self.get_object()
        device_id = request.query_params.get('device_id')
        if not device_id:
            return Response({'error': '请选择执行设备'}, status=400)
        try:
            device = MidsceneDevice.objects.get(id=device_id)
        except MidsceneDevice.DoesNotExist:
            return Response({'error': '设备不存在'}, status=404)

        items = list(sequence.items.select_related('case').order_by('order'))
        if not items:
            return Response({'error': '编排没有用例'}, status=400)
        cur = {
            'platform': device.platform,
            'model': (device.name or '').strip(),
            'resolution': _read_device_resolution(device),
        }
        rows = []
        for it in items:
            existing = it.case.replay_data
            if isinstance(existing, dict):
                existing = [existing]
            has_replay = bool(existing)
            pick = _pick_best_replay(device, existing) if has_replay else None
            pick = pick or {
                'match_level': 'no_replay', 'recommended_index': None,
                'recommended_name': '', 'has_match': False, 'current_device': cur,
            }
            used_index = it.replay_index if it.replay_mode == 'fixed' else (
                pick.get('recommended_index') if pick.get('recommended_index') is not None
                else it.replay_index)
            rows.append({
                'item_id': it.id, 'order': it.order, 'case_id': it.case_id,
                'case_name': it.case.name, 'replay_mode': it.replay_mode,
                'replay_index': it.replay_index, 'used_index': used_index,
                'match_level': pick.get('match_level', 'no_replay'),
                'recommended_name': pick.get('recommended_name', ''),
            })
        return Response({'device': cur, 'items': rows})

    @action(detail=True, methods=['post'], url_path='execute')
    def sequence_execute(self, request, pk=None):
        """执行一条编排（单设备）：锁设备、建父 run、投递编排任务。"""
        sequence = self.get_object()
        from .midscene_runner import parse_ai_prompt

        device_id = request.data.get('device_id')
        if not device_id:
            return Response({'error': '请选择执行设备'}, status=400)
        try:
            device_id = int(device_id)
        except (TypeError, ValueError):
            return Response({'error': '无效的设备 ID'}, status=400)

        install_package_id = request.data.get('install_package_id')
        if install_package_id in (None, '', 0, '0', 'null'):
            install_package_id = None
        else:
            try:
                install_package_id = int(install_package_id)
            except (TypeError, ValueError):
                return Response({'error': '无效的安装包 ID'}, status=400)
            chain_pkg_obj = MidsceneAppPackage.objects.filter(id=install_package_id).first()
            if not chain_pkg_obj:
                return Response({'error': '安装包不存在或已被删除'}, status=400)

        items = list(sequence.items.select_related('case').order_by('order'))
        if not items:
            return Response({'error': '编排没有用例'}, status=400)
        total_steps = sum(len(parse_ai_prompt(it.case.ai_prompt)) for it in items)

        run = None
        with transaction.atomic():
            try:
                device = MidsceneDevice.objects.select_for_update().get(id=device_id)
            except MidsceneDevice.DoesNotExist:
                return Response({'error': '设备不存在'}, status=404)

            if device.status == 'locked' and device.locked_by != request.user:
                return Response({'error': f'设备已被 {device.locked_by.username} 锁定'}, status=409)
            if device.status == 'offline':
                return Response({'error': f'设备 {device.name or device.device_id} 不在线'}, status=400)
            if install_package_id and chain_pkg_obj.platform != device.platform:
                return Response({'error': f'安装包平台与设备 {device.name or device.device_id} 不匹配（{chain_pkg_obj.get_platform_display()} 包）'}, status=400)

            for it in items:
                if it.install_package_id:
                    item_pkg = MidsceneAppPackage.objects.filter(id=it.install_package_id).first()
                    if not item_pkg:
                        return Response({'error': f'编排项 {it.case.name} 的安装包不存在或已被删除'}, status=400)
                    if item_pkg.platform != device.platform:
                        return Response({'error': f'编排项 {it.case.name} 的安装包平台与设备不匹配（{item_pkg.get_platform_display()} 包 -> {device.get_platform_display()} 设备）'}, status=400)

            busy_run = MidsceneSequenceRun.objects.filter(
                device=device, status__in=['pending', 'running', 'stopping']).exists()
            busy_exec = MidsceneExecutionRecord.objects.filter(
                device=device, status__in=['pending', 'running']).exists()
            if busy_run or busy_exec:
                return Response({'error': f'设备 {device.name or device.device_id} 正在执行中，请等待完成后再发起'}, status=409)

            run = MidsceneSequenceRun.objects.create(
                sequence=sequence, sequence_name=sequence.name, device=device,
                platform=device.platform, status='pending', total_steps=total_steps,
                executed_by=request.user,
            )

        # 事务提交后投递任务
        from .tasks import execute_midscene_sequence_task
        task = execute_midscene_sequence_task.delay(run.id, install_package_id=install_package_id)
        run.task_id = task.id
        run.save(update_fields=['task_id'])
        return Response({'run_id': run.id, 'task_id': task.id, 'status': 'pending'})


class MidsceneSequenceRunViewSet(viewsets.ReadOnlyModelViewSet, mixins.DestroyModelMixin):
    """编排执行记录（父 run + 每项子执行）。"""
    queryset = MidsceneSequenceRun.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['sequence', 'device', 'status']
    ordering_fields = ['created_at', 'started_at']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return MidsceneSequenceRunDetailSerializer
        return MidsceneSequenceRunSerializer

    @action(detail=True, methods=['post'], url_path='stop')
    def stop(self, request, pk=None):
        """停止编排：pending 直接停；running 置 stopping 并同步当前子项。"""
        run = self.get_object()
        if run.status not in ('pending', 'running'):
            return Response({'status': run.status})
        if run.status == 'pending':
            run.status = 'stopped'
            run.finished_at = timezone.now()
            run.save(update_fields=['status', 'finished_at'])
            return Response({'status': 'stopped'})
        run.status = 'stopping'
        run.save(update_fields=['status'])
        run.execution_records.filter(status='running').update(status='stopping')
        return Response({'status': 'stopping'})
