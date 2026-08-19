"""``project.collaborator`` — reglas de portal al activar hoja de horas
(Odoo ``hr_timesheet``).

Adaptación de Odoo ``hr_timesheet/models/project_collaborator.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 21 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte BLOQUEADO — 0 de 1 símbolo
====================================

Medido por AST: 1 clase (``_inherit``), 1 método
(``_toggle_project_sharing_portal_rules``).

======================================  ==================================
Símbolo de la referencia (línea)         Estado
======================================  ==================================
``_toggle_project_sharing_portal_rules``  bloqueado
(:9-17)
======================================  ==================================

La causa, medida
------------------

``grep -rln "project\\.collaborator\\|ProjectCollaborator" addons/project/``
→ **0 hits**: ``project.collaborator`` (compartición de proyecto con
usuarios de portal) no está portado en ``project``. El método además activa/
desactiva un ``ir.model.access``/``ir.rule`` por xmlid
(``hr_timesheet.access_account_analytic_line_portal_user``), mecanismo de
permisos por fila del cliente web de Odoo — este stack autoriza por
CAPACIDAD a nivel de vista DRF (``HasCapability``), no por
``ir.rule``/portal sharing.
"""


def apply_hr_timesheet_project_collaborator_extensions():
    """No-op declarado — ver el docstring del módulo."""
    return None
