"""``project.update`` — estadísticas de hoja de horas en el reporte de
avance (Odoo ``hr_timesheet``).

Adaptación de Odoo ``hr_timesheet/models/project_update.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 39 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte BLOQUEADO — 0 de 7 símbolos
====================================

Medido por AST: 1 clase (``_inherit``), 4 campos, 3 métodos
(``_compute_timesheet_percentage``, ``_compute_display_timesheet_stats``,
``create`` sobrescrito).

======================================  ==================================
Símbolo de la referencia                 Estado
======================================  ==================================
``display_timesheet_stats``              bloqueado
``allocated_time`` / ``timesheet_time``  bloqueado
``timesheet_percentage`` / ``uom_id``    bloqueado
``_compute_timesheet_percentage``        bloqueado
``_compute_display_timesheet_stats``     bloqueado
``create``                               bloqueado
======================================  ==================================

La causa, medida
------------------

``grep -rln "project\\.update\\|ProjectUpdate" addons/project/`` → **0
hits**: ``project.update`` (reporte periódico de avance de proyecto) no
está portado en ``project``. No hay clase destino sobre la que colgar
ninguno de los 7 símbolos.
"""


def apply_hr_timesheet_project_update_extensions():
    """No-op declarado — ver el docstring del módulo."""
    return None
