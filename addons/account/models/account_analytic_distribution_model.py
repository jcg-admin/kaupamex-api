"""Lo que ``account`` le cuelga de ``account.analytic.distribution.model``.

Adaptación de Odoo
``addons/account/models/account_analytic_distribution_model.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 70 líneas, 4 ``def``: medido
por AST — ``account_prefix``, ``product_id``, ``product_categ_id``,
``prefix_placeholder`` como campos; ``_get_default_search_domain_vals``,
``_get_applicable_models``, ``_create_domain``, ``_compute_prefix_placeholder``
como métodos). Extiende ``account.analytic.distribution.model`` — ya portado
en ``analytic/models/analytic_distribution_model.py``.

Qué se porta: ``prefix_placeholder`` (1 de 4 símbolos)
=======================================================

**Único símbolo portado.** ``prefix_placeholder`` es ``fields.Char(compute=...)``
**sin** ``store=True`` en la referencia (``odoo19c:`` línea 26) — el mismo
patrón ``store=False`` que ``fiscal_country_codes``
(``res_currency.py:17``, ya el caso canónico de este árbol). Se declara con el
despachador ``fields.Char(store=False, default=...)``
(``orm/fields_textual.py``): sin columna, sin migración, valor recalculado en
cada lectura — exactamente lo que ``store=False`` promete.

Su cómputo (``_compute_prefix_placeholder``, odoo19c: líneas 53-70) sólo
necesita ``account.account`` (ya portado, ``account_account.py``) y la
compañía del propio registro. La referencia usa ``self.env.company``
(compañía **activa de la sesión**); aquí no existe ese contexto ambiental —
se usa ``self.company`` (el campo propio del registro, ya declarado en
``analytic_distribution_model.py:47-51``). Sin compañía fijada, la búsqueda
de la cuenta de gasto queda sin filtrar — mismo criterio que
``account_analytic_plan.py`` de este mismo tramo.

Los otros 3 símbolos — BLOQUEADO por alcance de migración
============================================================

``account_prefix`` (Char), ``product_id``/``product_categ_id`` (Many2one) son
columnas **nuevas** sobre un modelo del app **``analytic``**
(``account.analytic.distribution.model`` vive en
``addons/analytic/models/analytic_distribution_model.py``). Django asigna la
migración de un campo al ``app_label`` de **su modelo**, no al del archivo que
lo declara vía ``add_to_class`` — el mismo mecanismo que
``addons/account/models/product.py`` ya documenta para sus columnas en
``product.template``: *"el autodetector atribuye la migración al app_label
del modelo... las columnas se crean desde product/migrations/ aunque las
contribuya account"*.

Aquí el destino sería ``addons/analytic/migrations/``, que **no está en la
lista de archivos escribibles de este tramo** (sólo
``addons/account/migrations/**``). Añadir el campo sin su migración dejaría
un atributo Python que revienta en el primer ``INSERT`` real (columna
inexistente) — peor que no portarlo. Se declara BLOQUEADO, no se fabrica.

Cascada: sin ``account_prefix``/``product_id``/``product_categ_id``,
``_get_default_search_domain_vals`` (que añade sus dos llaves al dict
default), ``_get_applicable_models`` (que filtra por ``account_prefix``) y
``_create_domain`` (cuya única rama nueva es ``fname == 'account_prefix'``)
no tienen sobre qué operar — los tres quedan BLOQUEADOS por la misma causa,
no por decisión propia.

Sucesor: tarea PENDIENTE DE ASIGNAR — declarar ``addons/analytic/migrations/``
en el alcance de un pase futuro, portar los 3 campos + envolver los 3 métodos
(por closure sobre la función original, igual que
``account_analytic_plan.py`` hace con ``_get_score`` en este mismo tramo para
el caso que SÍ estaba desbloqueado).
"""
import fields

from addons.account.models.account_account import AccountAccount
from addons.analytic.models.analytic_distribution_model import (
    AccountAnalyticDistributionModel,
)
from tools.translate import _


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


def apply_account_analytic_distribution_model_extensions():
    """Cuelga ``prefix_placeholder`` sobre ``account.analytic.distribution.model``.

    Ver docstring del módulo para el porte de este único símbolo y el bloqueo
    de los otros 3. Wiring en ``AccountConfig.ready()`` — pendiente (sucesor:
    ``apps.py`` fuera del alcance de este tramo). Invocable a mano mientras
    tanto; ver ``tests/unit/account/test_account_analytic_distribution_model.py``.
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
