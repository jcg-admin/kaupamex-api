"""URLs de la superficie de pago del comprador — ``payment``.

Montado en ``config/urls.py``::

    path('api/v2/payments/', include(('addons.payment.controllers.urls',
         'payments'), namespace='payments_v2'))

Los webhooks del proveedor entran por su propio módulo: son otro actor
(el gateway, no el comprador) y otra autorización (firma, no sesión).
"""
from django.urls import path

from addons.payment.controllers.portal import (
    initiate_payment,
    payment_history,
    payment_status,
)

app_name = 'payments'

urlpatterns = [
    path('initiate/', initiate_payment, name='payment-initiate'),
    path('<str:order_number>/status/', payment_status, name='payment-status'),
    path('<str:order_number>/history/', payment_history,
         name='payment-history'),
]
