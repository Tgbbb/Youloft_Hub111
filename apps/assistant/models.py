from django.db import models
from django.utils import timezone
from apps.users.models import User


class DifyConfig(models.Model):
    """Dify API配置（已废弃，保留向后兼容）"""
    api_url = models.URLField(max_length=500, verbose_name='API URL', help_text='Dify API endpoint URL')
    api_key = models.CharField(max_length=500, verbose_name='API Key', help_text='Dify API密钥')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'dify_configs'
        verbose_name = 'Dify配置（已废弃）'
        verbose_name_plural = 'Dify配置（已废弃）'
        ordering = ['-created_at']

    def __str__(self):
        return f"Dify Config - {'Active' if self.is_active else 'Inactive'}"

    @classmethod
    def get_active_config(cls):
        """获取当前激活的配置（已废弃，Agent 模式不再使用）"""
        return cls.objects.filter(is_active=True).first()


class AgentConfig(models.Model):
    """TestHub Agent 配置 — 替代 DifyConfig"""
    PROVIDER_CHOICES = [
        ('deepseek', 'DeepSeek'),
        ('qwen', '通义千问'),
        ('siliconflow', '硅基流动'),
        ('zhipu', '智谱'),
        ('openai', 'OpenAI'),
        ('other', '其他'),
    ]
    PROTOCOL_CHOICES = [
        ('auto', '自动探测'),
        ('responses', 'Responses API'),
        ('chat_completions', 'Chat Completions'),
    ]

    name = models.CharField(max_length=200, verbose_name='配置名称')
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, verbose_name='模型提供商')
    model_name = models.CharField(max_length=200, default='qwen-plus', verbose_name='模型名称')
    api_key = models.CharField(max_length=500, verbose_name='API Key')
    base_url = models.URLField(max_length=500, blank=True, verbose_name='API Base URL',
                                help_text='OpenAI兼容接口地址，留空使用默认')
    api_protocol = models.CharField(max_length=20, choices=PROTOCOL_CHOICES, default='auto',
                                     verbose_name='接入协议',
                                     help_text='自动探测优先使用 Responses API，失败自动降级 Chat Completions')
    max_tokens = models.IntegerField(default=8192, verbose_name='最大Token数')
    temperature = models.FloatField(default=0.7, verbose_name='温度参数')
    max_tool_calls = models.IntegerField(default=20, verbose_name='单轮最大工具调用次数',
                                         help_text='Agent 单轮对话最多调用的工具次数，复杂任务可调大')
    tool_groups = models.JSONField(default=list, blank=True, verbose_name='启用工具组',
                                   help_text='按后台功能模块启用工具，空表示全部启用')
    is_active = models.BooleanField(default=True, verbose_name='是否启用',
                                     help_text='启用后 Agent 将使用此配置')
    system_prompt_extra = models.TextField(blank=True, verbose_name='额外系统提示词',
                                            help_text='追加到 Agent 系统提示词末尾的自定义内容')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'agent_configs'
        verbose_name = 'Agent配置'
        verbose_name_plural = 'Agent配置'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.get_provider_display()})"

    @classmethod
    def get_active_config(cls):
        """获取当前激活的 Agent 配置"""
        return cls.objects.filter(is_active=True).first()


class AgentSkill(models.Model):
    """Agent 可调用的技能包（类似 Claude Code Skills）"""
    name = models.CharField(max_length=100, unique=True, verbose_name='技能标识',
                            help_text='用于调用的唯一标识，如: swagger-import')
    display_name = models.CharField(max_length=200, verbose_name='显示名称',
                                     help_text='如: Swagger 文档导入')
    description = models.CharField(max_length=500, verbose_name='简要描述',
                                    help_text='在 Skill 列表中展示的一句话说明')
    instructions = models.TextField(verbose_name='执行指令',
                                     help_text='注入到 Agent 系统提示词的指令内容，告诉 Agent 如何完成这个任务')
    tools = models.JSONField(default=list, blank=True, verbose_name='可用工具',
                              help_text='该 Skill 可用的工具列表，空列表表示使用全部工具')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    order = models.IntegerField(default=0, verbose_name='排序')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'agent_skills'
        verbose_name = 'Agent 技能'
        verbose_name_plural = 'Agent 技能'
        ordering = ['order', '-created_at']

    def __str__(self):
        return f'{self.display_name} ({self.name})'


class AssistantSession(models.Model):
    """智能助手会话记录"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assistant_sessions', verbose_name='用户')
    project = models.ForeignKey('projects.Project', on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='assistant_sessions', verbose_name='关联项目')
    session_id = models.CharField(max_length=200, verbose_name='会话ID')
    conversation_id = models.CharField(max_length=200, blank=True, null=True, verbose_name='Dify对话ID')
    title = models.CharField(max_length=500, blank=True, verbose_name='会话标题')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'assistant_sessions'
        verbose_name = '智能助手会话'
        verbose_name_plural = '智能助手会话'
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.title or self.session_id}"


class ChatMessage(models.Model):
    """聊天消息记录"""
    ROLE_CHOICES = [
        ('user', '用户'),
        ('assistant', '助手'),
    ]
    
    session = models.ForeignKey(AssistantSession, on_delete=models.CASCADE, related_name='chat_messages', verbose_name='会话')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, verbose_name='角色')
    content = models.TextField(verbose_name='消息内容')
    conversation_id = models.CharField(max_length=200, blank=True, null=True, verbose_name='Dify对话ID')
    message_id = models.CharField(max_length=200, blank=True, null=True, verbose_name='Dify消息ID')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    
    class Meta:
        db_table = 'chat_messages'
        verbose_name = '聊天消息'
        verbose_name_plural = '聊天消息'
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.get_role_display()}: {self.content[:50]}"


class AssistantMessage(models.Model):
    """智能助手消息记录（保留用于向后兼容）"""
    MESSAGE_TYPE_CHOICES = [
        ('user', '用户消息'),
        ('assistant', '助手回复'),
    ]
    
    session = models.ForeignKey(AssistantSession, on_delete=models.CASCADE, related_name='messages', verbose_name='会话')
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES, verbose_name='消息类型')
    content = models.TextField(verbose_name='消息内容')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    
    class Meta:
        db_table = 'assistant_messages'
        verbose_name = '智能助手消息'
        verbose_name_plural = '智能助手消息'
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.get_message_type_display()}: {self.content[:50]}"


class AgentFile(models.Model):
    """Agent 文件管理 — 上传文件 & 产出文件"""
    SOURCE_CHOICES = [
        ('upload', '用户上传'),
        ('output', 'Agent 产出'),
    ]

    session = models.ForeignKey(AssistantSession, on_delete=models.CASCADE,
                                related_name='files', verbose_name='所属会话')
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, verbose_name='来源')
    file_name = models.CharField(max_length=500, verbose_name='文件名')
    file_path = models.CharField(max_length=1000, verbose_name='存储路径')
    file_url = models.CharField(max_length=1000, verbose_name='访问URL')
    file_size = models.BigIntegerField(default=0, verbose_name='文件大小(字节)')
    content_type = models.CharField(max_length=200, blank=True, verbose_name='MIME类型')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')

    class Meta:
        db_table = 'agent_files'
        verbose_name = 'Agent 文件'
        verbose_name_plural = 'Agent 文件'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_source_display()}: {self.file_name}'


# ============================================================
# 知识库 RAG 模块（自建嵌入知识库，替代 Dify 依赖）
# ============================================================

class KnowledgeBase(models.Model):
    """知识库 — 自建 RAG 知识库根表

    一份 KnowledgeBase 可包含多个 KnowledgeDocument，文档被切分后
    存储为 KnowledgeChunk（含 Embedding 向量）。Agent 通过 search_knowledge_base
    工具检索相关 chunk 并拼装到上下文。
    """
    name = models.CharField(max_length=200, verbose_name='知识库名称')
    description = models.TextField(blank=True, verbose_name='描述')
    embedding_model = models.CharField(
        max_length=100,
        default='deepseek-embedding',
        verbose_name='Embedding模型'
    )
    embedding_dim = models.IntegerField(default=1024, verbose_name='向量维度')
    chunk_size = models.IntegerField(default=500, verbose_name='分块大小(字符)')
    chunk_overlap = models.IntegerField(default=50, verbose_name='分块重叠(字符)')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='knowledge_bases_created',
        verbose_name='创建人'
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'knowledge_bases'
        verbose_name = '知识库'
        verbose_name_plural = '知识库'
        ordering = ['-updated_at']

    def __str__(self):
        return self.name


class KnowledgeDocument(models.Model):
    """知识库文档 — 上传并被切块处理的文档"""
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('parsing', '解析中'),
        ('embedding', '向量化中'),
        ('done', '完成'),
        ('failed', '失败'),
    ]
    FILE_TYPE_CHOICES = [
        ('xmind', 'XMind'),
        ('pdf', 'PDF'),
        ('docx', 'Word'),
        ('md', 'Markdown'),
        ('txt', 'TXT'),
    ]

    knowledge_base = models.ForeignKey(
        KnowledgeBase,
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name='所属知识库'
    )
    file_name = models.CharField(max_length=500, verbose_name='文件名')
    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES)
    file_size = models.IntegerField(default=0, verbose_name='文件大小(字节)')
    file_path = models.CharField(max_length=1000, verbose_name='存储路径')
    total_chunks = models.IntegerField(default=0, verbose_name='分块数')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='处理状态'
    )
    error_message = models.TextField(blank=True, verbose_name='错误信息')
    uploaded_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_kb_documents',
        verbose_name='上传人'
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name='上传时间')
    processed_at = models.DateTimeField(null=True, blank=True, verbose_name='处理完成时间')

    class Meta:
        db_table = 'knowledge_documents'
        verbose_name = '知识库文档'
        verbose_name_plural = '知识库文档'
        ordering = ['-created_at']

    def __str__(self):
        return self.file_name


class KnowledgeChunk(models.Model):
    """知识库文档分块 — 含 Embedding 向量 + BM25 tokens

    Embedding 以 pickle 序列化后的 bytes 存入 BinaryField（MySQL BLOB）。
    知识库规模 < 100MB 时此方案性能足够。

    BM25 关键词检索：
    - bm25_tokens: jieba 分词预存结果，避免每次检索重新分词
    - 索引缓存到 media/retrieval_cache/bm25_kb{id}.pkl
    """
    knowledge_base = models.ForeignKey(
        KnowledgeBase,
        on_delete=models.CASCADE,
        related_name='chunks',
        verbose_name='所属知识库'
    )
    document = models.ForeignKey(
        KnowledgeDocument,
        on_delete=models.CASCADE,
        related_name='chunks',
        verbose_name='所属文档'
    )
    chunk_index = models.IntegerField(verbose_name='分块序号')
    content = models.TextField(verbose_name='文本内容')
    content_length = models.IntegerField(default=0, verbose_name='字符数')
    embedding = models.BinaryField(verbose_name='Embedding向量(pickle)')
    chunk_metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='元数据',
        help_text='如 {"page": 1, "section": "签到模块"}'
    )
    # === Hybrid Retrieval 字段（Phase 1） ===
    bm25_tokens = models.JSONField(
        default=list,
        blank=True,
        verbose_name='BM25分词结果',
        help_text='jieba 分词后的 token 列表，用于 BM25 索引'
    )
    # === 软删除 + 版本管理字段（Phase 2） ===
    is_active = models.BooleanField(
        default=True,
        verbose_name='是否启用',
        help_text='False 表示软删除（被新版本替代）'
    )
    version = models.IntegerField(
        default=1,
        verbose_name='版本号',
        help_text='同 path 下递增；1 为原始版本'
    )
    superseded_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supersedes',
        verbose_name='被哪个新版本替代',
        help_text='指向替代本 chunk 的新版本 chunk（用于版本链）'
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'knowledge_chunks'
        verbose_name = '知识库分块'
        verbose_name_plural = '知识库分块'
        ordering = ['knowledge_base', 'document', 'chunk_index']
        indexes = [
            models.Index(fields=['knowledge_base', 'document']),
            models.Index(fields=['knowledge_base', 'is_active']),
        ]

    def __str__(self):
        return f"{self.document.file_name}#{self.chunk_index} (v{self.version})"


class KnowledgeUpdateLog(models.Model):
    """知识库变更日志 — 记录所有写入/删除/更新操作

    用于:
    1. 审计：谁在什么时间更新了什么内容
    2. 回滚：可基于此 log 撤销错误更新
    3. UI 展示：知识库管理页"变更日志"标签
    """
    ACTION_CHOICES = [
        ('created', '新增'),
        ('updated', '更新'),
        ('new_version', '新增版本'),
        ('deleted', '软删除'),
        ('restored', '恢复'),
    ]

    knowledge_base = models.ForeignKey(
        KnowledgeBase,
        on_delete=models.CASCADE,
        related_name='update_logs',
        verbose_name='所属知识库'
    )
    chunk = models.ForeignKey(
        KnowledgeChunk,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='update_logs',
        verbose_name='关联分块',
        help_text='新版本的 chunk_id（删除时为被删的 chunk）'
    )
    superseded_chunk = models.ForeignKey(
        KnowledgeChunk,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='superseded_logs',
        verbose_name='被替代的分块',
        help_text='被新版本替代的旧 chunk_id（仅 new_version 时有值）'
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name='操作类型')
    summary = models.TextField(verbose_name='摘要', help_text='变更内容的一句话描述')
    user = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='kb_update_logs',
        verbose_name='操作用户'
    )
    session_id = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='触发的会话ID',
        help_text='从哪个智能助手会话触发的（如果是 AI 更新）'
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name='变更时间')

    class Meta:
        db_table = 'knowledge_update_logs'
        verbose_name = '知识库变更日志'
        verbose_name_plural = '知识库变更日志'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['knowledge_base', '-created_at']),
        ]

    def __str__(self):
        return f"[{self.get_action_display()}] {self.knowledge_base.name} - {self.summary[:30]}"
