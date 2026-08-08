"""Datos de arranque de ``account_fleet`` — ≙ el ``data/`` del addon de
referencia (``odoo19c: account_fleet/data/fleet_service_type_data.xml``,
``odoo-tools@622ddc2a``).

Allá es un archivo XML que el cargador de módulos aplica al instalar. Aquí
el bloque es un módulo Python con su especificación, y una data-migration lo
aplica — mismo mecanismo que ``account/data/account_tags.py``
(``:ref:`h-api-263```).
"""
from .fleet_service_types import VENDOR_BILL_SERVICE_XMLID, seed_fleet_service_types

__all__ = ['VENDOR_BILL_SERVICE_XMLID', 'seed_fleet_service_types']
