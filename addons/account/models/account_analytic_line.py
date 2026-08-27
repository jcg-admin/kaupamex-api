"""Lo que ``account`` le cuelga de ``account.analytic.line`` — ≙ ``_inherit``.

Adaptación de Odoo ``addons/account/models/account_analytic_line.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 183 líneas, 11 ``def``:
medido por AST — ``_compute_general_account_id``, ``_check_general_account_id``,
``_compute_partner_id``, ``_compute_analytic_profitability``,
``on_change_unit_amount``, ``view_header_get``, ``create``, ``_field_to_sql``,
``_search_analytic_profitability``, ``write``, ``unlink``). Extiende
``account.analytic.line`` — ya portado en ``analytic/models/analytic_line.py``
— con el enlace al apunte contable (``move_line``) y los campos que se
derivan de él.

Tarea #520 — el conector ``move_line`` construido; 3 de 11 ``def`` portados
================================================================================

``H-API-684`` (tramo anterior) dejó los 11 ``def`` BLOQUEADOS porque
``addons/analytic/migrations/`` no estaba en el alcance de ese tramo
(:ref:`h-docs-194`). Con esa carpeta en el alcance de esta tarea, se
construye el conector — pero **no todo lo que dependía de él se desbloquea**:
la mitad restante depende de columnas en ``account.move.line`` que este
tramo tampoco puede escribir (``account_move_line.py`` sigue fuera de la
lista). El bloqueo de esa mitad es real, no fabricado por el alcance.

Campos nuevos — 5, todos en ``analytic`` (mismo mecanismo que los archivos
hermanos de este tramo: la migración va al ``app_label`` del modelo, no del
archivo que la declara vía ``add_to_class``)
----------------------------------------------------------------------------

- ``move_line`` (odoo19c: :39-45, ``move_line_id``) — el conector. FK a
  ``account.AccountMoveLine``, ``on_delete=CASCADE`` (≙ ``ondelete=cascade``).
- ``general_account`` (odoo19c: :19-25, ``general_account_id``) — FK a
  ``account.AccountAccount``, ``on_delete=PROTECT`` (≙ ``ondelete=restrict``).
  ``compute='_compute_general_account_id', store=True, readonly=False`` en la
  referencia: **no** es un ``default=`` — es un valor que SUPLE al llamador
  cuando no lo da (mismo criterio que corrigió H-API-687 para ``move_type``
  de ``stock.picking``: un ``default=`` no distingue "no lo dieron" de "lo
  dieron y coincide"). Se implementa en ``save()``, sólo si viene vacío.
- ``product`` (odoo19c: :12-17, ``product_id``) — FK a
  ``product.ProductProduct``. Columna nueva independiente del conector; no
  necesitaba ``move_line`` para portarse, pero estaba en el mismo archivo
  BLOQUEADO por la migración ausente.
- ``code`` (odoo19c: :46, ``Char(size=8)``) y ``ref`` (odoo19c: :47,
  ``Char``) — Char simples, mismo motivo.

``category`` (odoo19c: :48, ``selection_add``) amplía el vocabulario YA
declarado en la base (``analytic_line.py``: ``[('other', 'Otro')]``) con
``invoice``/``vendor_bill`` — no genera migración, mismo mecanismo que
``business_domain`` en ``account_analytic_plan.py`` de este mismo tramo.

Los 3 ``def`` que el conector desbloquea
-------------------------------------------

- ``_compute_general_account_id`` — lee ``move_line.account``. Portado
  entero: ``account.AccountMoveLine.account`` YA existe
  (``account_move_line.py``), así que no hay bloqueo de segundo orden.
- ``_check_general_account_id`` — constraint: ``general_account`` debe
  coincidir con ``move_line.account`` cuando ``move_line`` está fijado.
  Portado vía ``chain_method`` sobre ``clean()`` (semántica de relevo: mi
  validación corre, y si no lanza, cae a la del mixin base — "cuenta
  analítica requerida").
- ``_compute_analytic_profitability`` — lee ``general_account.account_type``
  (ya desbloqueado por el punto anterior), ``category``, ``amount`` (ya
  existían en la base). Portado como campo ``store=False`` (la referencia NO
  declara ``store=True`` — ``compute=`` sin ``store=True`` es no-almacenado
  por defecto en Odoo), **sin** la mitad ``_field_to_sql``/
  ``_search_analytic_profitability`` — ver más abajo, sigue divergencia.

  **La referencia tiene un bug real** (``odoo19c: :87``): escribe
  ``line.analytic_profitablity = 'loss'`` — falta la **i** de
  *profitability*; el campo real se llama ``analytic_profitability`` (línea
  49). No se replica el typo.

Los 2 `def` que el conector desbloquea a medias — BLOQUEADO de segundo orden
--------------------------------------------------------------------------------

- ``journal_id`` (odoo19c: :26-33, ``related='move_line_id.journal_id'``) —
  ``account.move.line`` en este árbol **no declara** ``journal`` (medido:
  ``account_move_line.py:43-98`` — campos ``move``, ``account``, ``name``,
  ``debit``, ``credit``, ``balance``, ``display_type``, ``quantity``,
  ``price_unit``, ``currency``, ``full_reconcile``, ``matching_number``; sin
  ``journal``). ``account_move_line.py`` sigue fuera de la lista de archivos
  escribibles de esta tarea. BLOQUEADO, no campo.
- ``_compute_partner_id`` (odoo19c: :71-73, lee ``move_line_id.partner_id``)
  — ``account.move.line`` tampoco declara ``partner`` (mismo archivo medido
  arriba). BLOQUEADO por la misma causa que ``journal``.

Los 5 restantes — sin cambio respecto al tramo anterior
-------------------------------------------------------------

- ``create`` / ``write`` / ``unlink`` — invocan
  ``move_line_id._update_analytic_distribution()``, un método que la
  referencia cuelga sobre ``account.move.line`` desde el addon ``analytic``
  (no visto en este árbol) y que, aun colgándolo por ``add_to_class``,
  escribiría en ``AccountMoveLine.analytic_distribution`` — campo ausente,
  ``account_move_line.py`` fuera de alcance. BLOQUEADO, sin cambio.
- ``on_change_unit_amount`` — onchange de formulario. **Divergencia de
  mecanismo** (sin cliente web, sin cambio).
- ``view_header_get`` — título de vista lista del cliente web de Odoo.
  **Divergencia de mecanismo** (sin cambio).
- ``_field_to_sql`` / ``_search_analytic_profitability`` — SQL crudo de
  proyección/búsqueda de un campo ``store=False``, framework de ``_search``
  custom ausente en este ORM (misma ausencia que
  ``AccountAnalyticDistributionModel._create_domain`` ya documenta).
  **Divergencia de mecanismo** — ``analytic_profitability`` se declara sin
  esta mitad (sólo lectura vía ``default=``, no filtrable por
  ``.filter(analytic_profitability=...)``).

Sucesor: tarea PENDIENTE DE ASIGNAR — declarar ``account_move_line.py`` en el
alcance de un pase futuro; portar ``AccountMoveLine.journal``/``partner``/
``analytic_distribution`` con su migración en ``addons/account/migrations/``,
y entonces recuperar ``journal``, ``_compute_partner_id``,
``create``/``write``/``unlink``.
"""
from decimal import Decimal

import fields
import models
from django.core.exceptions import ValidationError

from addons.analytic.models.analytic_line import AccountAnalyticLine
from addons.product.models import ProductProduct
from orm.method_chain import chain_method

#: ≙ ``selection_add=[('invoice', 'Customer Invoice'), ('vendor_bill',
#: 'Vendor Bill')]`` (odoo19c: :48). Etiquetas en español por convención del
#: árbol (``redaccion-tecnica-es.md``).
_CATEGORY_EXTRA = [
    ('invoice', 'Factura de cliente'),
    ('vendor_bill', 'Factura de proveedor'),
]

#: ≙ ``['asset_current', 'asset_non_current', 'asset_fixed']``
#: (odoo19c: :83).
_ANALYTIC_PROFITABILITY_ASSET_TYPES = {
    'asset_current', 'asset_non_current', 'asset_fixed',
}


def _extend_selection_choices(model, field_name, extra_choices):
    """Amplía en sitio los ``choices`` de un campo ya declarado en ``model``.

    Mismo helper que ``account_analytic_plan.py`` de este mismo tramo — no
    genera migración, idempotente."""
    field = model._meta.get_field(field_name)
    already_present = {value for value, _label in field.choices}
    for value, label in extra_choices:
        if value not in already_present:
            field.choices.append((value, label))
            already_present.add(value)


def _add_if_absent(model, name, field):
    """Idempotente — mismo helper que ``account/models/product.py``."""
    if not any(f.name == name for f in model._meta.get_fields()):
        model.add_to_class(name, field)


def _compute_general_account(instance):
    """≙ ``_compute_general_account_id`` (odoo19c: :62-65)."""
    return instance.move_line.account if instance.move_line_id is not None else None


def _default_analytic_profitability(instance):
    """≙ ``_compute_analytic_profitability`` (odoo19c: :78-101), sin la
    mitad ``_field_to_sql``/``_search_analytic_profitability`` — ver
    docstring del módulo (divergencia: sin framework de ``_search`` custom).
    El typo ``analytic_profitablity`` de la referencia (línea 87) NO se
    replica."""
    account_type = getattr(instance.general_account, 'account_type', None) or ''
    category = instance.category
    amount = instance.amount if instance.amount is not None else Decimal('0.00')
    if (
        account_type.split('_')[0] == 'expense'
        or account_type in _ANALYTIC_PROFITABILITY_ASSET_TYPES
        or (not account_type and category not in ('invoice', 'other'))
        or (not account_type and category == 'other' and amount < 0)
    ):
        return 'loss'
    if (
        account_type.split('_')[0] == 'income'
        or (not account_type and category == 'other' and amount > 0)
    ):
        return 'revenue'
    return 'uncategorized'


def _derive_general_account_on_save(self, *args, **kwargs):
    """≙ el ``compute`` de ``general_account`` (odoo19c: :19-25,
    ``store=True, readonly=False``): SUPLE el valor que el llamador no dio —
    un ``general_account`` fijado a mano SIEMPRE gana (mismo criterio que
    corrigió H-API-687 para ``move_type`` de ``stock.picking``). Retorna
    ``None`` para que ``chain_method`` siga con el ``save()`` real."""
    if self.move_line_id is not None and self.general_account_id is None:
        self.general_account = _compute_general_account(self)
    return None


def _check_general_account(self, *args, **kwargs):
    """≙ ``_check_general_account_id`` (odoo19c: :62-66). Retorna ``None``
    para que ``chain_method`` siga con la validación base del mixin (cuenta
    analítica requerida) — semántica de relevo."""
    if (
        self.move_line_id is not None
        and self.general_account_id != self.move_line.account_id
    ):
        raise ValidationError({
            'general_account': 'ANALYTIC_LINE_GENERAL_ACCOUNT_MISMATCH',
        })
    return None


def apply_account_extensions():
    """Cuelga sobre ``account.analytic.line`` el conector y lo que depende de
    él. Ver docstring del módulo para los símbolos portados y los que siguen
    bloqueados.

    Cableada en ``AccountConfig.ready()`` vía ``_EXTENSIONES``. Invocable a
    mano; ver ``tests/unit/account/test_account_analytic_line.py``.
    """
    _add_if_absent(
        AccountAnalyticLine, 'move_line',
        fields.Many2one(
            'account.AccountMoveLine', on_delete=models.CASCADE,
            null=True, blank=True, related_name='analytic_lines',
            help_text='Odoo move_line_id (ondelete=cascade). El apunte '
                       'contable que generó esta línea analítica.',
        ),
    )
    _add_if_absent(
        AccountAnalyticLine, 'general_account',
        fields.Many2one(
            'account.AccountAccount', on_delete=models.PROTECT,
            null=True, blank=True, related_name='analytic_lines',
            help_text='Odoo general_account_id (ondelete=restrict, '
                       'compute+store+readonly=False). Se deriva de '
                       'move_line.account cuando no se fija a mano — ver '
                       'docstring del módulo.',
        ),
    )
    _add_if_absent(
        AccountAnalyticLine, 'product',
        fields.Many2one(
            'product.ProductProduct', on_delete=models.SET_NULL,
            null=True, blank=True, related_name='analytic_lines',
            help_text='Odoo product_id.',
        ),
    )
    _add_if_absent(
        AccountAnalyticLine, 'code',
        fields.Char(max_length=8, blank=True, default='', help_text='Odoo code.'),
    )
    _add_if_absent(
        AccountAnalyticLine, 'ref',
        fields.Char(max_length=255, blank=True, default='', help_text='Odoo ref.'),
    )
    _add_if_absent(
        AccountAnalyticLine, 'analytic_profitability',
        fields.Char(
            store=False, default=_default_analytic_profitability,
            help_text='Odoo analytic_profitability (compute, store=False). '
                       'loss/revenue/uncategorized según general_account.'
                       'account_type, category y amount — ver docstring del '
                       'módulo (sin el framework de _search custom).',
        ),
    )
    _extend_selection_choices(AccountAnalyticLine, 'category', _CATEGORY_EXTRA)

    chain_method(AccountAnalyticLine, 'save', _derive_general_account_on_save)
    chain_method(AccountAnalyticLine, 'clean', _check_general_account)
