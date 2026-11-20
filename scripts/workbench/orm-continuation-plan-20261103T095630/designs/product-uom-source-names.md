# `product.uom`: `product_id` y `company_id` con el nombre y el default de la fuente

Unidad `product-uom-source-names-0122` (TASK-API-0122), parte del sucesor
`product-fk-names-0122`.

## Contrato medido en la referencia

`odoo19c: addons/product/models/product_uom.py:13-16`:

- `product_id = fields.Many2one('product.product', 'Product', required=True,
  index=True, ondelete='cascade')`;
- `company_id = fields.Many2one('res.company', 'Company',
  default=lambda self: self.env.company)`.

El puerto los llamaba `product` y `company`, y `company` no tenía default:
un empaquetado creado sin empresa quedaba sin ella aunque hubiera una
empresa activa.

## Cambios

1. `ProductUom.product` → `ProductUom.product_id` y `ProductUom.company` →
   `ProductUom.company_id`, en forma C. Migración `no-op` en `sqlmigrate`.
2. `company_id` toma `default=_default_company`, que devuelve
   `env().company` (o nada sin empresa en contexto), con la forma de
   `_default_currency` de `product_supplierinfo.py`.
3. `ProductUom.__str__` lee `self.product_id`.
4. Censo `fk_reference_ondelete.tsv`, entrada CORRECTED de
   `tests/unit/orm/test_delete_policy_contract.py` (`ProductUom.company` →
   `company_id`) y `scripts/fk_naming_baseline.txt`.

## Símbolos que cambian

`ProductUom.product_id`, `ProductUom.company_id`
(`odoo19c: addons/product/models/product_uom.py:14-16`),
`_default_company`, `ProductUom.__str__`, la migración.

## Pruebas

Nombre y columna de los dos; `str()` compone código y variante; sin
empresa explícita el empaquetado toma la empresa activa. Control de
anulación: retirar el default hace caer exactamente esa prueba.
