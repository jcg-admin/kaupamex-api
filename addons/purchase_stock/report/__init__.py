"""Informes del addon ``purchase_stock``.

Vacío de imports por la misma razón que ``models/__init__.py``: lo que este
paquete contiene son extensiones que ``ready()`` aplicaría, no modelos que
importar temprano.

**Los cinco archivos de este directorio están NO PORTADOS**, cada uno con su
bloqueo medido en su propio docstring. Ninguno entra en
``PurchaseStockConfig._EXTENSIONES``: no hay función que invocar.

Se espeja además una particularidad de la fuente:
``odoo19c: addons/purchase_stock/report/__init__.py`` (6 líneas) importa
**cuatro de los cinco** módulos — ``stock_valuation_report`` no aparece. Ver el
hallazgo en el docstring de ese archivo.
"""
