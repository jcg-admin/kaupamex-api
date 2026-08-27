"""``project_account`` — vocabulario contable de la rentabilidad de proyecto.

Adaptación de Odoo ``project_account`` (``odoo-tools@622ddc2a``, ``odoo19c:``,
licencia ``LGPL-3`` declarada en su ``__manifest__.py``) — atribución y aviso
de licencia preservados (DEC-KX-03).

Qué es: el puente ``account`` ↔ ``project`` que aporta al panel de
rentabilidad del proyecto las secciones "Facturas de proveedor", "Otros
ingresos" y "Otros costos". No declara ningún modelo propio: extiende
``project.Project`` desde ``ready()`` (mismo idioma que ``product_expiry`` /
``hr_timesheet``).

Medido contra la referencia (``odoo19c: addons/project_account/models/``):
**1 archivo de modelo, 1 clase (``_inherit``), 0 campos, 10 métodos**. El
desenlace símbolo por símbolo vive en ``models/project_project.py``: 2
portados (el vocabulario de etiquetas y secuencias del panel), 5 con arista de
bloqueo declarada y 3 de navegación pura del cliente web (no se portan, mismo
criterio que ``account_debit_note``). Los directorios ``views/``, ``i18n/`` y
``tests/`` de la referencia son del cliente web / harness de Odoo y no se
portan (criterio ya establecido en el árbol).

Este archivo NO importa ``models`` — el patrón local (``addons/utm``,
``addons/hr_timesheet``) deja el ``__init__.py`` raíz sin imports; la
extensión corre en ``ProjectAccountConfig.ready()``.
"""
