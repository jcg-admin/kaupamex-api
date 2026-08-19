"""Modelos del addon ``purchase_stock``.

**Deliberadamente vacío de imports** — mismo criterio que
``addons.hr_hourly_cost.models`` / ``addons.account_fleet.models``:
``PurchaseStockConfig.ready()`` importa cada módulo y aplica su extensión, no
este paquete. En tiempo de import del paquete el registro de modelos aún no
está poblado y colgar un campo sobre ``stock.StockMove`` fallaría con
``AppRegistryNotReady``.

Este addon **no declara ningún modelo propio con ``_name`` nuevo** en el estado
en que queda este pase. La referencia sí declara uno —``vendor.delay.report``,
en ``report/vendor_delay_report.py``— y ahí está escrito por qué no se declara
aquí (es una vista SQL cuyas columnas de origen no existen todavía).

El orden de esta lista espeja el de ``odoo19c: addons/purchase_stock/models/
__init__.py`` (12 módulos); la lista viva es ``PurchaseStockConfig._EXTENSIONES``.
"""
