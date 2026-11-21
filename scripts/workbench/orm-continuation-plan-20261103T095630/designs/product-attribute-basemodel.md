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
