r"""``account.bank.statement`` — Adaptación de Odoo addons/account/models/account_bank_statement.py
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
  vía SQL crudo en ``_get_invalid_statement_ids``/``_search_is_valid``.

**Portado (H-API-331, tarea #126).** ``date`` era un campo plano — la
referencia lo deriva de la última línea posteada
(``_compute_date``, ``odoo19c: account_bank_statement.py:133-138``). No era
portable antes porque el ``compute`` ordena por ``internal_index``, que no
existía hasta H-API-321; con ``internal_index`` ya presente, el obstáculo
desapareció. Se porta como ``_compute_date()``, invocado desde
``recompute()`` — mismo patrón que ``_compute_first_line_index()``.

De paso, se extrae ``_compute_name()`` como método propio (antes inline
dentro de ``recompute()``): el gate de porte (``check_porte_completo.py``)
lo reportaba AUSENTE porque no existía un símbolo con ese nombre, aunque el
comportamiento (asignar ``name`` una sola vez, sin sobreescribir un valor ya
fijado) ya coincidía con el efecto práctico del ``compute`` de la referencia
(``_compute_name``, ``odoo19c: account_bank_statement.py:118-124`` — depende
de ``create_date``, que no vuelve a cambiar tras el INSERT, así que en la
práctica corre una sola vez). **Divergencia declarada:** el fallback de la
referencia cuando ``date`` es ``None`` usa ``create_date`` (fecha de
creación del registro); este modelo no denormaliza un timestamp de creación
(medido: ``grep -rn "create_date\|created_at\|auto_now_add"
src/addons/account/models/*.py`` → 0 hits en este addon salvo el propio
docstring). El puerto usa ``Estado #<pk>`` como aproximación estable —
mismo fallback que ya tenía el bloque inline, sin cambio de comportamiento.
DESCONOCIDO con condición de cierre: si se necesita fidelidad total al
fallback de creación, requiere sumar ``created_at`` (vía ``TimeStampedModel``
u homólogo) a este modelo — fuera del alcance de #126, que sólo pide portar
``_compute_date``.
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
        """Recalcula ``balance_end``/``first_line_index``/``date``/``name``/
        ``is_complete``/``problem_description`` (Odoo ``_compute_balance_end``
        + ``_compute_first_line_index`` + ``_compute_date`` + ``_compute_name``
        + ``_compute_is_complete``, colapsados: sin compute-engine, se invoca
        explícitamente tras modificar ``line_ids``)."""
        lines = self.line_ids.all()
        posted = [line for line in lines if line.move.state == 'posted']
        total = sum((line.amount for line in posted), Decimal('0.00'))
        self.balance_end = (self.balance_start or Decimal('0.00')) + total

        self._compute_first_line_index()
        self._compute_date()
        self._compute_name()

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

    def _compute_date(self):
        """Odoo ``_compute_date`` (``odoo19c: account_bank_statement.py:
        133-138``, tarea #126/H-API-331): la fecha de la última línea
        POSTEADA del estado, ordenadas por ``internal_index`` — no por
        ``date`` (sería circular: es el campo que se está calculando).
        Entre las líneas con ``internal_index`` ya calculado, se ordena
        ascendente y se toma la fecha de la última posteada; si ninguna
        está posteada, ``date`` queda en ``None``. ``readonly=False`` en la
        referencia: este compute sólo aporta el valor por defecto, el
        usuario puede sobreescribirlo después."""
        last_posted = (self.line_ids
                       .exclude(internal_index='')
                       .filter(move__state='posted')
                       .order_by('internal_index')
                       .last())
        self.date = last_posted.date if last_posted is not None else None

    def _compute_name(self):
        """Odoo ``_compute_name`` (``odoo19c: account_bank_statement.py:
        118-124``): ``<código del diario> Estado <fecha>``. La referencia
        recalcula sólo cuando cambia ``create_date`` — que no vuelve a
        cambiar tras el INSERT —, así que en la práctica corre una vez y
        el usuario puede sobreescribir el resultado después
        (``readonly=False``). Aquí se reproduce ese efecto sin motor de
        compute: no se sobreescribe un ``name`` ya fijado.

        Divergencia declarada (ver docstring del módulo): el fallback de la
        referencia cuando no hay ``date`` usa ``create_date``; este modelo
        no denormaliza timestamp de creación, así que cae a ``Estado
        #<pk>``."""
        if self.name:
            return
        prefix = f'{self.journal.code} ' if self.journal_id else ''
        self.name = f'{prefix}Estado {self.date}' if self.date else \
            f'{prefix}Estado #{self.pk or "?"}'

    # -------------------------------------------------------------------
    # BUSQUEDA/LOTE — SQL de ventana (Odoo _get_invalid_statement_ids)
    # -------------------------------------------------------------------

    @classmethod
    def _get_invalid_statement_ids(cls, all_statements=None,
                                   journal_ids=None, ids=None):
        """Odoo ``_get_invalid_statement_ids``
        (``odoo19c: account_bank_statement.py:242-275``): identifica, con
        una sola query de ventana (``LAG`` sobre ``first_line_index``
        particionado por diario), los estados cuyo ``balance_start`` NO
        coincide —redondeado a los decimales de su moneda— con el
        ``balance_end_real`` del estado anterior del mismo diario.

        ``all_statements`` es el parámetro de la referencia y conserva su
        sentido: con él, la query corre sobre TODOS los estados. Cuando es
        falso, la referencia lee el diario y los ids **del propio recordset**
        (``self.journal_id.ids`` / ``self.ids``); Django no tiene recordsets,
        así que esos dos llegan por argumento — ``journal_ids``/``ids`` son el
        sustituto declarado de ``self``, no parámetros inventados.
        Copiado tal cual (SQL crudo, no recorrido en Python): el ``LAG``
        compara contra el estado inmediatamente anterior en el
        ``PARTITION BY journal_id ORDER BY first_line_index`` real de
        PostgreSQL, no contra un "anterior" reconstruido a mano.
        """
        where = ["st.first_line_index != ''"]
        params = []
        having_sql = ''
        # ≙ los dos `{"" if all_statements else ...}` de la referencia
        # (:263, :268): la bandera decide si los dos acotamientos entran en
        # el SQL, no si los argumentos vienen o no.
        if not all_statements:
            if journal_ids is not None:
                where.append('st.journal_id = ANY(%s)')
                params.append(list(journal_ids))
            if ids is not None:
                having_sql = ' AND id = ANY(%s)'
                params.append(list(ids))
        where_sql = ' AND '.join(where)

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
    def _search_is_valid(cls, operator='in', value=True):
        """≙ ``_search_is_valid``
        (``odoo19c: account_bank_statement.py:219-223``): el equivalente
        buscable de ``is_valid``, sobre TODOS los estados.

        La guarda del operador se conserva verbatim: la referencia sólo sabe
        resolver ``in`` y devuelve ``NotImplemented`` para el resto. **No** es
        prescindible por no tener motor de domain — al revés: sin ella, un
        operador que no sabemos honrar devolvería un queryset que parece una
        respuesta y no lo es.

        DIVERGENCIA declarada en el valor buscado: la referencia devuelve
        siempre ``[('id', 'not in', invalid_ids)]``, sin mirar ``value``; aquí
        se ramifica, porque sin motor de domain nadie niega el término por
        fuera. Con ``value`` falso devuelve los inválidos, que es lo que
        ``is_valid in [False]`` significa.
        """
        if operator != 'in':
            return NotImplemented
        invalid_ids = cls._get_invalid_statement_ids(all_statements=True)
        qs = cls.objects.all()
        if value:
            return qs.exclude(pk__in=invalid_ids)
        return qs.filter(pk__in=invalid_ids)
