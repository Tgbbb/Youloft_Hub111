from rest_framework import serializers
from .models import AssistantSession, AssistantMessage, DifyConfig, AgentConfig, ChatMessage, AgentSkill, AgentFile


class DifyConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = DifyConfig
        fields = ['id', 'api_url', 'api_key', 'is_active', 'created_at', 'updated_at']
        extra_kwargs = {
            'api_key': {'write_only': True}  # Don't expose API key in responses
        }


class AgentConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentConfig
        fields = ['id', 'name', 'provider', 'model_name', 'api_key',
                  'base_url', 'max_tokens', 'max_tool_calls', 'temperature', 'is_active',
                  'system_prompt_extra', 'created_at', 'updated_at']
        extra_kwargs = {
            'api_key': {'write_only': True}
        }


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ['id', 'role', 'content', 'conversation_id', 'message_id', 'created_at']
        read_only_fields = ['conversation_id', 'message_id', 'created_at']


class AssistantMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssistantMessage
        fields = ['id', 'message_type', 'content', 'created_at']


class AssistantSessionSerializer(serializers.ModelSerializer):
    messages = AssistantMessageSerializer(many=True, read_only=True)
    chat_messages = ChatMessageSerializer(many=True, read_only=True)

    class Meta:
        model = AssistantSession
        fields = ['id', 'session_id', 'conversation_id', 'project_id', 'title', 'created_at', 'updated_at', 'messages', 'chat_messages']


class AssistantSessionCreateSerializer(serializers.ModelSerializer):
    project_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = AssistantSession
        fields = ['id', 'session_id', 'project_id', 'title']
        read_only_fields = ['id']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class AgentSkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentSkill
        fields = ['id', 'name', 'display_name', 'description', 'instructions',
                  'tools', 'is_active', 'order', 'created_at', 'updated_at']


class AgentFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentFile
        fields = ['id', 'session', 'source', 'file_name', 'file_url',
                  'file_size', 'content_type', 'created_at']
        read_only_fields = ['created_at']