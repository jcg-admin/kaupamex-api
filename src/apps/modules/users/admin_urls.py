from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .admin_views import AdminUserViewSet, AuditLogView

app_name = 'admin_users_v2'

router = DefaultRouter()
router.register(r'users', AdminUserViewSet, basename='admin-user')

urlpatterns = [
    path('', include(router.urls)),
    path('audit-log/', AuditLogView.as_view(), name='audit-log'),
]
