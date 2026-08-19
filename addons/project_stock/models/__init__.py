"""Modelos del addon ``project_stock`` — albaranes ligados a proyecto.

Adaptación de Odoo ``project_stock`` (``odoo-tools@622ddc2a``, ``odoo19c:``,
LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Este addon **no declara modelos propios**: como la referencia, extiende los
que ya existen (``stock.picking``, ``project.project``). Cada archivo espeja
el nombre del suyo en la referencia y expone ``apply_project_stock_*_
extensions()``, que ``ProjectStockConfig.ready()`` invoca — el idioma de
extensión cross-app ya establecido en este árbol (``product_expiry``,
``hr_timesheet``, ``account_qr_code_*``). Por eso aquí no se importa nada:
sin modelo concreto no hay clase que registrar en el import de la app.
"""
