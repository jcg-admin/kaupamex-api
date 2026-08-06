"""``account.bank.statement`` — Adaptación de Odoo addons/account/models/account_bank_statement.py
(odoo-tools@622ddc2a, odoo19c:).

Estado de cuenta bancario: agrupa líneas (``account.bank.statement.line``,
``line_ids``) entre un saldo inicial y uno final. Campos núcleo: ``name``,
``reference``, ``date``, ``first_line_index``, ``balance_start``,
``balance_end`` (calculado), ``balance_end_real`` (declarado), ``company``,
``currency``, ``journal``, ``is_complete``, ``is_valid``,
``problem_description``.

**Corregido (H-API-321).** Un pase anterior llamaba "simplificación" a NO
portar el SQL de ventana de ``is_valid``/``_get_invalid_statement_ids`` ni a
computar ``first_line_index`` desde ``internal_index`` real de las líneas —
el motor (PostgreSQL) no era el límite; la omisión era de alcance. Ambos se
portan ahora:

- ``first_line_index`` (``_compute_first_line_index``,
  ``odoo19c: account_bank_statement.py:126-131``): el ``internal_index`` más
  chico entre las líneas del estado que ya lo tienen calculado (cualquier
  estado del asiento, no sólo posteadas — igual que la referencia). Depende
  de que ``account.bank.statement.line.internal_index`` esté portado (lo
  está, ver ``account_bank_statement_line.py``).
- ``is_valid``/``_get_invalid_statement_ids``
  (``odoo19c: account_bank_statement.py:196-207,242-275``): el camino
  ``_compute_is_valid`` de UN solo estado (``len(self) == 1`` en la
  referencia) usa comparación directa contra el estado anterior — sin SQL
  de ventana, porque la propia referencia tampoco lo usa ahí — y es lo que
  implementa ``_compute_is_valid()`` de abajo. El camino de **búsqueda/lote**
  (``_search_is_valid``) sí usa la ventana (``LAG(balance_end_real) OVER
  (PARTITION BY journal_id ORDER BY first_line_index)``); se porta tal cual
  vía SQL crudo en ``_get_invalid_statement_ids``/``search_is_valid``.
"""
from decimal import Decimal

from django.db import connection

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
        help_text='internal_index más chico entre las líneas del estado '
                  '(Odoo first_line_index, computado — '
                  '_compute_first_line_index, ver docstring del módulo).',
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
            # Odoo `_first_line_index_idx`
            # (odoo19c: account_bank_statement.py:112) — soporta las queries
            # de `_compute_is_valid`/`_get_invalid_statement_ids` (filtran y
            # ordenan por `journal_id, first_line_index`).
            models.Index(
                fields=['journal', 'first_line_index'],
                name='acc_bank_stmt_first_line_idx',
            ),
        ]

    def __str__(self) -> str:
        return self.name or f'Estado de cuenta #{self.pk}'

    def recompute(self):
        """Recalcula ``balance_end``/``first_line_index``/``is_complete``/
        ``problem_description`` y rellena ``name`` si está vacío (Odoo
        ``_compute_balance_end`` + ``_compute_first_line_index`` +
        ``_compute_is_complete`` + ``_compute_name``, colapsados: sin
        compute-engine, se invoca explícitamente tras modificar ``line_ids``)."""
        lines = self.line_ids.all()
        posted = [line for line in lines if line.move.state == 'posted']
        total = sum((line.amount for line in posted), Decimal('0.00'))
        self.balance_end = (self.balance_start or Decimal('0.00')) + total

        self._compute_first_line_index()

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

    def _compute_first_line_index(self):
        """Odoo ``_compute_first_line_index``
        (``odoo19c: account_bank_statement.py:126-131``): el
        ``internal_index`` más chico entre las líneas del estado que ya lo
        tienen calculado — cualquier estado del asiento, no sólo posteadas,
        igual que la referencia (que sólo filtra por ``internal_index``
        truthy, no por ``state``)."""
        first = (self.line_ids
                 .exclude(internal_index='')
                 .order_by('internal_index')
                 .values_list('internal_index', flat=True)
                 .first())
        self.first_line_index = first or ''

    # -------------------------------------------------------------------
    # BUSQUEDA/LOTE — SQL de ventana (Odoo _get_invalid_statement_ids)
    # -------------------------------------------------------------------

    @classmethod
    def _get_invalid_statement_ids(cls, journal_ids=None, ids=None):
        """Odoo ``_get_invalid_statement_ids``
        (``odoo19c: account_bank_statement.py:242-275``): identifica, con
        una sola query de ventana (``LAG`` sobre ``first_line_index``
        particionado por diario), los estados cuyo ``balance_start`` NO
        coincide —redondeado a los decimales de su moneda— con el
        ``balance_end_real`` del estado anterior del mismo diario.

        ``journal_ids``/``ids`` acotan la búsqueda — equivalente al
        ``all_statements=False`` de la referencia. Sin argumentos corre
        sobre TODOS los estados; es el modo que usa ``search_is_valid``.
        Copiado tal cual (SQL crudo, no recorrido en Python): el ``LAG``
        compara contra el estado inmediatamente anterior en el
        ``PARTITION BY journal_id ORDER BY first_line_index`` real de
        PostgreSQL, no contra un "anterior" reconstruido a mano.
        """
        where = ["st.first_line_index != ''"]
        params = []
        if journal_ids is not None:
            where.append('st.journal_id = ANY(%s)')
            params.append(list(journal_ids))
        where_sql = ' AND '.join(where)

        having_sql = ''
        if ids is not None:
            having_sql = ' AND id = ANY(%s)'
            params.append(list(ids))

        query = f"""
            WITH statements AS (
                SELECT st.id,
                       st.balance_start,
                       st.journal_id,
                       LAG(st.balance_end_real) OVER (
                           PARTITION BY st.journal_id
                               ORDER BY st.first_line_index
                       ) AS prev_balance_end_real,
                       currency.decimal_places
                  FROM account_bank_statement st
             LEFT JOIN res_company co ON st.company_id = co.id
             LEFT JOIN account_journal j ON st.journal_id = j.id
             LEFT JOIN res_currency currency
                    ON COALESCE(j.currency_id, co.currency_id) = currency.id
                 WHERE {where_sql}
            )
            SELECT id
              FROM statements
             WHERE prev_balance_end_real IS NOT NULL
               AND ROUND(prev_balance_end_real, decimal_places)
                   != ROUND(balance_start, decimal_places)
               {having_sql}
        """
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return [row[0] for row in cursor.fetchall()]

    @classmethod
    def search_is_valid(cls, value=True):
        """Odoo ``_search_is_valid``
        (``odoo19c: account_bank_statement.py:219-223``): equivalente
        buscable de ``is_valid`` sobre TODOS los estados, vía
        ``_get_invalid_statement_ids`` (sin argumentos = modo
        ``all_statements``). La referencia sólo acepta ``operator ==
        'in'``; aquí un booleano simple, porque este puerto no tiene motor
        de domain."""
        invalid_ids = cls._get_invalid_statement_ids()
        qs = cls.objects.all()
        if value:
            return qs.exclude(pk__in=invalid_ids)
        return qs.filter(pk__in=invalid_ids)
