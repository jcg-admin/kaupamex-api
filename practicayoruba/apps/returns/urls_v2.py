"""URLs v2 — apps.returns buyer (F3 migrar-urls-rest-v2)."""
from django.urls import path
from .views import ReturnDetailView, ReturnListCreateView

app_name = 'returns_v2'

urlpatterns = [
    path('', ReturnListCreateView.as_view(), name='list-create'),
    path('<int:return_id>/', ReturnDetailView.as_view(), name='detail'),
]
