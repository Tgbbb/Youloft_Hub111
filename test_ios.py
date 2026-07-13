from apps.ui_automation.ios_device import IOSDevice

d = IOSDevice('172.16.8.168', 8100)
print('连接 WDA...')
d.connect()
print(f'连接成功, 屏幕={d.screen_size}')

print('截图...')
png = d.screenshot()
print(f'截图: {len(png)} bytes')

print('启动应用...')
d.launch_app('com.youloft.icloser')
print('启动完成')

print('再截图...')
png2 = d.screenshot()
print(f'截图: {len(png2)} bytes')

d.disconnect()
print('OK')
