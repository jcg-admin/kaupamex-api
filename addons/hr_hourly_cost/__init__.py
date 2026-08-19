"""``hr_hourly_cost`` — Costo por hora del empleado (Odoo ``hr_hourly_cost``).

Adaptación de Odoo ``hr_hourly_cost`` (``odoo-tools@622ddc2a``, ``odoo19c:``,
licencia ``LGPL-3`` declarada en su ``__manifest__.py``) — atribución y aviso
de licencia preservados (DEC-KX-03).

Qué es: un addon puente sin modelos propios que cuelga un único campo,
``hourly_cost``, sobre ``hr.employee`` (ya portado en
``addons/hr/models/hr_employee.py``). Lo consume ``hr_timesheet``
(``AccountAnalyticLine._hourly_cost()``, ``odoo19c: hr_timesheet/models/
hr_timesheet.py:498-500``) para valorizar las horas registradas.

Medido contra la referencia (``odoo19c: addons/hr_hourly_cost/models/``):
**1** archivo, **1** clase (``HrEmployee``, ``_inherit``), **1** campo
(``hourly_cost``). Ningún método. Símbolo por símbolo, sin recorte.

``hr.version`` — 0 hits, no BLOQUEADO
========================================

``grep -rn "hourly_cost" $ODOO19C/addons/hr/`` → 0. La referencia sólo
declara ``hourly_cost`` en ``hr.employee``; ``hr.version`` no lo toca. No hay
símbolo que bloquear en ese modelo.

Mecanismo — ``add_to_class`` desde ``ready()``, igual que
``product_expiry``/``account_fleet``: es el patrón ya establecido en este
árbol para un ``_inherit`` de addon sobre un modelo ajeno.

Instalación automática — sin wiring pendiente
================================================

A diferencia de la nota histórica de ``account_fleet/__init__.py`` (previa a
2026-08-14), ``LOCAL_APPS`` ya no es un literal a mano: se deriva del grafo de
addons (``config/settings/base.py::_local_apps``), que recorre todo
directorio bajo ``ADDONS_PATHS`` con ``__init__.py``
(``modules/module.py::get_modules``). Este addon entra a ``INSTALLED_APPS``
—y por tanto su ``ready()`` corre— sin que el orquestador toque
``config/settings/base.py``.

Wiring pendiente (fuera del alcance de este agente):

1. La migración que agrega la columna ``hourly_cost`` en ``hr.HrEmployee``
   vive en ``addons/hr/migrations/`` (la app dueña del modelo — mismo
   criterio que ``account_fleet``/``l10n_mx`` para columnas colgadas sobre
   modelo ajeno). ``add_to_class`` ya declara el campo en el registro; sin la
   migración, cualquier ``.save()`` que lo toque falla por columna
   inexistente.
"""
