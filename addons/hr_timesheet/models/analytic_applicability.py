"""``account.analytic.applicability`` — dominio de negocio "Hoja de horas"
(Odoo ``hr_timesheet``).

Adaptación de Odoo ``hr_timesheet/models/analytic_applicability.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 15 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Medido por AST: 1 clase (``_inherit``), 1 campo (``selection_add``). Ningún
método.

===============================  ==========================================
Símbolo (línea)                  Desenlace
===============================  ==========================================
``business_domain`` (:11-14)     **portado** — ``selection_add=[('timesheet',
                                  'Timesheet')]``, vía el mismo helper
                                  ``_extend_selection_choices`` que
                                  ``account/models/account_analytic_plan.py``
                                  ya usa para ampliar este mismo campo con
                                  ``('invoice', ...)``/``('bill', ...)``.
===============================  ==========================================

``account.analytic.applicability`` ya está portado — ``api: addons/
analytic/models/analytic_plan.py`` (``AccountAnalyticApplicability``, cuyo
``help_text`` de ``business_domain`` anticipaba textualmente: *"otros
addons de Odoo extienden la selección — no aplica aquí"*). Este archivo es
ese "otro addon".
"""
from addons.analytic.models import AccountAnalyticApplicability

#: ≙ ``selection_add=[('timesheet', 'Timesheet')]`` (odoo19c: :11-14).
#: Etiqueta en español por convención del árbol (``redaccion-tecnica-es.md``);
#: el valor guardado es idéntico al de la referencia.
_BUSINESS_DOMAIN_EXTRA = [
    ('timesheet', 'Hoja de horas'),
]


def _extend_selection_choices(model, field_name, extra_choices):
    """Amplía en sitio los ``choices`` de un campo ya declarado en ``model``.

    Idéntico al de ``account/models/account_analytic_plan.py``: no genera
    migración (no es una columna nueva), y ``field.choices`` es una lista
    mutable normal que ``Field.validate()`` consulta en cada llamada — la
    ampliación es efectiva de inmediato. Idempotente.
    """
    field = model._meta.get_field(field_name)
    already_present = {value for value, _label in field.choices}
    for value, label in extra_choices:
        if value not in already_present:
            field.choices.append((value, label))
            already_present.add(value)


def apply_hr_timesheet_analytic_applicability_extensions():
    """Amplía ``business_domain`` con ``'timesheet'`` sobre
    ``analytic.AccountAnalyticApplicability``.

    La llama ``HrTimesheetConfig.ready()``.
    """
    _extend_selection_choices(
        AccountAnalyticApplicability, 'business_domain', _BUSINESS_DOMAIN_EXTRA,
    )
