# El grupo de variantes de `product`: cuatro modelos que se llaman entre sí

Creado: 2026-11-20T15:36:39 (UTC). TASK-API-0122. Sucede a
`product-attribute-value-complete.md`, cuyo módulo declara la divergencia
de mecanismo que este grupo retira.

## Medido (`odoo19c: addons/product/models/`)

| Modelo | Fuente | Puerto | Falta |
|---|---|---|---|
| `product.template.attribute.line` | 284 líneas | 78 | `active`, `value_count`, `product_template_value_ids` declarado y diez métodos (`create`, `write`, `unlink`, `_update_product_template_attribute_values`, …) |
| `product.template.attribute.value` | 198 líneas | ~90 | once campos y doce métodos (`_check_valid_values`, `_get_combination_name`, …) |
| `product.template.attribute.exclusion` | 47 líneas | — | el modelo entero y sus dos filas de ACL |
| `product.template` (variantes) | `product_template.py:770-1400` | `addons/product/services.py` (100 líneas) | `_create_variant_ids` y once ayudantes como métodos del modelo |

Los cuatro son `TimeStampedModel`. La fuente está escrita sobre
recordsets (`filtered`, `mapped`, `with_context(active_test=False)`,
`_without_no_variant_attributes`): portar un modelo sin los otros obliga a
traducir cada llamada al manager de Django, que es la divergencia que ya
declara `product_attribute_value.py`.

`create`/`write`/`unlink` de la línea llaman
`product_tmpl_id._create_variant_ids()` y
`_update_product_template_attribute_values`; la exclusión llama
`_create_variant_ids`; PTAV llama `_get_combination_name` desde
`product.product`. No hay una pieza que cierre sola.

## Etapas

1. `basemodel-adoption-product-variant-cluster-0397`: los cuatro modelos
   (`product.template`, `product.product`, PTAL, PTAV) sobre
   `BaseModel`, sin cambio de conducta; se retiran las traducciones a
   manager de `product_attribute_value.py`. Precedente
   `designs/basemodel-adoption-uom.md`: medir antes qué consumidores leen
   con la ACL del usuario (los directorios de prueba de `sale`, `stock`,
   `purchase`, `mrp` corren hoy sin usuario).
2. `ptal-complete-0122`: campos y métodos de la línea, con
   `_update_product_template_attribute_values` en lugar de
   `services.sync_template_values`.
3. `product-template-attribute-exclusion-0122`: el modelo y sus dos filas.
4. `ptav-complete-0122`: campos y métodos de PTAV, `product_tmpl_id` y
   `attribute_id` almacenados.
5. `product-template-create-variant-ids-0122`: `_create_variant_ids` y
   sus ayudantes; `services.combinations` y sus consumidores pasan a los
   métodos.

Consumidores actuales de `addons/product/services.py` (grep, 2026-11-20T15:36:39):

          5 addons/product/services.py
          6 tests/integration/product/test_product_variants_and_stock.py
         14 tests/integration/sale/test_product_attribute.py
          2 tests/integration/test_orm/test_domain.py
          1 tests/unit/orm/test_contract_domains_reference.py
          1 tests/unit/tools/test_set_expression_against_the_reference.py
