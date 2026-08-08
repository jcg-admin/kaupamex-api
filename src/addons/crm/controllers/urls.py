"""URLs públicas — contacto (``crm``).

Montado en ``config/urls.py``:
  path('api/v2/contact/', include(('addons.crm.controllers.urls', 'contact'),
       namespace='contact_v2'))
"""
from django.urls import path

from addons.crm.controllers.main import ContactMessageCreateView

app_name = 'contact_v2'

urlpatterns = [
    path('messages/', ContactMessageCreateView.as_view(), name='create'),
]
