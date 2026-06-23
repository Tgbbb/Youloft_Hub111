from django.db import models
from django.utils import timezone
from apps.users.models import User
from apps.projects.models import Project

class Version(models.Model):
    """版本模型"""
    projects = models.ManyToManyField(Project, related_name='versions', verbose_name='关联项目')
    name = models.CharField(max_length=100, verbose_name='版本名称')
    description = models.TextField(blank=True, verbose_name='版本描述')
    is_baseline = models.BooleanField(default=False, verbose_name='是否为基线版本')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='创建者')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    def __str__(self):
        return self.name

    class Meta:
        db_table = 'versions'
        verbose_name = '版本'
        verbose_name_plural = '版本'
        ordering = ['-created_at']


class FunctionModule(models.Model):
    """功能模块模型 — 隶属于版本，用于细分版本的测试范围"""
    name = models.CharField(max_length=200, verbose_name='模块名称')
    version = models.ForeignKey(
        Version, on_delete=models.CASCADE, related_name='modules', verbose_name='所属版本'
    )
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='function_modules', verbose_name='所属项目'
    )
    description = models.TextField(blank=True, verbose_name='模块描述')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    def __str__(self):
        return f"{self.version.name} / {self.name}"

    class Meta:
        db_table = 'function_modules'
        verbose_name = '功能模块'
        verbose_name_plural = '功能模块'
        ordering = ['version', 'name']
        unique_together = [('version', 'name')]
