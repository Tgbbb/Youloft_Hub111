from django.contrib import admin

from .models import ToolboxConfig, PushCheckRun


@admin.register(ToolboxConfig)
class ToolboxConfigAdmin(admin.ModelAdmin):
    list_display = ('imap_host', 'imap_user', 'backend_host', 'backend_port', 'updated_by', 'updated_at')


@admin.register(PushCheckRun)
class PushCheckRunAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'status', 'force', 'started_at', 'finished_at')
    list_filter = ('status', 'force')
