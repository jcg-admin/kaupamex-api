# Estados, ciudades y pasos de acción: ondelete='restrict' por defecto

Fecha: 2026-11-11T05:51:17. Segundo tramo de la población de 93
(`designs/delete-policy-contract-tests.md`). TASK-API-0515.

## Contrato de la fuente (odoo-tools `abe4040ec1`)

| Campo | Declaración | Defecto aplicado |
|---|---|---|
| `res.country.state.country_id` | `odoo/addons/base/models/res_country.py:204` — `Many2one('res.country', required=True, index=True)` | `restrict` |
| `res.city.country_id` | `addons/base_address_extended/models/res_city.py:14` — `Many2one(comodel_name='res.country', required=True)` | `restrict` |
| `ir.actions.todo.action_id` | `odoo/addons/base/models/ir_actions.py:1357` — `Many2one('ir.actions.actions', required=True, index=True)` | `restrict` |

Regla: `fields_relational.py:274-282`. Los tres modelos son
`models.Model` y obligatorios: `restrict`. `ir.actions.actions` no está
en `IR_MODELS` (`odoo/orm/fields.py:37-40`), así que `restrict` es
admisible para él.

## Estado

Los tres con `on_delete=models.CASCADE` (`src/addons/base/models/res_country.py:291`,
`addons/base_address_extended/models/res_city.py:44`,
`src/addons/base/models/ir_actions.py:2601`): borrar un país borra en
silencio sus estados y sus ciudades, y con ellos el vínculo de cada
dirección que los use; borrar una acción borra sus pasos de configuración.

## Cambio

`PROTECT` (misma decisión que `stock-quant-restrict-ondelete.md`),
migraciones `AlterField` en `base` y `base_address_extended`, las tres
filas a `CORRECTED` y una prueba de conducta por campo con el padre
protegido **sólo** por la fila del campo medido (lección del control de
`stock.quant`).

Consumidores: llamadores que borren países o acciones (subconjunto
derivado). Una prueba que dependía de la cascada para limpiar depende de la
pérdida y se corrige en la prueba.

## RED, implementación y controles (2026-11-11T05:59:34)

RED: `tests/unit/base/test_restrict_ondelete_country_todo.py`, 3 fallos
`DID NOT RAISE ProtectedError` y 1 verde (país sin dependientes).

Implementación: los tres campos a `models.PROTECT`; migraciones
`base/0108_restrict_ondelete_defaults` (`AlterField` ×2) y
`base_address_extended/0003_restrict_ondelete_defaults` (×1), sólo estado.
`CORRECTED` gana las tres filas. Resultado: 14 passed, 89 xfailed.

El representante `restrict` de la batería de contrato era
`ir.actions.todo`, ahora corregido: su `xfail` pasaba a XPASS y su caso
«hoy borra» dejaba de ser verdad. Se movió a una fila `restrict` todavía
divergente, `fleet.vehicle.odometer.vehicle_id`
(`odoo19c: addons/fleet/models/fleet_vehicle_odometer.py:15`); la conducta
corregida de la acción queda en la prueba nueva.

| Mutación | Cae |
|---|---|
| `ResCountryState.country` → `CASCADE` | exactamente su caso de conducta y su fila paramétrica |
| `ResCity.country_id` → `CASCADE` | ídem |
| `IrActionsTodo.action` → `CASCADE` | ídem |

Población tras este tramo: 93 filas, 6 corregidas, 87 pendientes.

## Subconjunto derivado (2026-11-11T06:12:13)

Directorios que nombran los modelos tocados (`tests/unit/base`,
`tests/integration/base`, `tests/unit/orm`, `hr`, `base_vat`,
`base_address_extended`, `account_edi_ubl_cii`, `account`, `service`,
`l10n_mx`, `base_setup`, `base_geolocalize`, `fleet`), `-n 4`:
**1 failed, 6658 passed, 89 xfailed, 27 errors**.

- El **1 failed** era `test_base_geo.py::test_cascade_delete_with_country`:
  afirmaba que borrar un país borra sus estados, la pérdida que se
  corrige. Se reescribió al contrato de la fuente
  (`test_deleting_a_country_with_states_is_refused`), no se tocó la
  política. `test_base_geo.py`: 15 passed.
- Los **27 errors** (`test_ir_cron_runner`, `test_ir_sequence_date_range`,
  `test_environments_transaction`, `test_missing_recompute`, …)
  **pasan los 27 en serie** sobre el mismo árbol. Corrieron con `-n 4`
  mientras el ci-multidb de `e2c7ba00` creaba bases en paralelo; la
  causa concreta no está determinada y no se atribuye. La reejecución en
  serie con log es la evidencia de que no dependen del cambio.

  **Causa probable, medida en otro tramo (2026-11-11).** El patrón
  reapareció en el derivado HR: 23 errors con `-n 4`, que pasan en serie.
  Allí la traza dio en todos `Table base_parentpathprobe0 ... does not
  exist` en el teardown de `tests/conftest.py`. La sonda de
  `isolate_apps` de `test_parent_path_check` entraba en el registro por
  nombre y `load_modules` la elegía para `base`. El log de este tramo
  solo guardó el resumen y no la traza, así que aquí la causa es
  INFERRED, no PROVEN. Ver `designs/isolated-apps-registry-leak.md`.
