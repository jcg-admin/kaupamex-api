"""Admin URLs — apps.contact (UC-COM-02..03)."""
from django.urls import path
from .views import AdminContactMessageDetailView, AdminContactMessageListView, AdminContactMessageMarkReadView, AdminContactMessageReplyView


app_name = 'admin_contact'

urlpatterns = [
    path('contact/messages/',
         AdminContactMessageListView.as_view(),
         name='admin-list'),
    path('contact/messages/<int:message_id>/',
         AdminContactMessageDetailView.as_view(),
         name='admin-detail'),
    path('contact/messages/<int:message_id>/read/',
         AdminContactMessageMarkReadView.as_view(),
         name='admin-mark-read'),
    path('contact/messages/<int:message_id>/reply/',
         AdminContactMessageReplyView.as_view(),
         name='admin-reply'),
]
