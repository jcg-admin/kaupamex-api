"""SubscriptionInvoice — factura recurrente de una suscripción por período.

Parte de ``addons.sale_subscription`` — billing recurrente L0 (DEC-KX-05).
Layout ``models/`` (un archivo por modelo), espejo de odoo-tools.
"""

import fields
import models

from addons.account.services import create_invoice_from_subscription
from addons.base.models import TimeStampedModel
from addons.base.models import ResCompany
from addons.base.models.ir_rule import RuleScopedManager
from addons.sale_subscription.models.company_module_subscription import (
    CompanyModuleSubscription,
)
from addons.sale_subscription.models.subscription_billing_run import (
    SubscriptionBillingRun,
)


class SubscriptionInvoice(TimeStampedModel):
    """Factura recurrente de una suscripción por período (eje ``account`` L0).

    Documento de cobro **auditable** e **idempotente** por
    ``(subscription, period)`` (EX-04): reintentar una corrida no duplica la
    factura. El ``amount`` **congela** ``subscription.price`` — no referencia el
    tarifario en vivo (inmutabilidad histórica, H-API-01). El cobro reutiliza el
    eje ``payment`` del O2C (DEC-KX-07); esta factura sella el resultado en
    ``status``. Ver :ref:`diseno-motor-facturacion-recurrente-l0`.
    """

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Borrador'
        ISSUED = 'issued', 'Emitida'
        PAID = 'paid', 'Pagada'
        FAILED = 'failed', 'Cobro fallido'
        VOID = 'void', 'Anulada'

    company = fields.Many2one(
        ResCompany, on_delete=models.CASCADE, related_name='subscription_invoices',
        verbose_name='Empresa',
    )
    subscription = fields.Many2one(
        CompanyModuleSubscription, on_delete=models.PROTECT,
        related_name='invoices', verbose_name='Suscripción',
    )
    run = fields.Many2one(
        SubscriptionBillingRun, on_delete=models.PROTECT, related_name='invoices',
        verbose_name='Corrida',
    )
    period = fields.Char(max_length=7, verbose_name='Periodo')  # ``YYYY-MM``
    amount = fields.Monetary(
        max_digits=10, decimal_places=2, verbose_name='Monto',
    )
    currency = fields.Char(max_length=3, default='MXN', verbose_name='Moneda')
    status = fields.Selection(
        max_length=8, choices=Status.choices, default=Status.DRAFT,
        verbose_name='Estado',
    )
    issued_at = fields.Datetime(null=True, blank=True, verbose_name='Emitida en')
    paid_at = fields.Datetime(null=True, blank=True, verbose_name='Pagada en')
    failure_reason = fields.Char(
        max_length=255, blank=True, default='', verbose_name='Motivo de fallo',
    )
    # Asiento contable del cobro L0 en los libros de Kaupamex (H-API-05). FK
    # company→account (dirección correcta: account es la capa base). El enlace
    # hace idempotente post_to_ledger: no se duplica el asiento. related_name='+'
    # — sin accesor inverso (account limpio).
    account_move = fields.Many2one(
        'account.AccountMove', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
        verbose_name='Asiento contable',
    )

    objects = models.Manager()               # default: cross-company (L0)
    scoped = RuleScopedManager()             # L3: record rules (ir_rule)

    class Meta:
        db_table = 'subscription_invoice'
        verbose_name = 'Factura de suscripción'
        verbose_name_plural = 'Facturas de suscripción'
        ordering = ['-created_at']
        # Idempotencia (EX-04): una suscripción no se factura dos veces por el
        # mismo período. Reintentar la corrida es seguro.
        unique_together = [('subscription', 'period')]
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['run']),
        ]

    def __str__(self):
        return f'inv:{self.subscription_id}:{self.period}:{self.status}'

    def post_to_ledger(self):
        """Asienta el cobro L0 en los libros de Kaupamex (H-API-05).

        Emite (o devuelve) un ``account.move`` ``out_invoice`` de doble entrada
        en la **system company** (Kaupamex, el operador L0) — NO en los del
        tenant. Idempotente: si ya está asentada (``account_move`` fijado), la
        devuelve sin duplicar. Puente **explícito** — NO se dispara en la
        corrida de facturación (rompería flujos sin plan de cuentas L0).

        :raises UserError: si a la system company le faltan el diario/cuentas
            (delegado a ``account.services.create_invoice_from_subscription``).
        """
        if self.account_move_id is not None:
            return self.account_move
        system = ResCompany.get_system()
        move = create_invoice_from_subscription(self, system)
        move.post()
        self.account_move = move
        self.save(update_fields=['account_move', 'updated_at'])
        return move
