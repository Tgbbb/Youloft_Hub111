# -*- coding: utf-8 -*-
# 后校验增强（动作类型感知：OCR + 区域图像）单元测试。
import io
from unittest import mock

from django.test import SimpleTestCase
from PIL import Image, ImageDraw

from apps.ui_automation import midscene_runner


def _png(w=200, h=400, color=255, box=None):
    """生成一张 PNG 字节；box 传入时在图上画一个黑色矩形（制造区域变化）。"""
    img = Image.new('RGB', (w, h), (color, color, color))
    if box:
        ImageDraw.Draw(img).rectangle(box, fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


class NormTextTests(SimpleTestCase):
    def test_strip_punct_and_lower(self):
        self.assertEqual(midscene_runner._norm_text(' 登录： '), '登录')
        self.assertEqual(midscene_runner._norm_text('OK, Done!'), 'okdone')

    def test_none_is_empty(self):
        self.assertEqual(midscene_runner._norm_text(None), '')


class GridChangeTests(SimpleTestCase):
    def test_identical_not_changed(self):
        png = _png()
        res = midscene_runner._grid_change(png, png)
        self.assertIsNotNone(res)
        self.assertFalse(res['changed'])
        self.assertEqual(res['changed_cells'], 0)

    def test_large_change_detected(self):
        res = midscene_runner._grid_change(_png(), _png(box=(0, 0, 100, 400)))
        self.assertTrue(res['changed'])
        self.assertGreaterEqual(res['changed_cells'], 2)

    def test_small_localized_change_ignored(self):
        res = midscene_runner._grid_change(_png(), _png(box=(10, 10, 15, 15)))
        self.assertFalse(res['changed'])

    def test_missing_input_returns_none(self):
        self.assertIsNone(midscene_runner._grid_change(None, _png()))
        self.assertIsNone(midscene_runner._grid_change(_png(), None))


class BuildExpectTests(SimpleTestCase):
    def test_input_expect(self):
        exp = midscene_runner._build_step_expect(
            None, _png(), [{'action': 'input', 'text': 'abc'}])
        self.assertEqual(exp, {'kind': 'input', 'text': 'abc'})

    def test_input_blank_text_no_expect(self):
        self.assertIsNone(midscene_runner._build_step_expect(
            None, _png(), [{'action': 'input', 'text': '   '}]))

    def test_nav_expect_uses_new_text_diff(self):
        # 第一次调用取“步骤后”文本，第二次取“步骤前”文本
        with mock.patch.object(midscene_runner, '_text_lines_of',
                               side_effect=[['首页', '我的'], ['首页']]):
            exp = midscene_runner._build_step_expect(_png(), _png(), [{'action': 'tap'}])
        self.assertEqual(exp, {'kind': 'nav', 'anchors': ['我的']})

    def test_nav_no_new_text_no_expect(self):
        with mock.patch.object(midscene_runner, '_text_lines_of',
                               side_effect=[['首页'], ['首页']]):
            exp = midscene_runner._build_step_expect(_png(), _png(), [{'action': 'tap'}])
        self.assertIsNone(exp)

    def test_no_actions_no_expect(self):
        self.assertIsNone(midscene_runner._build_step_expect(None, _png(), []))

    def test_uncovered_action_no_expect(self):
        self.assertIsNone(midscene_runner._build_step_expect(
            None, _png(), [{'action': 'swipe'}]))


class VerifyExpectTests(SimpleTestCase):
    def test_input_present_no_anomaly(self):
        with mock.patch.object(midscene_runner, '_text_lines_of', return_value=['abc123']):
            out = midscene_runner._verify_step_expect({'kind': 'input', 'text': 'abc123'}, None, _png())
        self.assertEqual(out, [])

    def test_input_missing_anomaly(self):
        with mock.patch.object(midscene_runner, '_text_lines_of', return_value=['其他内容']):
            out = midscene_runner._verify_step_expect({'kind': 'input', 'text': 'abc123'}, None, _png())
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['type'], 'verify_input_mismatch')
        self.assertTrue(out[0]['recovered'])

    def test_nav_skips_ocr_when_content_changed(self):
        with mock.patch.object(midscene_runner, '_grid_change', return_value={'changed': True}):
            with mock.patch.object(midscene_runner, '_text_lines_of', return_value=[]) as o:
                out = midscene_runner._verify_step_expect({'kind': 'nav', 'anchors': ['首页']}, _png(), _png())
        self.assertEqual(out, [])
        o.assert_not_called()

    def test_nav_missing_anchor_anomaly(self):
        with mock.patch.object(midscene_runner, '_grid_change', return_value={'changed': False}):
            with mock.patch.object(midscene_runner, '_text_lines_of', return_value=['别的文本']):
                out = midscene_runner._verify_step_expect({'kind': 'nav', 'anchors': ['首页']}, _png(), _png())
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['type'], 'verify_nav_missing')
        self.assertTrue(out[0]['recovered'])

    def test_nav_anchor_present_no_anomaly(self):
        with mock.patch.object(midscene_runner, '_grid_change', return_value={'changed': False}):
            with mock.patch.object(midscene_runner, '_text_lines_of', return_value=['首页', '推荐']):
                out = midscene_runner._verify_step_expect({'kind': 'nav', 'anchors': ['首页']}, _png(), _png())
        self.assertEqual(out, [])

    def test_nav_majority_rule(self):
        anchors = ['甲', '乙', '丙']
        with mock.patch.object(midscene_runner, '_grid_change', return_value={'changed': False}):
            with mock.patch.object(midscene_runner, '_text_lines_of', return_value=['甲', '乙']):
                self.assertEqual(midscene_runner._verify_step_expect(
                    {'kind': 'nav', 'anchors': anchors}, _png(), _png()), [])
            with mock.patch.object(midscene_runner, '_text_lines_of', return_value=['甲']):
                out = midscene_runner._verify_step_expect(
                    {'kind': 'nav', 'anchors': anchors}, _png(), _png())
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['type'], 'verify_nav_missing')

    def test_no_expect_no_anomaly(self):
        self.assertEqual(midscene_runner._verify_step_expect(None, _png(), _png()), [])
        self.assertEqual(midscene_runner._verify_step_expect({}, _png(), _png()), [])

    def test_unknown_kind_no_anomaly(self):
        with mock.patch.object(midscene_runner, '_text_lines_of', return_value=['x']):
            out = midscene_runner._verify_step_expect({'kind': 'toggle'}, _png(), _png())
        self.assertEqual(out, [])

    def test_ocr_exception_degrades(self):
        with mock.patch.object(midscene_runner, '_text_lines_of', side_effect=Exception('ocr down')):
            out = midscene_runner._verify_step_expect({'kind': 'input', 'text': 'x'}, None, _png())
        self.assertEqual(out, [])


class OcrDegradeTests(SimpleTestCase):
    def test_ocr_unavailable_returns_empty(self):
        with mock.patch.object(midscene_runner, '_get_verify_ocr', side_effect=Exception('no ocr')):
            self.assertEqual(midscene_runner._ocr_lines(_png()), [])

    def test_ocr_empty_input_returns_empty(self):
        self.assertEqual(midscene_runner._ocr_lines(b''), [])
        self.assertEqual(midscene_runner._ocr_lines(None), [])
