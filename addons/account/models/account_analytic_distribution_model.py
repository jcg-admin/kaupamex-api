"""Lo que ``account`` le cuelga de ``account.analytic.distribution.model``.

Adaptación de Odoo
``addons/account/models/account_analytic_distribution_model.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 70 líneas, 4 ``def``: medido
por AST — ``account_prefix``, ``product_id``, ``product_categ_id``,
``prefix_placeholder`` como campos; ``_get_default_search_domain_vals``,
``_get_applicable_models``, ``_create_domain``, ``_compute_prefix_placeholder``
como métodos). Extiende ``account.analytic.distribution.model`` — ya portado
en ``analytic/models/analytic_distribution_model.py``.

Tarea #520 — los 3 símbolos restantes, portados
==================================================

``H-API-684`` (tramo anterior) dejó BLOQUEADOS estos 3 métodos porque su
alcance de escritura excluía ``addons/analytic/migrations/``. Ese bloqueo era
del alcance de la tarea, no del ORM — ver
:ref:`h-docs-194`. Con ``addons/analytic/migrations/`` en el alcance de esta
tarea, los 4 ``def`` de la referencia quedan **completos**: los 3 campos
(``account_prefix``, ``product``, ``product_categ``) y los 3 métodos que
dependían de ellos.

``account_prefix``/``product``/``product_categ`` → nuevas columnas en
``analytic``
----------------------------------------------------------------------------

Igual mecanismo que ``prefix_placeholder`` no necesitaba (por ser
``store=False``) y que ``account/models/product.py`` ya documenta para sus
columnas en ``product.template``: el autodetector de Django atribuye la
migración al ``app_label`` del **modelo** (``analytic``, porque
``account.analytic.distribution.model`` vive en
``addons/analytic/models/analytic_distribution_model.py``), no al del archivo
que la declara vía ``add_to_class``. Su migración aterriza en
``addons/analytic/migrations/``.

``product``/``product_categ`` son FK simples a ``product.ProductProduct`` /
``product.ProductCategory`` (ya portados). Sin ``check_company`` — este ORM
no tiene ese constraint declarativo; ver el mismo criterio ya fijado para
``product_id``/``product_categ_id`` de ``account_analytic_line.py`` en este
mismo tramo.

Los 3 métodos, con el idioma de este árbol (``chain_method``)
-----------------------------------------------------------------

La referencia los escribe como ``_inherit`` + ``super()`` — este idioma no
tiene ``super()`` (``orm/method_chain.py``). Cada uno se instala con
``chain_method``:

- ``_get_default_search_domain_vals`` (``odoo19c:`` líneas 78-84) —
  ``super() | {'product_id': False, 'product_categ_id': False}``. Semántica de
  **combinación** (ambas mitades corren siempre): ``combine=`` fusiona el dict
  base con las 2 llaves nuevas (``None``, no ``False`` — el mismo vocabulario
  que ``company``/``partner`` ya usan en la base).
- ``_create_domain`` (``odoo19c:`` líneas 86-92) — rama nueva:
  ``if fname == 'account_prefix': return []`` (dominio vacío = matches
  todo — el filtro real de ``account_prefix`` no es de igualdad, corre
  aparte en ``_get_applicable_models``). Semántica de **relevo**: si
  ``fname`` no es ``account_prefix``, devuelve ``None`` y ``chain_method``
  cae a la implementación base.
- ``_get_applicable_models`` (``odoo19c:`` líneas 94-99) — post-filtro sobre
  el queryset base por sub-cadena de ``account_prefix`` (delimitador
  ``[;,]\\s*``, igual que la referencia). Semántica de **combinación**: la
  función nueva sólo extrae ``vals.get('account_prefix')`` (lo único que el
  post-filtro necesita); ``combine`` recibe ese valor y el queryset base, y
  aplica el filtro.

``_get_default_search_domain_vals`` y ``_get_applicable_models`` son
``@classmethod``; ``_create_domain`` es ``@staticmethod`` en la base — los
tres los preserva ``chain_method`` (ver la tabla de su docstring).
"""
import re

import fields
import models

from addons.account.models.account_account import AccountAccount
from addons.analytic.models.analytic_distribution_model import (
    AccountAnalyticDistributionModel,
)
from addons.product.models import ProductCategory, ProductProduct
from orm.method_chain import chain_method
from tools.translate import _

#: ≙ ``re.compile(r'[;,]\s*')`` (odoo19c: :39). Compilado una vez — se usa en
#: cada llamada a ``_get_applicable_models``.
_ACCOUNT_PREFIX_DELIMITER = re.compile(r'[;,]\s*')


def _default_prefix_placeholder(instance):
    """≙ ``_compute_prefix_placeholder`` (odoo19c: :53-70), ver docstring del
    módulo para la sustitución de ``self.env.company`` por ``self.company``.
    """
    accounts = AccountAccount.objects.filter(account_type='expense')
    if instance.company_id is not None:
        accounts = accounts.filter(company=instance.company_id)
    expense_account = accounts.order_by('code').first()

    account_prefixes = '60, 61, 62'
    if expense_account and expense_account.code:
        prefix_base = expense_account.code[:2]
        try:
            prefix_num = int(prefix_base)
            account_prefixes = f'{prefix_num}, {prefix_num + 1}, {prefix_num + 2}'
        except ValueError:
            # silent OK because un código no numérico (odoo19c: :64-68) deja
            # el placeholder por defecto; la referencia hace exactamente lo
            # mismo (try/except ValueError: pass, sin log).
            pass
    return _('e.g. %(prefix)s', prefix=account_prefixes)


def _add_if_absent(model, name, field):
    """Idempotente — mismo helper que ``account/models/product.py`` (``ready()``
    puede correr más de una vez en tests que recargan el registro)."""
    if not any(f.name == name for f in model._meta.get_fields()):
        model.add_to_class(name, field)


def _default_search_domain_vals_extra(cls):
    """≙ la mitad nueva de ``_get_default_search_domain_vals``
    (odoo19c: :81-84): ``product``/``product_categ`` sin fijar. El resto del
    dict (``company``/``partner``) lo aporta la base — ver ``combine``."""
    return {'product': None, 'product_categ': None}


def _merge_default_search_domain_vals(new, previous):
    """``combine`` de ``_get_default_search_domain_vals`` — ≙ el ``|`` de la
    referencia (odoo19c: :81): las dos mitades conviven siempre."""
    return previous | new


def _create_domain_account_prefix(fname, value):
    """≙ la rama nueva de ``_create_domain`` (odoo19c: :86-89):
    ``account_prefix`` no filtra por igualdad — el filtro real está en
    ``_get_applicable_models``. Devuelve ``None`` para el resto de campos,
    que ``chain_method`` releva a la implementación base (semántica de
    relevo, no de combinación — aquí sólo UNA rama debe ganar)."""
    if fname == 'account_prefix':
        return models.Q()
    return None


def _account_prefix_from_vals(cls, vals):
    """El único dato que el post-filtro de ``_get_applicable_models``
    necesita — el resto lo aporta el queryset base, que ``combine`` recibe
    como segundo argumento (odoo19c: :96-99: ``vals.get('account_prefix')``
    se lee directo, no vía el dict mergeado con los defaults)."""
    return vals.get('account_prefix')


def _matches_account_prefix(model, target_prefix):
    """≙ el predicado del ``.filtered(lambda model: ...)`` (odoo19c: :96-99)."""
    if not model.account_prefix:
        return True
    prefixes = _ACCOUNT_PREFIX_DELIMITER.split(model.account_prefix)
    return any((target_prefix or '').startswith(p) for p in prefixes)


def _filter_applicable_models_by_prefix(target_prefix, base_queryset):
    """``combine`` de ``_get_applicable_models`` — post-filtra el queryset
    base (odoo19c: :94-99). Devuelve un queryset nuevo, no una lista: el
    llamador (``_get_distribution``, en la base) itera sobre el resultado."""
    matching_pks = [
        m.pk for m in base_queryset if _matches_account_prefix(m, target_prefix)
    ]
    return base_queryset.model.objects.filter(pk__in=matching_pks)


def apply_account_extensions():
    """Cuelga los 4 símbolos de la referencia sobre
    ``account.analytic.distribution.model``. Ver docstring del módulo.

    Cableada en ``AccountConfig.ready()`` vía ``_EXTENSIONES``. Invocable a
    mano; ver ``tests/unit/account/test_account_analytic_distribution_model.py``.
    """
    _add_if_absent(
        AccountAnalyticDistributionModel, 'prefix_placeholder',
        fields.Char(
            store=False, default=_default_prefix_placeholder,
            help_text='Odoo prefix_placeholder (compute, store=False). '
                       'Ejemplo de prefijo de cuenta según la cuenta de '
                       'gasto de la compañía del registro.',
        ),
    )
    _add_if_absent(
        AccountAnalyticDistributionModel, 'account_prefix',
        fields.Char(
            blank=True, default='',
            help_text='Odoo account_prefix. Esta distribución analítica '
                       'aplica a todas las cuentas contables que compartan '
                       'el prefijo especificado.',
        ),
    )
    _add_if_absent(
        AccountAnalyticDistributionModel, 'product',
        fields.Many2one(
            'product.ProductProduct', on_delete=models.CASCADE,
            null=True, blank=True, related_name='analytic_distribution_models',
            help_text='Odoo product_id (ondelete=cascade). Producto para el '
                       'que se usa esta distribución.',
        ),
    )
    _add_if_absent(
        AccountAnalyticDistributionModel, 'product_categ',
        fields.Many2one(
            'product.ProductCategory', on_delete=models.CASCADE,
            null=True, blank=True, related_name='analytic_distribution_models',
            help_text='Odoo product_categ_id (ondelete=cascade). Categoría '
                       'de producto que usa la cuenta analítica en el '
                       'default analítico.',
        ),
    )

    chain_method(
        AccountAnalyticDistributionModel, '_get_default_search_domain_vals',
        _default_search_domain_vals_extra,
        combine=_merge_default_search_domain_vals,
    )
    chain_method(
        AccountAnalyticDistributionModel, '_create_domain',
        _create_domain_account_prefix,
    )
    chain_method(
        AccountAnalyticDistributionModel, '_get_applicable_models',
        _account_prefix_from_vals,
        combine=_filter_applicable_models_by_prefix,
    )
