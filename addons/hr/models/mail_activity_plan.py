"""``mail.activity.plan`` — el plan de actividades gana departamento (Odoo
``hr``).

Adaptación de Odoo hr/models/mail_activity_plan.py (odoo-tools@622ddc2a,
odoo19c:, LGPL-3, 45 líneas) — atribución y aviso de licencia preservados
(DEC-KX-03).

Porte BLOQUEADO — 0 de 5 símbolos: el modelo destino no existe
===============================================================

La referencia extiende ``_inherit = 'mail.activity.plan'`` (los planes de
actividades por lotes de ``mail``). Medido en este pase:
``grep -rln "mail.activity.plan\\|MailActivityPlan" addons/ src/`` → el
único hit es la mención DEFERIDO de ``hr_department.py`` — **el modelo no
está portado** en ``addons/mail`` (que sí trae ``mail.activity`` y
``mail.activity.type``, pero no los planes).

===========================================================  ==============
Símbolo de la referencia (línea)                             Estado
===========================================================  ==============
``department_id`` (M2O a ``hr.department``, compute+store,   bloqueado
``:11-13``)
``department_assignable`` (compute, ``:14``)                 bloqueado
``_check_compatibility_with_model`` (``:16-36``)             bloqueado
``_compute_department_assignable`` (``:38-41``)              bloqueado
``_compute_department_id`` (``:43-45``)                      bloqueado
===========================================================  ==============

Los cinco símbolos cuelgan del MISMO ausente: la clase
``mail.activity.plan`` con sus ``res_model``/``template_ids``. No hay mitad
portable — ``department_assignable`` es ``res_model == 'hr.employee'`` y
``res_model`` es una columna del modelo ausente; la validación cruza
``template_ids``, del hermano también ausente
(``mail_activity_plan_template.py`` de este mismo pase).

Sucesor: portar ``mail.activity.plan`` + ``mail.activity.plan.template`` a
``addons/mail`` es una iniciativa del addon ``mail``, no de ``hr`` (el
SITIO del archivo lo fija la referencia:
``odoo19c: addons/mail/models/mail_activity_plan.py``). DESCONOCIDO con
condición de cierre: este archivo se completa cuando esas dos clases
existan en ``addons/mail/models/``; hasta entonces la extensión es un no-op
declarado — mismo patrón que ``discuss_channel.py`` de este addon. También
desbloquearía ``hr_department.plan_ids``/``plans_count`` (deferidos en
``hr_department.py``) y ``wizard/mail_activity_schedule.py``.
"""


def apply_hr_mail_activity_plan_extensions():
    """No-op declarado — ver el docstring del módulo (``mail.activity.plan``
    ausente)."""
    return None


__all__ = ['apply_hr_mail_activity_plan_extensions']
