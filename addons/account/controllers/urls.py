"""URLs — ``addons.account`` (registro de pago, UC-PAY-14).

Un solo verbo con ``pk`` (FBV) — ``path()`` directo, sin router. Ruta = la
confirmada de PARTE 7C de ``uc-pay-14-pago-parcial-abono`` (montada bajo
``api/v2/admin/finance/`` en ``config/urls.py``, mismo prefijo que los tres
wizards de H-API-406).
"""
from django.urls import path

from addons.account.controllers.views import register_payment

urlpatterns = [
    path('invoices/<int:pk>/register-payment/', register_payment,
         name='register-payment'),
]
