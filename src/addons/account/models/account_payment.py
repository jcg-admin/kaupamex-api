"""``account.payment`` — pago (Odoo ``account``).

Portación fiel de ``account_payment.py`` (Odoo 18/19). Campos núcleo:
``amount``, ``payment_type`` (inbound/outbound), ``partner_type``
(customer/supplier), ``state`` (draft/in_process/paid/canceled/rejected),
``journal``, ``partner``, ``currency``, ``company``, ``memo``,
``is_reconciled``.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models


class AccountPayment(models.Model):
    """``account.payment`` — registro de un pago entrante o saliente."""

    PAYMENT_TYPES = [
        ('outbound', 'Enviar'),
        ('inbound', 'Recibir'),
    ]
    PARTNER_TYPES = [
        ('customer', 'Cliente'),
        ('supplier', 'Proveedor'),
    ]
    STATES = [
        ('draft', 'Borrador'),
        ('in_process', 'En proceso'),
        ('paid', 'Pagado'),
        ('canceled', 'Cancelado'),
        ('rejected', 'Rechazado'),
    ]

    amount        = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0.00'),
        help_text='Importe del pago (Odoo amount).',
    )
    payment_type  = models.CharField(
        max_length=8, choices=PAYMENT_TYPES, default='inbound',
        help_text='Tipo de pago (Odoo payment_type, requerido).',
    )
    partner_type  = models.CharField(
        max_length=8, choices=PARTNER_TYPES, default='customer',
        help_text='Tipo de contraparte (Odoo partner_type, requerido).',
    )
    state         = models.CharField(
        max_length=12, choices=STATES, default='draft',
        help_text='Estado del pago (Odoo state).',
    )
    journal       = models.ForeignKey(
        'account.AccountJournal', on_delete=models.PROTECT, related_name='payments',
        help_text='Diario (Odoo journal_id).',
    )
    partner       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='account_payments',
        help_text='Contacto (Odoo partner_id → party).',
    )
    currency      = models.ForeignKey(
        'base.ResCurrency', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='payments',
        help_text='Moneda (Odoo currency_id).',
    )
    company       = models.ForeignKey(
        'company.Company', on_delete=models.CASCADE, related_name='payments',
        help_text='Empresa (Odoo company_id).',
    )
    memo          = models.CharField(
        max_length=255, blank=True, default='',
        help_text='Concepto (Odoo memo).',
    )
    is_reconciled = models.BooleanField(
        default=False, help_text='Pago conciliado (Odoo is_reconciled).',
    )

    class Meta:
        db_table = 'account_payment'
        ordering = ['-id']
        verbose_name = 'Pago'
        verbose_name_plural = 'Pagos'

    def __str__(self) -> str:
        return f'{self.get_payment_type_display()} {self.amount} ({self.state})'
