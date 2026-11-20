# `product.template.company_id`: el nombre de la fuente de la compañía

Unidad `product-template-company-id-0122` (TASK-API-0122), parte del
sucesor `product-fk-names-0122`.

## Contrato medido en la referencia

`odoo19c: addons/product/models/product_template.py:124` declara
`company_id = fields.Many2one('res.company', 'Company', index=True)`;
`product.product` lo hereda por `_inherits`. Este puerto lo llamaba
`company`, y la variante lo delegaba con una propiedad `company`.

## Cambios

1. `ProductTemplate.company` → `ProductTemplate.company_id` en forma C.
   Migración `0032_template_company_id`: dos operaciones `no-op`.
2. `ProductProduct.company` → `ProductProduct.company_id` (la delegación de
   `_inherits` con el nombre de la fuente).
3. Lecturas sobre plantilla o variante: `ProductTemplate.currency`,
   `ProductTemplate.cost_currency`, `ProductProduct._prepare_sellers` y
   `ProductProduct._select_seller`; `_inherit_company_default_taxes`
   (`addons/account/models/product.py`, el receptor `post_save` lee
   `instance.company_id`); `StockMoveLine._prepare_new_lot_vals`
   (`getattr(self.product, 'company', None)` devolvía `None` en silencio
   tras el renombre, y el lote nuevo habría quedado global aunque el
   producto fuese de la compañía de la línea).
4. `fiscal_country_codes` de la plantilla: `_compute_record_fiscal_country_codes`
   se compartía con `account.payment.term`, que sigue llamando `company` a
   su compañía, y su `@api.depends('company')` dejó de resolver en la
   plantilla (la carga de módulos fallaba). La plantilla recibe
   `_compute_template_fiscal_country_codes` con `@api.depends('company_id')`
   (`odoo19c: account/models/product.py:100-105`), y
   `record_fiscal_country_codes` acepta el registro o el entero.
5. Las pruebas crean con `company_id=`; el censo
   `outputs/fk_reference_ondelete.tsv` y `CORRECTED` del contrato de borrado
   nombran `ProductTemplate.company_id`; `scripts/fk_naming_baseline.txt`
   retira su línea.

`company` es un nombre genérico: cada modelo lleva el suyo. La búsqueda por
`grep` se acota a receptores de producto (`product`, `tmpl`, `template`,
`variant`, `instance` en receptores de señal con `sender=ProductTemplate`,
`self` en los métodos de las dos clases) y a `getattr(…, 'company')`; la red
para lo que el `grep` no ve es la batería entera, no un subconjunto.

## Símbolos que cambian

- `ProductTemplate.company_id`
  (`odoo19c: addons/product/models/product_template.py:124`),
  `ProductProduct.company_id`;
- `ProductTemplate.currency`, `ProductTemplate.cost_currency`,
  `_prepare_sellers`, `_select_seller`;
- `_inherit_company_default_taxes`, `StockMoveLine._prepare_new_lot_vals`;
- `record_fiscal_country_codes`, `_compute_template_fiscal_country_codes`,
  `apply_account_extensions`;
- la migración `0032_template_company_id`.

## Fuera de esta unidad, con su sucesor

- `ProductTemplate.uom` y `ProductProduct.product_tmpl` —
  `product-fk-names-0122`.
- `account.payment.term.company` — `account-fk-names-0121`.

## Pruebas

`tests/unit/product/test_product_template_company_id.py`: el nombre y la
columna; la variante delega `company_id`; la moneda de coste es la de la
compañía del producto; el lote nuevo de una línea toma la compañía del
producto. Control de anulación: devolver el `getattr` de
`_prepare_new_lot_vals` a `'company'` hace caer exactamente la prueba del
lote.
