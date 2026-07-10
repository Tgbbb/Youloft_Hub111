"""快速测试 VLM 调用"""
import os, sys, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'backend.settings'
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from apps.ui_automation.models import MidsceneExecutionRecord
from apps.ui_automation.midscene_runner import adb_screenshot, call_vlm, adb_get_screen_size

r = MidsceneExecutionRecord.objects.get(id=7)
cfg = r.midscene_case.ai_model_config
dev = r.device

print(f'设备: {dev.adb_serial}')
print(f'模型: {cfg.name} / {cfg.model_name}')
print(f'URL: {cfg.base_url}')

w, h = adb_get_screen_size(dev.adb_serial)
print(f'屏幕: {w}x{h}')

print('截图...')
png = adb_screenshot(dev.adb_serial)
print(f'截图: {len(png)} bytes')

print('调用 VLM...')
try:
    action = call_vlm(png, '点击设置按钮', cfg, w, h)
    print(f'VLM 返回: {action}')
except Exception as e:
    import traceback
    traceback.print_exc()
