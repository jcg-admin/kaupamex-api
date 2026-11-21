# product-pricelist-cluster-0397 — `product.pricelist` y `product.pricelist.item`

Unidades hijas de `basemodel-adoption-0397` (grupo `product`). Medición
hecha con un subagente de lectura (2026-11-21) y comprobada en sus puntos de
validación de prosa con `grep` en el árbol.

## Referencia y estado

- `odoo19c: addons/product/models/product_pricelist.py` (414 líneas): el
  puerto (125) declara cabecera y campos sin `required`/`translate`/
  valores por defecto; faltan `_default_currency_id`, los dominios de
  `item_ids`, `write`, `copy_data`, toda la familia de selección y precio
  (`_get_products_price` … `_compute_price_rule_multi`, `:90-286`), las
  tarifas por país y por cliente (`:288-385`), `get_import_templates`,
  `_unlink_except_used_as_rule_base` y `action_open_pricelist_report`.
- `odoo19c: addons/product/models/product_pricelist_item.py` (684 líneas,
  33 `def`): el puerto (461, 9 `def`) tiene los campos con cuatro
  `Monetary` donde la fuente declara `Float`, `price_markup` sin
  cómputo/inverso, y equivalentes con otro nombre y otra forma de
  `_is_applicable_for` (`matches`), `_compute_price` (`compute`) y
  `_compute_base_price` (`base_price_for`, que levanta
  `NotImplementedError` para `base='pricelist'`); faltan `create`,
  `write`, cinco restricciones como `@api.constrains`, los nueve
  `onchange`, las etiquetas y `_compute_price_before_discount`.

## Prosa heredada, validada

| Afirmación | Medido | Veredicto |
|---|---|---|
| la familia `_get_product_price` «se porta como `matches` y `best_rule_for`» | `best_rule_for` no está definido en el árbol (sólo citado en un docstring y en un test) | **falso** |
| la conversión de moneda no se porta porque no hay conversor con fecha y compañía | `ResCurrency._convert` existe (`src/addons/base/models/res_currency.py`) | **falso** |

## Consumidores

`sale` (dominio, `pricelist_id`, `_compute_has_active_pricelist`, la
extensión del ítem con `COMPUTE_PERCENTAGE`) y las pruebas de
`tests/unit/product/test_product_pricelist_*`. El precio de venta hoy es
`lst_price` (`addons/sale/services.py`, `sale_order_line.current_price`):
ninguna tarifa se consulta. En `product`, la fuente llama a la tarifa desde
`_get_contextual_price`/`_get_contextual_discount` y `_price_compute`, que
el puerto no tiene.

## Etapas, en orden de dependencia

1. `BaseModel` y paridad de campos de los dos modelos (cabeceras,
   valores por defecto, `Float`, `item_ids` con dominio, cómputos de
   empresa/moneda/markup/obligatoriedad, `_compute_display_name`).
2. Integridad: `create`/`write` del ítem, las cinco restricciones, `write`,
   `copy_data` y la guarda de borrado de la tarifa.
3. Precio de una regla: `_is_applicable_for`, `_compute_base_price` (con
   `_price_compute` en plantilla y variante, y `_convert`),
   `_compute_price`; sustituye `matches`/`compute`/`base_price_for` y
   repunta pruebas y la extensión de `sale`.
4. Selección y recursión: `_get_applicable_rules(_domain)`,
   `_compute_price_rule`, los cuatro envoltorios, `_price_get`,
   `_compute_price_rule_multi`, la rama `base='pricelist'`,
   `_compute_price_before_discount` y los `_get_contextual_*` de producto.
5. Etiquetas, `onchange`, tarifas por país y cliente (con
   `property_product_pricelist` de `res.partner`), importación y acción.
