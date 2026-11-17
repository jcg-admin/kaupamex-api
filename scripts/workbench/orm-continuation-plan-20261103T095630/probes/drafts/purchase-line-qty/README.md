# Borradores de las unidades 3 y 4 de `purchase.order.line`

**No son implementación aceptada.** Ninguno se ejecutó todavía contra la
base: se escribieron mientras un gate ci-multidb leía el árbol y sus
migraciones del disco, así que no se podían aplicar al código.

| Archivo | Unidad | Estado |
|---|---|---|
| `apply_unit4.py` | `purchase-line-qty-received-0122` | parche por anclas únicas sobre `addons/purchase/models/purchase_order_line.py`; falta la migración, que se genera con `makemigrations` |
| `test_purchase_line_qty_received.py` | idem | 8 pruebas, en rojo hasta aplicar el parche |
| `test_purchase_line_qty_invoiced.py` | `purchase-line-qty-invoiced-0122` | 9 pruebas; el piloto (`outputs/subagent-pilot-qty-invoiced-0122.md`) halló 7 comportamientos de la fuente que aún no cubren |

El parche se aplica desde la raíz de `kaupamex-api` (`python3
<ruta>/apply_unit4.py`) y rehúsa si alguna ancla no es única.
