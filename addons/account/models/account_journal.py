"""``account.journal`` — diario contable (Odoo ``account``).

Portación fiel de ``account_journal.py`` (Odoo 18/19, ``type`` idéntico:
sale/purchase/cash/bank/credit/general). Campos núcleo: ``name``, ``code``,
``type``, ``currency``, ``default_account``, ``company``, ``active``.
"""
import fields
import models


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

    name            = fields.Char(
        max_length=255, help_text='Nombre del diario (Odoo name, requerido).',
    )
    code            = fields.Char(
        max_length=12, help_text='Código corto del diario (Odoo code).',
    )
    type            = fields.Selection(
        max_length=12, choices=JOURNAL_TYPES,
        help_text='Tipo de diario (Odoo type, requerido).',
    )
    currency        = fields.Many2one(
        'base.ResCurrency', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='journals',
        help_text='Moneda del diario (Odoo currency_id).',
    )
    default_account = fields.Many2one(
        'account.AccountAccount', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='default_for_journals',
        help_text='Cuenta por defecto (Odoo default_account_id).',
    )
    company         = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE, related_name='journals',
        help_text='Empresa (Odoo company_id).',
    )
    active          = fields.Boolean(
        default=True, help_text='Diario activo (Odoo active).',
    )
    sequence        = fields.Integer(
        default=10, help_text='Orden del diario (Odoo sequence).',
    )
    # ``show_on_dashboard`` y ``color`` los declara la referencia en
    # ``account_journal_dashboard.py:30-31``, un ``_inherit`` del **mismo**
    # addon. Se portan aquí —misma clase, mismo addon— porque el archivo
    # aparte de allá es una separación de lectura, no de modelo; el resto de
    # ese archivo (la agregación del tablero) queda pendiente, sucesor #158.
    show_on_dashboard = fields.Boolean(
        default=True, help_text='Mostrar en el tablero (Odoo show_on_dashboard).',
    )
    color           = fields.Integer(
        default=0, help_text='Índice de color (Odoo color).',
    )

    class Meta:
        db_table = 'account_journal'
        # ≙ ``_order = 'sequence, type, code'`` (odoo19c: account_journal.py:45).
        ordering = ['sequence', 'type', 'code']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'code'], name='unique_journal_code_company',
            ),
        ]
        verbose_name = 'Diario contable'
        verbose_name_plural = 'Diarios contables'

    def __str__(self) -> str:
        return f'{self.code} — {self.name}'
