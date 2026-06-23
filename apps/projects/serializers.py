from rest_framework import serializers
from .models import Project, ProjectMember, ProjectEnvironment
from apps.users.serializers import UserSerializer

class ProjectSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ('id', 'name')

class ProjectEnvironmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectEnvironment
        fields = '__all__'

class ProjectMemberSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    user_id = serializers.IntegerField(write_only=True, required=False)
    username = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = ProjectMember
        fields = ['id', 'user', 'user_id', 'username', 'role', 'joined_at']

    def validate(self, attrs):
        # 支持传 username 自动查找 user_id
        username = attrs.pop('username', None)
        if username:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                user = User.objects.get(username=username)
                attrs['user_id'] = user.id
            except User.DoesNotExist:
                raise serializers.ValidationError({'username': f'用户 "{username}" 不存在'})
        if not attrs.get('user_id'):
            raise serializers.ValidationError({'user_id': '请提供 user_id 或 username'})
        return attrs

class ProjectSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    members = ProjectMemberSerializer(source='projectmember_set', many=True, read_only=True)
    environments = ProjectEnvironmentSerializer(many=True, read_only=True)
    
    class Meta:
        model = Project
        fields = ['id', 'name', 'description', 'knowledge_base', 'status', 'owner', 'members',
                 'environments', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

class ProjectCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ['name', 'description', 'knowledge_base', 'status']
    
    def create(self, validated_data):
        validated_data['owner'] = self.context['request'].user
        return super().create(validated_data)