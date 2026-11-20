# `product.pricelist`: la cabecera de la fuente y sus tres nombres

Unidad `product-pricelist-header-0122` (TASK-API-0122), parte del sucesor
`product-model-headers-3-0122` declarado en `product-category-header.md`.

## Contrato medido en la referencia

`odoo19c: addons/product/models/product_pricelist.py:10` a `:14` declara
`_name = 'product.pricelist'`, `_inherit = ['mail.thread',
'mail.activity.mixin']`, `_description = "Pricelist"`,
`_rec_names_search = ['name', 'currency_id']` y
`_order = "sequence, id, name"`. Sus campos relacionales propios:

| Fuente | Línea | Este puerto |
|---|---|---|
| `currency_id = fields.Many2one('res.currency', default=_default_currency_id, required=True)` | `odoo19c: addons/product/models/product_pricelist.py:36` | `currency` (nulo admitido) |
| `company_id = fields.Many2one('res.company', default=lambda self: self.env.company)` | `odoo19c: addons/product/models/product_pricelist.py:43` | `company` |
| `country_group_ids = fields.Many2many('res.country.group', relation='res_country_group_pricelist_rel', column1='pricelist_id', column2='res_country_group_id')` | `odoo19c: addons/product/models/product_pricelist.py:49` | `country_groups`, tabla y columnas de Django |

## Cambios

1. `ProductPricelist` declara los cinco atributos verbatim; `_inherit` nombra
   la extensión del hilo aunque la clase no herede `MailThread`.
2. `currency` → `currency_id` y `company` → `company_id`, en forma C.
3. `country_groups` → `country_group_ids` con `relation`, `column1` y
   `column2` de la fuente (`Many2manyField`). Precedente de la migración que
   renombra tabla y columnas conservando filas:
   `base/0114_res_partner_category_partner_ids`.
4. Consumidores: `SaleOrder._compute_has_active_pricelist` y
   `pricelist_domain` (`addons/sale/models/sale_order.py`). `pricelist_domain`
   era un alias de `payment_term_domain`, que sigue filtrando por `company`
   porque el plazo de pago aún no se renombra; pasa a ser una función propia
   sobre `company_id` (`odoo19c: addons/sale/models/sale_order.py:189`). Las
   pruebas crean con `company_id=`; el contrato de borrado
   (`tests/unit/orm/test_delete_policy_contract.py`) y el baseline de
   `check_fk_naming` nombran el campo nuevo.
5. La migración que genera Django para el Many2many es `RemoveField` +
   `AddField`, que borra la tabla y sus filas (`sqlmigrate` medido: `DROP
   TABLE`). Se reescribe como `RenameField` + `AlterField`, y `sqlmigrate`
   da entonces dos `RENAME TO` y dos `RENAME COLUMN`.

Búsqueda: `grep` de `pricelist*.currency|company|country_groups`,
`pricelist*__...`, `ProductPricelist.objects.*(` y `country_groups` en
`addons`, `src` y `tests`. `res.country.country_groups` es otro campo (el
inverso de `res.country.group.country_ids`) y no cambia.

## Símbolos que cambian

- `ProductPricelist._name`, `_inherit`, `_description`, `_rec_names_search`,
  `_order` (`odoo19c: addons/product/models/product_pricelist.py:10`);
- `ProductPricelist.currency_id`, `ProductPricelist.company_id`,
  `ProductPricelist.country_group_ids`;
- `_compute_has_active_pricelist`, `pricelist_domain`;
- la migración `0028_pricelist_source_header`, que renombra los tres.

## Fuera de esta unidad, con su sucesor

- `currency_id` es `required=True` con `_default_currency_id`
  (`odoo19c: addons/product/models/product_pricelist.py:16`) y `company_id`
  toma `self.env.company` por defecto: exigirlo pide decidir qué hacer con las
  filas sin moneda — `pricelist-currency-required-0122`.
- `item_ids`, `_get_product_price` y la familia de selección, ya declarados
  en el docstring del módulo; `pricelist`/`base_pricelist` del item —
  `product-fk-names-0122`.
- El hilo de `mail.thread` / `mail.activity.mixin` —
  `product-category-mail-0122` (misma adopción de `BaseModel`).

## Pruebas

`tests/unit/product/test_product_pricelist_header.py`: la cabecera verbatim;
los tres nombres con sus columnas, la tabla y las columnas del Many2many; un
grupo de países asignado sobrevive en la tabla de la fuente;
`pricelist_domain` admite la tarifa propia y la compartida, no la ajena.
Control de anulación: devolver `pricelist_domain` a `company` hace caer
exactamente esa prueba (1 failed, 5 passed).

## Corrección tras F2 en `284c2d42`

La batería completa salió verde con **9** `xfailed` contra 8 en `bce62146`.
El noveno era `test_the_django_policy_matches_the_source_ondelete
[product.ProductPricelist.company]`: el censo
`outputs/fk_reference_ondelete.tsv` nombra el campo por su nombre al
medirlo (`company`); al renombrar la entrada de `CORRECTED` a `company_id`
la fila dejó de estar corregida, volvió a `xfail` estricto y el
`FieldDoesNotExist` de `get_field('company')` se contó como fallo esperado.
Un verde que ocultaba una corrección perdida.

Se corrige la celda `field` de esa fila a `company_id` (sólo el nombre; la
política la lee la prueba del modelo vivo). Regenerar el censo entero no
cabe aquí: el sondeo actual da 1734 filas, con las columnas de auditoría,
contra las 907 que fija la población del contrato. Las otras filas
renombradas de `product` (`ProductCategory.parent`,
`ProductAttributeValue.attribute`, `ProductTemplateAttributeLine.attribute`,
`ProductPricelistItem.categ`, `ProductSupplierinfo.partner`) no entran en la
población destructiva, así que su nombre viejo no se resuelve en ninguna
prueba. Medido: el archivo da 95 passed, 2 xfailed; la fila de la tarifa
pasa como corregida.
