from django.urls import path
from .views import (
    AdminContactMessageListView,
    AdminContactMessageDetailView,
    AdminContactMessageMarkReadView,
    AdminContactMessageReplyView,
)

app_name = 'admin_contact_v2'

urlpatterns = [
    path('contact/messages/',
         AdminContactMessageListView.as_view(),
         name='admin-list'),
    path('contact/messages/<int:message_id>/read/',
         AdminContactMessageMarkReadView.as_view(),
         name='admin-mark-read'),
    path('contact/messages/<int:message_id>/reply/',
         AdminContactMessageReplyView.as_view(),
         name='admin-reply'),
    path('contact/messages/<int:message_id>/replies/',
         AdminContactMessageReplyView.as_view(),
         name='admin-replies'),
    path('contact/messages/<int:message_id>/',
         AdminContactMessageDetailView.as_view(),
         name='admin-detail'),
]
