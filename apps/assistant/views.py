"""
TestHub Agent — 对话式 AI 协作者 ViewSet

替换原有 Dify 代理模式，使用 Qwen-Agent + SSE 流式输出。
"""
import json
import os
import uuid
import logging
from django.conf import settings
from django.http import StreamingHttpResponse
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import AssistantSession, ChatMessage, AgentFile
from .serializers import (
    AssistantSessionSerializer,
    AssistantSessionCreateSerializer,
    ChatMessageSerializer,
)
from .agent import TestHubAgent

logger = logging.getLogger(__name__)


class AssistantSessionViewSet(viewsets.ModelViewSet):
    """智能助手会话视图集（复用现有逻辑）"""
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return AssistantSessionCreateSerializer
        return AssistantSessionSerializer

    def get_queryset(self):
        return AssistantSession.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_destroy(self, instance):
        """删除会话时同步清理所有文件"""
        import shutil
        # 清理目录
        session_dir = os.path.join(settings.MEDIA_ROOT, 'uploads', 'agent', instance.session_id)
        if os.path.isdir(session_dir):
            shutil.rmtree(session_dir, ignore_errors=True)
        instance.delete()

    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        """获取会话的历史消息"""
        session = self.get_object()
        messages = session.chat_messages.all()
        serializer = ChatMessageSerializer(messages, many=True)
        return Response(serializer.data)


class ChatViewSet(viewsets.ViewSet):
    """聊天功能 ViewSet — Qwen-Agent 驱动"""
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['post'])
    def send_message(self, request):
        """
        发送消息到 Agent（非流式，兼容旧接口）

        Request:
            session_id: 会话ID
            message: 用户消息
            project_id: 当前项目ID（可选，用于注入项目上下文）

        Response:
            user_message, assistant_message, tool_calls
        """
        session_id = request.data.get('session_id')
        message = request.data.get('message')
        project_id = request.data.get('project_id')

        if not session_id or not message:
            return Response(
                {'error': 'session_id和message都是必填项'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 获取会话
        try:
            session = AssistantSession.objects.get(
                session_id=session_id,
                user=request.user
            )
        except AssistantSession.DoesNotExist:
            return Response(
                {'error': '会话不存在'},
                status=status.HTTP_404_NOT_FOUND
            )

        # 保存用户消息
        user_message = ChatMessage.objects.create(
            session=session,
            role='user',
            content=message,
        )

        # 获取历史消息（最近 20 条）
        history = []
        history_messages = session.chat_messages.filter(
            id__lt=user_message.id
        ).order_by('-created_at')[:20]
        for msg in reversed(list(history_messages)):
            history.append({
                'role': msg.role,
                'content': msg.content
            })

        # 创建 Agent 实例
        agent = TestHubAgent(
            user=request.user,
            project_id=project_id,
        )

        # 收集 Agent 回复
        full_response = []
        tool_calls = []

        try:
            for event in agent.chat(message, history):
                if event['type'] == 'text':
                    full_response.append(event['content'])
                elif event['type'] == 'tool_call':
                    tool_calls.append({
                        'name': event['name'],
                        'args': event['args'],
                    })

            reply_text = ''.join(full_response)

            # 保存助手回复
            assistant_message = ChatMessage.objects.create(
                session=session,
                role='assistant',
                content=reply_text,
            )

            return Response({
                'user_message': ChatMessageSerializer(user_message).data,
                'assistant_message': ChatMessageSerializer(assistant_message).data,
                'tool_calls': tool_calls,
            })

        except Exception as e:
            logger.error(f'Agent error: {e}', exc_info=True)
            # 保存错误消息
            ChatMessage.objects.create(
                session=session,
                role='assistant',
                content=f'抱歉，处理您的请求时出错了：{str(e)}',
            )
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def send_message_stream(self, request):
        """
        发送消息到 Agent（SSE 流式）

        Request (JSON):
            session_id: 会话ID
            message: 用户消息
            project_id: 当前项目ID（可选）

        Response (SSE):
            event: text     → {"content": "..."}
            event: tool     → {"name": "...", "args": {...}}
            event: done     → {"message_id": 123}
            event: error    → {"content": "..."}
        """
        session_id = request.data.get('session_id')
        message = request.data.get('message')
        project_id = request.data.get('project_id')

        if not session_id or not message:
            return Response(
                {'error': 'session_id和message都是必填项'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 获取会话
        try:
            session = AssistantSession.objects.get(
                session_id=session_id,
                user=request.user
            )
        except AssistantSession.DoesNotExist:
            return Response(
                {'error': '会话不存在'},
                status=status.HTTP_404_NOT_FOUND
            )

        # 保存用户消息
        user_message = ChatMessage.objects.create(
            session=session,
            role='user',
            content=message,
        )

        # 获取历史消息
        history = []
        history_messages = session.chat_messages.filter(
            id__lt=user_message.id
        ).order_by('-created_at')[:60]  # 加大窗口，超过 20 条时 agent 会自动摘要压缩
        for msg in reversed(list(history_messages)):
            history.append({
                'role': msg.role,
                'content': msg.content
            })

        # 后台发的是增量，需要拼回完整文本
        full_text = ''

        def generate():
            nonlocal full_text

            try:
                agent = TestHubAgent(
                    user=request.user,
                    project_id=project_id,
                )

                for event in agent.chat(message, history):
                    if event['type'] == 'text':
                        full_text += event['content']
                        yield f'event: text\ndata: {json.dumps({"content": event["content"]}, ensure_ascii=False)}\n\n'

                    elif event['type'] == 'tool_call':
                        yield f'event: tool\ndata: {json.dumps({"name": event["name"], "args": event.get("args", {})}, ensure_ascii=False, default=str)}\n\n'

                    elif event['type'] == 'tool_result':
                        yield f'event: tool_result\ndata: {json.dumps({"name": event["name"], "result": event["result"]}, ensure_ascii=False)}\n\n'

                    elif event['type'] == 'error':
                        yield f'event: error\ndata: {json.dumps({"content": event["content"]}, ensure_ascii=False)}\n\n'

                    elif event['type'] == 'done':
                        assistant_message = ChatMessage.objects.create(
                            session=session,
                            role='assistant',
                            content=full_text.strip(),
                        )
                        yield f'event: done\ndata: {json.dumps({"message_id": assistant_message.id, "tool_calls_count": event.get("tool_calls_count", 0), "tool_calls_made": event.get("tool_calls_made", [])}, ensure_ascii=False)}\n\n'

            except Exception as e:
                logger.error(f'Stream error: {e}', exc_info=True)
                ChatMessage.objects.create(
                    session=session,
                    role='assistant',
                    content=f'抱歉，处理出错：{str(e)}',
                )
                yield f'event: error\ndata: {json.dumps({"content": str(e)}, ensure_ascii=False)}\n\n'

        response = StreamingHttpResponse(
            generate(),
            content_type='text/event-stream',
            status=200,
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response

    @action(detail=False, methods=['post'])
    def upload_file(self, request):
        """上传文件供 Agent 在会话中使用"""
        uploaded = request.FILES.get('file')
        session_id = request.data.get('session_id')

        if not uploaded:
            return Response({'error': '请选择文件'}, status=status.HTTP_400_BAD_REQUEST)
        if not session_id:
            return Response({'error': '请提供 session_id'}, status=status.HTTP_400_BAD_REQUEST)

        # 安全校验
        allowed_types = [
            'application/pdf', 'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'text/plain', 'text/csv', 'text/html',
            'application/json', 'application/x-yaml', 'text/yaml',
            'application/octet-stream',
        ]
        allowed_ext = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt', '.csv', '.html',
                       '.json', '.yaml', '.yml', '.md'}
        ext = os.path.splitext(uploaded.name)[1].lower()

        if uploaded.content_type not in allowed_types and ext not in allowed_ext:
            return Response(
                {'error': f'不支持的文件类型: {uploaded.content_type or ext}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 获取会话
        try:
            session = AssistantSession.objects.get(session_id=session_id, user=request.user)
        except AssistantSession.DoesNotExist:
            return Response({'error': '会话不存在'}, status=status.HTTP_404_NOT_FOUND)

        # 保存到会话专属目录
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'uploads', 'agent', session_id)
        os.makedirs(upload_dir, exist_ok=True)

        safe_name = f'{uuid.uuid4().hex[:8]}_{uploaded.name}'
        filepath = os.path.join(upload_dir, safe_name)

        with open(filepath, 'wb') as f:
            for chunk in uploaded.chunks():
                f.write(chunk)

        file_url = f'{settings.MEDIA_URL}uploads/agent/{session_id}/{safe_name}'

        # 创建文件记录
        agent_file = AgentFile.objects.create(
            session=session,
            source='upload',
            file_name=uploaded.name,
            file_path=filepath,
            file_url=file_url,
            file_size=uploaded.size,
            content_type=uploaded.content_type or '',
        )

        return Response({
            'id': agent_file.id,
            'file_name': uploaded.name,
            'file_path': filepath,
            'file_url': file_url,
            'size': uploaded.size,
        })

    @action(detail=False, methods=['get'])
    def list_files(self, request):
        """获取会话的文件列表"""
        session_id = request.query_params.get('session_id')
        if not session_id:
            return Response({'error': '请提供 session_id'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            session = AssistantSession.objects.get(session_id=session_id, user=request.user)
        except AssistantSession.DoesNotExist:
            return Response({'error': '会话不存在'}, status=status.HTTP_404_NOT_FOUND)

        files = session.files.all()
        return Response({
            'uploads': list(files.filter(source='upload').values(
                'id', 'file_name', 'file_url', 'file_size', 'created_at')),
            'outputs': list(files.filter(source='output').values(
                'id', 'file_name', 'file_url', 'file_size', 'created_at')),
        })

    @action(detail=False, methods=['get'])
    def download_file(self, request):
        """下载 Agent 产出文件"""
        file_id = request.query_params.get('id')
        if not file_id:
            return Response({'error': '请提供文件 id'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            agent_file = AgentFile.objects.get(id=file_id, session__user=request.user)
        except AgentFile.DoesNotExist:
            return Response({'error': '文件不存在'}, status=status.HTTP_404_NOT_FOUND)

        if not os.path.isfile(agent_file.file_path):
            return Response({'error': '文件已丢失'}, status=status.HTTP_404_NOT_FOUND)

        from django.http import FileResponse
        response = FileResponse(
            open(agent_file.file_path, 'rb'),
            as_attachment=True,
            filename=agent_file.file_name,
        )
        return response

    @action(detail=False, methods=['post'])
    def delete_file(self, request):
        """删除会话文件（同步删除本地文件）"""
        file_id = request.data.get('id')
        if not file_id:
            return Response({'error': '请提供文件 id'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            agent_file = AgentFile.objects.get(id=file_id, session__user=request.user)
        except AgentFile.DoesNotExist:
            return Response({'error': '文件不存在'}, status=status.HTTP_404_NOT_FOUND)

        # 删除本地文件
        if os.path.isfile(agent_file.file_path):
            os.remove(agent_file.file_path)

        agent_file.delete()
        return Response({'success': True, 'deleted': agent_file.file_name})

    @action(detail=False, methods=['post'])
    def test_agent(self, request):
        """
        测试 Agent 连通性（不依赖会话）
        用于调试 Tool 注册和 LLM 连接
        """
        message = request.data.get('message', '你好，请介绍一下你自己')
        project_id = request.data.get('project_id')

        agent = TestHubAgent(
            user=request.user,
            project_id=project_id,
        )

        results = {
            'llm_config': {
                'model': agent.llm_config.get('model'),
                'model_server': agent.llm_config.get('model_server'),
            },
            'tools': agent.tool_names,
            'project_id': project_id,
            'responses': [],
            'errors': [],
        }

        try:
            for event in agent.chat(message):
                if event['type'] == 'text':
                    results['responses'].append({'type': 'text', 'content': event['content']})
                elif event['type'] == 'tool_call':
                    results['responses'].append({
                        'type': 'tool_call',
                        'name': event['name'],
                        'args': event.get('args', {}),
                    })
                elif event['type'] == 'error':
                    results['errors'].append(event['content'])
        except Exception as e:
            results['errors'].append(str(e))

        return Response(results)


def assistant_view(request):
    """智能助手页面视图 - 用于前端嵌入"""
    from django.shortcuts import render
    return render(request, 'assistant/assistant.html')
