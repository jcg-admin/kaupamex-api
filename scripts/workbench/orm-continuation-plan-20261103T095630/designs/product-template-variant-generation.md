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
