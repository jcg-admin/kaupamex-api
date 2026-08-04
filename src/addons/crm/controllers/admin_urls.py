"""Admin URLs — bandeja de contacto (``crm``). Montado en /api/v2/admin/."""
from django.urls import path
from addons.crm.controllers.main import (
    AdminContactMessageListView,
    AdminContactMessageMarkReadView,
    AdminContactMessageV2View,
    AdminContactMessageReplyV2View,
)


app_name = 'admin_contact'

urlpatterns = [
    path('contact/messages/',
         AdminContactMessageListView.as_view(),
         name='admin-list'),
    path('contact/messages/<int:message_id>/',
         AdminContactMessageV2View.as_view(),
         name='message-detail'),
    path('contact/messages/<int:message_id>/read/',
         AdminContactMessageMarkReadView.as_view(),
         name='message-read'),
    path('contact/messages/<int:message_id>/reply/',
         AdminContactMessageReplyV2View.as_view(),
         name='message-reply'),
    path('contact/messages/<int:message_id>/replies/',
         AdminContactMessageReplyV2View.as_view(),
         name='message-replies'),
]
