# -*- coding: utf-8 -*-
"""iOS Agent 注册/心跳接口 与 心跳失效置离线任务。"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.ui_automation.models import MidsceneDevice
from apps.ui_automation.tasks import mark_stale_midscene_devices

User = get_user_model()

REPORT_URL = '/api/ui-automation/midscene/devices/agent_report/'
RELEASE_URL = '/api/ui-automation/midscene/devices/agent_release/'
LIST_URL = '/api/ui-automation/midscene/devices/'


class AgentReportApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='agent', password='pass')
        self.token = Token.objects.create(user=self.user)
        self.client = APIClient()

    def _auth(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)

    def test_requires_auth(self):
        r = self.client.post(REPORT_URL, {'device_id': 'UDID-1'}, format='json')
        self.assertEqual(r.status_code, 401)

    def test_creates_device_and_sets_fields(self):
        self._auth()
        r = self.client.post(REPORT_URL, {
            'device_id': 'UDID-1', 'platform': 'ios', 'name': 'iPhone (PC-A)',
            'wda_host': '192.168.8.55:9000', 'ios_version': '17.5.1', 'agent_host': 'PC-A',
        }, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data['created'])
        d = MidsceneDevice.objects.get(device_id='UDID-1')
        self.assertEqual(d.platform, 'ios')
        self.assertEqual(d.status, 'online')
        self.assertEqual(d.agent_host, 'PC-A')
        self.assertEqual(d.wda_host, '192.168.8.55:9000')
        self.assertEqual(d.tidevice_udid, 'UDID-1')
        self.assertIsNotNone(d.last_seen_at)

    def test_updates_existing_and_refreshes_last_seen(self):
        self._auth()
        d = MidsceneDevice.objects.create(
            platform='ios', device_id='UDID-1', status='offline',
            last_seen_at=timezone.now() - timedelta(minutes=30),
        )
        old_seen = d.last_seen_at
        r = self.client.post(REPORT_URL, {
            'device_id': 'UDID-1', 'platform': 'ios', 'wda_host': '127.0.0.1:9000',
            'agent_host': 'PC-A',
        }, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data['created'])
        d.refresh_from_db()
        self.assertEqual(d.status, 'online')
        self.assertGreater(d.last_seen_at, old_seen)

    def test_missing_device_id(self):
        self._auth()
        r = self.client.post(REPORT_URL, {'platform': 'ios'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_list_exposes_agent_fields(self):
        self._auth()
        MidsceneDevice.objects.create(
            platform='ios', device_id='UDID-9', status='online',
            agent_host='PC-B', last_seen_at=timezone.now(),
        )
        r = self.client.get(LIST_URL)
        self.assertEqual(r.status_code, 200)
        row = [x for x in r.data['results'] if x['device_id'] == 'UDID-9'][0]
        self.assertEqual(row['agent_host'], 'PC-B')
        self.assertIsNotNone(row['last_seen_at'])


class AgentReleaseApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='agent', password='pass')
        self.token = Token.objects.create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)

    def test_release_marks_offline(self):
        MidsceneDevice.objects.create(platform='ios', device_id='UDID-2', status='online')
        r = self.client.post(RELEASE_URL, {'device_id': 'UDID-2'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(MidsceneDevice.objects.get(device_id='UDID-2').status, 'offline')

    def test_release_unknown_device(self):
        r = self.client.post(RELEASE_URL, {'device_id': 'NOPE'}, format='json')
        self.assertEqual(r.status_code, 404)


class StaleDeviceTaskTests(TestCase):
    def test_stale_ios_device_goes_offline(self):
        MidsceneDevice.objects.create(
            platform='ios', device_id='UDID-3', status='online',
            last_seen_at=timezone.now() - timedelta(seconds=300),
        )
        n = mark_stale_midscene_devices.apply(args=[120]).get()
        self.assertEqual(n, 1)
        self.assertEqual(MidsceneDevice.objects.get(device_id='UDID-3').status, 'offline')

    def test_fresh_device_untouched(self):
        MidsceneDevice.objects.create(
            platform='ios', device_id='UDID-4', status='online',
            last_seen_at=timezone.now(),
        )
        n = mark_stale_midscene_devices.apply(args=[120]).get()
        self.assertEqual(n, 0)
        self.assertEqual(MidsceneDevice.objects.get(device_id='UDID-4').status, 'online')

    def test_locked_device_untouched(self):
        MidsceneDevice.objects.create(
            platform='ios', device_id='UDID-5', status='locked',
            last_seen_at=timezone.now() - timedelta(seconds=300),
        )
        n = mark_stale_midscene_devices.apply(args=[120]).get()
        self.assertEqual(n, 0)
        self.assertEqual(MidsceneDevice.objects.get(device_id='UDID-5').status, 'locked')

    def test_device_without_heartbeat_untouched(self):
        MidsceneDevice.objects.create(
            platform='ios', device_id='UDID-6', status='available', last_seen_at=None,
        )
        n = mark_stale_midscene_devices.apply(args=[120]).get()
        self.assertEqual(n, 0)
        self.assertEqual(MidsceneDevice.objects.get(device_id='UDID-6').status, 'available')
