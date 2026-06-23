from django.urls import path
from . import views

urlpatterns = [
    path('', views.VersionListCreateView.as_view(), name='version-list'),
    path('<int:version_id>/modules/', views.FunctionModuleListCreateView.as_view(), name='module-list'),
    path('modules/<int:pk>/', views.FunctionModuleDetailView.as_view(), name='module-detail'),
    path('<int:pk>/', views.VersionDetailView.as_view(), name='version-detail'),
    path('projects/<int:project_id>/versions/', views.get_project_versions, name='project-versions'),
]
