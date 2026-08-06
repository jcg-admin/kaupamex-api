"""``account.bank.statement`` — Adaptación de Odoo addons/account/models/account_bank_statement.py
(odoo-tools@622ddc2a, odoo19c:).

Estado de cuenta bancario: agrupa líneas (``account.bank.statement.line``,
``line_ids``) entre un saldo inicial y uno final. Campos núcleo: ``name``,
``reference``, ``date``, ``first_line_index``, ``balance_start``,
``balance_end`` (calculado), ``balance_end_real`` (declarado), ``company``,
``currency``, ``journal``, ``is_complete``, ``is_valid``,
``problem_description``.

**Simplificaciones documentadas (Clausula 2, principio rector):** la
referencia calcula ``is_valid``/``_get_invalid_statement_ids`` con una query
SQL de ventana (``LAG`` sobre ``first_line_index``) que compara contra el
estado íntegro de TODOS los diarios en una sola pasada — optimización de
lote, no de forma. Aquí ``is_valid()`` se recalcula por-instancia con el
mismo criterio (comparar contra el ``balance_end_real`` del estado anterior
del mismo diario); la forma observable es idéntica, la implementación es
por-fila en vez de por-lote (fuera de alcance de esta pasada portar el SQL
crudo con ventana). ``first_line_index`` en la referencia combina fecha +
secuencia + id de la línea para ordenar sin colisión; aquí se deriva del
``pk`` de la primera línea posteada (string zero-padded) porque
``account.bank.statement.line.internal_index`` no se porta en esta pasada
(ver docstring de ``account_bank_statement_line.py``).
"""
from decimal import Decimal

import models
import fields


class AccountBankStatement(models.Model):
    """``account.bank.statement`` — estado de cuenta bancario."""

    name = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Referencia del estado de cuenta (Odoo name, computado de '
                  'diario+fecha si no se declara).',
    )
    reference = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Referencia externa: nombre del archivo importado o de la '
                  'sincronización en línea (Odoo reference).',
    )
    date = fields.Date(
        null=True, blank=True,
        help_text='Fecha de la última línea posteada (Odoo date, computado).',
    )
    first_line_index = fields.Char(
        max_length=64, blank=True, default='',
        help_text='Índice de ordenamiento de la primera línea posteada (Odoo '
                  'first_line_index, computado — ver simplificación en el '
                  'docstring del módulo).',
    )
    balance_start = fields.Monetary(
        max_digits=16, decimal_places=2, default=Decimal('0.00'),
        help_text='Saldo inicial (Odoo balance_start).',
    )
    balance_end = fields.Monetary(
        max_digits=16, decimal_places=2, default=Decimal('0.00'),
        help_text='Saldo final calculado: balance_start + líneas posteadas '
                  '(Odoo balance_end, computado).',
    )
    balance_end_real = fields.Monetary(
        max_digits=16, decimal_places=2, default=Decimal('0.00'),
        help_text='Saldo final declarado por el banco (Odoo balance_end_real).',
    )
    company = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE, related_name='bank_statements',
        help_text='Empresa (Odoo company_id, related de journal_id.company_id).',
    )
    currency = fields.Many2one(
        'base.ResCurrency', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='bank_statements',
        help_text='Moneda (Odoo currency_id, computado de journal/company).',
    )
    journal = fields.Many2one(
        'account.AccountJournal', on_delete=models.CASCADE,
        related_name='bank_statements',
        help_text='Diario bancario (Odoo journal_id, computado de las líneas).',
    )
    is_complete = fields.Boolean(
        default=False,
        help_text='balance_end == balance_end_real, con líneas posteadas '
                  '(Odoo is_complete, computado).',
    )
    is_valid = fields.Boolean(
        default=True,
        help_text='balance_start coincide con el balance_end_real del estado '
                  'anterior del mismo diario (Odoo is_valid, computado).',
    )
    problem_description = fields.Text(
        blank=True, default='',
        help_text='Descripción del problema si no es completo o válido (Odoo '
                  'problem_description, computado).',
    )

    class Meta:
        db_table = 'account_bank_statement'
        ordering = ['-first_line_index']
        verbose_name = 'Estado de cuenta bancario'
        verbose_name_plural = 'Estados de cuenta bancarios'
        indexes = [
            models.Index(
                fields=['journal', 'date', '-id'],
                name='acc_bank_stmt_journal_date_idx',
            ),
        ]

    def __str__(self) -> str:
        return self.name or f'Estado de cuenta #{self.pk}'

    def recompute(self):
        """Recalcula ``balance_end``/``is_complete``/``problem_description`` y
        rellena ``name`` si está vacío (Odoo ``_compute_balance_end`` +
        ``_compute_is_complete`` + ``_compute_name``, colapsados: sin
        compute-engine, se invoca explícitamente tras modificar ``line_ids``)."""
        lines = self.line_ids.all()
        posted = [line for line in lines if line.move.state == 'posted']
        total = sum((line.amount for line in posted), Decimal('0.00'))
        self.balance_end = (self.balance_start or Decimal('0.00')) + total

        if not self.name:
            prefix = f'{self.journal.code} ' if self.journal_id else ''
            self.name = f'{prefix}Estado {self.date}' if self.date else \
                f'{prefix}Estado #{self.pk or "?"}'

        self.is_complete = bool(posted) and self.balance_end == self.balance_end_real
        self.is_valid = self._compute_is_valid()

        if not self.is_valid:
            self.problem_description = (
                'El saldo inicial no coincide con el saldo final del estado '
                'anterior, o falta un estado previo.')
        elif not self.is_complete:
            self.problem_description = (
                f'El saldo calculado ({self.balance_end}) no coincide con el '
                'saldo final declarado.')
        else:
            self.problem_description = ''

    def _compute_is_valid(self):
        """Odoo ``_get_statement_validity``: compara ``balance_start`` contra
        el ``balance_end_real`` del estado anterior del mismo diario."""
        if not self.journal_id:
            return True
        previous = (AccountBankStatement.objects
                    .filter(journal=self.journal)
                    .exclude(pk=self.pk)
                    .filter(first_line_index__lt=self.first_line_index or '')
                    .order_by('-first_line_index')
                    .first())
        if not previous:
            return True
        return self.balance_start == previous.balance_end_real
