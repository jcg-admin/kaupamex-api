from django.urls import path
from .views import ReturnListCreateView, ReturnDetailView

app_name = 'returns_v2'

urlpatterns = [
    path('',                      ReturnListCreateView.as_view(), name='list-create'),
    path('<int:return_id>/',       ReturnDetailView.as_view(),     name='detail'),
]
