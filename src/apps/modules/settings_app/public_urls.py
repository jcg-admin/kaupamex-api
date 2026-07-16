from django.urls import path
from .views import ShippingMethodListPublicView

app_name = 'public_shipping'

urlpatterns = [
    path('', ShippingMethodListPublicView.as_view(), name='list'),
]
