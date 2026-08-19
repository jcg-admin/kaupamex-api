"""Modelos del addon ``hr_timesheet`` (estructura Odoo: un archivo por
módulo — 12 de los 12 de la referencia, cada uno con desenlace declarado).

**Sólo importa el modelo propio** (``AccountAnalyticLineCalendarEmployee``)
— mismo criterio que ``addons.account_fleet.models``/
``addons.product_expiry.models``: los otros once archivos cuelgan
extensiones sobre modelos AJENOS (``hr.HrEmployee``, ``hr.HrEmployeePublic``,
``analytic.AccountAnalyticLine``, ``analytic.AccountAnalyticApplicability``,
``project.Project``, ``project.ProjectTask``, ``uom.Uom``,
``base.ResCompany``) y los cuelga ``HrTimesheetConfig.ready()``, no este
paquete — en tiempo de import del paquete el registro de modelos aún no está
poblado.
"""
from .account_analytic_line_calendar_employee import (
    AccountAnalyticLineCalendarEmployee,
)

__all__ = ['AccountAnalyticLineCalendarEmployee']
