"""URLs — addon ``bus`` (lectura de la cola por consulta, DEC-AF-06)."""
from django.urls import path

from .views import bus_poll

app_name = 'bus_v2'

urlpatterns = [
    path('poll/', bus_poll, name='poll'),
]
