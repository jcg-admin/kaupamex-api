# ptal-complete-0122 — porte completo de product.template.attribute.line

Etapa 2 del clúster de variantes. Medido contra
`odoo19c: addons/product/models/product_template_attribute_line.py`
(284 líneas, 22 símbolos de clase); el puerto declara 17. Ausentes:
`active` (`:18`), `value_count` (`:38`), `product_template_value_ids`
(`:39`, aquí existe como accesor inverso de la FK de PTAV),
`_compute_value_count` (`:44-47`), `_onchange_attribute_id` (`:49-58`),
`_check_valid_values` (`:60-78`), `create` (`:80-115`), `write`
(`:117-158`), `unlink` (`:160-192`),
`_update_product_template_attribute_values` (`:194-255`) y
`action_open_attribute_values` (`:268-284`).

## Símbolos que cambian

- `ProductTemplateAttributeLine.active`, `value_count` (calculado
  almacenado) y migración nueva con `ComputeStoredFields`.
- `_compute_value_count`, `_onchange_attribute_id`, `_check_valid_values`.
- `create`: reactiva la línea archivada con la misma configuración.
- `write`: rehúsa mover de plantilla o de atributo; al archivar vacía
  `value_ids`; llama a `_update_product_template_attribute_values` salvo el
  contexto `update_product_template_attribute_values=False`.
- `unlink`: retira los PTAV activos, borra o archiva la línea, y regenera
  variantes de las plantillas que la perdieron.
- `_update_product_template_attribute_values` sustituye a
  `addons/product/services.py::sync_template_values` (19 llamadores; tres
  archivos: `services.py`, `tests/integration/sale/test_product_attribute.py`,
  `tests/integration/product/test_product_variants_and_stock.py`).
- `action_open_attribute_values`.

## Divergencias a decidir midiendo

- El puerto declara `UniqueConstraint(product_tmpl_id, attribute_id)`
  (`unique_template_attribute`); la fuente no declara ninguna restricción.
  Con `active` y la reactivación de `create`, la restricción rechazaría la
  línea activa nueva junto a una archivada del mismo atributo. Se retira en
  la migración — porte, no divergencia.
- `Meta.ordering` (`sequence, id`) frente a `_order`
  (`sequence, attribute_id, id`).

## Radio

14 llamadas `line.write({'value_ids': …})` en tests: tras el porte crean
sus PTAV y sus variantes. Las pruebas que además crean PTAV a mano chocarán
con `_attribute_value_unique`, y las que crean variantes a mano con
`_combination_unique`. Son premisas de prueba que se corrigen leyendo el
PTAV/variante generados, no relajando el mecanismo.

## Implementación (2026-11-20)

- `addons/product/models/product_template_attribute_line.py`:
  `ProductTemplateAttributeLine.active` y `value_count`
  (`odoo19c: addons/product/models/product_template_attribute_line.py:18,38`),
  `_compute_value_count` (`:44-47`), `_onchange_attribute_id` (`:49-58`),
  `_check_valid_values` (`:60-78`), `create` (`:80-115`), `write`
  (`:117-158`), `unlink` (`:160-192`; el savepoint es
  `transaction.atomic`) y `_update_product_template_attribute_values`
  (`:194-255`). Se retira `unique_template_attribute` y `Meta.ordering`
  pasa a `sequence, attribute_id, id`.
- **Migración 0049** `addons/product/migrations/0049_attribute_line_complete.py`:
  opciones, retirada de la restricción, `active`, `value_count` y
  `ComputeStoredFields` para las filas existentes.
- `addons/product/services.py`: se retira `sync_template_values`;
  `combinations` llama a `_update_product_template_attribute_values`.
- `action_open_attribute_values` (`:268-284`) resuelve
  `product.product_template_attribute_value_view_tree` y `_view_form`, y las
  vistas de `product` no están portadas: sucesor **product-views-0122**.

## Pruebas

`tests/unit/product/test_ptal_complete.py` (11 casos). Premisas corregidas,
porque la línea ahora genera sus valores de plantilla y sus variantes:
`tests/unit/product/test_ptav_complete.py`,
`tests/unit/product/test_product_models.py`,
`tests/unit/product/test_product_attribute_value_complete.py`,
`tests/unit/product/test_variant_generation.py`,
`tests/unit/orm/test_new_record_nonstored_compute.py`,
`tests/integration/product/test_display_name_assignment.py`,
`tests/integration/product/test_product_attribute_custom_value.py` y
`tests/integration/sale/test_product_attribute.py` leen el PTAV generado
en vez de crearlo, y las que componen la variante a mano escriben la línea
con `create_product_product=False`, el contexto de la fuente (`:254`).

Anulación: reactivación, mover de plantilla, cambiar de atributo, vaciar al
archivar, las dos ramas de `_check_valid_values`, la regeneración de
`unlink`, `value_count` y el `onchange` tiran 1 de 11 cada uno; la llamada
de `write` a `_update_product_template_attribute_values` tira los 2 que
dependen de ella. Subconjunto derivado (product, sale, test_orm, orm):
4565 passed, 39 skipped, 8 xfailed.
