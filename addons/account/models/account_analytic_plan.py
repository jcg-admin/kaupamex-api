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
con AST al inicio de este tramo (``python3 -c "import ast..."`` sobre el
archivo de la referencia → una sola clase, ``AccountAnalyticApplicability``).

Qué se porta — 2 de los 3 métodos, y el vocabulario de ``business_domain``
============================================================================

**``business_domain`` (selection_add, odoo19c: líneas 10-18).** Amplía el
vocabulario de un campo YA declarado en la base
(``analytic_plan.py:206-213``: ``[('general', 'Miscelánea')]``) con
``invoice``/``bill``. Ampliar ``choices`` de un campo existente **no requiere
migración** — no es una columna nueva, es metadata Python de validación
(``Selection`` aquí es ``models.CharField``, sin ``CHECK`` de base de datos;
verificado: ``f.choices.append(...)`` + ``f.validate(...)`` acepta el valor
añadido sin tocar el esquema). Precedente conceptual ya escrito en este árbol:
``addons/stock/models/barcode.py`` — *"selection_add tiene equivalente aquí
—ampliar los choices de un campo existente—"* (bloqueado allí sólo porque el
modelo destino no existe; aquí sí existe). El ``ondelete`` de la referencia
(``:15-18``, cascada al retirar un valor) no tiene análogo — Django no
gestiona el ciclo de vida de un ``choices`` retirado; no aplica mientras sólo
se **añade**.

**``_compute_display_account_prefix`` / ``display_account_prefix``**
(odoo19c: líneas 78-81, 28-31) y **``_compute_prefix_placeholder`` /
``account_prefix_placeholder``** (odoo19c: líneas 32-57): ninguno de los dos
declara ``store=True`` en la referencia → ``store=False`` por defecto, igual
que ``prefix_placeholder`` de ``account_analytic_distribution_model.py`` en
este mismo tramo. Se declaran con ``fields.Char(store=False, ...)`` /
``fields.Boolean`` no-almacenado (ver ``_add_if_absent`` de abajo — ``Boolean``
no tiene despachador ``store=`` propio como ``Char``; se usa
``orm.fields_nonstored.NonStored`` directo, la misma clase que ``Char``
despacha internamente, ver su docstring: *"Sigue el protocolo de
contribute_to_class... para que funcione... en add_to_class"*).

Ninguno de los dos cómputos necesita ``account_prefix``/``product_categ_id``
(los dos campos bloqueados abajo) — sólo leen ``business_domain`` (ya
desbloqueado arriba) y ``account.account`` (ya portado). Se portan enteros,
sin recorte.

``_compute_prefix_placeholder`` **no filtra por compañía** en la referencia
(a diferencia de la de ``account_analytic_distribution_model.py``, que sí lo
hace vía ``_check_company_domain``) — se porta tal cual, sin inventar un
filtro que la fuente no tiene.

BLOQUEADO — ``account_prefix``, ``product_categ_id``, ``_get_score``
======================================================================

``account_prefix`` (Char) y ``product_categ_id`` (Many2one) son columnas
**nuevas** sobre ``account.analytic.applicability``, que vive en el app
``analytic``. Su migración correspondería a ``addons/analytic/migrations/``,
fuera de la lista de archivos escribibles de este tramo — mismo bloqueo,
palabra por palabra, que ``account_prefix``/``product_categ_id`` en
``account_analytic_distribution_model.py``.

``_get_score`` (odoo19c: líneas 59-76) **envuelve** el método del mismo
nombre ya portado en la base (``analytic_plan.py:240-248``) añadiendo
puntuación por ``account_prefix``/``product_categ_id`` — los dos campos
recién bloqueados. Sin ellos no hay rama nueva que envolver; envolverlo para
no añadir nada sería ruido sin efecto observable.

Sucesor: tarea PENDIENTE DE ASIGNAR — declarar ``addons/analytic/migrations/``
en el alcance de un pase futuro, portar los 2 campos y envolver ``_get_score``
por closure sobre la función original (técnica ya usada y probada aquí para
nada, porque no hizo falta: los dos símbolos SÍ portados no necesitaron
envolver un método existente).
"""
import fields

from addons.account.models.account_account import AccountAccount
from addons.analytic.models.analytic_plan import AccountAnalyticApplicability
from orm.fields_nonstored import NonStored
from tools.translate import _

#: ≙ ``selection_add=[('invoice', 'Invoice'), ('bill', 'Vendor Bill')]``
#: (odoo19c: :12-18). Etiquetas en español por convención del árbol
#: (``redaccion-tecnica-es.md``); el valor —lo que se guarda y compara— es
#: idéntico al de la referencia.
_BUSINESS_DOMAIN_EXTRA = [
    ('invoice', 'Factura de cliente'),
    ('bill', 'Factura de proveedor'),
]


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


def apply_account_analytic_plan_extensions():
    """Cuelga la extensión de ``account`` sobre ``account.analytic.applicability``.

    Amplía ``business_domain`` con ``invoice``/``bill`` y añade los dos
    campos ``store=False`` que dependen de ese vocabulario. Ver docstring del
    módulo para los 2 campos y el método bloqueados. Wiring en
    ``AccountConfig.ready()`` — pendiente (``apps.py`` fuera del alcance de
    este tramo; ver el sucesor). Invocable a mano mientras tanto; ver
    ``tests/unit/account/test_account_analytic_plan.py``.
    """
    _extend_selection_choices(
        AccountAnalyticApplicability, 'business_domain', _BUSINESS_DOMAIN_EXTRA,
    )
    _add_if_absent(
        AccountAnalyticApplicability, 'display_account_prefix',
        NonStored(
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
