# Fleet: el vehículo con lecturas o historial de conductor no se borra

Fecha: 2026-11-11T07:10:08 · TASK-API-0515 · contrato de
`designs/delete-policy-contract-tests.md`

## Filas del censo

| Modelo | Campo | Fuente | Hoy |
|---|---|---|---|
| `fleet.vehicle.odometer` | `vehicle` | `odoo19c: addons/fleet/models/fleet_vehicle_odometer.py:15`, `required=True` sin `ondelete` → `restrict` | `CASCADE` |
| `fleet.vehicle.assignation.log` | `vehicle` | `odoo19c: addons/fleet/models/fleet_vehicle_assignation_log.py:12`, `required=True` sin `ondelete` → `restrict` | `CASCADE` |

Regla por defecto: `odoo19c: odoo/orm/fields_relational.py:274-282`. Ninguno
de los dos modelos es transitorio. `fleet.vehicle` no sobreescribe `unlink`
(`grep "def unlink" addons/fleet/models/fleet_vehicle.py` → 0), así que la
fuente no tiene ningún flujo que borre las lecturas antes que el vehículo.

## Decisión

`on_delete=models.PROTECT` en los dos campos, con su migración. Es la misma
equivalencia que en los tramos anteriores: PROTECT falla siempre que hay
hijos, igual que `ON DELETE RESTRICT`.

## Consumidores

`grep` de borrados de vehículo en `tests/`, `addons/fleet` y `src` da solo la
prueba de contrato, cuyo representante `restrict` es justamente el odómetro.

## La prueba de contrato cambia de representante

El representante ORM de la familia `restrict` pasa a otra fila pendiente que
no requiera una construcción de datos cara. La fila elegida se indica en el
commit y en el docstring de la prueba. Las dos pruebas del odómetro pasan a
la prueba de conducta del tramo, que comprueba:

- borrar un vehículo con lecturas → `ProtectedError`, y la lectura sigue;
- borrar un vehículo con historial de conductor → `ProtectedError`;
- un vehículo sin hijos se borra (control positivo);
- cada caso aísla su FK: un fixture por hijo, para que ninguno proteja al
  padre en lugar del otro. Es la lección del tramo de quant.

## Lo que no cierra

Las otras 79 filas pendientes del censo, que seguirán por tramos.

## Resultado (2026-11-12)

- `addons/fleet/migrations/0009_vehicle_children_restrict.py`: dos
  `AlterField` de `on_delete`. `sqlmigrate` da `(no-op)` en las dos: la
  política vive en el `Collector` de Django y la FK física sigue
  `NO ACTION DEFERRABLE`, así que no hay DDL ni costo de instalación.
- `tests/unit/fleet/test_vehicle_restrict_ondelete.py`: 3 passed (lecturas,
  historial de conductor y el control sin hijos). En rojo antes del cambio:
  2 failed, 1 passed.
- Prueba de contrato: las dos filas entran en `CORRECTED`; el representante
  ORM de `restrict` pasa a `stock.StockRule.picking_type`
  (`odoo19c: addons/stock/models/stock_rule.py:87`; `stock.picking.type` no
  sobreescribe `unlink` —el de `stock_picking.py:1170` es de
  `stock.picking`—). Contrato + fleet: 75 passed, 81 xfailed.
- Anulación (el odómetro vuelve a `CASCADE`): caen exactamente el caso de
  lecturas y la fila declarativa del odómetro; el historial sigue verde.
