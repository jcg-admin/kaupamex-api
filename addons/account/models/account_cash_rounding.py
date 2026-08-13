"""``account.cash.rounding`` — Adaptación de Odoo addons/account/models/account_cash_rounding.py
(odoo-tools@622ddc2a, odoo19c:).

Redondeo de efectivo: en países donde la moneda menor circulante ya no existe
(p. ej. Suiza, 0.05 CHF), la factura se redondea a esa unidad. Dos estrategias
fieles a la referencia: ``biggest_tax`` (ajustar el monto del impuesto) o
``add_invoice_line`` (agregar línea de ajuste). Campos núcleo: ``name``,
``rounding``, ``strategy``, ``profit_account``/``loss_account``,
``rounding_method`` (UP/DOWN/HALF-UP).

``profit_account_id``/``loss_account_id`` en la referencia son
``company_dependent`` (Property fields) — se portan como FK simples (mismo
criterio de simplificación que ``account_account.py`` para relaciones
cross-company; no hay infraestructura de property fields en este ORM).
"""
from decimal import ROUND_DOWN, ROUND_HALF_UP, ROUND_UP, Decimal

import fields
import models
from exceptions import ValidationError
from tools.translate import _

_ROUNDING_METHOD_TO_DECIMAL = {
    'UP': ROUND_UP,
    'DOWN': ROUND_DOWN,
    'HALF-UP': ROUND_HALF_UP,
}


class AccountCashRounding(models.Model):
    """``account.cash.rounding`` — perfil de redondeo de efectivo por factura."""

    STRATEGY_BIGGEST_TAX = 'biggest_tax'
    STRATEGY_ADD_INVOICE_LINE = 'add_invoice_line'
    STRATEGIES = [
        (STRATEGY_BIGGEST_TAX, 'Modificar monto de impuesto'),
        (STRATEGY_ADD_INVOICE_LINE, 'Agregar línea de redondeo'),
    ]
    METHOD_UP = 'UP'
    METHOD_DOWN = 'DOWN'
    METHOD_HALF_UP = 'HALF-UP'
    ROUNDING_METHODS = [
        (METHOD_UP, 'Arriba'),
        (METHOD_DOWN, 'Abajo'),
        (METHOD_HALF_UP, 'Más cercano'),
    ]

    name = fields.Char(
        max_length=255,
        help_text='Nombre del perfil de redondeo (Odoo name, requerido).',
    )
    rounding = fields.Monetary(
        max_digits=16, decimal_places=2, default=Decimal('0.01'),
        help_text='Menor moneda circulante distinta de cero (Odoo rounding, '
                  'ej. 0.05).',
    )
    strategy = fields.Selection(
        max_length=16, choices=STRATEGIES, default=STRATEGY_ADD_INVOICE_LINE,
        help_text='Estrategia de redondeo (Odoo strategy).',
    )
    profit_account = fields.Many2one(
        'account.AccountAccount', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cash_rounding_profit_profiles',
        help_text='Cuenta para la ganancia por redondeo (Odoo profit_account_id, '
                  'company_dependent en la referencia).',
    )
    loss_account = fields.Many2one(
        'account.AccountAccount', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cash_rounding_loss_profiles',
        help_text='Cuenta para la pérdida por redondeo (Odoo loss_account_id, '
                  'company_dependent en la referencia).',
    )
    rounding_method = fields.Selection(
        max_length=8, choices=ROUNDING_METHODS, default=METHOD_HALF_UP,
        help_text='Regla de desempate del redondeo (Odoo rounding_method).',
    )

    class Meta:
        db_table = 'account_cash_rounding'
        ordering = ['name']
        verbose_name = 'Redondeo de efectivo'
        verbose_name_plural = 'Redondeos de efectivo'

    def __str__(self) -> str:
        return self.name

    def clean(self):
        # Odoo @api.constrains('rounding') validate_rounding.
        if self.rounding is not None and self.rounding <= 0:
            raise ValidationError(
                _('Establece un valor de redondeo estrictamente positivo.'))

    def round(self, amount):
        """Redondea ``amount`` a la precisión ``rounding`` (Odoo ``round``)."""
        if not self.rounding:
            return amount
        amount = amount if isinstance(amount, Decimal) else Decimal(str(amount))
        rounding = Decimal(str(self.rounding))
        quantized = (amount / rounding).to_integral_value(
            rounding=_ROUNDING_METHOD_TO_DECIMAL[self.rounding_method])
        return quantized * rounding

    def compute_difference(self, amount):
        """Diferencia entre ``amount`` y su redondeo (Odoo ``compute_difference``).

        Ej. ``amount=23.91``, redondeado ``24.00`` → resultado ``0.09``.
        """
        amount = amount if isinstance(amount, Decimal) else Decimal(str(amount))
        return self.round(amount) - amount
