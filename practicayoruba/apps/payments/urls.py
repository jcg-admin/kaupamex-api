"""URLs — apps.payments (Sprint 15)."""
from django.urls import path
from .views import (
    InitiatePaymentView, PaymentReturnView,
    InstallmentPlansView,
)

app_name = 'payments'

urlpatterns = [
    path('initiate/',
         InitiatePaymentView.as_view(), name='initiate'),
    path('installments/',
         InstallmentPlansView.as_view(), name='installments'),
    path('<str:order_number>/return/',
         PaymentReturnView.as_view(), name='return'),
]
