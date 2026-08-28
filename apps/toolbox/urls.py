from django.urls import path

from .views import (
    PushCheckConfigView,
    PushCheckRunCreateView,
    PushCheckRunListView,
    PushCheckRunDetailView,
    SyncCheckConfigView,
    SyncCheckRunCreateView,
    SyncCheckRunListView,
    SyncCheckTodayView,
    ReplyCheckConfigView,
    ReplyCheckRunCreateView,
    ReplyCheckRunListView,
    ReplyCheckTodayView,
)

urlpatterns = [
    path('push-check/config/', PushCheckConfigView.as_view(), name='push-check-config'),
    path('push-check/run/', PushCheckRunCreateView.as_view(), name='push-check-run'),
    path('push-check/runs/', PushCheckRunListView.as_view(), name='push-check-runs'),
    path('push-check/runs/<int:pk>/', PushCheckRunDetailView.as_view(), name='push-check-run-detail'),
    path('sync-check/config/', SyncCheckConfigView.as_view(), name='sync-check-config'),
    path('sync-check/run/', SyncCheckRunCreateView.as_view(), name='sync-check-run'),
    path('sync-check/runs/', SyncCheckRunListView.as_view(), name='sync-check-runs'),
    path('sync-check/runs/today/', SyncCheckTodayView.as_view(), name='sync-check-today'),
    path('reply-check/config/', ReplyCheckConfigView.as_view(), name='reply-check-config'),
    path('reply-check/run/', ReplyCheckRunCreateView.as_view(), name='reply-check-run'),
    path('reply-check/runs/', ReplyCheckRunListView.as_view(), name='reply-check-runs'),
    path('reply-check/runs/today/', ReplyCheckTodayView.as_view(), name='reply-check-today'),
]
