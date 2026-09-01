# -*- coding: utf-8 -*-
"""统一通知 Webhook 发送器：支持钉钉机器人 markdown 推送。

复用 UnifiedNotificationConfig（config_type='webhook_dingtalk'），
按机器人内 enabled 过滤，支持钉钉加签（secret -> timestamp + sign）。
"""

import base64
import hashlib
import hmac
import time
import urllib.parse

import requests

from .models import UnifiedNotificationConfig


def get_active_dingtalk_bots():
    """收集所有启用中的钉钉机器人配置。"""
    configs = UnifiedNotificationConfig.objects.filter(
        config_type='webhook_dingtalk', is_active=True)
    bots = []
    for config in configs:
        for bot in config.get_webhook_bots():
            if (bot.get('type') == 'dingtalk'
                    and bot.get('enabled', True)
                    and bot.get('webhook_url')):
                bots.append(bot)
    return bots


def _signed_webhook_url(webhook_url, secret):
    """钉钉加签：timestamp + HMAC-SHA256 + base64 + quote_plus。"""
    timestamp = str(round(time.time() * 1000))
    string_to_sign = '{}\n{}'.format(timestamp, secret)
    sign = urllib.parse.quote_plus(base64.b64encode(
        hmac.new(secret.encode('utf-8'), string_to_sign.encode('utf-8'),
                 digestmod=hashlib.sha256).digest()))
    sep = '&' if '?' in webhook_url else '?'
    return '{}{}timestamp={}&sign={}'.format(webhook_url, sep, timestamp, sign)


def send_dingtalk_markdown(title, text, timeout=10):
    """向所有启用的钉钉机器人推送一条 markdown，返回 [{name, ok, error}]。"""
    results = []
    for bot in get_active_dingtalk_bots():
        url = bot.get('webhook_url')
        secret = bot.get('secret')
        if secret:
            url = _signed_webhook_url(url, secret)
        payload = {
            'msgtype': 'markdown',
            'markdown': {'title': title, 'text': text},
        }
        item = {'name': bot.get('name') or '钉钉机器人', 'ok': False, 'error': ''}
        try:
            resp = requests.post(
                url, json=payload,
                headers={'Content-Type': 'application/json'}, timeout=timeout,
                # verify=False：绕过企业安全软件/代理的 HTTPS 拦截（自签名中间证书）
                # 导致 requests 校验失败；webhook 已带加签 secret，风险可控。
                # 若后续想恢复校验，可设置 REQUESTS_CA_BUNDLE/SSL_CERT_FILE 指向企业 CA 后改回 verify=True。
                verify=False)
            if resp.status_code != 200:
                item['error'] = 'HTTP {}: {}'.format(resp.status_code, resp.text[:200])
            else:
                try:
                    data = resp.json()
                except Exception:
                    data = {}
                errcode = data.get('errcode', 0)
                errmsg = data.get('errmsg', '')
                item['ok'] = (errcode == 0)
                if not item['ok']:
                    item['error'] = 'errcode={} errmsg={}'.format(errcode, errmsg)
        except Exception as exc:
            item['error'] = str(exc)
        results.append(item)
    return results
