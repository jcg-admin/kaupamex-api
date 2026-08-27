"""``mail.activity.plan`` — el plan de actividades es asignable por
departamento en ``hr.applicant`` (Odoo ``hr_recruitment``).

Adaptación de Odoo ``hr_recruitment/models/mail_activity_plan.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 13 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte BLOQUEADO — 0 de 1 símbolo: el modelo destino no existe
==================================================================

La referencia extiende ``_inherit = 'mail.activity.plan'``. Medido en este
pase: ``grep -rln "mail.activity.plan\\|MailActivityPlan" addons/ src/`` →
el modelo NO está portado en ``addons/mail`` — mismo ausente que
``addons.hr.models.mail_activity_plan`` ya declaró (no-op idéntico, misma
causa raíz).

``_compute_department_assignable`` (``:9-13``) marca el plan asignable por
departamento cuando su ``res_model`` es ``'hr.applicant'`` — un ``elif``
sobre lo que ``hr`` ya cuelga para ``'hr.employee'``. Sin la clase base no
hay método previo del que relevarse ni columna que actualizar.

Sucesor: el mismo que ``addons.hr.models.mail_activity_plan`` — portar
``mail.activity.plan``/``mail.activity.plan.template`` a ``addons/mail``.
"""


def apply_hr_recruitment_mail_activity_plan_extensions():
    """No-op declarado — ``mail.activity.plan`` ausente (ver docstring)."""
    return None


__all__ = ['apply_hr_recruitment_mail_activity_plan_extensions']
