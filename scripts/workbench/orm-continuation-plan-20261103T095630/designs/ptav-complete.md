# product.template.attribute.value completo (etapa 4 del cluster)

Unidad `ptav-complete-0122`, TASK-API-0122. Sucesor que el módulo
declaraba con TASK-API-0493. Orden: ver «Orden corregido» en
`product-variant-cluster.md`.

## Referencia

`odoo19c: addons/product/models/product_template_attribute_value.py:10-198`.

Medido contra `addons/product/models/product_template_attribute_value.py`:
portados `name`, `attribute_line_id`, `product_attribute_value_id`,
`price_extra` y la cabecera. Faltan:

| Símbolo | Fuente | Forma aquí |
|---|---|---|
| `ptav_active` | `:23` | `Boolean(default=True)`, columna |
| `product_tmpl_id`, `attribute_id` | `:51-54` | `related` almacenado e indexado; migración con relleno desde la línea |
| `currency_id`, `html_color`, `is_custom`, `display_type`, `image` | `:42,58-62` | `related` sin columna |
| `color`, `_get_default_color` | `:18-19,61` | `Integer(default=_get_default_color)`; callable a nivel de módulo (divergencia de mecanismo de `_get_default_color`, ya registrada) |
| `_attribute_value_unique` | `:64-67` | nombre conservado en `Meta.constraints`, en lugar de `unique_template_attribute_value` |
| `_check_valid_values` | `:69-79` | `@api.constrains` |
| `create`, `write` | `:81-115` | rehúsan escribir `ptav_product_variant_ids`, cambiar el valor o el producto |
| `unlink` | `:117-148` | quita de las variantes los valores de líneas de un solo valor, `_unlink_or_archive` de las variantes, borra o archiva cada valor en su propio savepoint (`transaction.atomic`, `tools.mute_logger`) |
| `_compute_display_name` | `:150-157` | `"<atributo>: <valor>"` |
| `_only_active`, `_without_no_variant_attributes`, `_ids2str`, `_get_combination_name`, `_filter_single_value_lines`, `_is_from_single_value_line` | `:159-198` | sobre recordsets, verbatim |

Y en `product.product`, que `unlink` necesita:
`_filter_to_unlink` y `_unlink_or_archive`
(`odoo19c: addons/product/models/product_product.py:744-781`).

## Lo que esta etapa no cierra

- `exclude_for` y la rama `'exclude_for' in values` de `write` (llama
  `_create_variant_ids`): son de `product-template-attribute-exclusion-0122`
  y `product-template-create-variant-ids-0122`. Quedan declarados en el
  módulo con esos sucesores.

## Pruebas

`tests/unit/product/test_ptav_complete.py`: los campos `related`
almacenados se rellenan desde la línea; `ptav_active` por defecto;
`_check_valid_values` rehúsa un valor ajeno a la línea; `write` rehúsa
cambiar el valor o escribir las variantes; `unlink` borra si puede y
archiva si no; `display_name`; `_get_combination_name` omite las líneas de
un solo valor y los atributos `no_variant`; `_unlink_or_archive` archiva la
variante que no se puede borrar. Anulación por método.
