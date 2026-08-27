"""Modelos del addon ``hr_homeworking`` (estructura Odoo: un archivo por
modelo — los seis de la referencia).

Importa SOLO el modelo concreto (``hr.employee.location``). Los otros cinco
archivos son extensiones de modelos ajenos y los importa
``HrHomeworkingConfig.ready()`` — en tiempo de import de este paquete el
registro de modelos aún no está poblado y colgar sobre
``hr.HrEmployee``/``base.ResUsers`` fallaría con ``AppRegistryNotReady``
(mismo criterio que ``addons.account_fleet.models``).
"""
from addons.hr_homeworking.models.hr_homeworking import DAYS, HrEmployeeLocation

__all__ = ['DAYS', 'HrEmployeeLocation']
