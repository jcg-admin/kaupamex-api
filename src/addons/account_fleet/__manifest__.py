# Adaptado de Odoo `account_fleet/__manifest__.py` (LGPL-3,
# odoo-tools@622ddc2a, odoo19c:) — atribución y aviso de licencia
# preservados (DEC-KX-03).
{
    'name': 'Puente Contabilidad ↔ Flota (account_fleet)',
    'version': '1.0',
    'category': 'Accounting/Accounting',
    'summary': 'Vincula facturas de proveedor con vehículos: crea el '
               'servicio de flota "Vendor Bill" al postear una línea con '
               'vehículo, y expone bill_count/account_move_ids en '
               'fleet.vehicle.',
    # `depends` MEDIDO contra los imports reales de este addon (los 4 modelos
    # que cuelga: account.AccountMove, account.AccountMoveLine,
    # fleet.FleetVehicle, fleet.FleetVehicleLogServices), no copiado de la
    # referencia (que declara sólo `fleet` + `account` — igual que aquí).
    'depends': [
        'account',   # AccountMove, AccountMoveLine
        'fleet',     # FleetVehicle, FleetVehicleLogServices, FleetServiceType
    ],
    # Licencia de la fuente de la que se adapta este addon, tal como su
    # manifest la declara (DEC-KX-03 punto 1): `account_fleet` en Odoo
    # Community es LGPL-3.
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    # `auto_install: True` en la referencia (se activa solo si `fleet` y
    # `account` están instalados). Aquí no hay instalador de módulos en
    # caliente — el alta es `INSTALLED_APPS` (pendiente, ver `__init__.py`).
    'auto_install': False,
}
