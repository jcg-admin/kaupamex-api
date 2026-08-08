"""Tests — addons ``product_matrix`` + ``sale_product_matrix``: retirado.

Este módulo probaba la grilla de variantes (Odoo ``product.template``
``product_add_mode`` + ``_get_template_matrix``) construida sobre el eje
``chartsize`` (``VariantType``/``VariantOption``/``ProductVariant``). Esa
familia se disolvió (H-API-212 y hermanas: ``variant`` desapareció, el
``product.ProductProduct`` **es** la variante — ver
``sale/models/sale_order_line.py:133``), y **ninguno de los dos addons que
consumían el eje se adaptó**:

- ``ProductMatrixConfig.build()`` (``src/addons/product_matrix/models/
  product_matrix_config.py:66-83``) lee ``product.variant_types``,
  ``variant.sku``, ``variant.effective_price()``, ``variant.stock`` — cero
  de esos cuatro existe en ``product.ProductTemplate``/``ProductProduct``
  (verificado: ``grep -rn "variant_types\\|effective_price" src/addons/product/``
  → vacío; ``ProductProduct`` no declara ``sku`` — es ``default_code``).
- ``SaleOrderMatrix.apply()`` (``src/addons/sale_product_matrix/models/
  sale_order_matrix.py:52,60``) hace
  ``SaleOrderLine.objects.update_or_create(order=order, variant=variant, …)``
  y ``SaleOrderLine.objects.filter(order=order, variant=variant)`` — el campo
  ``variant`` no existe en ``sale.SaleOrderLine`` (verificado:
  ``grep -n "variant" src/addons/sale/models/sale_order_line.py`` → sólo el
  comentario que documenta su retiro).

Los dos métodos son código muerto: cualquier llamada real levanta
``AttributeError``/``TypeError`` antes de tocar la base de datos. No es un
problema de estos tests — es que ninguno de los dos addons recibió el
rediseño que la fusión de ``variant`` en ``product`` exige (reconstruir la
grilla sobre ``ProductTemplateAttributeValue`` en vez de ``chartsize``). Se
documenta como hallazgo de código (no se rediseña aquí: excede el alcance de
un rewrite de tests) y el módulo se retira en vez de fallar en cada corrida.
"""
