# product-template-crud-0122 — campos de la plantilla leídos de su variante y CRUD restante

Sucesor declarado por `product-template-variant-generation-0122`.

## Referencia

`odoo19c: addons/product/models/product_template.py`:

- `_compute_template_field_from_variant_field` (`:269-290`) y
  `_set_product_variant_field` (`:292-310`): el valor de la variante única,
  o el defecto con varias; al escribir, se propaga a la variante única
  (o a la única archivada).
- `standard_price` (`:100-106`, calculado no almacenado con inverso y
  búsqueda), `volume` (`:108-109`, almacenado), `weight` (`:111-113`,
  almacenado), `default_code` (`:153-155`, almacenado) y `barcode`
  (`:152`, no almacenado): `_compute_*`/`_set_*` en `:312-351,438-442`.
- `_get_related_fields_variant_template` (`:509-511`) y la copia a la
  primera variante en `create` (`:575-581`).
- `write`: `_update_uom` de las variantes al cambiar `uom_id`
  (`:586-588`), invalidación de imágenes de la variante (`:597-603`) y
  `combo_ids = False` al dejar de ser combo (`:604-606`).

## Estado del puerto (medido 2026-11-20)

- La plantilla almacena `standard_price`, `volume`, `weight` y
  `default_code` como columnas propias: no se leen de la variante.
- `barcode` es una `property` ad hoc que replica el helper sin nombrarlo.
- Radio: lecturas `template.<campo>` en el árbol ≈ 0; altas de plantilla
  con `default_code=` 10 y con `standard_price=` 1 (pasan por
  `objects.create`, que no llama al `create` del ORM).

## Plan

Portar los dos helpers, convertir los cinco campos a calculados con
inverso como la fuente (migración que copia cada columna de la plantilla a
su variante única antes de retirarla o recalcularla), sustituir la
`property` `barcode` por el campo calculado, y completar `create`/`write`.
Medir antes: `ProductProduct._update_uom` (`stock/models/product.py:1028`
existe; la base `product_product.py:1194` no), `combo_ids` del lado de la
plantilla, y los `objects.create(... default_code=...)` de las pruebas.

## Decisiones medidas

- `product.product` no declara campos de imagen (no hereda `ImageMixin`):
  la invalidación de `:597-603` no tiene sobre qué actuar. Sucesor
  **product-variant-images-0122** (las imágenes de la variante,
  `odoo19c: addons/product/models/product_product.py`).
- `ProductProduct._update_uom` de la base (`odoo19c:
  addons/product/models/product_product.py:1194-1197`, gancho que devuelve
  `True`) se porta; la extensión de `stock` ya existe
  (`addons/stock/models/product.py:1028`).
- Migración: antes de convertir las columnas de la plantilla, se copia cada
  valor no vacío a su variante única cuando la de ésta está vacía, para no
  perder datos; `standard_price` deja de tener columna en la plantilla
  (calculado no almacenado, como la fuente) y `volume`, `weight`,
  `default_code` se recalculan con `ComputeStoredFields`.
