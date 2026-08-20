# -*- coding: utf-8 -*-
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class ToolboxConfig(models.Model):
    """工具合集共享配置（单例），当前服务于推送对比工具。"""

    imap_host = models.CharField(max_length=255, default='imap.qiye.aliyun.com', verbose_name='IMAP服务器')
    imap_port = models.IntegerField(default=993, verbose_name='IMAP端口')
    imap_user = models.CharField(max_length=255, blank=True, default='', verbose_name='IMAP账号')
    imap_password = models.CharField(max_length=512, blank=True, default='', verbose_name='IMAP密码')
    imap_timeout = models.IntegerField(default=20, verbose_name='IMAP超时(秒)')
    backend_host = models.CharField(max_length=255, default='192.168.1.110', verbose_name='推送后台地址')
    backend_port = models.IntegerField(default=8015, verbose_name='推送后台端口')
    push_cookie = models.TextField(blank=True, default='', verbose_name='推送后台Cookie')
    tesseract_path = models.CharField(max_length=512, blank=True, default='', verbose_name='Tesseract路径(可选)')
    last_uid = models.BigIntegerField(null=True, blank=True, verbose_name='最近处理邮件UID')
    last_date = models.CharField(max_length=64, blank=True, default='', verbose_name='最近处理邮件日期')
    last_problems = models.IntegerField(default=0, verbose_name='最近处理问题数')
    updated_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, verbose_name='最后修改人')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'toolbox_config'
        verbose_name = '工具合集配置'
        verbose_name_plural = verbose_name

    @classmethod
    def get_singleton(cls):
        obj = cls.objects.first()
        if obj is None:
            obj = cls.objects.create()
        return obj

    def __str__(self):
        return '工具合集共享配置'


class PushCheckRun(models.Model):
    """推送对比工具运行记录。"""

    STATUS_CHOICES = (
        ('pending', '待执行'),
        ('running', '执行中'),
        ('success', '成功'),
        ('failed', '失败'),
    )

    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, verbose_name='发起人')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    force = models.BooleanField(default=False, verbose_name='强制重查')
    log = models.TextField(blank=True, default='', verbose_name='运行日志')
    summary = models.JSONField(default=dict, blank=True, verbose_name='结果摘要')
    started_at = models.DateTimeField(auto_now_add=True, verbose_name='开始时间')
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name='结束时间')

    class Meta:
        db_table = 'toolbox_push_check_run'
        verbose_name = '推送对比运行记录'
        verbose_name_plural = verbose_name
        ordering = ['-started_at']

    def __str__(self):
        return '推送对比 #%s (%s)' % (self.pk, self.get_status_display())
