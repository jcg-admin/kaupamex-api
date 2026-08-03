"""Datos semilla del addon ``base`` — equivalente nativo de ``base/data/*.xml``.

La referencia reparte la semilla **por modelo** (``odoo19c: base/data/`` tiene
``res_company_data.xml``, ``res_partner_data.xml``, …), así que aquí hay un
módulo por modelo y este ``__init__`` sólo re-exporta.
"""

from addons.base.data.res_company import (
    FOUNDER_COMPANY_CODE,
    FOUNDER_L1_SETTINGS,
    SYSTEM_COMPANY_CODE,
)

__all__ = [
    'FOUNDER_COMPANY_CODE',
    'FOUNDER_L1_SETTINGS',
    'SYSTEM_COMPANY_CODE',
]
