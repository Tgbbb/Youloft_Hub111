# -*- coding: utf-8 -*-
"""Midscene HTML 测试报告生成测试：数据统计、HTML 渲染、文件生成与复用。"""
import io
import os
import tempfile

from django.conf import settings
from django.test import TestCase, override_settings
from PIL import Image

from apps.ui_automation.midscene_report import (
    _resolve_media_path,
    build_report_data,
    generate_report_file,
    to_html,
)
from apps.ui_automation.models import MidsceneExecutionRecord


def _make_png_bytes(seed=1):
    import random
    rnd = random.Random(seed)
    img = Image.new('L', (64, 64))
    img.putdata([rnd.randint(0, 255) for _ in range(64 * 64)])
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def _make_record(**overrides):
    data = dict(
        case_name='登录流程',
        platform='android',
        status='failed',
        auto_plan=False,
        duration=83,
        total_steps=2,
        steps_detail=[
            {
                'step': 1,
                'instruction': '点击同意并继续',
                'status': 'passed',
                'action': 'tap',
                'screenshot': '/media/midscene/1/step_1.png',
                'aiReasoning': ['[轮1] 点击协议弹窗按钮'],
                'error': '',
            },
            {
                'step': 2,
                'instruction': '点击登录',
                'status': 'failed',
                'action': 'tap',
                'screenshot': '/media/midscene/1/step_2.png',
                'aiReasoning': ['[轮1] 未找到登录按钮', '[轮2] 重试'],
                'error': '步骤执行超时',
            },
        ],
        error_message='步骤 2 执行失败',
    )
    data.update(overrides)
    return MidsceneExecutionRecord.objects.create(**data)


class ReportDataTests(TestCase):
    def setUp(self):
        self.record = _make_record()

    def test_build_report_data_stats(self):
        data = build_report_data(self.record)
        self.assertEqual(data['stats'], {'total': 2, 'passed': 1, 'failed': 1, 'stopped': 0})
        self.assertEqual(data['pass_rate'], 50.0)
        self.assertEqual(data['status_label'], '失败')
        self.assertEqual(data['duration'], '1m23s')
        self.assertEqual(data['device_name'], '-')


class ReportHtmlTests(TestCase):
    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_to_html_embeds_screenshot_and_escapes(self):
        record = _make_record()
        shot_dir = os.path.join(settings.MEDIA_ROOT, 'midscene', '1')
        os.makedirs(shot_dir, exist_ok=True)
        with open(os.path.join(shot_dir, 'step_1.png'), 'wb') as f:
            f.write(_make_png_bytes(1))

        html_text = to_html(record)
        self.assertIn('登录流程', html_text)
        self.assertIn('点击同意并继续', html_text)
        self.assertIn('data:image/png;base64,', html_text)
        self.assertIn('步骤执行超时', html_text)
        self.assertIn('执行概要', html_text)
        self.assertIn('通过率 50%', html_text)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_to_html_escapes_reasoning(self):
        record = _make_record(steps_detail=[{
            'step': 1,
            'instruction': '<script>alert(1)</script>',
            'status': 'passed',
            'action': 'tap',
            'screenshot': '',
            'aiReasoning': ['含 <img> 的推理 {x}'],
            'error': '',
        }])
        html_text = to_html(record)
        self.assertNotIn('<script>alert(1)</script>', html_text)
        self.assertIn('&lt;script&gt;', html_text)
        self.assertIn('含 &lt;img&gt; 的推理', html_text)
        self.assertIn('{x}', html_text)  # 花括号不破坏渲染


class ReportFileTests(TestCase):
    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_generate_reuse_and_force(self):
        record = _make_record()
        path1 = generate_report_file(record)
        expected = '/media/midscene/%d/report.html' % record.id
        self.assertEqual(path1, expected)
        record.refresh_from_db()
        self.assertEqual(record.report_path, expected)
        abs_path = os.path.join(settings.MEDIA_ROOT, 'midscene', str(record.id), 'report.html')
        self.assertTrue(os.path.isfile(abs_path))

        # 已存在且非 force：直接复用，不重写
        mtime = os.path.getmtime(abs_path)
        path2 = generate_report_file(record)
        self.assertEqual(path2, expected)
        self.assertEqual(os.path.getmtime(abs_path), mtime)

        # force：重新生成
        path3 = generate_report_file(record, force=True)
        self.assertEqual(path3, expected)


class ResolveMediaPathTests(TestCase):
    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_resolve_and_traversal_guard(self):
        root = settings.MEDIA_ROOT
        ok_dir = os.path.join(root, 'midscene', '1')
        os.makedirs(ok_dir, exist_ok=True)
        target = os.path.join(ok_dir, 'step_1.png')
        with open(target, 'wb') as f:
            f.write(_make_png_bytes(1))

        self.assertEqual(_resolve_media_path('/media/midscene/1/step_1.png'), os.path.realpath(target))
        self.assertIsNone(_resolve_media_path('/media/../settings.py'))
        self.assertIsNone(_resolve_media_path('http://evil.com/x.png'))
        self.assertIsNone(_resolve_media_path('/media/midscene/1/missing.png'))
