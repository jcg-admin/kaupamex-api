"""Addon ``purchase_stock`` — la compra que mueve inventario.

Adaptación de Odoo ``purchase_stock`` (``odoo19c: addons/purchase_stock/``,
LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

**Sin imports a propósito.** Es el patrón del árbol (``addons/utm/__init__.py``
es la plantilla): importar ``models``/``report``/``wizard`` aquí los cargaría
en tiempo de import del paquete, cuando el registro de modelos de Django aún no
está poblado, y toda extensión sobre un modelo ajeno fallaría con
``AppRegistryNotReady``. Quien las carga es ``PurchaseStockConfig.ready()``.

``_create_buy_rules`` — el ``post_init_hook`` que NO se porta
===============================================================

La fuente declara en este archivo (``odoo19c: :9-15``) un gancho de
post-instalación:

.. code-block:: python

    def _create_buy_rules(env):
        warehouse_ids = env['stock.warehouse'].search([('buy_pull_id', '=', False)])
        warehouse_ids.write({'buy_to_resupply': True})

Su comentario explica para qué: si ``purchase_stock`` se instala **después** de
que ya existan almacenes, esos almacenes no tendrían regla de compra. El gancho
se la crea marcándoles ``buy_to_resupply``.

**Bloqueado por el mecanismo, no por los datos.** Medido:

.. code-block:: text

    grep -rn "post_init_hook" addons/ src/ --include=*.py   → 0

Este árbol no tiene ciclo de instalación de addons con ganchos: una app de
Django se declara en el grafo de manifiestos
(``src/config/settings/base.py:152``) y sus migraciones corren con ``migrate``;
no hay un momento «recién instalado» que disparar.

Las dos piezas que el gancho necesita **sí existen tras este pase**:
``StockWarehouse.buy_pull`` (columna) y ``StockWarehouse.buy_to_resupply``
(``property`` con *setter*), ambas en ``models/stock.py``. Así que el
equivalente de este gancho es **una migración de datos** —del orquestador, no
de este pase— con este cuerpo:

.. code-block:: python

    for warehouse in StockWarehouse.objects.filter(buy_pull__isnull=True):
        warehouse.buy_to_resupply = True

Se deja escrito aquí, con su origen citado, para que la migración no haya que
derivarla de nuevo.
"""
