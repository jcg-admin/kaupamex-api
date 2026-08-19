"""Extensión de ``hr.employee`` — lo que ``hr_skills`` le cuelga al empleado.

Adaptación de Odoo hr_skills/models/hr_employee.py (odoo-tools@622ddc2a,
odoo19c:, LGPL-3, 209 líneas) — atribución y aviso de licencia preservados
(DEC-KX-03).

Porte símbolo por símbolo — 6 campos + 8 métodos
==================================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``resume_line_ids`` (One2many, ``:17``)
     - sin código — reverso automático de
       ``hr_skills.HrResumeLine.employee`` (``related_name='resume_line_ids'``)
   * - ``employee_skill_ids`` (One2many, ``:18-19``)
     - sin código — reverso automático de
       ``hr_skills.HrEmployeeSkill.employee``
       (``related_name='employee_skill_ids'``)
   * - ``current_employee_skill_ids`` (compute, readonly=False, ``:20-21``)
     - propiedad de sólo lectura — la escritura anidada es parte del
       protocolo de comandos BLOQUEADO (ver ``hr_individual_skill_
       mixin.py``, DIVERGENCIA 3)
   * - ``skill_ids`` (Many2many, compute+store, ``:22``)
     - portado — columna real (``store=True``); recómputo
       ``_compute_skill_ids()`` disponible (sin motor de ``@api.depends``)
   * - ``certification_ids`` (One2many, compute, readonly=False, ``:23``)
     - propiedad de sólo lectura — ídem ``current_employee_skill_ids``
   * - ``display_certification_page`` (compute, ``:24``)
     - propiedad
   * - ``_compute_current_employee_skill_ids`` (``:26-30``)
     - portado — el cuerpo de la propiedad de arriba
   * - ``_compute_skill_ids`` (``:32-35``)
     - portado
   * - ``_compute_certification_ids`` (``:37-40``)
     - portado — el cuerpo de la propiedad ``certification_ids``
   * - ``_compute_display_certification_page`` (``:42-43``)
     - portado
   * - ``create`` (``:45-51``) / ``write`` (``:53-58``)
     - BLOQUEADOS — protocolo de comandos x2many (ver DIVERGENCIA 3 de
       ``hr_individual_skill_mixin.py``); sin ellos, la escritura anidada
       de habilidades desde el ``vals`` del empleado no tiene transporte
   * - ``_add_certification_activity_to_employees`` (``:60-144``)
     - BLOQUEADO por ausencia de ``Domain`` exportado (``fields.Domain`` —
       tarea **#356** de ``docs: source/fields/__init__.py``); depende
       además de ``hr.job.job_skill_ids`` (este mismo pase) y de
       ``activity_schedule`` — el bloqueo real es sólo ``Domain``
   * - ``_load_scenario`` (``:145-152``)
     - BLOQUEADO — ``convert.convert_file`` (carga de datos demo XML), sin
       vistas/datos XML en este pase (ver el manifest)
   * - ``get_internal_resume_lines`` (``:153-209``)
     - portado — DIVERGENCIA: sin el chequeo ``has_access('read')`` de la
       referencia (framework ACL de Odoo); la autorización por capacidad es
       responsabilidad de la capa DRF (``HasCapability``, CLAUDE.md de
       ``api``), no construida en este pase (sin vistas)

Divergencias declaradas
========================

1. **``relativedelta`` → aritmética de ``timedelta``.** ``python-dateutil``
   NO es dependencia del proyecto (medido: ``grep -i dateutil uv.lock`` →
   0 hits). ``get_internal_resume_lines`` sólo usa deltas de días
   (``relativedelta(days=±1)``), sustituibles 1:1 por ``timedelta``.
"""
from datetime import date, timedelta

import fields

from addons.base.models import ResUsers
from addons.hr.models.hr_employee import HrEmployee
from addons.hr_skills.models.hr_employee_skill import HrEmployeeSkill
from addons.hr_skills.models.hr_skill_type import HrSkillType
from orm.model_classes import extend_model


def _compute_current_employee_skill_ids(self):
    """≙ ``_compute_current_employee_skill_ids`` (``:25-28``)."""
    current_by_employee = HrEmployeeSkill.get_current_skills_by_employee(
        self.employee_skill_ids.all(),
    )
    return current_by_employee.get(self.pk, [])


def current_employee_skill_ids(self):
    """≙ ``current_employee_skill_ids`` — la propiedad de sólo lectura
    (ver la tabla de la cabecera)."""
    return self._compute_current_employee_skill_ids()


def _compute_skill_ids(self):
    """≙ ``_compute_skill_ids`` (``:30-33``)."""
    skill_ids = list(
        self.employee_skill_ids.values_list('skill_id', flat=True).distinct(),
    )
    self.skill_ids.set(skill_ids)
    return self.skill_ids


def _compute_certification_ids(self):
    """≙ ``_compute_certification_ids`` (``:35-38``) — el cuerpo de
    ``certification_ids``."""
    return self.employee_skill_ids.filter(skill_type__is_certification=True)


def certification_ids(self):
    """≙ ``certification_ids`` — la propiedad de sólo lectura."""
    return self._compute_certification_ids()


def _compute_display_certification_page(self):
    """≙ ``_compute_display_certification_page`` (``:40-41``)."""
    return HrSkillType.objects.filter(is_certification=True).exists()


def display_certification_page(self):
    """≙ ``display_certification_page`` — la propiedad."""
    return self._compute_display_certification_page()


@classmethod
def get_internal_resume_lines(cls, res_id, res_model):
    """≙ ``get_internal_resume_lines`` (``:143-186``) — DIVERGENCIA:
    sin el chequeo ``has_access('read')`` (ver la tabla de la cabecera)."""
    if not res_id:
        return []
    if res_model == 'res.users':
        user = ResUsers.objects.filter(pk=res_id).first()
        employee = user.employee if user is not None else None
        res_id = employee.pk if employee is not None else None
        if res_id is None:
            return []
    result = []
    employee_versions = list(
        HrEmployee.objects.get(pk=res_id).versions.order_by('date_version'),
    )
    if not employee_versions:
        return result
    interval_date_start = False
    current_date_start = None
    for i in range(len(employee_versions) - 1):
        current_version = employee_versions[i]
        next_version = employee_versions[i + 1]
        current_date_start = max(
            current_version.date_version,
            current_version.contract_date_start or date.min,
        )
        current_date_end = min(
            next_version.date_version - timedelta(days=1),
            current_version.contract_date_end or date.max,
        )
        if not current_version.job_title:
            if interval_date_start:
                previous_version = employee_versions[i - 1]
                result.append({
                    'id': previous_version.pk,
                    'job_title': previous_version.job_title,
                    'date_start': interval_date_start,
                    'date_end': current_date_start - timedelta(days=1),
                })
                interval_date_start = False
        elif (current_version.job_title != next_version.job_title
                or current_date_end + timedelta(days=1) != next_version.date_version):
            result.append({
                'id': current_version.pk,
                'job_title': current_version.job_title,
                'date_start': interval_date_start or current_date_start,
                'date_end': current_date_end,
            })
            interval_date_start = False
        else:
            interval_date_start = interval_date_start or current_date_start

    last_version = employee_versions[-1]
    if last_version.job_title:
        current_date_start = max(
            last_version.date_version,
            last_version.contract_date_start or date.min,
        )
        result.append({
            'id': last_version.pk,
            'job_title': last_version.job_title,
            'date_start': interval_date_start or current_date_start,
            'date_end': last_version.contract_date_end or False,
        })
    elif interval_date_start:
        previous_version = employee_versions[-2]
        result.append({
            'id': previous_version.pk,
            'job_title': previous_version.job_title,
            'date_start': interval_date_start,
            'date_end': current_date_start - timedelta(days=1),
        })
    return result[::-1]


def apply_hr_skills_hr_employee_extensions():
    """Cuelga sobre ``hr.employee`` lo que ``hr_skills`` le añade — ≙
    ``_inherit``."""
    extend_model(
        'hr', 'HrEmployee',
        campos={
            'skill_ids': fields.Many2many(
                'hr_skills.HrSkill', blank=True,
                related_name='employees_with_skill',
                help_text='Odoo skill_ids (compute+store) — sincronizar '
                          'con _compute_skill_ids().',
            ),
        },
        metodos={
            '_compute_current_employee_skill_ids': _compute_current_employee_skill_ids,
            '_compute_skill_ids': _compute_skill_ids,
            '_compute_certification_ids': _compute_certification_ids,
            '_compute_display_certification_page': _compute_display_certification_page,
            'get_internal_resume_lines': get_internal_resume_lines,
        },
        propiedades={
            'current_employee_skill_ids': current_employee_skill_ids,
            'certification_ids': certification_ids,
            'display_certification_page': display_certification_page,
        },
    )
