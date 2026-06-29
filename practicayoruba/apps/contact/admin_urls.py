"""Admin URLs — apps.contact (UC-COM-02..03, F8 consolidation)."""
from django.urls import path
from .views import (
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
]
