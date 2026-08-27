"""Modelos del addon ``hr_skills`` (estructura Odoo: un addon, un archivo por
modelo).

Orden de import: ``hr_skill_type`` primero — ``hr_individual_skill_mixin``
lo importa directo (para ``_default_skill_type``, no como string) y
``hr_skill``/``hr_skill_level`` lo referencian sólo por string
(``'hr_skills.HrSkillType'``), así que no imponen orden.

Las CUATRO extensiones de este addon sobre modelos ajenos
(``hr.employee``, ``hr.employee.public``, ``hr.job``, ``resource.resource``)
NO se importan aquí — van por ``apps.py.ready()`` vía ``importlib`` (mismo
patrón que ``addons/hr/models/__init__.py``, que tampoco importa sus propias
extensiones ``res_company.py``/``res_partner.py``/``resource.py``/etc.).
"""
from .hr_skill_type import HrSkillType
from .hr_skill import HrSkill
from .hr_skill_level import HrSkillLevel
from .hr_resume_line_type import HrResumeLineType
from .hr_resume_line import HrResumeLine
from .hr_individual_skill_mixin import HrIndividualSkillMixin
from .hr_employee_skill import HrEmployeeSkill
from .hr_job_skill import HrJobSkill

__all__ = [
    'HrEmployeeSkill', 'HrIndividualSkillMixin', 'HrJobSkill', 'HrResumeLine',
    'HrResumeLineType', 'HrSkill', 'HrSkillLevel', 'HrSkillType',
]
