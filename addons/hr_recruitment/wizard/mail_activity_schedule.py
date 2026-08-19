"""``mail.activity.schedule`` — filtrado por departamento en reclutamiento
(Odoo ``hr_recruitment``).

Adaptación de Odoo ``hr_recruitment/wizard/mail_activity_schedule.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 13 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte BLOQUEADO — 0 de 1 símbolo: el modelo destino no existe
==================================================================

``_compute_department_assignable`` (``:9-13``) marca el wizard asignable
por departamento cuando ``res_model == 'hr.applicant'``, encadenando sobre
el mismo método que ``addons.hr.wizard.mail_activity_schedule`` ya declaró
no-op por el mismo ausente. Medido: ``grep -rln "mail.activity.schedule"
addons/ src/`` → sólo la mención DEFERIDO de ``hr``, ningún porte. Mismo
DESCONOCIDO con condición de cierre que su hermano de ``hr``: se completa
cuando el wizard base exista en ``addons/mail``.
"""


def apply_hr_recruitment_mail_activity_schedule_extensions():
    """No-op declarado — ``mail.activity.schedule`` ausente (ver docstring)."""
    return None


__all__ = ['apply_hr_recruitment_mail_activity_schedule_extensions']
