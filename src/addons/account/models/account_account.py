"""``account.account`` — plan de cuentas (Odoo ``account``).

Portación fiel de ``account_account.py`` (Odoo 18/19). Campos persistidos
núcleo: ``code``, ``name``, ``account_type`` (Selection), ``reconcile``,
``deprecated``, ``currency``, ``note``. ``internal_group`` deriva de
``account_type`` (Odoo ``_compute_internal_group``) → se computa en ``save()``.

Cross-app (DEC-SALE-01): ``currency`` → ``base.ResCurrency``; ``company`` →
``company.Company`` (Odoo ``res.company``).

Hallazgo H-ACC-01 (drift 18→19): el enum ``account_type`` de 19 añade
``expense_other`` respecto de 18. Se adopta el **superset de 19** (nada
fabricado; ambos valores existen en 19). Ver audit.
"""
import api
from django.db import models


class AccountAccount(models.Model):
    """``account.account`` — cuenta contable del plan (Odoo base contable)."""

    # account_type — superset de Odoo 19 (18 + expense_other). H-ACC-01.
    ACCOUNT_TYPES = [
        ('asset_receivable', 'Por cobrar'),
        ('asset_cash', 'Banco y efectivo'),
        ('asset_current', 'Activo circulante'),
        ('asset_non_current', 'Activo no circulante'),
        ('asset_prepayments', 'Pagos anticipados'),
        ('asset_fixed', 'Activo fijo'),
        ('liability_payable', 'Por pagar'),
        ('liability_credit_card', 'Tarjeta de crédito'),
        ('liability_current', 'Pasivo circulante'),
        ('liability_non_current', 'Pasivo no circulante'),
        ('equity', 'Capital'),
        ('equity_unaffected', 'Resultado del ejercicio'),
        ('income', 'Ingreso'),
        ('income_other', 'Otros ingresos'),
        ('expense', 'Gasto'),
        ('expense_depreciation', 'Depreciación'),
        ('expense_direct_cost', 'Costo de ventas'),
        ('expense_other', 'Otros gastos'),
        ('off_balance', 'Fuera de balance'),
    ]

    # internal_group — Odoo _compute_internal_group: prefijo del account_type.
    INTERNAL_GROUPS = [
        ('equity', 'Capital'),
        ('asset', 'Activo'),
        ('liability', 'Pasivo'),
        ('income', 'Ingreso'),
        ('expense', 'Gasto'),
        ('off', 'Fuera de balance'),
    ]

    code           = models.CharField(
        max_length=64, help_text='Código de cuenta (Odoo account.account.code).',
    )
    name           = models.CharField(
        max_length=255, help_text='Nombre de la cuenta (Odoo name, requerido).',
    )
    account_type   = models.CharField(
        max_length=32, choices=ACCOUNT_TYPES,
        help_text='Tipo de cuenta (Odoo account_type, requerido).',
    )
    internal_group = models.CharField(
        max_length=16, choices=INTERNAL_GROUPS, blank=True, default='',
        help_text='Grupo interno derivado de account_type (Odoo internal_group).',
    )
    reconcile      = models.BooleanField(
        default=False,
        help_text='Permite conciliación (Odoo reconcile).',
    )
    deprecated     = models.BooleanField(
        default=False, help_text='Cuenta obsoleta (Odoo deprecated).',
    )
    currency       = models.ForeignKey(
        'base.ResCurrency', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='accounts',
        help_text='Moneda de la cuenta (Odoo currency_id).',
    )
    company        = models.ForeignKey(
        'company.Company', on_delete=models.CASCADE, related_name='accounts',
        help_text='Empresa (Odoo company_id / company_ids).',
    )
    note           = models.TextField(
        blank=True, default='', help_text='Notas internas (Odoo note).',
    )

    class Meta:
        db_table = 'account_account'
        ordering = ['code']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'code'], name='unique_account_code_company',
            ),
        ]
        verbose_name = 'Cuenta contable'
        verbose_name_plural = 'Cuentas contables'

    def __str__(self) -> str:
        return f'{self.code} {self.name}'

    @api.depends('account_type')
    def _compute_internal_group(self):
        # Odoo _compute_internal_group: el grupo es el prefijo del account_type
        # ('asset_receivable' -> 'asset'; 'off_balance' -> 'off').
        at = self.account_type or ''
        self.internal_group = at.split('_')[0] if at else ''

    def save(self, *args, **kwargs):
        self._compute_internal_group()
        return super().save(*args, **kwargs)
