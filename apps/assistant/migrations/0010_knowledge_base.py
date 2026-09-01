# 知识库 RAG 模型迁移

from django.conf import settings
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('assistant', '0009_agentconfig_tool_groups'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='KnowledgeBase',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='知识库名称')),
                ('description', models.TextField(blank=True, verbose_name='描述')),
                ('embedding_model', models.CharField(default='deepseek-embedding', max_length=100, verbose_name='Embedding模型')),
                ('embedding_dim', models.IntegerField(default=1024, verbose_name='向量维度')),
                ('chunk_size', models.IntegerField(default=500, verbose_name='分块大小(字符)')),
                ('chunk_overlap', models.IntegerField(default=50, verbose_name='分块重叠(字符)')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('created_by', models.ForeignKey(null=True, on_delete=models.deletion.SET_NULL, related_name='knowledge_bases', to=settings.AUTH_USER_MODEL, verbose_name='创建人')),
            ],
            options={
                'verbose_name': '知识库',
                'verbose_name_plural': '知识库',
                'db_table': 'knowledge_bases',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='KnowledgeDocument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file_name', models.CharField(max_length=500, verbose_name='文件名')),
                ('file_type', models.CharField(choices=[('xmind', 'XMind'), ('pdf', 'PDF'), ('docx', 'Word'), ('md', 'Markdown'), ('txt', 'TXT')], max_length=20)),
                ('file_size', models.IntegerField(default=0, verbose_name='文件大小(字节)')),
                ('file_path', models.CharField(max_length=1000, verbose_name='存储路径')),
                ('total_chunks', models.IntegerField(default=0, verbose_name='分块数')),
                ('status', models.CharField(choices=[('pending', '待处理'), ('parsing', '解析中'), ('embedding', '向量化中'), ('done', '完成'), ('failed', '失败')], default='pending', max_length=20, verbose_name='处理状态')),
                ('error_message', models.TextField(blank=True, verbose_name='错误信息')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='上传时间')),
                ('processed_at', models.DateTimeField(blank=True, null=True, verbose_name='处理完成时间')),
                ('uploaded_by', models.ForeignKey(null=True, on_delete=models.deletion.SET_NULL, related_name='uploaded_kb_documents', to=settings.AUTH_USER_MODEL, verbose_name='上传人')),
                ('knowledge_base', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='documents', to='assistant.knowledgebase', verbose_name='所属知识库')),
            ],
            options={
                'verbose_name': '知识库文档',
                'verbose_name_plural': '知识库文档',
                'db_table': 'knowledge_documents',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='KnowledgeChunk',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('chunk_index', models.IntegerField(verbose_name='分块序号')),
                ('content', models.TextField(verbose_name='文本内容')),
                ('content_length', models.IntegerField(default=0, verbose_name='字符数')),
                ('embedding', models.BinaryField(verbose_name='Embedding向量(pickle)')),
                ('chunk_metadata', models.JSONField(blank=True, default=dict, help_text='如 {"page": 1, "section": "签到模块"}', verbose_name='元数据')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='创建时间')),
                ('document', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='chunks', to='assistant.knowledgedocument', verbose_name='所属文档')),
                ('knowledge_base', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='chunks', to='assistant.knowledgebase', verbose_name='所属知识库')),
            ],
            options={
                'verbose_name': '知识库分块',
                'verbose_name_plural': '知识库分块',
                'db_table': 'knowledge_chunks',
                'ordering': ['knowledge_base', 'document', 'chunk_index'],
            },
        ),
        migrations.AddIndex(
            model_name='knowledgechunk',
            index=models.Index(fields=['knowledge_base', 'document'], name='knowledge_c_knowled_5e6f1f_idx'),
        ),
    ]
