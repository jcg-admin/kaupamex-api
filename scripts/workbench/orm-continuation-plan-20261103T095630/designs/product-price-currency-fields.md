# Moneda y precio de producto como campos calculados

Unidad `product-price-currency-fields-0397`, prerrequisito de
`product-combo-basemodel`: en la referencia, `product.combo.item` declara
`currency_id` y `lst_price` como `related` al producto, y aquí los dos eran
propiedades de Python, no campos.

## Estado heredado medido

- `ProductTemplate.currency` y `ProductTemplate.cost_currency` eran
  propiedades con otro nombre; la referencia declara los campos calculados
  `currency_id` y `cost_currency_id`
  (`odoo19c: addons/product/models/product_template.py:88-91`).
- `ProductProduct.currency`, `ProductProduct.price_extra`,
  `ProductProduct.lst_price` y `ProductProduct.list_price` eran propiedades.
  La referencia declara `price_extra` y `lst_price` calculados, `lst_price`
  con su inverso y convirtiendo por la unidad del contexto
  (`odoo19c: addons/product/models/product_product.py:25-33`), y `list_price`
  y la moneda le llegan por `_inherits`.
- La prosa decía que la conversión por unidad «no se porta: este archivo no
  conoce el contexto». Es falso: el entorno del recordset lleva el contexto.
- `ProductTemplateAttributeValue.currency_id` era una propiedad que leía la
  propiedad `currency` de la plantilla.

## Implementación

- `ProductTemplate.currency_id` y `ProductTemplate.cost_currency_id`:
  Many2one calculados sin columna, con `ProductTemplate._compute_currency_id`
  (`odoo19c: addons/product/models/product_template.py:257-260`) y
  `ProductTemplate._compute_cost_currency_id` (`:264-267`). La moneda de
  `res.company` se llama aquí `currency`, y la compañía principal la da
  `ResCompany.get_main_company`.
- `ProductProduct.price_extra` y `ProductProduct.lst_price`: calculados sin
  columna, con `ProductProduct._compute_product_price_extra`
  (`odoo19c: addons/product/models/product_product.py:319-321`),
  `ProductProduct._compute_product_lst_price` (`:325-335`) y el inverso
  `ProductProduct._set_product_lst_price` (`:309-316`). Son `Monetary` y no
  `Float` porque `list_price` y el `price_extra` de los valores de atributo ya
  lo son, y `lst_price` los suma.
- `ProductProduct.currency_id` y `ProductProduct.cost_currency_id`: `related`
  a la plantilla (lo que en la fuente da `_inherits`).
- Se retira la propiedad `ProductProduct.list_price`, que ocultaba la
  delegación de `_inherits` y no admitía escritura; el inverso de
  `lst_price` escribe `list_price` en la variante y la delegación lo lleva a
  la plantilla.
- `ProductTemplateAttributeValue.currency_id`: `related`
  (`odoo19c: addons/product/models/product_template_attribute_value.py:41`).
- Consumidores: `ProductPricelistItem` (`addons/product/models/
  product_pricelist_item.py`), la línea de compra
  (`addons/purchase/models/purchase_order_line.py`) y `ProductComboItem`
  (`addons/product/models/product_combo_item.py`) leen `currency_id` y
  `cost_currency_id`.

## Lo que no se cierra aquí

`env.company` no lee `allowed_company_ids` del contexto, así que
`with_company` no cambia la moneda de coste. Sucesor ya registrado:
`environment-companies-from-context-0485`.

## Pruebas

`tests/unit/product/test_product_price_currency_fields.py`: moneda con y sin
compañía, moneda de coste con la compañía activa, suma de extras,
conversión por la unidad del contexto, e inverso de `lst_price`.

## Lo que destapó el subconjunto derivado

Leer `lst_price` atraviesa ahora la delegación de `_inherits` hacia la
ficha, que comprueba el acceso de quien lee. La propiedad anterior leía la
FK de Django y no comprobaba nada. Dos lecturas sin usuario en el entorno
quedaron denegadas:

- `add_item_to_draft` (`addons/sale/services.py`), el `_cart_add` local. En la
  referencia el carrito opera como superusuario (`request.cart` es
  `order_sudo`, `odoo19c: addons/website_sale/controllers/cart.py:113-123`),
  así que el precio se lee con `sudo()`.
- el fixture `wishlist_item` de
  `tests/integration/test_v2_cart_wishlist_notifications.py`, que es código de
  prueba sin usuario: lee con `sudo()`.

Premisas de prueba que cambian: `list_price` ya no es propiedad de la
variante sino campo delegado
(`tests/unit/product/test_product_product_class_attributes.py`) y la moneda
de coste se llama `cost_currency_id`
(`tests/unit/product/test_product_template_company_id.py`).

Anulación: la compañía en la moneda, la compañía activa en la de coste, la
suma de extras, la conversión por unidad y la resta del extra en el inverso
tiran cada una sus casos. La primera versión de la prueba de moneda no
discriminaba (la compañía y la principal compartían moneda); ahora la
compañía lleva otra.
