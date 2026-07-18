"""``account.journal`` — diario contable (Odoo ``account``).

Portación fiel de ``account_journal.py`` (Odoo 18/19, ``type`` idéntico:
sale/purchase/cash/bank/credit/general). Campos núcleo: ``name``, ``code``,
``type``, ``currency``, ``default_account``, ``company``, ``active``.
"""
from django.db import models


class AccountJournal(models.Model):
    """``account.journal`` — diario donde se registran los asientos."""

    JOURNAL_TYPES = [
        ('sale', 'Ventas'),
        ('purchase', 'Compras'),
        ('cash', 'Efectivo'),
        ('bank', 'Banco'),
        ('credit', 'Tarjeta de crédito'),
        ('general', 'Varios'),
    ]

    name            = models.CharField(
        max_length=255, help_text='Nombre del diario (Odoo name, requerido).',
    )
    code            = models.CharField(
        max_length=12, help_text='Código corto del diario (Odoo code).',
    )
    type            = models.CharField(
        max_length=12, choices=JOURNAL_TYPES,
        help_text='Tipo de diario (Odoo type, requerido).',
    )
    currency        = models.ForeignKey(
        'base.ResCurrency', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='journals',
        help_text='Moneda del diario (Odoo currency_id).',
    )
    default_account = models.ForeignKey(
        'account.AccountAccount', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='default_for_journals',
        help_text='Cuenta por defecto (Odoo default_account_id).',
    )
    company         = models.ForeignKey(
        'company.Company', on_delete=models.CASCADE, related_name='journals',
        help_text='Empresa (Odoo company_id).',
    )
    active          = models.BooleanField(
        default=True, help_text='Diario activo (Odoo active).',
    )

    class Meta:
        db_table = 'account_journal'
        ordering = ['code']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'code'], name='unique_journal_code_company',
            ),
        ]
        verbose_name = 'Diario contable'
        verbose_name_plural = 'Diarios contables'

    def __str__(self) -> str:
        return f'{self.code} — {self.name}'
