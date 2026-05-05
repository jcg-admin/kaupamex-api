from django.urls import path
from .views import AdminUserListView

app_name = 'admin_users'

urlpatterns = [
    path('users/', AdminUserListView.as_view(), name='user-list'),
]
