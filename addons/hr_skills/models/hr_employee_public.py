"""Extensión de ``hr.employee.public`` — el reflejo público de las
habilidades del empleado.

Adaptación fiel de Odoo hr_skills/models/hr_employee_public.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3, 14 líneas) — atribución y aviso de
licencia preservados (DEC-KX-03). Porte completo — 5 de 5 campos.

Los cinco son ``related``/reversos sobre ``employee_id`` — el mismo patrón
de delegación que ``addons/hr/models/hr_employee_public.py`` ya usa para
``job_title``, ``share``, ``phone``… (propiedades que leen
``self.employee_id``). Ninguno necesita ``extend_model(campos=…)``: son
propiedades de sólo lectura.

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``resume_line_ids`` (``:9``)
     - propiedad — ``self.employee_id.resume_line_ids``
   * - ``employee_skill_ids`` (``:10-11``)
     - propiedad — ``self.employee_id.employee_skill_ids``
   * - ``current_employee_skill_ids`` (``related``, ``:12``)
     - propiedad — ``self.employee_id.current_employee_skill_ids``
   * - ``certification_ids`` (``related``, ``:13``)
     - propiedad — ``self.employee_id.certification_ids``
   * - ``display_certification_page`` (``related``, ``:14``)
     - propiedad — ``self.employee_id.display_certification_page``
"""
from orm.model_classes import extend_model


def resume_line_ids(self):
    """≙ ``resume_line_ids`` (``:9``)."""
    return self.employee_id.resume_line_ids.all() if self.employee_id_id else []


def employee_skill_ids(self):
    """≙ ``employee_skill_ids`` (``:10-11``)."""
    return self.employee_id.employee_skill_ids.all() if self.employee_id_id else []


def current_employee_skill_ids(self):
    """≙ ``current_employee_skill_ids`` (``:12``)."""
    return self.employee_id.current_employee_skill_ids if self.employee_id_id else []


def certification_ids(self):
    """≙ ``certification_ids`` (``:13``)."""
    return (self.employee_id.certification_ids
            if self.employee_id_id else [])


def display_certification_page(self):
    """≙ ``display_certification_page`` (``:14``)."""
    return bool(self.employee_id_id
                and self.employee_id.display_certification_page)


def apply_hr_skills_hr_employee_public_extensions():
    """Cuelga sobre ``hr.employee.public`` lo que ``hr_skills`` le añade —
    ≙ ``_inherit``."""
    extend_model(
        'hr', 'HrEmployeePublic',
        propiedades={
            'resume_line_ids': resume_line_ids,
            'employee_skill_ids': employee_skill_ids,
            'current_employee_skill_ids': current_employee_skill_ids,
            'certification_ids': certification_ids,
            'display_certification_page': display_certification_page,
        },
    )
