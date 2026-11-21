# product-tag-basemodel-0397 — `product.tag` como `BaseModel`, completo

Unidad hija de `basemodel-adoption-0397` (grupo `product`).

## Referencia

`odoo19c: addons/product/models/product_tag.py` (62 líneas):
`_get_default_template_id` y `_get_default_variant_id` (`:12-16`, valor
por defecto desde el contexto), `name` (requerido, traducible),
`sequence`, `color`, `product_template_ids` y `product_product_ids`
(`:21-33`, con sus tablas de relación), `product_ids` (calculado con
búsqueda, `:34-37`), `visible_to_customers`, `image`, `_name_uniq`
(`:44-47`), `_compute_product_ids` (`:49-52`), `copy_data` (`:54-56`) y
`_search_product_ids` (`:58-62`).

## Estado del puerto (medido 2026-11-21)

`(ImageMixin, TimeStampedModel)`; los dos Many2many se llaman
`product_templates` y `product_variants` (la fuente: `product_template_ids`
y `product_product_ids`; consumidores: `addons/account/models/product.py`,
`addons/account/demo/account_demo.py`), `product_ids` es una `property`, y
el docstring declara como «no se porta» `_search_product_ids` y
`copy_data`: eso es divergencia en lugar de porte, y se porta.

Los nombres `product_templates`/`product_variants` no tienen consumidores
fuera de `addons/product/models/product_tag.py` (las coincidencias en
`account` son otros `related_name` y variables locales): se renombran a los
de la fuente con la misma tabla de relación. `name` sin `translate=True`,
como el resto del grupo, hasta TASK-GEN-0060.
