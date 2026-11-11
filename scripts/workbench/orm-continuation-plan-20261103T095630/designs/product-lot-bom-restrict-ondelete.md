# Lotes y listas de materiales: ondelete='restrict' por defecto

Fecha: 2026-11-11T06:33:13. Tercer tramo de la población de 93
(`designs/delete-policy-contract-tests.md`). TASK-API-0515.

## Contrato de la fuente (odoo-tools `abe4040ec1`)

| Campo | Declaración | Defecto |
|---|---|---|
| `stock.lot.product_id` | `addons/stock/models/stock_lot.py:44-48` — `Many2one('product.product', ..., required=True, check_company=True, tracking=True)` | `restrict` |
| `mrp.bom.product_tmpl_id` | `addons/mrp/models/mrp_bom.py:31-34` — `Many2one('product.template', ..., required=True)` | `restrict` |

Modelos `models.Model`, obligatorios, sin `ondelete`:
`fields_relational.py:274-282` da `restrict`.

## Estado

`addons/stock/models/stock_lot.py:269` y `addons/mrp/models/mrp_bom.py:57`,
los dos `CASCADE`: borrar un producto borra sus lotes (y con ellos la
trazabilidad de números de serie); borrar una plantilla borra sus listas de
materiales.

## Cambio

`PROTECT`, migraciones `AlterField` en `stock` y `mrp`, las dos filas a
`CORRECTED` y una prueba de conducta por campo con el padre protegido sólo
por la fila medida (sin quants que apunten al lote ni otros hijos).

## RED, implementación y controles (2026-11-11T06:35:39)

RED: 2 fallos `DID NOT RAISE ProtectedError`, 1 verde (plantilla sin
dependientes). Implementación: los dos campos a `PROTECT`; migraciones
`stock/0026_restrict_ondelete_product` y `mrp/0002_restrict_ondelete_product`
(`AlterField`, sólo estado); `CORRECTED` gana las dos filas. Resultado:
15 passed, 87 xfailed.

| Mutación | Cae |
|---|---|
| `StockLot.product` → `CASCADE` | exactamente su caso de conducta y su fila paramétrica |
| `MrpBom.product_tmpl` → `CASCADE` | ídem |

Población tras este tramo: 93 filas, 8 corregidas, 85 pendientes.
