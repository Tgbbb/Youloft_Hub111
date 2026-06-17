from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from django.contrib.auth import get_user_model

User = get_user_model()


@csrf_exempt
@require_http_methods(["POST"])
def test_register(request):
    try:
        data = json.loads(request.body)

        # 检查用户名是否已存在
        if User.objects.filter(username=data.get('username')).exists():
            return JsonResponse({
                'success': False,
                'error': '用户名已存在'
            }, status=400)

        # 图形验证码校验（替代短信验证码）
        captcha_token = data.get('captcha_token', '').strip()
        captcha_code = data.get('captcha_code', '').strip()
        if not captcha_token or not captcha_code:
            return JsonResponse({
                'success': False,
                'error': '请输入图形验证码'
            }, status=400)

        from .captcha import validate_captcha
        if not validate_captcha(captcha_token, captcha_code):
            return JsonResponse({
                'success': False,
                'error': '图形验证码错误或已过期，请刷新重试'
            }, status=400)

        # 手机号（可选）
        phone = data.get('phone', '').strip() or None

        # 如果填了手机号，校验格式和唯一性
        if phone:
            import re
            if not re.match(r'^1[3-9]\d{9}$', phone):
                return JsonResponse({'success': False, 'error': '手机号格式不正确'}, status=400)
            if User.objects.filter(phone=phone).exists():
                return JsonResponse({'success': False, 'error': '该手机号已被注册'}, status=400)

        # 创建用户
        user = User.objects.create_user(
            username=data.get('username'),
            email=data.get('email', ''),
            password=data.get('password'),
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            phone=phone or '',
            department=data.get('department', ''),
            position=data.get('position', '')
        )

        # 生成 JWT token
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)

        return JsonResponse({
            'success': True,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'phone': user.phone,
                'first_name': user.first_name,
                'last_name': user.last_name
            },
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)