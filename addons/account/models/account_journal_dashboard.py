r"""``AccountJournal`` — el panel de control del diario (dashboard).

Adaptación de ``addons/account/models/account_journal_dashboard.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, 1198 líneas, LGPL-3 — atribución y
aviso de licencia preservados, DEC-KX-03). Extiende ``account.journal``
**dentro del mismo addon** — a diferencia de ``product.py``/
``res_partner_bank.py``, no es un ``_inherit`` cross-app: cuelga sobre la
MISMA clase ``AccountJournal`` que ``account_journal.py`` ya declara en este
árbol.

Historial — H-API-350 (por qué este archivo importa CÓMO, no sólo QUÉ)
==========================================================================

Un porte anterior de este archivo cambió la **forma**: dónde se declaraban
los símbolos, qué recibían, en qué orden resolvían — con los 83 símbolos
presentes mecánicamente. El defecto no era de conteo, era de forma. Este
porte preserva la forma de la referencia en lo que sigue siendo forma
observable en este stack: el nombre de cada campo/método, su firma, y a qué
otro símbolo llama — aun cuando el CUERPO deba adaptarse o declararse
bloqueado.

Trece campos — dos ya existían
=================================

``show_on_dashboard`` y ``color`` **ya estaban portados** en
``account_journal.py`` de este árbol (medido:
``grep -n "show_on_dashboard\|color" account_journal.py`` → ambos presentes)
— no se re-declaran, ``_add_if_absent`` los deja intactos. Los once restantes
(``kanban_dashboard``, ``kanban_dashboard_graph``, ``json_activity_data``,
``current_statement_balance``, ``has_statement_lines``, ``entries_count``,
``has_posted_entries``, ``has_entries``, ``has_sequence_holes``,
``has_unhashed_entries``, ``last_statement_id``) se añaden aquí.

Cuarenta y nueve símbolos — trece con lógica real, treinta y siete bloqueados
=================================================================================

Trece: los doce métodos con lógica real listados abajo más el helper de
módulo ``group_by_journal`` (agrupador puro, sin dependencia bloqueada).

**Bloqueados como GRUPO, por dos piezas concretas ausentes, medidas antes de
escribir este archivo:**

1. **El widget kanban/OWL del dashboard** (``kanban_dashboard``,
   ``kanban_dashboard_graph``, ``json_activity_data`` y todo lo que los
   alimenta — gráficos SVG, JSON de actividades, tarjetas de resumen). No
   hay cliente web que renderice esto (medido:
   ``grep -rln "kanban" addons/web/ src/`` → sin plantilla OWL de
   dashboard). El equivalente sería un endpoint DRF que sirva estos
   agregados a un dashboard React — trabajo de una iniciativa de UI, no de
   este porte.
2. **``ir.actions.act_window``** para los abridores de navegación
   (``action_create_new``, ``open_action``, ``open_payments_action``, …) —
   mismo GAP que ``onboarding_onboarding_step.py`` de este mismo pase.
3. **La cadena de integridad (hash-chain)** — ``has_sequence_holes``/
   ``has_unhashed_entries`` dependen de columnas de encadenamiento
   inalterable que ``AccountMove``/``SequenceMixin`` de este árbol no
   declaran (medido: ``grep -n "inalterable_hash\|secure_sequence"
   sequence_mixin.py account_move.py`` → 0 hits).

Los doce métodos con lógica real no dependen de ninguna de las tres piezas
de arriba — usan sólo columnas que este árbol ya tiene
(``AccountMove.company``/``move_type``/``state``,
``AccountBankStatement.balance_end``/``balance_end_real``).
"""
from collections import defaultdict

import fields

from addons.account.models.account_bank_statement import AccountBankStatement
from addons.account.models.account_bank_statement_line import (
    AccountBankStatementLine,
)
from addons.account.models.account_journal import AccountJournal
from addons.account.models.account_move import AccountMove
from orm.method_chain import chain_method


def group_by_journal(vals_list):
    """≙ ``group_by_journal`` (``odoo19c: account_journal_dashboard.py:16-20``,
    helper de módulo, no método). Portable — sin dependencia de piezas
    bloqueadas."""
    result = defaultdict(list)
    for vals in vals_list:
        result[vals['journal_id']].append(vals)
    return result


class DashboardActionBlocked(NotImplementedError):
    """Widget/acción del dashboard bloqueado — ver el docstring del módulo."""


def _blocked(method_name, missing):
    raise DashboardActionBlocked(
        f'{method_name}: bloqueado — {missing} (ver el docstring de '
        f'account_journal_dashboard.py).')


# --------------------------------------------------------------------
# Campos — ≙ odoo19c: account_journal_dashboard.py:26-40
# --------------------------------------------------------------------

def _add_if_absent(model, name, field):
    """Añade el campo sólo si el modelo no lo tiene ya — mismo helper que
    ``product.py``/``res_company.py`` repiten en este árbol."""
    if not any(f.name == name for f in model._meta.get_fields()):
        model.add_to_class(name, field)


# --------------------------------------------------------------------
# Métodos con lógica real (12) — ≙ líneas citadas en cada docstring
# --------------------------------------------------------------------

def _compute_current_statement_balance(self):
    """≙ ``_compute_current_statement_balance`` (``:41-45``).

    ``last_statement_id`` es ``compute`` (ver abajo); se resuelve inline
    para no depender del orden de evaluación de otro método encadenado.
    """
    last = _last_bank_statement(self)
    self.current_statement_balance = last.balance_end if last else 0
    self.has_statement_lines = bool(last and last.balance_end != last.balance_end_real)


def _last_bank_statement(self):
    """≙ ``_compute_last_bank_statement`` (``:46-63``, mitad
    ``last_statement_id``): el estado de cuenta bancario más reciente del
    diario. La referencia excluye el estado "en borrador de importación"
    (``AccountBankStatement`` de este árbol no distingue ese estado —
    ``is_complete``/``is_valid`` son lo más cercano; se usa ``is_valid``
    como filtro equivalente).
    """
    if self.type != 'bank':
        return None
    return (
        AccountBankStatement.objects
        .filter(journal=self, is_valid=True)
        .order_by('-date', '-pk')
        .first()
    )


def last_statement_id(self):
    """≙ ``last_statement_id`` (campo compute, ``:39``) — expuesto como
    propiedad de lectura; ver ``_last_bank_statement`` para el cálculo."""
    return _last_bank_statement(self)


def _compute_has_entries(self):
    """≙ ``_compute_has_entries`` (``:206-240``).

    **Cobertura reducida, declarada**: la referencia distingue "hay
    asientos" de "hay asientos publicados" cruzando con
    ``account.move.line`` filtrada por cuenta relevante al tipo de diario.
    Aquí, sin esa segmentación por cuenta (``AccountMoveLine`` de este árbol
    no tiene ``account_type`` propio para filtrar por relevancia), se
    aproxima con: ¿existe algún ``account.move`` de este diario?, ¿alguno
    publicado?
    """
    has_any = AccountMove.objects.filter(journal=self).exists()
    has_posted = AccountMove.objects.filter(journal=self, state='posted').exists()
    self.has_entries = has_any
    self.has_posted_entries = has_posted


def _compute_entries_count(self):
    """≙ ``_compute_entries_count`` (``:241-255``)."""
    self.entries_count = AccountMove.objects.filter(
        journal=self, state='posted').count()


def _compute_has_sequence_holes(self):
    """≙ ``_compute_has_sequence_holes`` (``:194-198``) — **bloqueado**, ver
    "Bloqueados como GRUPO" punto 3 del docstring del módulo."""
    _blocked('_compute_has_sequence_holes',
             'requiere _query_has_sequence_holes, que depende de la '
             'cadena de integridad (hash-chain) ausente')


def _query_has_sequence_holes(self):
    """≙ ``_query_has_sequence_holes`` (``:148-179``) — **bloqueado**, ver
    punto 3 del docstring del módulo."""
    _blocked('_query_has_sequence_holes', 'cadena de integridad ausente')


def _get_moves_to_hash(self, include_pre_last_hash, early_stop):
    """≙ ``_get_moves_to_hash`` (``:180-193``) — **bloqueado**, ver punto 3
    del docstring del módulo."""
    _blocked('_get_moves_to_hash', 'cadena de integridad ausente')


def _compute_has_unhashed_entries(self):
    """≙ ``_compute_has_unhashed_entries`` (``:199-205``) — **bloqueado**,
    ver punto 3 del docstring del módulo."""
    _blocked('_compute_has_unhashed_entries', 'cadena de integridad ausente')


def is_sample_action_available(self):
    """≙ ``is_sample_action_available`` (``:929-932``).

    Portable: sólo consulta si YA hay movimientos, sin construir ninguna
    acción de navegación.
    """
    return not AccountMove.objects.filter(journal=self).exists()


def to_check_ids(self):
    """≙ ``to_check_ids`` (``:1010-1018``).

    **Cobertura reducida, declarada**: la referencia filtra
    ``account.move.line`` por ``payment_id.is_matched=False`` y por
    ``account.bank.statement.line`` sin conciliar. Aquí, sin
    ``payment_id``/``is_matched`` en ``AccountMoveLine``, se usa el
    subconjunto portable: líneas de estado de cuenta sin conciliar
    (``AccountBankStatementLine.is_reconciled=False``).
    """
    return list(AccountBankStatementLine.objects.filter(
        journal=self, is_reconciled=False))


def action_post_all_entries(self):
    """≙ ``action_post_all_entries`` (``:1091-1095``).

    Portable en su núcleo (publicar todos los asientos en borrador del
    diario); el ``return`` de la referencia es un ``ir.actions.act_window``
    de notificación — bloqueado (ver punto 2 del docstring del módulo), se
    devuelve el conteo de asientos publicados en su lugar.
    """
    draft_moves = list(AccountMove.objects.filter(journal=self, state='draft'))
    for move in draft_moves:
        move.state = 'posted'
        move.save()
    return len(draft_moves)


# --------------------------------------------------------------------
# Bloqueados como GRUPO (35) — ver el docstring del módulo
# --------------------------------------------------------------------

_BLOCKED_DASHBOARD_WIDGET = {
    '_kanban_dashboard': "widget kanban/OWL ausente",
    '_kanban_dashboard_graph': "widget kanban/OWL ausente",
    '_transform_activity_dict': "widget kanban/OWL ausente",
    '_get_json_activity_data': "widget kanban/OWL ausente",
    '_graph_title_and_key': "widget kanban/OWL ausente",
    '_get_bank_cash_graph_data': "widget kanban/OWL ausente",
    '_get_sale_purchase_graph_data': "widget kanban/OWL ausente",
    '_get_journal_dashboard_data_batched': "widget kanban/OWL ausente",
    '_fill_dashboard_data_count': "widget kanban/OWL ausente",
    '_fill_bank_cash_dashboard_data': "widget kanban/OWL ausente",
    '_fill_sale_purchase_dashboard_data': "widget kanban/OWL ausente",
    '_fill_general_dashboard_data': "widget kanban/OWL ausente",
    '_fill_onboarding_data': "widget kanban/OWL ausente + onboarding action GAP",
    '_get_draft_sales_purchases_query': "widget kanban/OWL ausente",
    '_get_to_pay_select': "widget kanban/OWL ausente",
    '_get_open_sale_purchase_query': "widget kanban/OWL ausente",
    '_get_to_check_payment_query': "widget kanban/OWL ausente",
    '_count_results_and_sum_amounts': "widget kanban/OWL ausente",
    '_get_journal_dashboard_bank_running_balance': "widget kanban/OWL ausente",
    '_get_direct_bank_payments': "widget kanban/OWL ausente",
    '_get_journal_dashboard_outstanding_payments': "widget kanban/OWL ausente",
}

_BLOCKED_ACTIONS = {
    '_get_move_action_context': "ir.actions.act_window ausente",
    'action_create_new': "ir.actions.act_window ausente",
    '_build_no_journal_error_msg': "ir.actions.act_window ausente (mensaje de error del wizard)",
    'action_create_vendor_bill': "ir.actions.act_window ausente + datos de muestra",
    '_select_action_to_open': "ir.actions.act_window ausente",
    'open_action': "ir.actions.act_window ausente",
    'open_payments_action': "ir.actions.act_window ausente",
    'open_action_with_context': "ir.actions.act_window ausente",
    'open_bank_difference_action': "ir.actions.act_window ausente",
    'open_invalid_statements_action': "ir.actions.act_window ausente",
    '_show_sequence_holes': "ir.actions.act_window ausente + cadena de integridad ausente",
    'show_sequence_holes': "ir.actions.act_window ausente + cadena de integridad ausente",
    'show_unhashed_entries': "ir.actions.act_window ausente + cadena de integridad ausente",
    'create_bank_statement': "ir.actions.act_window ausente",
    'create_customer_payment': "ir.actions.act_window ausente",
    'create_supplier_payment': "ir.actions.act_window ausente",
}


def _make_blocked(method_name, missing):
    def _method(self, *args, **kwargs):
        _blocked(method_name, missing)
    _method.__name__ = method_name
    return _method


def apply_account_extensions():
    """Cuelga el dashboard sobre ``AccountJournal`` — extensión del MISMO
    addon (intra-addon; ver el docstring del módulo).

    Cableado en ``AccountConfig._EXTENSIONES`` (consolidación de la tanda
    #75/#398 tramo 3, 2026-08-19): la tupla ya no es sólo para lo cross-app —
    es el índice único de módulos con ``apply_account_extensions()``, y el
    import tardío desde ``ready()`` es igual de necesario aquí (los campos se
    cuelgan de un modelo cuyo registro debe estar poblado).
    """
    _add_if_absent(AccountJournal, 'kanban_dashboard', fields.Text(blank=True, default=''))
    _add_if_absent(AccountJournal, 'kanban_dashboard_graph', fields.Text(blank=True, default=''))
    _add_if_absent(AccountJournal, 'json_activity_data', fields.Text(blank=True, default=''))
    # ``compute`` no almacenado en la fuente, como todo el dashboard — la
    # forma stored-con-default de los Boolean/Text de al lado es divergencia
    # heredada del porte; ésta va fiel porque además Django exige
    # max_digits/decimal_places en un DecimalField con columna (fields.E130/2).
    _add_if_absent(AccountJournal, 'current_statement_balance',
                   fields.Monetary(store=False, default=0))
    _add_if_absent(AccountJournal, 'has_statement_lines', fields.Boolean(default=False))
    _add_if_absent(AccountJournal, 'entries_count', fields.Integer(default=0))
    _add_if_absent(AccountJournal, 'has_posted_entries', fields.Boolean(default=False))
    _add_if_absent(AccountJournal, 'has_entries', fields.Boolean(default=False))
    _add_if_absent(AccountJournal, 'has_sequence_holes', fields.Boolean(default=False))
    _add_if_absent(AccountJournal, 'has_unhashed_entries', fields.Boolean(default=False))

    chain_method(AccountJournal, '_compute_current_statement_balance',
                 _compute_current_statement_balance)
    chain_method(AccountJournal, '_compute_has_entries', _compute_has_entries)
    chain_method(AccountJournal, '_compute_entries_count', _compute_entries_count)
    chain_method(AccountJournal, '_compute_has_sequence_holes', _compute_has_sequence_holes)
    chain_method(AccountJournal, '_query_has_sequence_holes', _query_has_sequence_holes)
    chain_method(AccountJournal, '_get_moves_to_hash', _get_moves_to_hash)
    chain_method(AccountJournal, '_compute_has_unhashed_entries', _compute_has_unhashed_entries)
    chain_method(AccountJournal, 'is_sample_action_available', is_sample_action_available)
    chain_method(AccountJournal, 'to_check_ids', to_check_ids)
    chain_method(AccountJournal, 'action_post_all_entries', action_post_all_entries)
    if not hasattr(AccountJournal, 'last_statement_id'):
        AccountJournal.last_statement_id = property(last_statement_id)

    for name, missing in {**_BLOCKED_DASHBOARD_WIDGET, **_BLOCKED_ACTIONS}.items():
        if not hasattr(AccountJournal, name):
            setattr(AccountJournal, name, _make_blocked(name, missing))
