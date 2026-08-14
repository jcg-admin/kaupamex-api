"""``account.bank.statement.line`` — Adaptación de Odoo addons/account/models/account_bank_statement_line.py
(odoo-tools@622ddc2a, odoo19c:).

Línea de movimiento bancario: la referencia la declara ``_inherits =
{'account.move': 'move_id'}`` — cada línea ES un asiento contable
(``account.move``), con campos propios de importación bancaria encima.

Se porta con el patrón ya establecido en este árbol para ``_inherits``: **FK
real + delegación por propiedad** (NO herencia multi-tabla de Django), mismo
criterio que ``mail_mail.py`` → ``mail.message`` (ver su docstring).
``currency``/``date``/``state`` siguen delegados por propiedad de solo
lectura, sin denormalizar (mismo trade-off que ``mail_mail.subject``); para
cambiarlos se toca ``linea.move.X``.

**``journal``/``company`` — corregido (H-API-321).** Un pase anterior los
dejaba como propiedad delegada (``self.move.journal``) y documentaba la
decisión como "sin denormalizar". La referencia SÍ los denormaliza
(``odoo19c: account_bank_statement_line.py:31-44`` — ``related=
move_id.journal_id``/``move_id.company_id``, ``store=True``, ``index=False
# covered by account_bank_statement_line_main_idx``) — precisamente porque
``_main_idx``/``_unreconciled_idx``/``_orphan_idx`` (líneas 151-153)
necesitan esas dos columnas físicas en ESTA tabla: un índice de PostgreSQL
no puede cubrir una columna de otra tabla a través de un FK. Se porta la
forma real: ``journal``/``company`` pasan a ser columnas propias,
sincronizadas en ``save()`` desde ``move`` (mismo espíritu que el
``related=..., store=True, precompute=True`` de Odoo, sin motor de compute
propio). Quedan ``null=True`` a nivel de columna —evita pedir un default
irreal en la migración sobre una tabla que puede tener filas—, pero
``save()`` los deja poblados en todo INSERT real mientras ``move`` esté
seteado (que es obligatorio).

**``internal_index`` / ``running_balance`` / ``is_valid`` — antes
"simplificados" en el ``docstring`` de este módulo, ahora portados
fielmente (H-API-321):**

- ``internal_index`` (``_compute_internal_index``,
  ``odoo19c: account_bank_statement_line.py:258-280``): combina fecha +
  secuencia invertida + id, zero-padded, para poder comparar
  ``internal_index < X`` en una sola condición en vez de repetir en cada
  query ``fecha < X OR (fecha = X AND secuencia > Y) OR (fecha = X AND
  secuencia = Y AND id < Z)``. El orden de la secuencia se invierte
  (``MAXINT - sequence``) porque el orden por defecto del modelo es
  descendente (``_order = "internal_index desc"``, línea 15 de la
  referencia): una ``sequence`` más alta debe listarse primero dentro de la
  misma fecha, así que se le asigna el valor MÁS CHICO del resto para que
  ordene primero en ASC — y por tanto también primero cuando el criterio
  completo se lee en DESC. Depende del ``pk`` propio (el ``id`` va dentro
  del índice como desempate), así que sólo puede calcularse tras el INSERT
  — ver ``save()`` y el guard ``filtered(lambda line: line._origin.id)`` de
  la referencia, que hace exactamente eso: no computar sin un id real.
- ``running_balance`` — la referencia la declara ``compute=
  '_compute_running_balance'`` **sin** ``store=True``: no es una columna,
  se recalcula en cada lectura. Aquí, una ``@property`` que llama a
  ``_compute_running_balances`` (SQL crudo, ancla en el ``balance_start``
  del último estado de cuenta anterior al lote —
  ``odoo19c: account_bank_statement_line.py:178-256``). Se copia tal
  cual, no se traduce a un acumulado fila-por-fila en Python: los estados
  de cuenta actúan como "checkpoints" que reinician el acumulado a su
  ``balance_start`` declarado (no al calculado) en cada frontera — un
  recorrido ingenuo que sólo sume ``amount`` da un resultado distinto en
  cuanto hay más de un estado de cuenta en el rango.
"""
from decimal import Decimal

from django.db import connection
from django.utils.dateparse import parse_date

import fields
import models
from addons.base.models import ResCompany

# Máximo de un ``int4`` de PostgreSQL — la columna ``sequence`` de la
# referencia es int4 (odoo19c: comentario de ``_compute_internal_index``,
# "assert self._fields['sequence'].column_type[1] == 'int4'";
# ``xmlrpc.client.MAXINT`` vale lo mismo, ``2**31-1``). Se fija la
# constante directa en vez de importar ``xmlrpc.client`` sólo por el valor.
MAXINT = 2147483647


class AccountBankStatementLine(models.Model):
    """``account.bank.statement.line`` — línea de movimiento bancario."""

    # Enlace _inherits (Odoo move_id, account_bank_statement_line.py:25-30) —
    # Many2one required + cascade, NO herencia multi-tabla (ver docstring).
    move = fields.Many2one(
        'account.AccountMove', on_delete=models.CASCADE,
        related_name='bank_statement_line',
        help_text='Asiento contable del que esta línea es la extensión '
                  'bancaria (Odoo move_id, _inherits). currency/date/state '
                  'se delegan a él; journal/company se sincronizan en '
                  'save() (ver docstring del módulo).',
    )
    journal = fields.Many2one(
        'account.AccountJournal', on_delete=models.PROTECT,
        null=True, blank=True, related_name='bank_statement_lines',
        help_text='Diario — denormalizado de move.journal (Odoo journal_id, '
                  'related=move_id.journal_id, store=True, index=False # '
                  'covered by _main_idx). Se sincroniza en save(); no se '
                  'edita directo, se cambia linea.move.journal.',
    )
    company = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE,
        null=True, blank=True, related_name='bank_statement_lines',
        help_text='Empresa — denormalizada de move.company (Odoo company_id, '
                  'related=move_id.company_id, store=True). Se sincroniza en '
                  'save(); no se edita directo, se cambia linea.move.company.',
    )
    statement = fields.Many2one(
        'account.AccountBankStatement', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='line_ids',
        help_text='Estado de cuenta al que pertenece, si ya fue agrupada '
                  '(Odoo statement_id).',
    )
    sequence = fields.Integer(
        default=1,
        help_text='Orden dentro del estado de cuenta (Odoo sequence; '
                  'invertido dentro de internal_index, ver docstring del '
                  'módulo).',
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
    internal_index = fields.Char(
        max_length=32, blank=True, default='',
        help_text='Índice de orden: fecha + secuencia invertida + id, '
                  'zero-padded (Odoo internal_index, compute='
                  '_compute_internal_index, store=True). Se recalcula en '
                  'save() — ver docstring del módulo.',
    )

    class Meta:
        db_table = 'account_bank_statement_line'
        ordering = ['-internal_index']
        verbose_name = 'Línea de estado de cuenta bancario'
        verbose_name_plural = 'Líneas de estado de cuenta bancario'
        indexes = [
            models.Index(
                fields=['statement', 'sequence'],
                name='acc_bank_stmt_line_seq_idx',
            ),
            # Odoo `_main_idx` (odoo19c: account_bank_statement_line.py:153).
            models.Index(
                fields=['journal', 'company', 'internal_index'],
                name='acc_bank_stmt_line_main_idx',
            ),
            # Odoo `_unreconciled_idx` (línea 151) — parcial, `IS NOT TRUE`
            # equivale a `= False` porque is_reconciled no admite NULL.
            models.Index(
                fields=['journal', 'company', 'internal_index'],
                name='acc_bank_stmt_line_unrecon_idx',
                condition=models.Q(is_reconciled=False),
            ),
            # Odoo `_orphan_idx` (línea 152) — líneas sin estado de cuenta.
            models.Index(
                fields=['journal', 'company', 'internal_index'],
                name='acc_bank_stmt_line_orphan_idx',
                condition=models.Q(statement__isnull=True),
            ),
        ]

    def __str__(self) -> str:
        return self.payment_ref or f'Línea bancaria #{self.pk}'

    # ---- Campos delegados (≙ _inherits de account.move) ----
    # Solo lectura, como el resto de delegaciones del árbol (mail_mail,
    # product_product, res_users). Para escribirlos se toca linea.move.X.

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

    # ---- Sincronización + compute de internal_index ----

    def save(self, *args, **kwargs):
        """Sincroniza ``journal``/``company`` desde ``move`` (denormalizado
        para poder indexar — ver docstring del módulo) y recalcula
        ``internal_index`` tras el INSERT, porque depende del ``pk`` propio
        (``odoo19c: account_bank_statement_line.py:258-280``). En creación
        hace dos escrituras: el INSERT normal, y luego un ``UPDATE`` puntual
        del índice ya con el id asignado — no hay forma de conocer el id
        antes del INSERT con un PK autoincremental."""
        if self.move_id:
            self.journal_id = self.move.journal_id
            self.company_id = self.move.company_id
        creating = self.pk is None
        if creating:
            super().save(*args, **kwargs)
            self._compute_internal_index()
            type(self).objects.filter(pk=self.pk).update(
                internal_index=self.internal_index)
        else:
            self._compute_internal_index()
            super().save(*args, **kwargs)

    def _compute_internal_index(self):
        """Odoo ``_compute_internal_index``
        (``odoo19c: account_bank_statement_line.py:258-280``): fecha +
        secuencia invertida + id, zero-padded — ver docstring del módulo
        para el porqué de la inversión.

        ``self.date`` (delegado de ``move.date``) puede llegar como ``str``
        cuando el ``move`` se construyó en memoria y no se releyó de la
        base (Django sólo corre ``DateField.to_python`` al cargar desde
        DB/formularios, no en la asignación directa) — se normaliza antes
        de ``strftime``.
        """
        if not self.pk:
            return
        date_value = self.date
        if isinstance(date_value, str):
            date_value = parse_date(date_value)
        if not date_value:
            return
        self.internal_index = (
            f'{date_value.strftime("%Y%m%d")}'
            f'{MAXINT - self.sequence:0>10}'
            f'{self.pk:0>10}'
        )

    # ---- running_balance: no-store, recalculado en cada lectura ----

    @property
    def running_balance(self):
        """Saldo acumulado hasta esta línea (Odoo ``running_balance``, SIN
        ``store=True`` — ver docstring del módulo y
        ``_compute_running_balances`` abajo)."""
        return self._compute_running_balances([self.pk]).get(
            self.pk, Decimal('0.00'))

    @classmethod
    def _compute_running_balances(cls, line_ids):
        """Odoo ``_compute_running_balance``
        (``odoo19c: account_bank_statement_line.py:178-256``): ancla el
        cálculo en el ``balance_start`` del último estado de cuenta anterior
        al lote, y recorre las líneas en orden de ``internal_index``
        reiniciando el acumulado al ``balance_start`` declarado en cada
        frontera de estado de cuenta (``is_anchor``). SQL crudo, copiado tal
        cual — ver docstring del módulo para el porqué.

        Devuelve ``{id: Decimal}`` para las líneas pedidas en ``line_ids``
        (las demás filas que la query visita son sólo soporte del
        acumulado, igual que en la referencia).

        Alcance multi-empresa: la empresa del diario de cada línea, más sus
        hijas — Odoo resuelve esto con ``child_of``
        (``company2children``); aquí, ``parent_path`` (mismo patrón que
        ``product/models/product_category.py:162``).
        """
        lines = list(cls.objects.filter(pk__in=line_ids))
        if not lines:
            return {}

        by_journal = {}
        for line in lines:
            by_journal.setdefault(line.journal_id, []).append(line)

        result = {}
        with connection.cursor() as cursor:
            for journal_id, journal_lines in by_journal.items():
                indexes = sorted(
                    line.internal_index for line in journal_lines
                    if line.internal_index)
                if not indexes:
                    for line in journal_lines:
                        result[line.pk] = Decimal('0.00')
                    continue
                min_index, max_index = indexes[0], indexes[-1]

                company_id = journal_lines[0].company_id
                company_ids = [company_id]
                company = ResCompany.objects.filter(pk=company_id).first()
                if company is not None and company.parent_path:
                    company_ids = list(
                        ResCompany.objects
                        .filter(parent_path__startswith=company.parent_path)
                        .values_list('pk', flat=True))

                cursor.execute(
                    """
                    SELECT first_line_index, COALESCE(balance_start, 0.0)
                      FROM account_bank_statement
                     WHERE first_line_index != ''
                       AND first_line_index < %s
                       AND journal_id = %s
                     ORDER BY first_line_index DESC
                     LIMIT 1
                    """,
                    [min_index, journal_id],
                )
                row = cursor.fetchone()
                current = Decimal('0.00')
                extra_sql = ''
                params = [max_index, journal_id, company_ids]
                if row:
                    starting_index, current = row
                    current = Decimal(str(current))
                    extra_sql = 'AND st_line.internal_index >= %s'
                    params.append(starting_index)

                cursor.execute(
                    f"""
                    SELECT
                        st_line.id,
                        st_line.amount,
                        st.first_line_index = st_line.internal_index
                            AS is_anchor,
                        COALESCE(st.balance_start, 0.0),
                        move.state
                      FROM account_bank_statement_line st_line
                      JOIN account_move move ON move.id = st_line.move_id
                 LEFT JOIN account_bank_statement st
                        ON st.id = st_line.statement_id
                     WHERE st_line.internal_index <= %s
                       AND st_line.journal_id = %s
                       AND st_line.company_id = ANY(%s)
                       {extra_sql}
                     ORDER BY st_line.internal_index
                    """,
                    params,
                )
                pending_ids = {line.pk for line in journal_lines}
                for st_line_id, amount, is_anchor, balance_start, state \
                        in cursor.fetchall():
                    if is_anchor:
                        current = Decimal(str(balance_start))
                    if state == 'posted':
                        current = current + Decimal(str(amount))
                    if st_line_id in pending_ids:
                        result[st_line_id] = current
        return result
