from django.urls import path
from .views import SiteSettingsView

app_name = 'settings_app'

urlpatterns = [
    path('settings/', SiteSettingsView.as_view(), name='site-settings'),
]
