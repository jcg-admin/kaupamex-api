# Las 11 filas `restrict` que no son de empresa

TASK-API-0515 · contrato `designs/delete-policy-contract-tests.md` ·
referencia `odoo-tools` en `abe4040ec1`. Procedimiento de los tramos
anteriores (`fleet-restrict-ondelete.md`): `PROTECT` con su `AlterField`
(sin DDL: la política vive en el `Collector`), una prueba de conducta con un
fixture por hijo y la fila a `CORRECTED`.

## Primero el flujo del padre (medido)

`PROTECT` sólo reproduce la fuente cuando el padre **no** borra antes a sus
hijos. Leído `unlink` y los `_unlink_except` de cada padre:

| Fila | Padre | `unlink` del padre en la fuente | Desenlace |
|---|---|---|---|
| `stock.StockRule.location_dest` | `stock.location` | `odoo19c: addons/stock/models/stock_location.py:266-267`: extiende el borrado a las ubicaciones hijas; no toca reglas | `PROTECT` |
| `stock.StockRule.picking_type` | `stock.picking.type` | sin `unlink` (el de `stock_picking.py:1170` es de `stock.picking`) | `PROTECT`; es el representante ORM `restrict` del contrato: cambia de representante |
| `sale_timesheet.ProjectSaleLineEmployeeMap.project` | `project.project` | `odoo19c: addons/project/models/project_project.py:704-712`: borra acciones y cuentas analíticas vacías, no el mapa | `PROTECT` |
| `sale_timesheet.ProjectSaleLineEmployeeMap.employee` | `hr.employee` | `odoo19c: addons/hr/models/hr_employee.py:1473-1476`: borra el `resource`, no el mapa | `PROTECT` |
| `account.AccountFiscalPositionAccount.account_src`, `account_dest` | `account.account` | `_unlink_except_linked_to_fiscal_position`, `odoo19c: addons/account/models/account_account.py:1142-1145`: `UserError` antes del borrado | `PROTECT` **y** portar la guarda, que da el mensaje de la fuente |
| `account.AccountPaymentMethodLine.payment_method` | `account.payment.method` | `odoo19c: addons/account/models/account_payment_method.py:90-92`: **borra antes sus líneas** | portar ese `unlink`; sin él `PROTECT` rehusaría lo que la fuente permite |
| `account.AccountPartialReconcile.debit_move`, `credit_move` | `account.move.line` | `unlink` → `remove_move_reconcile()` (`odoo19c: addons/account/models/account_move_line.py:1984-1988,3138-3140`): **borra antes los parciales** | portar `remove_move_reconcile` y ese `unlink` antes de `PROTECT` |

Medido en el Consumer: `AccountPaymentMethod` no declara `unlink`,
`account_move_line.py` no declara `unlink` ni `remove_move_reconcile`, y
`account_account.py` no declara las guardas `_unlink_except_*`.

## Orden

1. Tramo A (`PROTECT` puro): `location_dest`, `picking_type`, el mapa de
   `sale_timesheet` (2) y las dos de posición fiscal con su guarda.
2. Tramo B: `AccountPaymentMethod.unlink` y luego su fila.
3. Tramo C: `remove_move_reconcile` y `AccountMoveLine.unlink`, luego las
   dos filas de parciales.

## Pruebas previstas

Por fila: borrar el padre con hijo → `ProtectedError` (o el `UserError` de
la guarda) y el hijo sigue; sin hijo, se borra (control). En B y C, además:
borrar el padre borra antes a los hijos que la fuente borra.

## Lo que no cierra

Las 20 filas `restrict` de `company` y las 47 `set null`: otros tramos.
