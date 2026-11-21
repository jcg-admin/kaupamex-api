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

## Implementación (2026-11-21)

- `addons/product/models/product_tag.py`: `ProductTag` deriva de
  `(models.BaseModel, TimeStampedModel)`; `product_template_ids` y
  `product_product_ids` con las tablas y columnas de la fuente
  (`odoo19c: addons/product/models/product_tag.py:21-33`), `product_ids`
  calculado con búsqueda (`:34-37`), `image` (`:43`) en lugar del
  `ImageMixin`, `ProductTag._compute_product_ids` (`:49-52`),
  `ProductTag.copy_data` (`:54-56`) y `ProductTag._search_product_ids`
  (`:58-62`). `_get_default_template_id` y `_get_default_variant_id`
  (`:12-16`) quedan a nivel de módulo y leen el entorno activo: la
  divergencia de mecanismo de `_get_default_color`, añadida a
  `scripts/divergencias_declaradas.txt`.
- **Migración 0052** `addons/product/migrations/0052_tag_basemodel.py`:
  copia `image_1920` a `image` antes de retirar las columnas del mixin, y
  las dos relaciones conservan tabla y filas — sólo se renombran sus
  columnas (`SeparateDatabaseAndState`).
- `src/orm/fields_relational.py`: `_reverse_one2many_convert_to_write`
  resolvía la tupla de ids con `browse` sobre la clase; ahora con el
  entorno del registro, como `record.env[self.comodel_name].browse` de la
  fuente (`odoo19c: odoo/orm/fields_relational.py:671-674`). Lo destapó el
  `default=` de un `Many2many` directo hacia un `BaseModel`.

Pruebas: `tests/unit/product/test_product_tag_basemodel.py` (6 casos).
Anulación: la unión, la búsqueda, la copia y el valor por defecto tiran su
caso; devolver `browse` a la clase tira los cuatro que crean por el ORM.
Subconjunto derivado: 5054 passed, 39 skipped, 8 xfailed.

## Defecto destapado por F2 sobre `11160e88`

`tests/unit/scripts/test_divergencias_declaradas.py` exige un motivo encima
de cada entrada de `scripts/divergencias_declaradas.txt`; la segunda entrada
de `product.tag` iba pegada a la primera. Se añade su línea de motivo.
