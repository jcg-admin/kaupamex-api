"""``ir.http`` — bootstrap de sesión del cliente web (Odoo ``hr_timesheet``).

Adaptación de Odoo ``hr_timesheet/models/ir_http.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 43 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte BLOQUEADO — 0 de 2 símbolos
====================================

Medido por AST: 1 clase (``_inherit``, ``AbstractModel``), 2 métodos
(``session_info``, ``get_timesheet_uoms``).

======================================  ==================================
Símbolo de la referencia (línea)         Estado
======================================  ==================================
``session_info`` (:9-27)                 bloqueado
``get_timesheet_uoms`` (:29-43)          bloqueado
======================================  ==================================

La causa, medida
------------------

``src/addons/base/models/ir_http.py:177`` declara ``IrHttp`` con ``class
Meta: abstract = True`` — es utilería de slugs de URL (``slugify_one``), no
el bootstrap de sesión del cliente web de Odoo (``session_info``, que
inyecta al JS del navegador el factor de conversión de UOM por compañía).
Este stack es headless (DRF + React, sin cliente web de Odoo que consumir
un ``session_info`` ampliado); y aunque no lo fuera, colgar un campo/método
sobre una clase abstracta de Django no genera superficie real — mismo
patrón de bloqueo que ``res_config_settings.py`` de este mismo addon
(``Meta.abstract = True``).
"""


def apply_hr_timesheet_ir_http_extensions():
    """No-op declarado — ver el docstring del módulo."""
    return None
