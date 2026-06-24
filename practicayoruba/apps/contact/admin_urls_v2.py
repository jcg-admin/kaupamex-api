"""
Admin URLs v2 — apps.contact F5 (§2.5).

Mounted in config/urls.py:
  path('api/v2/admin/', include('apps.contact.admin_urls_v2', namespace='admin_contact_v2'))
"""
from django.urls import path

from .views_v2 import AdminContactMessageReplyV2View, AdminContactMessageV2View

app_name = 'admin_contact_v2'

urlpatterns = [
    path('contact/messages/<int:message_id>/',
         AdminContactMessageV2View.as_view(),
         name='message-detail'),
    path('contact/messages/<int:message_id>/replies/',
         AdminContactMessageReplyV2View.as_view(),
         name='message-reply'),
]
