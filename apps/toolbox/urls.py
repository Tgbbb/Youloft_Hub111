from django.urls import path

from .views import (
    PushCheckConfigView,
    PushCheckRunCreateView,
    PushCheckRunListView,
    PushCheckRunDetailView,
)

urlpatterns = [
    path('push-check/config/', PushCheckConfigView.as_view(), name='push-check-config'),
    path('push-check/run/', PushCheckRunCreateView.as_view(), name='push-check-run'),
    path('push-check/runs/', PushCheckRunListView.as_view(), name='push-check-runs'),
    path('push-check/runs/<int:pk>/', PushCheckRunDetailView.as_view(), name='push-check-run-detail'),
]
