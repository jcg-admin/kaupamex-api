"""``hr_fleet`` — puente Empleados ↔ Flota (Odoo ``Fleet History``).

Adaptación de Odoo ``hr_fleet`` (``odoo-tools@622ddc2a``, ``odoo19c:``,
licencia ``LGPL-3`` declarada en su ``__manifest__.py``) — atribución y
aviso de licencia preservados (DEC-KX-03).

Qué es: un módulo puente (``auto_install: True`` en la referencia cuando
``hr`` y ``fleet`` están ambos instalados) que NO declara modelos propios:
vincula ``hr.employee`` con ``fleet.vehicle`` vía el contacto de trabajo
del empleado (``work_contact``), y mantiene los dos lados sincronizados —
al cambiar el conductor de un vehículo se resuelve su empleado, al cambiar
el contacto de trabajo de un empleado se actualizan sus vehículos, y la
baja de un empleado puede liberar su coche de empresa
(``wizard/hr_departure_wizard.py``).

Estructura — 8 archivos de extensión en ``models/`` + 1 en ``wizard/``
(los mismos nueve de la referencia), aplicados desde
``HrFleetConfig.ready()`` con el patrón
``apply_hr_fleet_<archivo>_extensions()``.

Alta en ``INSTALLED_APPS``: automática — ``LOCAL_APPS`` se deriva del grafo
de manifiestos (``config/settings/base.py``, ``_local_apps()``); el
``depends: ['hr', 'fleet']`` de este addon lo coloca después de ambos.

Wiring pendiente (fuera del alcance de este agente): las migraciones de las
columnas que este addon cuelga — ``mobility_card`` sobre ``hr.employee``
(vive en ``hr/migrations/``), y ``mobility_card``/``driver_employee_id``/
``future_driver_employee_id`` sobre ``fleet.vehicle``,
``driver_employee_id`` sobre ``fleet.vehicle.assignation.log`` y
``purchaser_employee_id`` sobre ``fleet.vehicle.log.services`` (viven en
``fleet/migrations/``) — la migración de una columna pertenece a la app
dueña del modelo (mismo criterio que ``account_fleet``). ``makemigrations``
es del orquestador.
"""
