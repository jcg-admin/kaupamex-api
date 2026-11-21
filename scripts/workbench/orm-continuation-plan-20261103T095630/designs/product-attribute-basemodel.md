# product-attribute-basemodel-0397 — `product.attribute` como `BaseModel`, completo

Unidad hija de `basemodel-adoption-0397` (grupo `product`, primero por no
tener FK salientes y ser comodelo de todo el clúster de variantes).

## Referencia

`odoo19c: addons/product/models/product_attribute.py` (168 líneas): la
restricción `_check_multi_checkbox_no_variant` (`:14-17`); `name`,
`active`, `create_variant`, `display_type` (seis valores, `:38-49`),
`sequence` (`default=20`, `index=True`); `value_ids`, `template_value_ids`,
`attribute_line_ids` (inversos); `product_tmpl_ids` (calculado almacenado,
`:66-70`); `number_related_products` (`:71`);
`_compute_number_related_products` (`:76-86`), `_compute_products`
(`:89-99`), `_onchange_display_type` (`:103-106`), `write` (`:110-134`),
`_unlink_except_used_on_product` (`:136-145`), `action_archive`
(`:149-155`), `action_open_product_template_attribute_lines` (`:157-165`) y
`_without_no_variant_attributes` (`:167-168`).

## Estado del puerto (medido 2026-11-21)

`TimeStampedModel` puro, 72 líneas: `name`, `create_variant`, tres de los
seis `display_type` y `sequence` con `default=10`. Las constantes de clase
`CREATE_*`/`DISPLAY_*` no tienen consumidores fuera del archivo y la fuente
no las declara: se retiran. ACL: las dos filas de la fuente ya están en
`addons/product/security/ir.model.access.csv`.

## Divergencia declarada

`name` sin `translate=True`, como `product.attribute.value` en este árbol:
el almacenamiento `jsonb` de los campos traducibles es TASK-GEN-0060.

## Radio a medir

Pruebas que crean atributos con `display_type` fuera de los tres valores
actuales, o `multi` con variantes (la restricción lo rehúsa); lecturas de
`sequence` por defecto 10.

## Implementación (2026-11-21)

`addons/product/models/product_attribute.py`: `ProductAttribute` deriva de
`(models.BaseModel, TimeStampedModel)` con los campos de la fuente y
`ProductAttribute._compute_number_related_products`
(`odoo19c: addons/product/models/product_attribute.py:75-86`),
`ProductAttribute._compute_products` (`:88-99`),
`ProductAttribute._onchange_display_type` (`:103-106`),
`ProductAttribute.write` (`:110-134`),
`ProductAttribute._unlink_except_used_on_product` (`:136-145`),
`ProductAttribute.action_archive` (`:149-155`),
`ProductAttribute.action_open_product_template_attribute_lines`
(`:157-165`) y `ProductAttribute._without_no_variant_attributes`
(`:167-168`); `_check_multi_checkbox_no_variant` (`:14-17`) es un
`CheckConstraint` de `Meta`. **Migración 0051**
`addons/product/migrations/0051_attribute_basemodel.py`: campos nuevos,
alteraciones, la restricción y `ComputeStoredFields` de
`product_tmpl_ids`.

Pruebas: `tests/unit/product/test_product_attribute_basemodel.py`
(9 casos). Premisas: `attribute_line_ids` es ahora un recordset, no un
gestor de Django, y
`tests/integration/product/test_product_variants_and_stock.py`,
`tests/integration/sale/test_product_attribute.py` y
`tests/unit/product/test_attribute_line_source_relation.py` lo leen con
`len()` y la iteración del recordset.

Anulación: productos, conteo (tira también las tres guardas que lo leen),
guarda de `write`, guarda de borrado, guarda de archivado, `onchange` y la
herramienta tiran sus casos. Subconjunto derivado: 5045 passed + los 3
premisas corregidas (19 passed), 8 xfailed.
