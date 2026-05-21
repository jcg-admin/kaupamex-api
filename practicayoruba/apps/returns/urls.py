"""URLs — apps.returns (comprador, /api/v1/returns/)."""
from django.urls import path
from .views import ReturnDetailView, ReturnListCreateView


app_name = 'returns'

urlpatterns = [
    path('', ReturnListCreateView.as_view(), name='list-create'),
    path('<int:return_id>/', ReturnDetailView.as_view(), name='detail'),
]
