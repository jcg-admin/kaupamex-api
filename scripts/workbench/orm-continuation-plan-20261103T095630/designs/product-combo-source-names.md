# `product.combo` y `product.combo.item`: los nombres de la fuente

Unidad `product-combo-source-names-0122` (TASK-API-0122), parte del sucesor
`product-fk-names-0122`.

## Contrato medido en la referencia

- `odoo19c: addons/product/models/product_combo.py:14`:
  `company_id = fields.Many2one(string="Company",
  comodel_name='res.company', index=True)`.
- `odoo19c: addons/product/models/product_combo_item.py:12-14`:
  `company_id = fields.Many2one(related='combo_id.company_id',
  precompute=True, store=True)`, `combo_id = fields.Many2one(
  comodel_name='product.combo', ondelete='cascade', required=True, ...)`,
  `product_id = fields.Many2one(..., ondelete='restrict', ...)`.

El puerto los llamaba `company`, `combo` y `product`.

## El riesgo de esta unidad: lecturas que hoy son el `attname` entero

El código ya lee `company_id` y `combo_id` con el nombre de la fuente, pero
como el entero que Django genera para `company`/`combo`:

- `ProductComboItem.save`: `if self.combo_id:` y
  `self.company_id = self.combo.company_id`;
- `ProductCombo` (validación de compañía): `item.company_id !=
  self.company_id`.

Tras el cambio esos nombres son el registro. La presencia de un FK
obligatorio no asignado se comprueba con `combo_id_id`, no leyendo el
registro (lección de `product-supplierinfo-source-names.md`), y la
asignación pasa a registro con registro. Las comparaciones registro contra
registro siguen siendo correctas.

## Cambios

1. `ProductCombo.company` → `company_id`; `ProductComboItem.combo` →
   `combo_id`, `.product` → `product_id`, `.company` → `company_id`, en
   forma C. Migración sin SQL de datos.
2. `ProductComboItem.save` (`combo_id_id`), `__str__`, `lst_price`,
   `currency`; `ProductCombo.currency` (`getattr(self.company, …)`) y la
   validación de compañía; `ProductTemplate.check_combo_choices`
   (`item.product.sale_ok`).
3. Pruebas que crean con `combo=`/`product=`.
4. Censo, entradas CORRECTED si las hay y `scripts/fk_naming_baseline.txt`.

Sin sustitución global: `'product.combo'` y `'product.combo.item'` son
nombres de modelo (la trampa de `product-template-uom-id.md`), y
`item.product` en `website_sale_wishlist` y `sale/services.py` es otro
modelo.

## Pruebas

Nombres y columnas; una opción toma la compañía de su elección al crearse;
`check_combo_choices` rechaza una opción no vendible. Control de anulación:
devolver la propagación de `save` a la forma anterior hace caer la prueba de
compañía.
