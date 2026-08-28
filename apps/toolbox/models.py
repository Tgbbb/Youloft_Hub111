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


class SyncCheckConfig(models.Model):
    """同步确认工具配置（单例）：监听「已同步至线上」邮件的间隔与截止时间。"""

    enabled = models.BooleanField(default=True, verbose_name='启用自动监听')
    require_push_activity = models.BooleanField(
        default=True, verbose_name='当天无推送活动时跳过监听',
        help_text='当天无推送对比运行记录时，不监听、不报超时')
    interval_minutes = models.IntegerField(default=15, verbose_name='检查间隔(分钟)')
    deadline_time = models.CharField(max_length=8, default='18:30', verbose_name='当天截止时间(HH:MM)')
    mail_subject = models.CharField(
        max_length=255, default='回复：【测试需求】关于常规PUSH的测试需求', verbose_name='邮件标题关键词')
    mail_body_keyword = models.CharField(max_length=100, default='已同步至线上', verbose_name='正文关键词')
    extract_mode = models.CharField(
        max_length=20, default='vision_fallback', verbose_name='截图提取方式',
        choices=[('ocr', 'OCR识别'), ('vision_fallback', '视觉模型优先·OCR回退')],
        help_text='视觉模型从截图提取字段（复用 TestHub Agent 配置的模型），失败自动回退 OCR')
    last_check_at = models.DateTimeField(null=True, blank=True, verbose_name='上次检查时间')
    enable_dingtalk_notify = models.BooleanField(
        default=False, verbose_name='异常钉钉通知',
        help_text='对比不一致或超时未收到时，通过统一通知配置中的钉钉机器人推送')
    updated_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, verbose_name='最后修改人')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'toolbox_sync_check_config'
        verbose_name = '同步确认配置'
        verbose_name_plural = verbose_name

    @classmethod
    def get_singleton(cls):
        obj = cls.objects.first()
        if obj is None:
            obj = cls.objects.create()
        return obj

    def __str__(self):
        return '同步确认配置'


class SyncCheckRun(models.Model):
    """同步确认按天状态记录。"""

    STATUS_CHOICES = (
        ('pending', '待监听'),
        ('ok', '已收到·对比通过'),
        ('fail', '已收到·对比不一致'),
        ('timeout', '超时未收到'),
    )

    date = models.DateField(unique=True, verbose_name='日期')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    mail_uid = models.BigIntegerField(null=True, blank=True, verbose_name='邮件UID')
    mail_subject = models.CharField(max_length=255, blank=True, default='', verbose_name='邮件标题')
    ocr_text = models.TextField(blank=True, default='', verbose_name='OCR原文')
    parsed_fields = models.JSONField(default=dict, blank=True, verbose_name='解析字段')
    backend_record = models.JSONField(default=dict, blank=True, verbose_name='后台记录')
    diffs = models.JSONField(default=list, blank=True, verbose_name='差异列表')
    log = models.TextField(blank=True, default='', verbose_name='检查日志')
    checked_at = models.DateTimeField(null=True, blank=True, verbose_name='最近检查时间')
    notify_sent_status = models.CharField(
        max_length=10, blank=True, default='', verbose_name='已通知的异常状态',
        help_text='当天已推送钉钉的异常状态，用于去重')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'toolbox_sync_check_run'
        verbose_name = '同步确认记录'
        verbose_name_plural = verbose_name
        ordering = ['-date']

    def __str__(self):
        return '同步确认 %s (%s)' % (self.date, self.get_status_display())


class ReplyCheckConfig(models.Model):
    """配置回复提醒工具配置（单例）：筛选未回复配置邮件并钉钉提醒。"""

    enabled = models.BooleanField(default=True, verbose_name='启用自动监听')
    interval_minutes = models.IntegerField(default=15, verbose_name='检查间隔(分钟)')
    qc_recipient_keywords = models.CharField(
        max_length=255, default='品管部,qc@youloft.com', verbose_name='品管部收件人关键字',
        help_text='逗号分隔，匹配 To/CC 的显示名或地址，任一命中即算收件人有品管部')
    body_keyword = models.CharField(max_length=100, default='请QC检查', verbose_name='正文关键字')
    title_keywords = models.CharField(
        max_length=255, default='配置,广告,测试需求', verbose_name='标题关键字',
        help_text='逗号分隔，标题命中任一即纳入')
    ad_keyword = models.CharField(
        max_length=255, default='广告', verbose_name='广告关键字',
        help_text='逗号分隔，标题命中任一即视为广告并立即提醒')
    notify_threshold_minutes = models.IntegerField(default=30, verbose_name='非广告提醒阈值(分钟)')
    enable_dingtalk_notify = models.BooleanField(
        default=True, verbose_name='钉钉通知',
        help_text='未回复配置邮件通过「统一通知配置」中的钉钉机器人推送')
    last_check_at = models.DateTimeField(null=True, blank=True, verbose_name='上次检查时间')
    updated_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, verbose_name='最后修改人')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'toolbox_reply_check_config'
        verbose_name = '配置回复提醒配置'
        verbose_name_plural = verbose_name

    @classmethod
    def get_singleton(cls):
        obj = cls.objects.first()
        if obj is None:
            obj = cls.objects.create()
        return obj

    def __str__(self):
        return '配置回复提醒配置'


class ReplyCheckRun(models.Model):
    """配置回复提醒按天检查记录。"""

    date = models.DateField(unique=True, verbose_name='日期')
    unreplied_count = models.IntegerField(default=0, verbose_name='未回复数量')
    ad_unreplied_count = models.IntegerField(default=0, verbose_name='广告未回复数量')
    unresolved = models.JSONField(
        default=list, blank=True, verbose_name='未回复列表',
        help_text='[{subject,sender,send_time,ad,is_replied,key}]')
    notified_keys = models.JSONField(
        default=list, blank=True, verbose_name='已通知主题',
        help_text='当天已推送钉钉的归一化主题，用于去重')
    log = models.TextField(blank=True, default='', verbose_name='检查日志')
    checked_at = models.DateTimeField(null=True, blank=True, verbose_name='最近检查时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'toolbox_reply_check_run'
        verbose_name = '配置回复提醒记录'
        verbose_name_plural = verbose_name
        ordering = ['-date']

    def __str__(self):
        return '配置回复提醒 %s' % self.date
