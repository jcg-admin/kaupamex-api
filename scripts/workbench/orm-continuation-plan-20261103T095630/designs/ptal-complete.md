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
