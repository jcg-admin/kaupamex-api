from django.urls import path
from .views import ContactMessageCreateView

app_name = 'contact_v2'

urlpatterns = [
    path('messages/',
         ContactMessageCreateView.as_view(),
         name='create'),
]
