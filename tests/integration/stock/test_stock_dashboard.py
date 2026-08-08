"""
Tests — Stock dashboard, decrement and configuration: retirado (parte HTTP).

Probaba ``/api/v2/admin/inventory/`` + ``/api/v2/admin/inventory/alerts/``
(UC-INV-01/02/04). El addon ``stock`` (sucesor de ``inventory``,
H-API-212 y hermanas) no tiene capa REST en absoluto: no existe
``views.py``/``serializers.py``/``urls.py`` bajo ``src/addons/stock/``
(verificado: ``find src/addons/stock -iname views.py -o -iname urls.py`` →
vacío), y ningún ``urls.py`` del árbol registra ``/admin/inventory/``. La
maqueta de dashboard (UC-INV-01) y el modelo ``StockAlert`` que alimentaba
tampoco tienen sucesor portado.

``InventoryService`` (UC-INV-02, decremento) **sí** existe y **sí** se
prueba a nivel de servicio — ver ``test_stock_adjustments.py`` (rehecho a
nivel de servicio en este mismo pase) y los tests de ``addons.sale.services``
que lo ejercen vía ``add_item_to_draft``/``confirm_draft_order``. Las partes
de ``StaticPageVersion``/``SiteSettings`` (UC-CFG-04/05) no son de ``stock``
ni de ``sale`` — quedan fuera del alcance de este pase.
"""
