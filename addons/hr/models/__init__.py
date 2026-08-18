"""Modelos del addon ``hr`` (estructura Odoo: un archivo por modelo)."""
from .hr_contract_type import HrContractType
from .hr_department import HrDepartment
from .hr_departure_reason import HrDepartureReason
from .hr_employee_category import HrEmployeeCategory
from .hr_job import HrJob
from .hr_mixin import HrMixin
from .hr_payroll_structure_type import HrPayrollStructureType
from .hr_work_location import HrWorkLocation

__all__ = [
    'HrContractType', 'HrDepartment', 'HrDepartureReason',
    'HrEmployeeCategory', 'HrJob', 'HrMixin', 'HrPayrollStructureType',
    'HrWorkLocation',
]
