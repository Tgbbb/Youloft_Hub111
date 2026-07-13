# -*- coding: utf-8 -*-
"""
Midscene AI 移动端自动化 - 序列化器
"""
from rest_framework import serializers
from .models import (
    MidsceneProject, MidsceneDevice, MidsceneCase, MidsceneExecutionRecord
)


class MidsceneProjectSerializer(serializers.ModelSerializer):
    owner_name = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()
    case_count = serializers.SerializerMethodField()

    class Meta:
        model = MidsceneProject
        fields = [
            'id', 'name', 'description', 'default_app_package', 'default_ios_bundle_id',
            'owner', 'owner_name',
            'members', 'member_count', 'case_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'owner', 'created_at', 'updated_at']

    def get_owner_name(self, obj):
        return obj.owner.username if obj.owner else None

    def get_member_count(self, obj):
        return obj.members.count()

    def get_case_count(self, obj):
        return obj.midscene_cases.count()


class MidsceneDeviceSerializer(serializers.ModelSerializer):
    platform_display = serializers.SerializerMethodField()
    locked_by_name = serializers.SerializerMethodField()

    class Meta:
        model = MidsceneDevice
        fields = [
            'id', 'platform', 'platform_display', 'device_id', 'name',
            'status', 'android_version', 'adb_serial',
            'ios_version', 'tidevice_udid', 'wda_host',
            'locked_by', 'locked_by_name', 'locked_at', 'max_lock_time',
            'ip_address', 'port',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_platform_display(self, obj):
        return obj.get_platform_display()

    def get_locked_by_name(self, obj):
        return obj.locked_by.username if obj.locked_by else None


class MidsceneDeviceSimpleSerializer(serializers.ModelSerializer):
    """设备简单序列化器（用于下拉选择）"""
    platform_display = serializers.SerializerMethodField()

    class Meta:
        model = MidsceneDevice
        fields = ['id', 'platform', 'platform_display', 'device_id', 'name', 'status']

    def get_platform_display(self, obj):
        return obj.get_platform_display()


class MidsceneCaseSerializer(serializers.ModelSerializer):
    project_name = serializers.SerializerMethodField()
    model_config_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    latest_result = serializers.SerializerMethodField()

    class Meta:
        model = MidsceneCase
        fields = [
            'id', 'project', 'project_name', 'name', 'description',
            'ai_prompt', 'ai_act_context', 'ai_model_config', 'model_config_name',
            'max_steps', 'action_delay',
            'app_package', 'app_activity',
            'created_by', 'created_by_name',
            'created_at', 'updated_at', 'latest_result',
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    def get_project_name(self, obj):
        return obj.project.name if obj.project else None

    def get_model_config_name(self, obj):
        return obj.ai_model_config.name if obj.ai_model_config else None

    def get_created_by_name(self, obj):
        return obj.created_by.username if obj.created_by else None

    def get_latest_result(self, obj):
        latest = obj.execution_records.first()
        if latest:
            return {
                'id': latest.id,
                'status': latest.status,
                'pass_rate': latest.pass_rate,
                'finished_at': latest.finished_at,
            }
        return None


class MidsceneCaseCreateSerializer(serializers.ModelSerializer):
    """创建 Midscene 用例"""
    project_id = serializers.IntegerField(required=False, allow_null=True)
    ai_model_config_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = MidsceneCase
        fields = [
            'name', 'description', 'project_id', 'ai_prompt',
            'ai_act_context',
            'ai_model_config_id', 'max_steps', 'action_delay',
            'app_package', 'app_activity',
        ]

    def create(self, validated_data):
        project_id = validated_data.pop('project_id', None)
        ai_model_config_id = validated_data.pop('ai_model_config_id', None)

        if project_id:
            validated_data['project_id'] = project_id
        if ai_model_config_id:
            validated_data['ai_model_config_id'] = ai_model_config_id

        return super().create(validated_data)


class MidsceneExecutionRecordSerializer(serializers.ModelSerializer):
    case_name = serializers.SerializerMethodField()
    device_name = serializers.SerializerMethodField()
    platform_display = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    executed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = MidsceneExecutionRecord
        fields = [
            'id', 'midscene_case', 'case_name', 'device', 'device_name',
            'platform', 'platform_display', 'status', 'status_display',
            'progress', 'started_at', 'finished_at', 'duration',
            'model_config_snapshot', 'report_path',
            'total_steps', 'passed_steps', 'failed_steps',
            'steps_detail', 'error_message',
            'executed_by', 'executed_by_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_case_name(self, obj):
        return obj.case_name

    def get_device_name(self, obj):
        return obj.device.name or obj.device.device_id if obj.device else None

    def get_platform_display(self, obj):
        return obj.get_platform_display() if obj.platform else None

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_executed_by_name(self, obj):
        return obj.executed_by.username if obj.executed_by else None
