r"""``product.catalog.mixin`` — el stock en el catálogo, addon ``stock``.

Adaptación de Odoo ``stock/models/product_catalog_mixin.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 16 líneas) — atribución y aviso
de licencia preservados (DEC-KX-03).

Qué aporta ``stock`` al catálogo de productos: **un interruptor**. El catálogo
de ``product`` no sabe nada de existencias; ``stock`` le añade la pregunta
*"¿esta pantalla debe mostrar el disponible?"*, con respuesta ``False`` por
defecto y pensada para que cada documento concreto la reescriba —un albarán sí,
una lista de precios no—.

Porte símbolo por símbolo — 1 de 2
===================================

.. list-table::
   :header-rows: 1
   :widths: 44 14 42

   * - Símbolo (línea)
     - Estado
     - Razón
   * - ``_is_display_stock_in_catalog`` (``:15-16``)
     - portado
     - autónomo; ``False`` como punto de extensión, igual que la fuente
   * - ``_get_action_add_from_catalog_extra_context`` (``:9-13``)
     - **bloqueado**
     - extiende un método que ``product`` **no porta**, con causa ya medida

*Métrica:* entradas del cuerpo de ``class ProductCatalogMixin`` en el archivo de
la referencia, contadas por AST — 3, de las que ``_inherit`` no es un símbolo a
portar (aquí lo expresa la herencia de Python).
*Ciega a:* lo que otros addons cuelgan del mismo mixin.

El bloqueo, con su medición — NO es un diferimiento
====================================================

``_get_action_add_from_catalog_extra_context`` **sólo existe para extender** su
homónimo de ``product``: su cuerpo es ``{**super()…, 'display_stock': …}``.
Ese homónimo no está portado, y su ausencia ya está medida y declarada en
``addons/product/models/product_catalog_mixin.py:72-81``: construye un
``ir.actions.act_window`` que abre **dos vistas XML** —
``product_view_kanban_catalog`` y ``product_view_search_catalog``— que no
existen en este árbol (medido allí: **0** hits), y sin ellas la acción
apuntaría a nada.

Escribir aquí una extensión de un método inexistente produciría o bien un
``AttributeError`` en la primera llamada, o bien un método que nadie encadena —
las dos formas del "relleno" que ``auto-audit-before-writing.md`` prohíbe.

El **dato** no se pierde: ``_is_display_stock_in_catalog`` sí se porta, así que
cuando exista la ruta DRF que sustituya a la acción de ventana, el interruptor
ya está y sólo hay que leerlo. Sucesor: la misma tarea **#330** cubre el
catálogo de ``stock``; la vista que lo bloquea es de ``product``.

Divergencia declarada
======================

**D-1 — clase Python, no modelo abstracto de Django.** El mixin de ``product``
al que extiende ya es una clase Python plana
(``addons/product/models/product_catalog_mixin.py:99``) porque **ninguno de sus
símbolos es una columna**. Esta extensión hereda esa forma; es el mismo criterio
que ``stock_replenish_mixin.py`` declara en su D-1.
"""
from addons.product.models.product_catalog_mixin import ProductCatalogMixin


class StockProductCatalogMixin(ProductCatalogMixin):
    """``product.catalog.mixin`` extendido por ``stock`` — ≙ ``_inherit``."""

    _name = 'product.catalog.mixin'
    _description = 'Product Catalog Mixin'

    def _is_display_stock_in_catalog(self):
        """≙ ``_is_display_stock_in_catalog`` (``odoo19c: :15-16``).

        Punto de extensión: la referencia devuelve ``False`` y lo reescribe
        cada documento que sí quiere ver el disponible en el catálogo.
        """
        return False
