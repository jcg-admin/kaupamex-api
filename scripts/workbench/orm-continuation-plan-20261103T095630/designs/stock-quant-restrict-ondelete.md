# stock.quant: product, location y lot con ondelete='restrict'

Fecha: 2026-11-11T05:31:33. Unidad seleccionada de la población de 96
(`designs/delete-policy-contract-tests.md`): las tres filas `restrict`
**explícitas** → `CASCADE`. TASK: TASK-API-0515 (la política `ondelete`
se materializa por `_auto_init` en la fuente).

## Contrato de la fuente

`odoo19c: addons/stock/models/stock_quant.py` (odoo-tools `abe4040ec1`):

- `:44-47` `product_id = fields.Many2one('product.product', ...,
  ondelete='restrict', required=True, ...)`
- `:56-59` `location_id = fields.Many2one('stock.location', ...,
  ondelete='restrict', required=True, ...)`
- `:63-66` `lot_id = fields.Many2one('stock.lot', ..., ondelete='restrict',
  ...)`

`ondelete='restrict'` → `ON DELETE RESTRICT`: borrar un producto, una
ubicación o un lote con existencias falla de inmediato; las existencias se
conservan.

## Estado

`addons/stock/models/stock_quant.py:370-387`: las tres con
`on_delete=models.CASCADE`. Borrar un producto, una ubicación o un lote
**borra en silencio sus quants** (las existencias).

## Decisión: PROTECT, no RESTRICT

| Opción | Semántica | Frente a `ON DELETE RESTRICT` |
|---|---|---|
| `models.PROTECT` | siempre `ProtectedError` si hay hijos | igual: PostgreSQL falla siempre que exista la fila hija |
| `models.RESTRICT` | permite el borrado si el hijo cae por otra cascada en la misma operación | más débil: `quant.company` es `CASCADE` aquí, así que borrar la compañía arrastraría el quant aunque su ubicación sea `restrict` |

`PROTECT` es además la forma de las 49 filas `restrict` ya coherentes
(`foreign-keys-delete-contract.md`, «(restrict, PROTECT) 49»). Sin
`DB_RESTRICT` en Django, se queda en Python (determinación 3 de ese diseño).
La FK física no cambia (Django 6.0.5 no emite `ON DELETE`).

## Cambio

- Las tres a `on_delete=models.PROTECT` y migración `AlterField` (sólo
  estado).
- `test_delete_policy_contract.py`: las tres filas salen de la población
  marcada `xfail` (conjunto `CORRECTED`), y su caso pasa en verde.
- Prueba de conducta nueva por campo: borrar el padre con un quant lanza
  `ProtectedError` y el quant sigue; sin quants, el padre se borra.

## Consumidores a medir

Llamadores que borren productos, ubicaciones o lotes: el subconjunto
derivado de `stock`, `product`, `mrp`, `purchase_stock`, `sale_stock`
y los que nombren `StockQuant`. Una prueba que dependía de la cascada
para limpiar es una dependencia de la pérdida y se corrige en la prueba,
no en la política.

Controles: con `CASCADE` de vuelta en cada campo cae exactamente su caso de
conducta y su fila paramétrica.

*Métrica:* filas de `stock.quant` antes y después de borrar el padre.
*Ciega a:* `quant.company` (`CASCADE` aquí; en la fuente es un `related`
almacenado sin FK): divergencia distinta, fuera de esta unidad.

## RED, implementación y controles (2026-11-11T05:41:03)

RED: los tres casos de conducta fallaron con `DID NOT RAISE
ProtectedError` (el borrado se ejecutaba y arrastraba el quant).

Implementación: `product`, `location` y `lot` de `StockQuant` a
`on_delete=models.PROTECT`; migración `stock/0025_quant_restrict_ondelete`
(`AlterField` ×3, sólo estado; la FK física no cambia).
`test_delete_policy_contract.py`: conjunto `CORRECTED` con las tres filas,
que corren sin `xfail`. Resultado: 11 passed, 95 xfailed.

Control que destapó un defecto de la prueba: con `CASCADE` de vuelta en
`product` sólo cayó la fila paramétrica; el caso de conducta seguía verde
porque el lote del fixture también apunta al producto y era él quien
lanzaba `ProtectedError`. Se separaron los fixtures (quant sin lote para
producto y ubicación; con lote sólo para el caso del lote). Repetidos:

| Mutación | Cae |
|---|---|
| `product` → `CASCADE` | exactamente `test_deleting_the_parent_of_a_quant_is_refused[variant]` y su fila paramétrica |
| `location` → `CASCADE` | exactamente `...[location]` y su fila paramétrica |
| `lot` → `CASCADE` | exactamente `test_deleting_the_lot_of_a_quant_is_refused` y su fila paramétrica |
