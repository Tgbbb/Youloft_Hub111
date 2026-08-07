import os
import re
import json
import yaml
import requests
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import DifyConfig, AgentConfig, AgentSkill
from .serializers import DifyConfigSerializer, AgentConfigSerializer, AgentSkillSerializer


class DifyConfigViewSet(viewsets.ModelViewSet):
    """Dify配置管理ViewSet"""
    queryset = DifyConfig.objects.all()
    serializer_class = DifyConfigSerializer
    permission_classes = [IsAuthenticated]
    
    def list(self, request):
        """获取激活的配置"""
        active_config = DifyConfig.get_active_config()
        if active_config:
            serializer = self.get_serializer(active_config)
            # 返回时隐藏完整的API key，只显示部分
            data = serializer.data
            if 'api_key' in data and data['api_key']:
                data['api_key_masked'] = data['api_key'][:8] + '****'
                del data['api_key']
            return Response(data)
        return Response({'message': '未找到激活的配置'}, status=status.HTTP_404_NOT_FOUND)
    
    def create(self, request):
        """创建新配置"""
        # 如果设置为激活，先将其他配置设为不激活
        if request.data.get('is_active', True):
            DifyConfig.objects.update(is_active=False)
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    def update(self, request, pk=None, partial=False):
        """更新配置"""
        instance = self.get_object()
        
        # 如果设置为激活，先将其他配置设为不激活
        if request.data.get('is_active', False):
            DifyConfig.objects.exclude(pk=pk).update(is_active=False)
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    
    def partial_update(self, request, pk=None):
        """部分更新配置"""
        return self.update(request, pk=pk, partial=True)
    
    @action(detail=False, methods=['post'])
    def test_connection(self, request):
        """测试Dify API连接"""
        api_url = request.data.get('api_url')
        api_key = request.data.get('api_key')
        
        if not api_url or not api_key:
            return Response(
                {'error': 'API URL和API Key都是必填项'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # 发送测试请求到Dify API
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            
            # 使用一个简单的测试消息
            test_data = {
                'inputs': {},
                'query': 'test',
                'user': 'test_user'
            }
            
            # 去除URL末尾的斜杠
            api_url = api_url.rstrip('/')
            
            response = requests.post(
                f'{api_url}/chat-messages',
                headers=headers,
                json=test_data,
                timeout=30
            )
            
            if response.status_code == 200:
                return Response({'message': '连接成功！', 'success': True})
            else:
                return Response({
                    'error': f'连接失败: {response.status_code}',
                    'detail': response.text,
                    'success': False
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except requests.exceptions.Timeout:
            return Response({
                'error': '连接超时，请检查API URL是否正确',
                'success': False
            }, status=status.HTTP_408_REQUEST_TIMEOUT)
        except requests.exceptions.RequestException as e:
            return Response({
                'error': f'连接错误: {str(e)}',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)


class AgentConfigViewSet(viewsets.ModelViewSet):
    """TestHub Agent 配置管理 ViewSet"""
    queryset = AgentConfig.objects.all()
    serializer_class = AgentConfigSerializer
    permission_classes = [IsAuthenticated]

    def list(self, request):
        """获取激活的 Agent 配置"""
        active_config = AgentConfig.get_active_config()
        if active_config:
            serializer = self.get_serializer(active_config)
            data = serializer.data
            if 'api_key' in data and data['api_key']:
                data['api_key_masked'] = data['api_key'][:8] + '****'
                del data['api_key']
            return Response(data)
        return Response({'message': '未找到激活的Agent配置'}, status=status.HTTP_404_NOT_FOUND)

    def create(self, request):
        if request.data.get('is_active', True):
            AgentConfig.objects.update(is_active=False)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None, partial=False):
        instance = self.get_object()
        if request.data.get('is_active', False):
            AgentConfig.objects.exclude(pk=pk).update(is_active=False)
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def partial_update(self, request, pk=None):
        return self.update(request, pk=pk, partial=True)

    @action(detail=False, methods=['post'])
    def test_connection(self, request):
        """测试 Agent LLM 连接（与 sdk_runtime 同一套协议逻辑）。

        - 前端可传 config_id + use_stored_key=true 使用已保存的 API Key 测试；
        - 按 api_protocol 测试：auto 优先探测 Responses，失败降级 Chat Completions。
        """
        from apps.assistant import sdk_runtime

        config_id = request.data.get('config_id')
        use_stored_key = request.data.get('use_stored_key', False)

        stored = None
        if use_stored_key and config_id:
            stored = AgentConfig.objects.filter(pk=config_id).first()

        model_name = request.data.get('model_name') or (stored.model_name if stored else 'qwen-plus')
        api_key = request.data.get('api_key') or (stored.api_key if stored else '')
        base_url = request.data.get('base_url') or (stored.base_url if stored else '')
        provider = request.data.get('provider') or (stored.provider if stored else 'qwen')
        api_protocol = request.data.get('api_protocol') or (stored.api_protocol if stored else 'auto')

        if not api_key:
            return Response({'error': 'API Key 是必填项，或先保存配置后使用已保存的 Key 测试'},
                            status=status.HTTP_400_BAD_REQUEST)

        target_url = base_url.rstrip('/')
        if not target_url:
            target_url = (sdk_runtime.PROVIDER_DEFAULT_BASE.get(provider, '') or '').rstrip('/')
        if not target_url:
            return Response({'error': '请填写 API Base URL 或选择模型提供商'},
                            status=status.HTTP_400_BAD_REQUEST)

        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        payload = {
            'model': model_name,
            'input': 'ping',
            'max_output_tokens': 16,
            'stream': False,
        }
        chat_payload = {
            'model': model_name,
            'messages': [{'role': 'user', 'content': 'ping'}],
            'max_tokens': 16,
        }

        def _probe(url, body):
            candidates = [url]
            # 兼容不带 /v1 的裸地址（如 https://api.deepseek.com）
            if not url.endswith('/v1') and '/compatible-mode/v1' not in url:
                candidates.append(url + '/v1')
            last_err = None
            for candidate in dict.fromkeys(candidates):
                resp = requests.post(candidate, headers=headers, json=body, timeout=20)
                if resp.status_code == 200:
                    return True, None
                last_err = f'{candidate}: {resp.status_code} {resp.text[:200]}'
            return False, last_err

        try:
            protocol_ok = {}
            used_protocol = None
            error_detail = None

            if api_protocol in ('responses', 'chat_completions'):
                if api_protocol == 'responses':
                    ok, err = _probe(f'{target_url}/responses', payload)
                    protocol_ok['responses'] = ok
                    used_protocol = 'responses' if ok else None
                    error_detail = err
                else:
                    ok, err = _probe(f'{target_url}/chat/completions', chat_payload)
                    protocol_ok['chat_completions'] = ok
                    used_protocol = 'chat_completions' if ok else None
                    error_detail = err
            else:
                # auto：优先探测 Responses，失败再探测 Chat Completions
                ok, err = _probe(f'{target_url}/responses', payload)
                protocol_ok['responses'] = ok
                if ok:
                    used_protocol = 'responses'
                else:
                    ok2, err2 = _probe(f'{target_url}/chat/completions', chat_payload)
                    protocol_ok['chat_completions'] = ok2
                    error_detail = err2
                    if ok2:
                        used_protocol = 'chat_completions'

            if used_protocol:
                return Response({
                    'message': '连接成功！',
                    'success': True,
                    'protocol': used_protocol,
                    'protocol_label': 'Responses API' if used_protocol == 'responses' else 'Chat Completions',
                    'protocol_support': protocol_ok,
                    'model': model_name,
                })
            return Response({
                'error': f'连接失败: {error_detail or "两种协议均不支持"}',
                'success': False,
                'protocol_support': protocol_ok,
            }, status=status.HTTP_400_BAD_REQUEST)

        except requests.exceptions.Timeout:
            return Response({'error': '连接超时', 'success': False},
                            status=status.HTTP_408_REQUEST_TIMEOUT)
        except requests.exceptions.RequestException as e:
            return Response({'error': f'连接错误: {str(e)}', 'success': False},
                            status=status.HTTP_400_BAD_REQUEST)


class AgentSkillViewSet(viewsets.ViewSet):
    """Agent Skill 管理 — 基于本地文件系统"""
    permission_classes = [IsAuthenticated]

    def list(self, request):
        """列出所有已安装的 Skill"""
        from .skill_loader import scan_skills
        skills = scan_skills()
        results = []
        for s in skills:
            results.append({
                'name': s.name,
                'dir_name': s.dir_name,
                'display_name': s.display_name,
                'description': s.description,
                'enabled': s.enabled,
                'order': s.order,
                'has_mcp': s.mcp_config is not None,
                'has_error': s.has_error,
            })
        return Response(results)

    @action(detail=False, methods=['post'])
    def import_skill(self, request):
        """导入 Skill 包"""
        uploaded = request.FILES.get('file')
        if not uploaded:
            return Response({'error': '请上传 .zip 文件'}, status=400)

        # 保存临时文件
        import tempfile
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        try:
            for chunk in uploaded.chunks():
                tmp.write(chunk)
            tmp.close()

            from .skill_loader import install_skill
            skill = install_skill(tmp.name)
            if skill:
                return Response({'success': True, 'name': skill.name,
                                 'display_name': skill.display_name})
            return Response({'error': '未找到 SKILL.md 文件'}, status=400)
        finally:
            os.unlink(tmp.name)

    @action(detail=False, methods=['post'])
    def toggle_skill(self, request):
        """启用/禁用 Skill（修改 config.yaml）"""
        name = request.data.get('name')
        enabled = request.data.get('enabled', True)

        from .skill_loader import SKILLS_DIR, scan_skills
        skill = None
        for s in scan_skills():
            if s.name == name:
                skill = s
                break
        if not skill:
            return Response({'error': 'Skill 不存在'}, status=404)

        cfg_path = os.path.join(SKILLS_DIR, skill.dir_name, 'config.yaml')
        cfg = {}
        if os.path.isfile(cfg_path):
            with open(cfg_path, 'r', encoding='utf-8') as f:
                cfg = yaml.safe_load(f) or {}
        cfg['enabled'] = enabled
        with open(cfg_path, 'w', encoding='utf-8') as f:
            yaml.dump(cfg, f, allow_unicode=True)

        from .skill_loader import invalidate_skills_cache
        invalidate_skills_cache()
        return Response({'success': True, 'name': name, 'enabled': enabled})

    @action(detail=False, methods=['post'])
    def delete_skill(self, request):
        """删除 Skill"""
        name = request.data.get('name')
        from .skill_loader import delete_skill
        ok = delete_skill(name)
        return Response({'success': ok})


# ============================================================
# 独立 MCP Server 管理
# ============================================================

class MCPServerViewSet(viewsets.ViewSet):
    """独立 MCP Server 管理 — 与 Skill 解耦"""
    permission_classes = [IsAuthenticated]

    MCP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), 'mcp_servers')

    def _ensure_dir(self):
        os.makedirs(self.MCP_DIR, exist_ok=True)

    def list(self, request):
        """列出所有 MCP Server"""
        from .skill_loader import get_enabled_skills
        self._ensure_dir()

        # 独立 MCP 配置
        standalone = []
        for fname in sorted(os.listdir(self.MCP_DIR)):
            if fname.endswith('.json'):
                path = os.path.join(self.MCP_DIR, fname)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        cfg = json.load(f)
                    standalone.append({
                        'name': fname.replace('.json', ''),
                        'file': fname,
                        'type': cfg.get('type', 'stdio'),
                        'command': cfg.get('command', cfg.get('url', '')),
                        'enabled': cfg.get('enabled', True),
                        'source': 'mcp',
                    })
                except Exception as e:
                    standalone.append({'name': fname, 'error': str(e), 'source': 'mcp'})

        # Skill 中嵌入的 MCP
        embedded = []
        for sk in get_enabled_skills():
            if sk.mcp_config:
                servers = sk.mcp_config.get('mcpServers', {})
                for name, cfg in servers.items():
                    embedded.append({
                        'name': f'{sk.name}/{name}',
                        'type': cfg.get('type', 'stdio'),
                        'command': cfg.get('command', cfg.get('url', '')),
                        'enabled': sk.enabled,
                        'source': 'skill',
                        'skill_name': sk.display_name,
                    })

        return Response({'standalone': standalone, 'embedded': embedded})

    @action(detail=False, methods=['post'])
    def add_server(self, request):
        """添加 MCP Server"""
        name = request.data.get('name', '').strip()
        if not name:
            return Response({'error': '请输入名称'}, status=400)

        # 安全的文件名
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
        cfg = {
            'enabled': True,
            'type': request.data.get('type', 'stdio'),
            'command': request.data.get('command', ''),
            'args': request.data.get('args', []),
            'url': request.data.get('url', ''),
            'env': request.data.get('env', {}),
        }

        self._ensure_dir()
        path = os.path.join(self.MCP_DIR, f'{safe_name}.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return Response({'success': True, 'name': safe_name})

    @action(detail=False, methods=['post'])
    def delete_server(self, request):
        """删除 MCP Server"""
        name = request.data.get('name', '')
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
        path = os.path.join(self.MCP_DIR, f'{safe_name}.json')
        if os.path.isfile(path):
            os.remove(path)
            return Response({'success': True})
        return Response({'error': '不存在'}, status=404)

    @action(detail=False, methods=['post'])
    def toggle_server(self, request):
        """启用/禁用 MCP Server"""
        name = request.data.get('name', '')
        enabled = request.data.get('enabled', True)
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
        path = os.path.join(self.MCP_DIR, f'{safe_name}.json')
        if os.path.isfile(path):
            with open(path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            cfg['enabled'] = enabled
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            return Response({'success': True})
        return Response({'error': '不存在'}, status=404)
