# -*- coding: utf-8 -*-
"""
清理 Midscene 执行截图目录

删除没有对应执行记录的孤儿目录（例如执行记录已删除但截图残留），
可选按天数过滤。用法：
    python manage.py cleanup_midscene_media --dry-run
    python manage.py cleanup_midscene_media --days 30
"""
import os
import shutil
from datetime import datetime, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.ui_automation.models import MidsceneExecutionRecord


class Command(BaseCommand):
    help = '清理 Midscene 执行截图：删除无对应执行记录的孤儿目录'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', type=int, default=0,
            help='只清理 N 天前最后写入的截图目录（0=不限）',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='只打印将删除的目录，不实际删除',
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']

        midscene_root = os.path.join(settings.MEDIA_ROOT, 'midscene')
        if not os.path.isdir(midscene_root):
            self.stdout.write(f'Midscene 截图目录不存在: {midscene_root}')
            return

        existing_ids = set(MidsceneExecutionRecord.objects.values_list('id', flat=True))
        cutoff = datetime.now() - timedelta(days=days) if days > 0 else None

        orphans = []
        for name in os.listdir(midscene_root):
            entry = os.path.join(midscene_root, name)
            if not os.path.isdir(entry) or not name.isdigit():
                continue
            if int(name) in existing_ids:
                continue
            if cutoff is not None:
                mtime = datetime.fromtimestamp(os.path.getmtime(entry))
                if mtime > cutoff:
                    continue
            orphans.append(entry)

        if not orphans:
            self.stdout.write('没有需要清理的孤儿截图目录')
            return

        self.stdout.write(f'发现 {len(orphans)} 个孤儿截图目录（dry-run={dry_run}）')
        for entry in sorted(orphans):
            self.stdout.write(f'  {entry}')
            if not dry_run:
                shutil.rmtree(entry, ignore_errors=True)

        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f'已清理 {len(orphans)} 个目录'))
