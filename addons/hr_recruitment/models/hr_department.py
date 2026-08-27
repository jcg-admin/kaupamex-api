"""``hr.department`` — el pulso de reclutamiento por departamento (Odoo
``hr_recruitment``).

Adaptación fiel de Odoo ``hr_recruitment/models/hr_department.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 35 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03). Porte completo — 3 campos + 2
computes, los 5 símbolos de la fuente.

``_inherit`` lo expresa ``extend_model('hr', 'HrDepartment', …)`` — par de
Django porque ``hr.HrDepartment`` no declara ``_name`` propio en este árbol.
"""
from django.apps import apps

import fields
from orm.environments import get_current_user
from orm.model_classes import extend_model


def new_applicant_count(department):
    """≙ ``_compute_new_applicant_count`` (``odoo19c: :16-25``).

    DIVERGENCIA: la fuente vela por ``hr_recruitment.group_hr_recruitment_
    interviewer`` (``self.env.user.has_group``); aquí ``has_group`` existe
    (``base.ResUsers.has_group``) y resuelve ``False`` sin la fila
    sembrada — el guard se conserva, sólo cambia su fuente de verdad.
    """
    user = get_current_user()
    if user is None or not user.has_group('hr_recruitment.group_hr_recruitment_interviewer'):
        return 0
    HrApplicant = apps.get_model('hr_recruitment', 'HrApplicant')
    return HrApplicant.objects.filter(
        department=department, stage__sequence__lte=1,
    ).count()


def recruitment_stats(department):
    """≙ ``_compute_recruitment_stats`` (``odoo19c: :27-35``) — devuelve
    ``(new_hired_employee, expected_employee)``, el par que la fuente
    calcula en un único ``_read_group`` sobre ``hr.job``."""
    HrJob = apps.get_model('hr', 'HrJob')
    jobs = HrJob.objects.filter(department=department)
    no_of_hired = sum(job.no_of_hired_employee for job in jobs)
    no_of_recruitment = sum(job.no_of_recruitment for job in jobs)
    return no_of_hired, no_of_recruitment


def new_hired_employee(department):
    return recruitment_stats(department)[0]


def expected_employee(department):
    return recruitment_stats(department)[1]


def apply_hr_recruitment_hr_department_extensions():
    """Cuelga sobre ``hr.department`` lo que ``hr_recruitment`` le añade —
    ≙ ``_inherit``. Los tres campos son compute puro (sin ``store``, sin
    columna): se instalan como propiedades de sólo lectura."""
    extend_model(
        'hr', 'HrDepartment',
        propiedades={
            'new_applicant_count': new_applicant_count,
            'new_hired_employee': new_hired_employee,
            'expected_employee': expected_employee,
        },
    )
