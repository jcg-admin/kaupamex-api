"""Modelos del addon ``analytic`` (estructura Odoo: un archivo por modelo).

Puerto de Odoo Community `analytic/` (odoo-tools@622ddc2a, odoo19c:, LGPL-3).
Contabilidad analítica (planes jerárquicos + cuentas + apuntes +
distribución libre), **sin** el sistema de columna dinámica por plan de la
referencia (``account.analytic.line`` con una columna ``x_planN_id`` por
plan raíz, generada en runtime vía ``ir.model.fields`` + DDL). Django no
tiene meta-programación de esquema en el ORM (las migraciones son estáticas);
reimplementar ese mecanismo exigiría un generador de migraciones a medida,
fuera de alcance de este corte. Cada archivo de modelo documenta en su
propio docstring qué se simplifica y por qué — ver en particular
``analytic_plan.py`` (la decisión raíz) y ``analytic_mixin.py`` (la SQL de
Postgres que tampoco se porta, porque este proyecto usa MariaDB).

Modelos portados (7 ``_name`` de la referencia, todos presentes aquí):

- ``account.analytic.plan`` → ``AccountAnalyticPlan``
- ``account.analytic.applicability`` → ``AccountAnalyticApplicability``
- ``account.analytic.account`` → ``AccountAnalyticAccount``
- ``analytic.plan.fields.mixin`` → ``AnalyticPlanFieldsMixin`` (abstracto)
- ``account.analytic.line`` → ``AccountAnalyticLine``
- ``analytic.mixin`` → ``AnalyticMixin`` (abstracto)
- ``account.analytic.distribution.model`` → ``AccountAnalyticDistributionModel``

Los 2 ``_inherit`` de la referencia (``ir_config_parameter.py``,
``res_config_settings.py``) NO se portan en este addon — ver el resumen de
la tarea que generó este puerto para el detalle de a qué modelo apuntan y
qué haría falta para colgarles los campos correspondientes.
"""
from .analytic_plan import AccountAnalyticPlan, AccountAnalyticApplicability
from .analytic_account import AccountAnalyticAccount
from .analytic_mixin import AnalyticMixin
from .analytic_line import AnalyticPlanFieldsMixin, AccountAnalyticLine
from .analytic_distribution_model import AccountAnalyticDistributionModel

__all__ = [
    'AccountAnalyticPlan',
    'AccountAnalyticApplicability',
    'AccountAnalyticAccount',
    'AnalyticPlanFieldsMixin',
    'AccountAnalyticLine',
    'AnalyticMixin',
    'AccountAnalyticDistributionModel',
]
