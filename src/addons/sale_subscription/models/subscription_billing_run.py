"""SubscriptionBillingRun — corrida periódica de facturación L0 (UC-PLT-18).

Parte de ``addons.sale_subscription`` — billing recurrente L0 (DEC-KX-05).
Layout ``models/`` (un archivo por modelo), espejo de odoo-tools.
"""

from decimal import Decimal

import fields
import models

from addons.base.models import TimeStampedModel


class SubscriptionBillingRun(TimeStampedModel):
    """Corrida periódica de facturación L0 (UC-PLT-18 / #180).

    La mitad *cash* del O2C re-domiciliado (DEC-KX-07): el Actor Tiempo (o el
    operador) dispara una corrida por período; ésta emite las
    ``SubscriptionInvoice`` de las suscripciones vencidas y cobra. Persiste el
    **resumen auditable** que el ``run_billing`` sin estado no tenía (H-API-01/
    H-API-02). Ver :ref:`diseno-motor-facturacion-recurrente-l0`.
    """

    class TriggeredBy(models.TextChoices):
        TIME = 'time', 'Planificador (Actor Tiempo)'
        OPERATOR = 'operator', 'Corrida manual del operador'

    period = fields.Char(max_length=7, verbose_name='Periodo')  # ``YYYY-MM``
    triggered_by = fields.Selection(
        max_length=8, choices=TriggeredBy.choices, default=TriggeredBy.TIME,
        verbose_name='Disparada por',
    )
    started_at = fields.Datetime(auto_now_add=True, verbose_name='Inicio')
    finished_at = fields.Datetime(
        null=True, blank=True, verbose_name='Fin',
    )
    invoices_issued = fields.Integer(default=0, verbose_name='Facturas emitidas')
    amount_charged = fields.Monetary(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Monto cobrado',
    )
    currency = fields.Char(max_length=3, default='MXN', verbose_name='Moneda')
    failures = fields.Integer(default=0, verbose_name='Cobros fallidos')

    class Meta:
        db_table = 'subscription_billing_run'
        verbose_name = 'Corrida de facturación'
        verbose_name_plural = 'Corridas de facturación'
        ordering = ['-started_at']
        indexes = [models.Index(fields=['period'])]

    def __str__(self):
        return f'run:{self.period}:{self.triggered_by}'
