"""
模块项目序列化器共用 Mixin：统一暴露并绑定 main_project。
"""
from rest_framework import serializers

from apps.projects.models import Project
from apps.projects.linkage import resolve_or_create_main_project


class MainProjectSerializerMixin(serializers.Serializer):
    """
    为模块项目序列化器统一提供：
    - main_project（可选写入主项目 id）
    - main_project_name（只读名称）
    - 创建时未传 main_project 自动解析或补建公共项目并绑定
    - 同表唯一性校验
    """

    main_project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(), required=False, allow_null=True
    )
    main_project_name = serializers.SerializerMethodField()

    def get_main_project_name(self, obj):
        return obj.main_project.name if getattr(obj, 'main_project_id', None) else None

    def validate_main_project(self, value):
        if value is not None:
            queryset = self.Meta.model.objects.filter(main_project=value)
            if self.instance is not None:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError('该主项目已绑定同类型的其他模块项目')
        return value

    def create(self, validated_data):
        main_project = validated_data.pop('main_project', None)
        if main_project is None:
            main_project = resolve_or_create_main_project(
                Project,
                self.Meta.model,
                name=validated_data['name'],
                owner_id=validated_data['owner'].pk,
                status=validated_data.get('status', '') or '',
                description=validated_data.get('description', '') or '',
            )
        validated_data['main_project'] = main_project
        return super().create(validated_data)

    def update(self, instance, validated_data):
        main_project = validated_data.pop('main_project', None)
        instance = super().update(instance, validated_data)
        if main_project is not None:
            instance.main_project = main_project
            instance.save(update_fields=['main_project'])
        return instance
