"""``account.bank.statement.line`` — Adaptación de Odoo addons/account/models/account_bank_statement_line.py
(odoo-tools@622ddc2a, odoo19c:).

Línea de movimiento bancario: la referencia la declara ``_inherits =
{'account.move': 'move_id'}`` — cada línea ES un asiento contable
(``account.move``), con campos propios de importación bancaria encima.

Se porta con el patrón ya establecido en este árbol para ``_inherits``: **FK
real + delegación por propiedad** (NO herencia multi-tabla de Django), mismo
criterio que ``mail_mail.py`` → ``mail.message`` (ver su docstring). Los
campos ``journal``/``company``/``currency``/``date``/``state`` de la
referencia son ``related='move_id.X', store=True`` — aquí se delegan por
propiedad de solo-lectura sin denormalizar (mismo trade-off que
``mail_mail.subject``); para cambiarlos se toca ``linea.move.journal`` etc.

**Simplificación documentada (Clausula 2):** ``internal_index`` (referencia
usa fecha+secuencia+id combinados para ordenar sin colisión, evitando window
functions repetidas) y ``running_balance`` (recorrido con anclaje al estado
anterior + SQL crudo) no se portan en esta pasada — requieren la
infraestructura de ordenamiento fino que ``account.bank.statement`` también
simplifica (ver su docstring). Se porta el núcleo transaccional: monto,
referencia de pago, conciliación (bandera), vínculo a estado de cuenta.
"""
from decimal import Decimal

import fields
import models


class AccountBankStatementLine(models.Model):
    """``account.bank.statement.line`` — línea de movimiento bancario."""

    # Enlace _inherits (Odoo move_id, account_bank_statement_line.py:25-30) —
    # Many2one required + cascade, NO herencia multi-tabla (ver docstring).
    move = fields.Many2one(
        'account.AccountMove', on_delete=models.CASCADE,
        related_name='bank_statement_line',
        help_text='Asiento contable del que esta línea es la extensión '
                  'bancaria (Odoo move_id, _inherits). journal/company/'
                  'currency/date/state se delegan a él.',
    )
    statement = fields.Many2one(
        'account.AccountBankStatement', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='line_ids',
        help_text='Estado de cuenta al que pertenece, si ya fue agrupada '
                  '(Odoo statement_id).',
    )
    sequence = fields.Integer(
        default=1, help_text='Orden dentro del estado de cuenta (Odoo sequence).',
    )
    partner = fields.Many2one(
        'base.ResPartner', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='bank_statement_lines',
        help_text='Tercero de la transacción (Odoo partner_id).',
    )
    account_number = fields.Char(
        max_length=64, blank=True, default='',
        help_text='Número de cuenta bancaria del tercero, previo a su '
                  'creación como registro (Odoo account_number).',
    )
    partner_name = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Nombre del tercero tal como llega en el formato '
                  'electrónico importado, cuando no se puede resolver a un '
                  'partner (Odoo partner_name).',
    )
    transaction_type = fields.Char(
        max_length=64, blank=True, default='',
        help_text='Tipo de transacción, si el formato importado lo declara '
                  '(Odoo transaction_type).',
    )
    payment_ref = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Etiqueta/descripción de la transacción (Odoo payment_ref).',
    )
    amount = fields.Monetary(
        max_digits=16, decimal_places=2, default=Decimal('0.00'),
        help_text='Monto de la transacción, en la moneda del diario (Odoo '
                  'amount).',
    )
    foreign_currency = fields.Many2one(
        'base.ResCurrency', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='bank_statement_lines_foreign',
        help_text='Moneda distinta a la del diario, si la transacción es '
                  'multi-moneda (Odoo foreign_currency_id).',
    )
    amount_currency = fields.Monetary(
        max_digits=16, decimal_places=2, null=True, blank=True,
        help_text='Monto expresado en foreign_currency (Odoo amount_currency).',
    )
    is_reconciled = fields.Boolean(
        default=False,
        help_text='La línea ya fue conciliada contra sus apuntes (Odoo '
                  'is_reconciled, computado — aquí bandera explícita que '
                  'fija el flujo de conciliación).',
    )

    class Meta:
        db_table = 'account_bank_statement_line'
        ordering = ['-id']
        verbose_name = 'Línea de estado de cuenta bancario'
        verbose_name_plural = 'Líneas de estado de cuenta bancario'
        indexes = [
            models.Index(
                fields=['statement', 'sequence'],
                name='acc_bank_stmt_line_seq_idx',
            ),
        ]

    def __str__(self) -> str:
        return self.payment_ref or f'Línea bancaria #{self.pk}'

    # ---- Campos delegados (≙ _inherits de account.move) ----
    # Solo lectura, como el resto de delegaciones del árbol (mail_mail,
    # product_product, res_users). Para escribirlos se toca linea.move.X.

    @property
    def journal(self):
        """Diario del asiento (delegado por ``_inherits``)."""
        return self.move.journal

    @property
    def company(self):
        """Empresa del asiento (delegado por ``_inherits``)."""
        return self.move.company

    @property
    def currency(self):
        """Moneda del diario o de la empresa (Odoo ``_compute_currency_id``:
        ``journal.currency_id or company.currency_id``)."""
        return self.move.journal.currency or self.move.company.currency

    @property
    def date(self):
        """Fecha contable del asiento (delegado por ``_inherits``)."""
        return self.move.date

    @property
    def state(self):
        """Estado del asiento — draft/posted/cancel (delegado por
        ``_inherits``)."""
        return self.move.state
