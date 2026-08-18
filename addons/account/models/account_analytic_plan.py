"""Lo que ``account`` le cuelga de ``account.analytic.applicability``.

Adaptación de Odoo ``addons/account/models/account_analytic_plan.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 81 líneas, 3 ``def``: medido
por AST sobre ``AccountAnalyticApplicability`` — ``_compute_prefix_placeholder``,
``_get_score``, ``_compute_display_account_prefix``; más los campos
``business_domain`` (``selection_add``), ``account_prefix``,
``product_categ_id``, ``display_account_prefix``,
``account_prefix_placeholder``). Pese al nombre del archivo en la referencia,
la clase que extiende es ``account.analytic.applicability`` — ya portada en
``analytic/models/analytic_plan.py`` — no ``account.analytic.plan``: medido
con AST al inicio del tramo original (``python3 -c "import ast..."`` sobre el
archivo de la referencia → una sola clase, ``AccountAnalyticApplicability``).

Tarea #520 — el símbolo restante, portado
============================================

``H-API-684`` dejó ``account_prefix``/``product_categ_id``/``_get_score``
BLOQUEADOS porque ``addons/analytic/migrations/`` no estaba en el alcance de
ese tramo (:ref:`h-docs-194`). Con esa carpeta en el alcance de esta tarea,
los 3 ``def`` de la referencia quedan **completos**.

``account_prefix``/``product_categ`` → nuevas columnas en ``analytic``
--------------------------------------------------------------------------

Mismo mecanismo que ``account_analytic_distribution_model.py`` de este mismo
tramo: la migración aterriza en ``addons/analytic/migrations/`` porque
``account.analytic.applicability`` vive en
``addons/analytic/models/analytic_plan.py`` (el ``app_label`` del modelo, no
del archivo que declara el campo vía ``add_to_class`` — ``account/models/
product.py``).

``_get_score`` — envuelve la base con ``chain_method``
------------------------------------------------------

La referencia (``odoo19c:`` líneas 59-76) hace ``score = super()._get_score(
**kwargs); if score == -1: return -1; ...; return score`` — un envoltorio que
necesita el resultado de la base ANTES de decidir el propio. La semántica de
relevo por defecto de ``chain_method`` llama a la función nueva PRIMERO, así
que no sirve tal cual; se usa ``combine=``:

- la función nueva (``_account_prefix_categ_bonus``) sólo calcula el PLUS (o
  el veto, señalado con ``None``) que ``account_prefix``/``product_categ``
  aportan — no conoce el puntaje base;
- ``combine`` recibe ese plus/veto y el puntaje base (el resultado de
  ``previous(...)``, la implementación ya portada en
  ``analytic_plan.py:240-248``), y decide: ``-1`` si cualquiera de los dos
  vetó, o la suma en otro caso — exactamente la lógica de corto-circuito de
  la referencia.

``kwargs.get('account')``/``kwargs.get('product')`` llegan como **PK crudo**
(igual que ``kwargs.get('company_id')``, ya usado por la base — ver
``tests/unit/analytic/test_analytic_plan.py``), no como instancia: se
resuelven con ``.filter(pk=...).first()``, el equivalente de
``self.env[...].browse(...)`` de la referencia sin ``env`` ambiental.
"""
import re

import fields
import models

from addons.account.models.account_account import AccountAccount
from addons.analytic.models.analytic_plan import AccountAnalyticApplicability
from addons.product.models import ProductCategory, ProductProduct
from orm.method_chain import chain_method
from tools.translate import _

#: ≙ ``selection_add=[('invoice', 'Invoice'), ('bill', 'Vendor Bill')]``
#: (odoo19c: :12-18). Etiquetas en español por convención del árbol
#: (``redaccion-tecnica-es.md``); el valor —lo que se guarda y compara— es
#: idéntico al de la referencia.
_BUSINESS_DOMAIN_EXTRA = [
    ('invoice', 'Factura de cliente'),
    ('bill', 'Factura de proveedor'),
]

#: ≙ ``re.split("[,;]", ...)`` (odoo19c: :68).
_ACCOUNT_PREFIX_SPLIT = re.compile(r'[,;]')


def _extend_selection_choices(model, field_name, extra_choices):
    """Amplía en sitio los ``choices`` de un campo ya declarado en ``model``.

    Ver docstring del módulo: no genera migración (no es una columna nueva),
    y ``field.choices`` es una lista mutable normal que ``Field.validate()``
    consulta en cada llamada — la ampliación es efectiva de inmediato.
    Idempotente: no duplica un valor ya presente (``ready()`` puede correr
    más de una vez en tests que recargan el registro de apps).
    """
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


def _default_display_account_prefix(instance):
    """≙ ``_compute_display_account_prefix`` (odoo19c: :78-81)."""
    return instance.business_domain in ('general', 'invoice', 'bill')


def _default_account_prefix_placeholder(instance):
    """≙ ``_compute_prefix_placeholder`` (odoo19c: :34-57). Sin filtro de
    compañía — ver docstring del módulo, la referencia tampoco lo aplica
    aquí."""
    account_expense = AccountAccount.objects.filter(
        account_type='expense').order_by('code').first()
    account_income = AccountAccount.objects.filter(
        account_type='income').order_by('code').first()

    if instance.business_domain == 'bill':
        account = account_expense
        account_prefixes = '60, 61, 62'
    else:
        account = account_income
        account_prefixes = '40, 41, 42'

    if account and account.code:
        prefix_base = account.code[:2]
        try:
            prefix_num = int(prefix_base)
            account_prefixes = f'{prefix_num}, {prefix_num + 1}, {prefix_num + 2}'
        except ValueError:
            # silent OK because un código no numérico (odoo19c: :49-55) deja
            # el placeholder por defecto; la referencia hace exactamente lo
            # mismo (try/except ValueError: pass, sin log).
            pass
    return _('e.g. %(prefix)s', prefix=account_prefixes)


def _account_prefix_categ_bonus(self, **kwargs):
    """El plus (o el veto, ``None``) que ``account_prefix``/``product_categ``
    aportan al puntaje — ``combine`` decide con esto y con el puntaje base
    (odoo19c: :59-76). Un veto se señala devolviendo ``None`` — la ausencia
    de puntaje, distinta de ``0`` (que sí suma)."""
    plus = 0
    if self.account_prefix:
        prefixes = tuple(
            p for p in _ACCOUNT_PREFIX_SPLIT.split(self.account_prefix.replace(' ', ''))
            if p
        )
        account_id = kwargs.get('account')
        account = (
            AccountAccount.objects.filter(pk=account_id).first() if account_id else None
        )
        if account is not None and account.code and account.code.startswith(prefixes):
            plus += 1
        else:
            return None
    if self.product_categ_id is not None:
        product_id = kwargs.get('product')
        product = (
            ProductProduct.objects.filter(pk=product_id).first() if product_id else None
        )
        product_categ = getattr(product, 'categ', None) if product is not None else None
        if product_categ is not None and product_categ.pk == self.product_categ_id:
            plus += 1
        else:
            return None
    return plus


def _combine_score_with_bonus(bonus, base_score):
    """≙ ``if score == -1: return -1; ...; return score`` (odoo19c: :60-76).

    ``bonus is None`` es el veto de ``_account_prefix_categ_bonus``; un
    ``base_score`` de ``-1`` (de la base ya portada) también corta corto,
    igual que la referencia."""
    if base_score == -1 or bonus is None:
        return -1
    return base_score + bonus


def apply_account_extensions():
    """Cuelga los 3 símbolos de la referencia sobre
    ``account.analytic.applicability``. Ver docstring del módulo.

    Cableada en ``AccountConfig.ready()`` vía ``_EXTENSIONES``. Invocable a
    mano; ver ``tests/unit/account/test_account_analytic_plan.py``.
    """
    _extend_selection_choices(
        AccountAnalyticApplicability, 'business_domain', _BUSINESS_DOMAIN_EXTRA,
    )
    _add_if_absent(
        AccountAnalyticApplicability, 'display_account_prefix',
        fields.NonStored(
            default=_default_display_account_prefix,
            help_text='Odoo display_account_prefix (compute, store=False). '
                       'Si el campo account_prefix debería mostrarse para '
                       'este dominio de negocio.',
        ),
    )
    _add_if_absent(
        AccountAnalyticApplicability, 'account_prefix_placeholder',
        fields.Char(
            store=False, default=_default_account_prefix_placeholder,
            help_text='Odoo account_prefix_placeholder (compute, '
                       'store=False). Ejemplo de prefijo según la primera '
                       'cuenta de gasto/ingreso del plan de cuentas.',
        ),
    )
    _add_if_absent(
        AccountAnalyticApplicability, 'account_prefix',
        fields.Char(
            blank=True, default='',
            help_text='Odoo account_prefix. Prefijos de cuenta contable '
                       'sobre los que aplica esta regla de aplicabilidad.',
        ),
    )
    _add_if_absent(
        AccountAnalyticApplicability, 'product_categ',
        fields.Many2one(
            'product.ProductCategory', on_delete=models.SET_NULL,
            null=True, blank=True, related_name='analytic_applicabilities',
            help_text='Odoo product_categ_id. Categoría de producto sobre '
                       'la que aplica esta regla.',
        ),
    )

    chain_method(
        AccountAnalyticApplicability, '_get_score',
        _account_prefix_categ_bonus, combine=_combine_score_with_bonus,
    )
