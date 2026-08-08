"""Procesamiento común de notificaciones de pago — framework ``payment``.

Lógica compartida post-aprobación que en Odoo vive en el framework
(``payment.transaction._handle_notification_data``): actualizar ``Payment`` y
``Order`` cuando un provider notifica un pago aprobado. Los controladores de
webhook de cada provider (``payment_mercado_pago``/``payment_paypal``) la
consumen; no pertenece a ningún provider concreto.
"""
import logging
from decimal import Decimal

from django.db import transaction

from addons.payment.models import Payment


logger = logging.getLogger('apps')


def _process_payment_approval(
    gateway_payment_id: str, gateway: str, amount: Decimal | None = None
) -> tuple[Payment | None, bool]:
    """
    Actualiza Payment y Order cuando el pago es aprobado.
    Idempotente: si el Payment ya es APPROVED, no cambia nada.
    FR-PAY-03.02, FR-PAY-04.01 (H-PAY-005).

    Retorna (payment, newly_approved) donde:
      - payment: instancia Payment o None si no se encontro.
      - newly_approved: True si la transicion ocurrio en esta llamada,
        False si el Payment ya estaba APPROVED (llamada idempotente).

    H-CICLO87-02: antes la funcion retornaba ``payment`` en ambos casos
    (nueva aprobacion e idempotente). Los callers creaban siempre un
    PaymentGatewayEvent EVENT_PAYMENT_APPROVED sin distinguir si el pago
    realmente se aprobo en esta llamada. Con webhooks con diferentes
    X-Request-ID (reintentos normales del gateway), cada reintento
    insertaba un EVENT_PAYMENT_APPROVED adicional en auditoria.
    """

    with transaction.atomic():
        payment = (
            Payment.objects
            .select_for_update()
            .select_related('sale_order')
            .filter(gateway_payment_id=gateway_payment_id, gateway=gateway)
            .first()
        )
        if not payment:
            logger.warning(
                'Webhook %s: no se encontró Payment con gateway_payment_id=%s',
                gateway, gateway_payment_id,
            )
            return None, False

        if payment.status == Payment.STATUS_APPROVED:
            logger.info('Webhook %s: pago %s ya estaba APPROVED — idempotente', gateway, gateway_payment_id)
            return payment, False

        payment.status = Payment.STATUS_APPROVED
        if amount:
            payment.amount = amount
        payment.save(update_fields=['status', 'amount', 'updated_at'])

        # DEC-BC-12 / O2C R8: el Payment APPROVED de arriba ES el eje de
        # pago — la proyección canónica deriva PAID de él; la columna espejo
        # ya no se escribe (V5d la retira).
        logger.info(
            'Orden %s → PAID (proyectado) tras pago aprobado (%s)',
            payment.sale_order.name, gateway,
        )

    return payment, True

