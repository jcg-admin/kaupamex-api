# Generación de variantes y exclusiones (etapas 3 y 5 del cluster, juntas)

Unidad `product-template-variant-generation-0122`, TASK-API-0122.

## Por qué juntas

`odoo19c: addons/product/models/product_template_attribute_exclusion.py:29-47`:
`create`/`write`/`unlink` llaman `product_tmpl_id._create_variant_ids()`;
`odoo19c: addons/product/models/product_template.py:770-870`
(`_create_variant_ids`) lee las exclusiones vía
`_filter_combinations_impossible_by_config`. Ninguna cierra sola.

## Referencia

- exclusión: el modelo entero (`:6-47`) y sus dos filas de ACL
  (`security/ir.model.access.csv:13,28`); `exclude_for` en PTAV (`:44-49`)
  y la rama de `write` de PTAV que regenera (`:113-114`).
- plantilla: `_create_variant_ids` (`:770-870`), `_prepare_variant_values`,
  `has_dynamic_attributes`, `valid_product_template_attribute_line_ids`,
  `_filter_combinations_impossible_by_config`,
  `_is_combination_possible_by_config`, `_get_own_attribute_exclusions`
  (`:902-1130`), y los ganchos de `create`/`write` (`:567-591`) con el
  contexto `create_product_product`.
- nombre: la fuente llama a las líneas `attribute_line_ids`; aquí el
  inverso es `attribute_lines` (8 apariciones). Se renombra.

## Radio a medir antes de implementar

- ¿`ProductTemplate.objects.create` pasa por el `create` del ORM? Si sí,
  toda plantilla creada en la suite generará su variante y los 68
  `ProductProduct.objects.create(` explícitos duplicarían la variante sin
  atributos (`_combination_unique` lo rehúsa entre activas).
- `make_product` crea ficha + variante a mano.

## Radio medido

`src/orm/models.py:326` (`AccessQuerySet`) no declara `create`:
`ProductTemplate.objects.create(...)` es el `QuerySet.create` de Django
(`model(**kw).save()`) y no pasa por `BaseModel.create`
(`src/orm/models.py:871`). El gancho de `create` de la plantilla sólo
alcanza a los llamadores del `create` del ORM
(`env['product.template'].create`, `ProductTemplate.create([...])`), no a
los 68 `ProductProduct.objects.create(` ni a `make_product`.

## Implementación — símbolos que cambian (2026-11-20)

Etapas 3 y 5 del clúster juntas: la exclusión sólo tiene sentido si
`_create_variant_ids` la lee, y la generación sólo es fiel si filtra por
exclusión.

- **Modelo nuevo** `ProductTemplateAttributeExclusion` en
  `addons/product/models/product_template_attribute_exclusion.py`, porte de
  `odoo19c: addons/product/models/product_template_attribute_exclusion.py:6-47`
  (campos, `create`, `unlink`, `write` que llaman a `_create_variant_ids`).
  Sus dos filas de ACL en `addons/product/security/ir.model.access.csv`
  (`odoo19c: addons/product/security/ir.model.access.csv`), y
  `tests/unit/product/test_product_security.py` pasa de 33 a 35 filas.
- **Migración 0047** `addons/product/migrations/0047_template_attribute_exclusion.py`:
  `AlterField` del `product_tmpl_id` de la línea (inverso
  `attribute_line_ids`) y `CreateModel` de la exclusión.
- **Migración 0048** `addons/product/migrations/0048_combination_indices_compute.py`:
  `combination_indices` pasa a calculado almacenado
  (`odoo19c: addons/product/models/product_product.py:59`) con
  `ComputeStoredFields` para las filas existentes.
- `ProductProduct._compute_combination_indices`
  (`odoo19c: addons/product/models/product_product.py:301-303`) sustituye a
  `build_combination_indices`, `refresh_combination_indices` y
  `COMBINATION_SEPARATOR`, que la fuente no tiene.
- `ProductTemplateAttributeLine._without_no_variant_attributes` y
  `_is_configurable`
  (`odoo19c: addons/product/models/product_template_attribute_line.py:257-271`);
  el inverso pasa de `attribute_lines` a `attribute_line_ids`
  (`addons/product/services.py` lo sigue).
- `ProductTemplateAttributeValue.write`: la rama `exclude_for` regenera
  variantes (`odoo19c: addons/product/models/product_template_attribute_value.py:113-114`).
- `ProductTemplate.create` y `write`
  (`odoo19c: addons/product/models/product_template.py:568-610`),
  `_create_variant_ids` (`:770-870`), `_prepare_variant_values` (`:871`),
  `has_dynamic_attributes` (`:879-887`),
  `valid_product_template_attribute_line_ids` (`:890-900`),
  `_get_own_attribute_exclusions` (`:990`),
  `_filter_combinations_impossible_by_config` (`:1076`) y
  `_is_combination_possible_by_config` (`:1113`).

Pendiente, con sucesor `product-template-crud-0122`: la copia de campos
relacionados en `create` y las ramas `uom_id`, imagen y `combo_ids` de
`write`. `product.attribute` es de Django: `has_dynamic_attributes` itera
por línea en vez de `mapped` relacional múltiple (TASK-API-0401).

## Pruebas y anulación

`tests/unit/product/test_variant_generation.py` (8 casos);
`tests/unit/product/test_product_models.py` cambia los dos casos de los
helpers retirados por `test_the_combination_indices_follow_the_values`.
Anulado cada mecanismo, cae exactamente su caso: filtro de exclusión,
gancho de `create`, guarda dinámica, cascada de archivado y filtro
`no_variant` — 1 de 8 en cada uno. Subconjunto derivado (product, sale,
test_orm, account, mail, orm, purchase): 5550 passed, 39 skipped,
8 xfailed.
- `ProductTemplate.check_combo_has_no_attributes`
  (`odoo19c: addons/product/models/product_template.py:460-462`) sólo sigue
  el renombre del inverso a `attribute_line_ids`; su prueba es
  `tests/unit/product/test_product_models.py`.
