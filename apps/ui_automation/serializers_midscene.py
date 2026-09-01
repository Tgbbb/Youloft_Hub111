# -*- coding: utf-8 -*-
"""
Midscene AI 移动端自动化 - 序列化器
"""
from rest_framework import serializers
from apps.projects.serializer_mixins import MainProjectSerializerMixin
from .models import (
    MidsceneProject, MidsceneDevice, MidsceneCase, MidsceneCaseFolder,
    MidsceneExecutionRecord, MidsceneAppPackage, MidsceneAppInstallRecord,
    MidsceneGlobalConfig, MidsceneSequence, MidsceneSequenceItem, MidsceneSequenceRun,
)


class MidsceneProjectSerializer(MainProjectSerializerMixin, serializers.ModelSerializer):
    owner_name = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()
    case_count = serializers.SerializerMethodField()

    class Meta:
        model = MidsceneProject
        fields = [
            'id', 'name', 'description', 'default_app_package', 'default_ios_bundle_id',
            'owner', 'owner_name',
            'members', 'member_count', 'case_count', 'main_project', 'main_project_name',
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
    folder_name = serializers.SerializerMethodField()
    model_config_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    latest_result = serializers.SerializerMethodField()

    class Meta:
        model = MidsceneCase
        fields = [
            'id', 'project', 'project_name', 'folder', 'folder_name', 'name', 'description',
            'ai_prompt', 'ai_act_context', 'ai_model_config', 'model_config_name',
            'max_steps', 'action_delay',
            'app_package', 'app_activity',
            'replay_data',
            'created_by', 'created_by_name',
            'created_at', 'updated_at', 'latest_result',
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    def get_project_name(self, obj):
        return obj.project.name if obj.project else None

    def get_folder_name(self, obj):
        return obj.folder.name if obj.folder else None

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
    folder_id = serializers.IntegerField(required=False, allow_null=True)
    ai_model_config_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = MidsceneCase
        fields = [
            'name', 'description', 'project_id', 'folder_id', 'ai_prompt',
            'ai_act_context',
            'ai_model_config_id', 'max_steps', 'action_delay',
            'app_package', 'app_activity',
        ]

    def validate(self, attrs):
        folder_id = attrs.get('folder_id') or self.initial_data.get('folder_id')
        project_id = attrs.get('project_id') or self.initial_data.get('project_id')
        if folder_id:
            try:
                folder = MidsceneCaseFolder.objects.get(id=folder_id)
            except MidsceneCaseFolder.DoesNotExist:
                raise serializers.ValidationError({'folder_id': '文件夹不存在'})
            if project_id and folder.project_id and folder.project_id != int(project_id):
                raise serializers.ValidationError({'folder_id': '文件夹不属于当前项目'})
        return attrs

    def create(self, validated_data):
        project_id = validated_data.pop('project_id', None)
        folder_id = validated_data.pop('folder_id', None)
        ai_model_config_id = validated_data.pop('ai_model_config_id', None)

        if project_id:
            validated_data['project_id'] = project_id
        if folder_id:
            validated_data['folder_id'] = folder_id
        if ai_model_config_id:
            validated_data['ai_model_config_id'] = ai_model_config_id

        return super().create(validated_data)

    def update(self, instance, validated_data):
        folder_id = validated_data.pop('folder_id', None)
        if folder_id:
            validated_data['folder_id'] = folder_id
        elif 'folder_id' in self.initial_data:
            # 显式传空表示移出文件夹
            instance.folder_id = None
            instance.save(update_fields=['folder'])
        return super().update(instance, validated_data)


class MidsceneCaseFolderSerializer(serializers.ModelSerializer):
    case_count = serializers.SerializerMethodField()

    class Meta:
        model = MidsceneCaseFolder
        fields = [
            'id', 'project', 'parent_folder', 'name',
            'case_count', 'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    def get_case_count(self, obj):
        return obj.midscene_cases.count()


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
            'sequence_run', 'created_at', 'updated_at',
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


class MidsceneAppPackageSerializer(serializers.ModelSerializer):
    platform_display = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    size_display = serializers.SerializerMethodField()
    install_count = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = MidsceneAppPackage
        fields = [
            'id', 'name', 'platform', 'platform_display', 'file',
            'file_url', 'package_name', 'version_name', 'version_code',
            'file_size', 'size_display', 'md5', 'description',
            'created_by', 'created_by_name', 'install_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'file', 'created_by', 'created_at', 'updated_at']

    def get_platform_display(self, obj):
        return obj.get_platform_display()

    def get_created_by_name(self, obj):
        return obj.created_by.username if obj.created_by else None

    def get_size_display(self, obj):
        size = obj.file_size or 0
        if size >= 1024 * 1024 * 1024:
            return f'{size / (1024 * 1024 * 1024):.1f} GB'
        if size >= 1024 * 1024:
            return f'{size / (1024 * 1024):.1f} MB'
        if size >= 1024:
            return f'{size / 1024:.1f} KB'
        return f'{size} B'

    def get_install_count(self, obj):
        return obj.install_records.count()

    def get_file_url(self, obj):
        try:
            if obj.file:
                return obj.file.url
        except Exception:
            pass
        return ''


class MidsceneAppInstallRecordSerializer(serializers.ModelSerializer):
    device_name = serializers.SerializerMethodField()
    package_name = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = MidsceneAppInstallRecord
        fields = [
            'id', 'package', 'package_name', 'device', 'device_name',
            'status', 'status_display', 'options', 'log', 'error_message',
            'task_id', 'started_at', 'finished_at', 'duration',
            'created_by', 'created_by_name', 'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_device_name(self, obj):
        return f"{obj.device.name or obj.device.device_id} ({obj.device.get_platform_display()})" if obj.device else None

    def get_package_name(self, obj):
        return f"{obj.package.name} ({obj.package.get_platform_display()})" if obj.package else None

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_created_by_name(self, obj):
        return obj.created_by.username if obj.created_by else None


class MidsceneGlobalConfigSerializer(serializers.ModelSerializer):
    use_deep_locate_display = serializers.SerializerMethodField()

    class Meta:
        model = MidsceneGlobalConfig
        fields = ['id', 'use_locate', 'use_deep_locate', 'use_deep_locate_display',
                  'updated_by', 'updated_at']
        read_only_fields = ['id', 'use_deep_locate_display', 'updated_by', 'updated_at']

    def get_use_deep_locate_display(self, obj):
        return obj.get_use_deep_locate_display() if obj.use_deep_locate else '不覆盖'


class MidsceneSequenceItemSerializer(serializers.ModelSerializer):
    """编排项（读）。"""
    case_name = serializers.SerializerMethodField()

    class Meta:
        model = MidsceneSequenceItem
        fields = ['id', 'order', 'case', 'case_name', 'clear_relaunch', 'break_on_fail',
                  'replay_mode', 'replay_index']

    def get_case_name(self, obj):
        return obj.case.name if obj.case else ''


class MidsceneSequenceItemWriteSerializer(serializers.Serializer):
    """编排项（写）：新增/更新订阅。"""
    case_id = serializers.IntegerField()
    clear_relaunch = serializers.BooleanField(required=False, default=False)
    break_on_fail = serializers.BooleanField(required=False, default=True)
    replay_mode = serializers.ChoiceField(choices=['auto', 'fixed'], required=False, default='auto')
    replay_index = serializers.IntegerField(required=False, default=0)

    def validate_case_id(self, value):
        if not MidsceneCase.objects.filter(id=value).exists():
            raise serializers.ValidationError('用例不存在')
        return value


class MidsceneSequenceSerializer(serializers.ModelSerializer):
    project_name = serializers.SerializerMethodField()
    folder_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()
    items = MidsceneSequenceItemSerializer(many=True, read_only=True)

    class Meta:
        model = MidsceneSequence
        fields = ['id', 'name', 'project', 'project_name', 'folder', 'folder_name', 'description',
                  'created_by', 'created_by_name', 'item_count', 'items',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    def get_project_name(self, obj):
        return obj.project.name if obj.project else None

    def get_folder_name(self, obj):
        return obj.folder.name if obj.folder else None

    def get_created_by_name(self, obj):
        return obj.created_by.username if obj.created_by else None

    def get_item_count(self, obj):
        return obj.items.count()


class MidsceneSequenceCreateSerializer(serializers.ModelSerializer):
    """创建/更新编排：items 可写，整体重建顺序。"""
    items = MidsceneSequenceItemWriteSerializer(many=True, required=False)
    project_id = serializers.IntegerField(required=False, allow_null=True)
    folder_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = MidsceneSequence
        fields = ['id', 'name', 'project_id', 'folder_id', 'description', 'items']

    def validate(self, attrs):
        items = attrs.get('items')
        if items is not None and not items:
            raise serializers.ValidationError({'items': '编排至少需要 1 个用例'})
        project_id = attrs.get('project_id') or self.initial_data.get('project_id')
        folder_id = attrs.get('folder_id') or self.initial_data.get('folder_id')
        if folder_id:
            try:
                folder = MidsceneCaseFolder.objects.get(id=folder_id)
            except MidsceneCaseFolder.DoesNotExist:
                raise serializers.ValidationError({'folder_id': '文件夹不存在'})
            if project_id and folder.project_id and folder.project_id != int(project_id):
                raise serializers.ValidationError({'folder_id': '文件夹不属于当前项目'})
        return attrs

    def _rebuild_items(self, sequence, items):
        sequence.items.all().delete()
        for i, it in enumerate(items or []):
            MidsceneSequenceItem.objects.create(
                sequence=sequence, order=i,
                case_id=it['case_id'],
                clear_relaunch=it.get('clear_relaunch', False),
                break_on_fail=it.get('break_on_fail', True),
                replay_mode=it.get('replay_mode', 'auto'),
                replay_index=it.get('replay_index', 0),
            )

    def create(self, validated_data):
        items = validated_data.pop('items', None)
        project_id = validated_data.pop('project_id', None)
        folder_id = validated_data.pop('folder_id', None)
        validated_data['project_id'] = project_id
        validated_data['folder_id'] = folder_id
        sequence = super().create(validated_data)
        self._rebuild_items(sequence, items or [])
        return sequence

    def update(self, instance, validated_data):
        items = validated_data.pop('items', None)
        project_id = validated_data.pop('project_id', None)
        folder_id = validated_data.pop('folder_id', None)
        if project_id is not None:
            validated_data['project_id'] = project_id
        if folder_id is not None:
            validated_data['folder_id'] = folder_id
        sequence = super().update(instance, validated_data)
        if items is not None:
            self._rebuild_items(sequence, items)
        return sequence


class MidsceneSequenceRunSerializer(serializers.ModelSerializer):
    sequence_name = serializers.SerializerMethodField()
    device_name = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    executed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = MidsceneSequenceRun
        fields = ['id', 'sequence', 'sequence_name', 'device', 'device_name', 'platform',
                  'status', 'status_display', 'progress', 'total_steps', 'passed_steps',
                  'failed_steps', 'started_at', 'finished_at', 'duration', 'task_id',
                  'error_message', 'executed_by', 'executed_by_name', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_sequence_name(self, obj):
        return obj.sequence_name

    def get_device_name(self, obj):
        return obj.device.name or obj.device.device_id if obj.device else None

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_executed_by_name(self, obj):
        return obj.executed_by.username if obj.executed_by else None


class MidsceneSequenceRunDetailSerializer(MidsceneSequenceRunSerializer):
    """编排运行详情：附带每项子执行记录。"""
    executions = serializers.SerializerMethodField()

    class Meta(MidsceneSequenceRunSerializer.Meta):
        fields = MidsceneSequenceRunSerializer.Meta.fields + ['executions']

    def get_executions(self, obj):
        # 子执行按创建顺序（即编排项顺序）展示，而非模型默认的 -created_at
        qs = obj.execution_records.all().order_by('created_at')
        return MidsceneExecutionRecordSerializer(qs, many=True).data
