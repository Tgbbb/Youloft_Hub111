from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AssistantSessionViewSet, ChatViewSet, assistant_view
from .views_config import DifyConfigViewSet, AgentConfigViewSet, AgentSkillViewSet, MCPServerViewSet

router = DefaultRouter()
router.register(r'sessions', AssistantSessionViewSet, basename='assistant-sessions')
router.register(r'chat', ChatViewSet, basename='chat')
router.register(r'config/dify', DifyConfigViewSet, basename='dify-config')
router.register(r'config/agent', AgentConfigViewSet, basename='agent-config')
router.register(r'skills', AgentSkillViewSet, basename='agent-skills')
router.register(r'mcp', MCPServerViewSet, basename='mcp-servers')

urlpatterns = [
    path('', include(router.urls)),
    path('view/', assistant_view, name='assistant-view'),
]