# product-uom-basemodel-0397 — `product.uom` como `BaseModel`, completo

Unidad hija de `basemodel-adoption-0397` (grupo `product`).

## Referencia

`odoo19c: addons/product/models/product_uom.py` (32 líneas): cabecera
(`:9-11`), `uom_id`, `product_id` (requeridos, indexados, `cascade`),
`barcode` (`index='btree_not_null'`, requerido, `copy=False`),
`company_id` (por defecto la empresa activa), `_barcode_uniq` (`:18`),
`_check_barcode_uniqueness` (`:20-26`, `@api.constrains('barcode')`) y
`_compute_display_name` (`:28-32`, con `show_variant_name` en el contexto).

## Estado del puerto (medido 2026-11-21)

`TimeStampedModel` puro. La comprobación contra las variantes vive en
`clean()`, que el `create`/`write` del ORM no llama; `_compute_display_name`
está declarado «no se porta» (divergencia en lugar de porte) y `__str__`
compone «para:» en español; `barcode` no es requerido, no lleva
`copy=False` y su índice no es parcial.

## Implementación (2026-11-21)

`addons/product/models/product_uom.py`: `ProductUom` deriva de
`(models.BaseModel, TimeStampedModel)`; `barcode` requerido, `copy=False`,
`index='btree_not_null'`; `ProductUom._check_barcode_uniqueness`
(`odoo19c: addons/product/models/product_uom.py:20-26`) es un
`@api.constrains('barcode')` y sustituye a `ProductUom.clean`;
`ProductUom._compute_display_name` (`:28-32`). `__str__` devuelve el
nombre para mostrar. Se retira del docstring el «no se porta».
**Migración 0054** `addons/product/migrations/0054_uom_basemodel.py`:
`barcode`, su índice parcial y el mensaje de la restricción.

Pruebas: `tests/unit/product/test_product_uom_basemodel.py` (5 casos);
`tests/unit/product/test_product_uom_source_names.py` lee el nombre con
`show_variant_name` (premisa del «para:» anterior). Anulación: sin el
decorador caen los dos casos de reutilización; sin la rama del contexto,
los dos del nombre. Subconjunto derivado (product, sale, stock, orm):
4464 passed, 39 skipped, 2 xfailed.
