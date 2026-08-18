"""Modelos del addon ``hr`` (estructura Odoo: un addon, un archivo por modelo).

``hr_version`` se agrega aquí (tarea #513) — es un modelo de este mismo
addon (``odoo19c: addons/hr/models/hr_version.py``), no un addon separado.
Import ANTES de ``hr_payroll_structure_type``: ``hr_version.py`` lo importa a
nivel de módulo (no ``string`` lazy) para el helper
``_default_salary_structure_for_company``.
"""
from .hr_payroll_structure_type import HrPayrollStructureType
from .hr_contract_type import HrContractType
from .hr_department import HrDepartment
from .hr_departure_reason import HrDepartureReason
from .hr_employee_category import HrEmployeeCategory
from .hr_version import HrVersion
from .hr_employee import HrEmployee
from .hr_job import HrJob
from .hr_mixin import HrMixin
from .hr_work_location import HrWorkLocation

__all__ = [
    'HrContractType', 'HrDepartment', 'HrDepartureReason',
    'HrEmployee', 'HrEmployeeCategory', 'HrJob', 'HrMixin',
    'HrPayrollStructureType', 'HrVersion', 'HrWorkLocation',
]
