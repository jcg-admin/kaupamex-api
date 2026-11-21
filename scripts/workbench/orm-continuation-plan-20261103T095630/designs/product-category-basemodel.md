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
