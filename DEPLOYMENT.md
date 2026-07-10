# TestHub 部署记录

**部署路径**: `E:\TestHub\testhub_platform`
**Git 仓库**: `https://github.com/Tgbbb/Test_Hub` (私有)

## 服务地址

| 服务 | 地址 |
|------|------|
| 前端 (Vue 3) | http://localhost:3000 |
| 后端 (Django API) | http://localhost:8000 |
| API 文档 (Swagger) | http://localhost:8000/api/docs/ |
| Django Admin | http://localhost:8000/admin/ |
| 内网访问 | http://192.168.8.120:3000 |

## 账号

- **超级用户**: `admin` / `admin123`
- **注册**: 图形验证码（无需手机号）

## 技术栈

| 组件 | 说明 |
|------|------|
| 后端 | Python 3.12 + Django 4.2 |
| 前端 | Vue 3 + Vite |
| 数据库 | MySQL 8.0 (端口 3307，独立数据目录 `E:\TestHub\mysql_data`) |
| 缓存 | Redis 3.0 (端口 6379) |
| 异步任务 | Celery 5.3 (Redis broker, solo pool) |
| OCR | Tesseract (`E:\ocr\tesseract.exe`) + PyMuPDF |
| APP 自动化 | Airtest 1.4.3 + PyMuPDF |

## 启动方式

```bash
# 方式一：双击 start.bat（推荐，自动启动全部6个服务）
# 方式二：手动逐项启动
source venv/Scripts/activate
python manage.py runserver 0.0.0.0:8000
celery -A backend worker --pool=solo --loglevel=info
cd frontend && npm run dev
```

## 关键配置

| 配置项 | 值 |
|------|------|
| MySQL 数据目录 | `E:\TestHub\mysql_data` |
| MySQL 用户 | `root` (无密码) |
| Tesseract 路径 | `E:\ocr\tesseract.exe` |
| ADB 路径 | `E:\adb\platform-tools\adb.exe` |
| SSH 密钥 | `~/.ssh/id_rsa.pub` (843682137@qq.com) |

## 管理命令

```bash
python manage.py init_components   # 初始化 APP 自动化组件库
```

## 防火墙

内网共享需管理员运行：
```cmd
netsh advfirewall firewall add rule name="TestHub-3000" dir=in action=allow protocol=TCP localport=3000
netsh advfirewall firewall add rule name="TestHub-8000" dir=in action=allow protocol=TCP localport=8000
```
