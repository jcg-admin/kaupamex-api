# product-category-basemodel-0397 — `product.category` como `BaseModel`, completo

Unidad hija de `basemodel-adoption-0397` (grupo `product`).

## Referencia

`odoo19c: addons/product/models/product_category.py` (69 líneas):
`_inherit = ['mail.thread']`, `_parent_name`, `_parent_store`,
`_rec_name = 'complete_name'`, `_order`; `name` (índice trigram),
`complete_name` (calculado, recursivo, almacenado), `parent_id`,
`parent_path`, `child_id`, `product_count` (calculado), 
`product_properties_definition`; `_compute_complete_name` (`:29-35`),
`_compute_product_count` (`:37-44`), `_check_category_recursion`
(`:46-49`), `name_create` (`:51-54`), `_compute_display_name`
(`:56-61`, `hierarchical_naming`) y `copy_data` (`:63-69`).

## Estado del puerto (medido 2026-11-21)

`TimeStampedModel`; `complete_name` y `parent_path` se mantienen en
`save()` con `build_complete_name`, y la recursión se comprueba en
`clean()`; `product_count` es una `property`. El docstring declara «no se
porta» `name_create`, `copy_data` y el nombre según `hierarchical_naming`:
divergencia en lugar de porte; se portan.

## Implementación (2026-11-21)

- `addons/product/models/product_category.py`: `ProductCategory` deriva de
  `(models.BaseModel, MailThread, TimeStampedModel)`; `complete_name`
  calculado, recursivo y almacenado, `product_count` calculado,
  `product_properties_definition` como `PropertiesDefinition`;
  `ProductCategory._compute_complete_name`
  (`odoo19c: addons/product/models/product_category.py:28-34`),
  `ProductCategory._compute_product_count` (`:36-43`),
  `ProductCategory._check_category_recursion` (`:45-48`),
  `ProductCategory.name_create` (`:50-53`),
  `ProductCategory._compute_display_name` (`:55-60`) y
  `ProductCategory.copy_data` (`:62-68`). `ProductCategory.save` sólo
  mantiene `parent_path` en el camino de Django, como `hr.department`; se
  retiran `build_complete_name`, `clean` y la `property` `product_count`.
- **Migración 0055** `addons/product/migrations/0055_category_basemodel.py`:
  alteraciones y `ComputeStoredFields` de `complete_name`.
- Un padre vacío de un `BaseModel` es un recordset vacío, no `None`. Dos
  recorridos del árbol de categorías terminaban con `is not None` y no
  acababan: `addons/stock/models/stock_location.py` (reglas de ubicación)
  y `addons/stock/models/product.py::parent_route_ids`; colgaron
  `tests/integration/sale/test_stock_product_quantities.py::
  test_get_total_routes_unions_product_and_category_routes` y, con la lista
  creciendo, mataron dos trabajadores de `xdist`. Se recorren por verdad,
  como la fuente (`while categ:`), igual que las comprobaciones de la
  categoría de un producto en `addons/stock/models/product.py`,
  `addons/stock/models/stock_rule.py` (tres),
  `addons/account/models/product.py`,
  `addons/account/models/account_analytic_plan.py` y
  `addons/product/models/product_pricelist_item.py`. Barrido: ningún otro
  recorrido `while … is not None` sobre `.parent_id` recibe una categoría.

## Pruebas

`tests/unit/product/test_product_category_basemodel.py` (9 casos).
Premisas: `child_id` es un recordset
(`tests/unit/product/test_product_category_header.py`) y la guarda de
ciclos ya no está en `clean()`, sino al escribir el padre
(`tests/unit/product/test_product_models.py`). Escribir un ciclo lo
rechaza `_parent_store_update` («Recursion Detected.») antes de la
restricción, como en la fuente, así que la restricción se mide forzando el
ciclo por debajo del ORM. Anulación: el nombre completo (tira también el
nombre plano), el conteo, la restricción, el nombre según el contexto, la
copia y `name_create` tiran sus casos. Subconjunto derivado (product,
sale, stock, account, orm): 5724 passed + las 2 premisas corregidas.
