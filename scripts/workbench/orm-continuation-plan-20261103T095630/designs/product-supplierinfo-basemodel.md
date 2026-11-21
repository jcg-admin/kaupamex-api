# product.supplierinfo a BaseModel

Unidad `product-supplierinfo-basemodel-0397`, tramo product. Referencia
`odoo19c: addons/product/models/product_supplierinfo.py` (119 líneas).

## Estado heredado medido

`ProductSupplierinfo` era Django con `TimeStampedModel`. La plantilla y la
unidad se derivaban en `save()`, `price_discounted` y `product_variant_count`
eran propiedades, las invariantes de compañía y variante vivían en `clean()`,
y `_get_filtered_supplier` era un `classmethod` que recibía la lista de
tarifas. Tres frases de la prosa eran falsas o ya no se sostenían:

| Prosa | Medido | Veredicto |
|---|---|---|
| `Uom._compute_price` no acepta un `Decimal` | conserva el tipo del importe (`addons/uom/models/uom_uom.py`, `_like`) | falso |
| `_compute_price` no se porta porque es código muerto | `porte-completo-no-parcial.md` porta todo símbolo | se porta |
| `_compute_product_id` es plomería del cliente | es un `compute` almacenado de la fuente | se porta |

Y un defecto en un consumidor: `AccountMoveLine` leía
`getattr(first_seller, 'product_uom', None)`, un atributo que no existe, así
que la unidad del proveedor nunca llegaba a la línea de factura. La fuente lee
`seller_ids[:1].product_uom_id`
(`odoo19c: addons/account/models/account_move_line.py:884-891`).

## Implementación

- `addons/product/models/product_supplierinfo.py`: `ProductSupplierinfo`
  deriva de `(models.BaseModel, TimeStampedModel)`. `product_uom_id`,
  `product_id` y `product_tmpl_id` son calculados almacenados y precalculados,
  `price_discounted` calculado sin columna, `product_variant_count` `related`,
  y los `default` de compañía y moneda son los de la fuente. Métodos:
  `ProductSupplierinfo._compute_product_uom_id`
  (`odoo19c: addons/product/models/product_supplierinfo.py:60-63`),
  `ProductSupplierinfo._compute_price` (`:66-68`),
  `ProductSupplierinfo._compute_price_discounted` (`:71-74`),
  `ProductSupplierinfo._compute_product_tmpl_id` (`:77-80`),
  `ProductSupplierinfo._compute_product_id` (`:83-86`),
  `ProductSupplierinfo._onchange_product_tmpl_id` (`:89-92`),
  `ProductSupplierinfo.get_import_templates` (`:95-99`),
  `ProductSupplierinfo._sanitize_vals` (`:101-106`),
  `ProductSupplierinfo.create` (`:109-112`),
  `ProductSupplierinfo.write` (`:114-116`) y
  `ProductSupplierinfo._get_filtered_supplier` (`:118-119`), ahora sobre el
  recordset. Se retiran `ProductSupplierinfo.clean` y
  `ProductSupplierinfo.save`.
- `price` y `discount` siguen `Monetary`, con la razón de comparabilidad del
  docstring del módulo.
- `res.partner` es aquí un modelo de Django: `_get_filtered_supplier` lee
  `active` sin `sudo()`, y sin empresa activa deja pasar sólo las tarifas de
  todas las empresas.
- `ProductTemplate.product_variant_count` pasa de propiedad a campo calculado
  (`ProductTemplate._compute_product_variant_count`,
  `odoo19c: addons/product/models/product_template.py:413-415`): el
  `related` de la tarifa lo necesita.
- Consumidores:
  - `ProductProduct._prepare_sellers` usa `self.sudo()` y `env.company` y
    ordena el recordset, como la fuente (`odoo19c: product_product.py:1016-1018`);
  - `AccountMoveLine` (`addons/account/models/account_move_line.py`) lee la
    unidad de la primera tarifa;
  - la extensión de `purchase` (`addons/purchase/models/product.py`) es de
    instancia, como la fuente, y trata un `order_id` `None` igual que el
    recordset vacío;
  - los `seller_ids.all()` / `.exists()` de `purchase`, `purchase_stock` y
    `product` pasan a recordset.
- **Migración 0058** `addons/product/migrations/0058_supplierinfo_basemodel.py`:
  sólo metadatos de campo.

## Lo que destapó el porte en el ORM

Asignar `False` o un recordset vacío a un Many2one (`self.product_id = False`
en `_onchange_product_tmpl_id`) fallaba: el descriptor de Django sólo acepta
`None` o una instancia. `src/orm/models.py` adapta
`ForwardManyToOneDescriptor.__set__` (`_forward_set`) como
`Many2one.convert_to_cache` (`odoo19c: odoo/orm/fields_relational.py:329-346`).

## Premisas de prueba que cambian

Los consumidores de prueba de `_get_filtered_supplier` y `_prepare_sellers`
reciben un recordset; `get_import_templates` se llama sobre el modelo del
entorno; una variante vacía es un recordset vacío, no `None`; y la variante de
otra plantilla ya no la rechaza `clean()` sino que la limpia el `onchange`.

## Pruebas y anulación

`tests/unit/product/test_product_supplierinfo_basemodel.py`. Anulación: el
cálculo de la plantilla (sin `create`), `_sanitize_vals` (plantilla vacía
explícita), el de la unidad, el precio con descuento, el proveedor archivado,
el conteo de variantes y `_forward_set` tiran cada uno sus casos.
