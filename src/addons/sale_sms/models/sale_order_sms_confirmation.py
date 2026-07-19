"""Modelo ``SaleOrderSmsConfirmation`` — addon ``sale_sms``.

Adaptación de Odoo ``sale_sms``, que **no aporta modelos**: es un módulo de
datos + seguridad que envía un SMS de confirmación cuando se confirma una
``sale.order`` (usa una ``sms.template`` de confirmación disparada en
``action_confirm``). En Django, ese comportamiento se materializa como el
**bridge** ``sale`` + ``sms``: un modelo relacionado (DEC-SALE-01) que enlaza
cada orden con el ``SmsSms`` de confirmación emitido para ella.

Bridge ``sale`` + ``sms``: registra y dispara el SMS de confirmación de la orden.
"""
import fields
import models

from addons.sms.models import SmsSms
from addons.base.models import TimeStampedModel


class SaleOrderSmsConfirmation(TimeStampedModel):
    """Vincula una ``sale.order`` con su SMS de confirmación (Odoo sale_sms)."""

    order   = models.OneToOneField(
        'sale.SaleOrder', on_delete=models.CASCADE, related_name='sms_confirmation',
        help_text='Orden de venta (Odoo sale.order).',
    )
    message = fields.Many2one(
        'sms.SmsSms', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='sale_confirmations',
        help_text='SMS de confirmación emitido (Odoo sms.sms).',
    )

    class Meta:
        db_table = 'sale_order_sms_confirmation'
        verbose_name = 'Confirmación SMS de orden de venta'
        verbose_name_plural = 'Confirmaciones SMS de órdenes de venta'

    def __str__(self) -> str:
        return f'{self.order} ← {self.message or "sin SMS"}'

    @classmethod
    def send_for(cls, order, number, template):
        """Emite el SMS de confirmación de ``order`` renderizando ``template``.

        Replica el disparo de Odoo ``sale_sms`` al confirmar la orden: renderiza
        la ``sms.template`` con el contexto de la orden, crea el ``SmsSms``
        destinado a ``number`` y persiste el vínculo (idempotente por orden — un
        único registro de confirmación).
        """
        body = template.render({
            'order': order.name or '',
            'total': str(order.amount_total()),
        })
        message = SmsSms.objects.create(number=number, body=body)
        link, _created = cls.objects.update_or_create(
            order=order, defaults={'message': message},
        )
        return link
