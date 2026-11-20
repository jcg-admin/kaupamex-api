# `product.template.categ_id`: el nombre de la fuente de la categoría

Unidad `product-template-categ-id-0122` (TASK-API-0122), parte del sucesor
`product-fk-names-0122`.

## Contrato medido en la referencia

`odoo19c: addons/product/models/product_template.py:81` declara
`categ_id = fields.Many2one('product.category', 'Product Category', ...)`.
`product.product` lo hereda por `_inherits` y lo lee como `categ_id`. Este
puerto lo llamaba `categ`, y la variante lo delegaba con una propiedad
`categ`.

## Cambios

1. `ProductTemplate.categ` → `ProductTemplate.categ_id` en forma C.
   Migración `0031_template_categ_id`: dos operaciones `no-op` en
   `sqlmigrate`.
2. `ProductProduct.categ` → `ProductProduct.categ_id`: la delegación por
   `_inherits` toma el nombre de la fuente.
3. Lecturas: todo `.categ`, `getattr(x, 'categ', None)`,
   `select_related('categ')`, `select_related('…__categ')` y `categ__…` pasa
   a `categ_id`. Los `getattr` eran el riesgo silencioso: con el nombre viejo
   devuelven `None` sin error, y la regla de tarifa de categoría
   (`ProductPricelistItem.matches`) habría dejado de aplicar a todo producto.
   Puntos tocados: `_get_category_account` (`account`),
   `_account_prefix_categ_bonus` (`account_analytic_plan`),
   `ProductCategory.product_count`, `ProductTemplate` (propiedades de
   categoría), `get_total_routes`, `filter_has_routes`,
   `_search_filter_for_stock_putaway_rule` (`stock/models/product.py`),
   `StockLocation._get_putaway_strategy`, `StockMove`,
   `StockMoveLine.product_category_name`, `StockQuant.product_categ`,
   `StockQuant._get_removal_strategy`, `StockRule._get_rule` (y su
   `get_rule_for_routes`), `StockRule._search_rule`,
   `StockRule._search_rule_for_warehouses`,
   `StockWarehouseOrderpoint._get_default_route`,
   `ProductListView` y `_published_products` (`website_sale`),
   `WishlistView` y `WishlistItemSerializer` (`website_sale_wishlist`).
4. Las pruebas crean con `categ_id=`; el parámetro `categ` de
   `tests/factories/product_factory.make_product` se conserva como nombre
   del ayudante y pasa `categ_id=` al modelo.
5. `scripts/fk_naming_baseline.txt` retira `ProductTemplate.categ`; el censo
   `outputs/fk_reference_ondelete.tsv` nombra la fila `categ_id` (fuera de la
   población destructiva, pero el nombre viejo es la trampa de
   `product-pricelist-header.md`).

Búsqueda: `.categ`, `'categ'`, `"categ"`, `categ__`, `__categ'` y `categ=`
en `addons`, `src` y `tests`; ningún XML ni CSV de datos lo nombra. Sólo dos
símbolos se llamaban `categ`: el campo de la plantilla y la propiedad de la
variante.

## Símbolos que cambian

- `ProductTemplate.categ_id`
  (`odoo19c: addons/product/models/product_template.py:81`),
  `ProductProduct.categ_id`;
- `ProductPricelistItem.matches`, `ProductCategory.product_count`;
- los consumidores del punto 3;
- la migración `0031_template_categ_id`.

## Fuera de esta unidad, con su sucesor

- `ProductTemplate.company`, `ProductTemplate.uom`,
  `ProductProduct.product_tmpl` (unos 260 puntos de lectura) —
  `product-fk-names-0122`.

## Pruebas

`tests/unit/product/test_product_template_categ_id.py`: el nombre y la
columna; la variante delega `categ_id`; una regla de categoría alcanza a los
productos de su rama y no a los de otra. Control de anulación: devolver el
`getattr` de `ProductPricelistItem.matches` a `'categ'` hace caer
exactamente la prueba de la regla (1 failed, 2 passed).
