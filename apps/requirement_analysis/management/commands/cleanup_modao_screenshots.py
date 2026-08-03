"""清理墨刀导入产生的孤儿截图目录（未被任何 ModaoImport 记录引用）。"""

import os
import re
import shutil
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.requirement_analysis.models import ModaoImport

FOLDER_RE = re.compile(r'^[A-Za-z0-9_-]{1,64}$')


class Command(BaseCommand):
    help = '删除 modao_screenshots 下未被任何导入记录引用的孤儿目录'

    def add_arguments(self, parser):
        parser.add_argument(
            '--older-than-hours', type=int, default=24,
            help='仅清理最后修改时间早于该时长的目录（默认 24 小时，保护进行中的导入）',
        )
        parser.add_argument('--dry-run', action='store_true', help='只列出不删除')

    def handle(self, *args, **options):
        older_than_hours = options['older_than_hours']
        dry_run = options['dry_run']

        root = os.path.realpath(os.path.join(settings.MEDIA_ROOT, 'modao_screenshots'))
        if not os.path.isdir(root):
            self.stdout.write(f'目录不存在: {root}')
            return

        # 收集所有被导入记录引用的目录名（import_id + 画布 URL）
        referenced = set()
        for m in ModaoImport.objects.all().only('id', 'data'):
            data = m.data or {}
            import_id = str(data.get('import_id') or '')
            if FOLDER_RE.match(import_id):
                referenced.add(import_id)
            for c in data.get('canvases', []):
                url = c.get('screenshotUrl') or c.get('screenshot_url') or ''
                if not url:
                    shots = c.get('screenshots') or []
                    url = shots[0].get('url', '') if shots else ''
                m2 = re.search(r'modao_screenshots/([^/]+)/', url or '')
                if m2 and FOLDER_RE.match(m2.group(1)):
                    referenced.add(m2.group(1))

        cutoff = time.time() - older_than_hours * 3600
        deleted = 0
        freed = 0
        for name in sorted(os.listdir(root)):
            if not FOLDER_RE.match(name) or name in referenced:
                continue
            path = os.path.realpath(os.path.join(root, name))
            # 安全校验：目标必须仍位于 modao_screenshots 目录内
            if not path.startswith(root + os.sep) or not os.path.isdir(path):
                continue
            try:
                if os.path.getmtime(path) > cutoff:
                    continue  # 可能是进行中的导入
            except OSError:
                continue
            size = sum(
                os.path.getsize(os.path.join(dp, f))
                for dp, _, fns in os.walk(path) for f in fns
            )
            if dry_run:
                self.stdout.write(f'[dry-run] 将删除: {path} ({size / 1024:.0f}KB)')
            else:
                shutil.rmtree(path)
                self.stdout.write(f'已删除: {path} ({size / 1024:.0f}KB)')
            deleted += 1
            freed += size

        self.stdout.write(self.style.SUCCESS(
            f'完成: 删除 {deleted} 个目录，释放 {freed / 1024 / 1024:.1f}MB'
        ))
