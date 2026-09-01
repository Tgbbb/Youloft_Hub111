# -*- coding: utf-8 -*-
"""Midscene 用例编排：回放索引解析（不依赖数据库的逻辑）。"""
from unittest import mock
from django.test import SimpleTestCase
from apps.ui_automation import tasks as midscene_tasks
from apps.ui_automation.models import MidsceneExecutionRecord, MidsceneSequenceItem


class SequenceModelTests(SimpleTestCase):
    def test_execution_status_has_skipped(self):
        statuses = [c[0] for c in MidsceneExecutionRecord.STATUS_CHOICES]
        self.assertIn('skipped', statuses)

    def test_item_replay_mode_choices(self):
        choices = [c[0] for c in MidsceneSequenceItem.REPLAY_MODE_CHOICES]
        self.assertEqual(choices, ['auto', 'fixed'])


class SequenceReplayIndexTests(SimpleTestCase):
    def _item(self, replay_mode, replay_index, replay_data):
        item = mock.Mock(replay_mode=replay_mode, replay_index=replay_index)
        item.case = mock.Mock(replay_data=replay_data)
        return item

    def test_fixed_uses_replay_index(self):
        dev = mock.Mock(platform='android', name='X')
        it = self._item('fixed', 7, [{'device': {'platform': 'android'}}])
        self.assertEqual(midscene_tasks._resolve_replay_index(dev, it), 7)

    def test_auto_uses_recommended_index(self):
        dev = mock.Mock(platform='android', name='X')
        it = self._item('auto', 0, [{'device': {'platform': 'android'}}])
        with mock.patch('apps.ui_automation.views_midscene._pick_best_replay',
                        return_value={'recommended_index': 3}):
            self.assertEqual(midscene_tasks._resolve_replay_index(dev, it), 3)

    def test_auto_fallback_latest_when_no_match(self):
        dev = mock.Mock(platform='android', name='X')
        it = self._item('auto', 0, [{'device': {'platform': 'android'}}])
        with mock.patch('apps.ui_automation.views_midscene._pick_best_replay',
                        return_value={'recommended_index': None}):
            self.assertEqual(midscene_tasks._resolve_replay_index(dev, it), 0)

    def test_auto_no_replay_data_falls_back_latest(self):
        dev = mock.Mock(platform='android', name='X')
        it = self._item('auto', 0, None)
        self.assertEqual(midscene_tasks._resolve_replay_index(dev, it), 0)
