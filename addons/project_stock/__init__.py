"""``project_stock`` — albaranes ligados a proyecto.

Adaptación de Odoo ``project_stock`` (``odoo-tools@622ddc2a``, ``odoo19c:``,
licencia ``LGPL-3`` declarada en su ``__manifest__.py``) — atribución y aviso
de licencia preservados (DEC-KX-03).

Qué es: el puente ``stock`` ↔ ``project`` — cada albarán (``stock.picking``)
puede pertenecer a un proyecto, y el proyecto sabe listar sus entregas,
recepciones y movimientos. No declara ningún modelo propio: extiende
``stock.StockPicking`` (la FK ``project``) y ``project.Project`` (la
capacidad de filtrado) desde ``ready()`` — mismo idioma que
``product_expiry`` / ``hr_timesheet``.

Medido contra la referencia (``odoo19c: addons/project_stock/models/``):
**2 archivos de modelo, 2 clases (``_inherit``), 1 campo, 4 métodos**. El
desenlace símbolo por símbolo vive en cada módulo espejo. Los directorios
``views/`` e ``i18n/`` de la referencia son del cliente web y no se portan
(criterio ya establecido en el árbol).

Este archivo NO importa ``models`` — el patrón local (``addons/utm``,
``addons/hr_timesheet``) deja el ``__init__.py`` raíz sin imports; la
extensión corre en ``ProjectStockConfig.ready()``.

Wiring pendiente (fuera del alcance de este agente): la migración de la
columna ``project_id`` sobre ``stock_picking`` va en la app DUEÑA del modelo
(``addons/stock/migrations/``) — mismo criterio que las columnas de
``hr_timesheet`` sobre ``analytic``/``project``.
"""
