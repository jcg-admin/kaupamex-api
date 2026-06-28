"""
Rutas v1 de pagos que permanecen en /api/v1/payments/.

- webhooks/*: DEC-V2-02 — nunca migrar.
- initiate/: flujo legacy de redirección (InitiatePaymentView), reemplazado
  por CheckoutApiPaymentView en v2 pero mantenido hasta sunset de v1.
- admin/<id>/refund/: ruta duplicada vía payments/ prefix; migrar en M-11.
"""
from django.urls import path
from .views import InitiatePaymentView, AdminRefundView
from .webhooks import MercadoPagoWebhookView, PayPalWebhookView

urlpatterns = [
    path('webhooks/mercadopago/', MercadoPagoWebhookView.as_view(), name='webhook-mercadopago'),
    path('webhooks/paypal/',      PayPalWebhookView.as_view(),      name='webhook-paypal'),
    path('initiate/',             InitiatePaymentView.as_view(),    name='initiate'),
    path('admin/<int:payment_id>/refund/', AdminRefundView.as_view(), name='admin-refund'),
]
