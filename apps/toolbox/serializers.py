# -*- coding: utf-8 -*-
from rest_framework import serializers

from .models import ToolboxConfig, PushCheckRun, SyncCheckConfig, SyncCheckRun


def _mask_secret(value):
    value = (value or '').strip()
    if not value:
        return ''
    if len(value) <= 4:
        return '****'
    return '****' + value[-4:]


class ToolboxConfigSerializer(serializers.ModelSerializer):
    """配置序列化器：返回时对密码/Cookie 掩码，写入时空值表示不修改。"""

    class Meta:
        model = ToolboxConfig
        fields = [
            'imap_host', 'imap_port', 'imap_user', 'imap_password',
            'imap_timeout', 'backend_host', 'backend_port', 'push_cookie',
            'tesseract_path', 'last_uid', 'last_date', 'last_problems',
            'updated_by', 'updated_at',
        ]
        read_only_fields = ['last_uid', 'last_date', 'last_problems', 'updated_by', 'updated_at']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['imap_password'] = _mask_secret(data.get('imap_password'))
        data['push_cookie'] = _mask_secret(data.get('push_cookie'))
        return data


class PushCheckRunListSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True, default='')

    class Meta:
        model = PushCheckRun
        fields = ['id', 'username', 'status', 'force', 'summary', 'started_at', 'finished_at']


class PushCheckRunDetailSerializer(PushCheckRunListSerializer):
    class Meta(PushCheckRunListSerializer.Meta):
        fields = ['id', 'username', 'status', 'force', 'summary', 'log', 'started_at', 'finished_at']


class SyncCheckConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = SyncCheckConfig
        fields = [
            'id', 'enabled', 'require_push_activity', 'interval_minutes', 'deadline_time',
            'mail_subject', 'mail_body_keyword', 'enable_dingtalk_notify', 'last_check_at',
            'updated_by', 'updated_at',
        ]
        read_only_fields = ['id', 'last_check_at', 'updated_by', 'updated_at']


class SyncCheckRunListSerializer(serializers.ModelSerializer):
    class Meta:
        model = SyncCheckRun
        fields = ['id', 'date', 'status', 'mail_subject', 'diffs', 'checked_at', 'created_at']


class SyncCheckRunDetailSerializer(SyncCheckRunListSerializer):
    class Meta(SyncCheckRunListSerializer.Meta):
        fields = [
            'id', 'date', 'status', 'mail_uid', 'mail_subject', 'ocr_text',
            'parsed_fields', 'backend_record', 'diffs', 'log', 'notify_sent_status',
            'checked_at', 'created_at',
        ]
