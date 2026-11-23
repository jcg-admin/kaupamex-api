# U1 — los catálogos hoja de `stock` adoptan `BaseModel`

Fecha: 2026-11-23T13:40:07. TASK-API-0397, unidad hija de `basemodel-adoption-0397`.
Partición: `outputs/stock-basemodel-adoption-research.md`, sección 6, fila U1.

Referencia: los seis modelos son `models.Model` en la fuente, y la
estrategia de retirada se lee por la verdad del Many2one, no por su
existencia: `if product_id.categ_id.removal_strategy_id:` y
`if loc.removal_strategy_id:`
(`odoo19c: addons/stock/models/stock_quant.py:618-628`).

Prueba del corte: `tests/integration/stock/test_putaway_rule_storage_category.py`,
`tests/integration/sale/test_stock_lot.py`,
`tests/integration/sale/test_product_expiry.py` y
`tests/unit/base/test_reflect_model_params_ordering.py`, más
`tests/unit/stock` y `tests/integration/stock`.

## Qué cambia

Las seis clases heredan de `models.BaseModel` (que aporta
`DefaultGetMixin` y el `_order = 'id'` por defecto), así que sus
Many2one entre dos `BaseModel` devuelven un recordset: vacío si no hay
fila, en lugar de `None`. Por eso `_get_removal_strategy` deja de
comparar con `None` y comprueba la verdad del valor, como la fuente; lo
mismo `get_putaway_location`, que con `is None` tomaba una regla sin
categoría por una con categoría y devolvía una sububicación con
existencias en lugar del destino (`if not putaway_rule.storage_category_id`,
`odoo19c: addons/stock/models/product_strategy.py:150`). La prueba nueva
lo discrimina: con el `is None` repuesto cae exactamente ella. `company` y
`product_uom` de la capacidad leen igual su Many2one por verdad.

La prueba de ordenación usaba `ProductRemoval` como sujeto sin
`_order`; al heredar `BaseModel` ya tiene uno, así que el sujeto pasa a
`StockRoute`, que aún no es `BaseModel` (U6).

## Símbolos

| Archivo | Símbolos |
|---|---|
| `addons/stock/models/stock_storage_category.py` | `StockStorageCategory`, `StockStorageCategoryCapacity`, `company`, `product_uom` |
| `addons/stock/models/stock_package_type.py` | `StockPackageType` |
| `addons/stock/models/product_strategy.py` | `ProductRemoval`, `StockPutawayRule`, `get_putaway_location`, `write` (sólo formato) |
| `addons/stock/models/stock_scrap.py` | `StockScrapReasonTag` |
| `addons/stock/models/stock_quant.py` | `_get_removal_strategy` |

## Lo que este corte no cierra

U2–U6 de la misma partición; los consumidores que aún usan la API de
gestor (`.filter`, `.set`, `.all()`) sobre relaciones que siguen
siendo gestores siguen como están, porque el otro extremo no es
`BaseModel` todavía.
