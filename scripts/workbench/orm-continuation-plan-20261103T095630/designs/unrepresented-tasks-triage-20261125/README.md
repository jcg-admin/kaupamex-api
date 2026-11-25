# Clasificación de las 59 TASK sin unidad en el plan (2026-11-25)

Población: `outputs/plan_coverage.json` → `unrepresented` (59 TASK) al
asentar `account-account-mc2c2-0397`. Repartida en cuatro tramos disjuntos
(`ids[i::4]`) y clasificada por cuatro subagentes de solo lectura, sin pytest
ni escrituras en ningún repositorio; cada uno dejó su `sliceN-triage.md` con
las citas `archivo:línea` de cada veredicto. Conteo por archivo: `rg -o "\| *(CLOSED|UNIT|NOT-ORM|BLOCKED)" sliceN-triage.md`.

| Veredicto | Tramo 1 | Tramo 2 | Tramo 3 | Tramo 4 | Total |
|---|---|---|---|---|---|
| CLOSED | 5 | 4 | 6 | 5 | 20 |
| UNIT | 5 | 3 | 4 | 3 | 15 |
| NOT-ORM | 3 | 7 | 4 | 6 | 20 |
| BLOCKED | 2 | 1 | 1 | 0 | 4 |

`TASK-GEN-0558` cuenta como UNIT (su mitad nativa); su mitad sobre filas de
Django está BLOCKED hasta que esos modelos adopten `BaseModel`.

## Nivel de verificación

Los veredictos están en **nivel 3** (persistidos, no verificados), salvo los
que se comprobaron de forma independiente al consolidar, por lectura del
árbol:

- Tramo 2: `TASK-API-0282` (`src/orm/models.py:9062-9068`), `TASK-API-0512`
  (commit `051ca50e`), `TASK-GEN-0060` (`src/orm/fields_textual.py:888`) y
  `TASK-API-0115` (`tests/unit/orm/test_modified_engine.py`).
- Tramo 3: `TASK-API-0152` (`addons/base_setup/models/res_config_settings.py:528`),
  `TASK-API-0283` (`src/addons/base/models/ir_model.py:930`), `TASK-API-0414`
  (commit `f9b6bed9`), `TASK-API-0493` (commit `471db3b6`); `TASK-GEN-0634`
  UNIT confirmado (`src/addons/base/models/res_company.py:512`).
- Tramo 1: `TASK-API-0174` (pila explícita en
  `src/modules/module_graph.py:230-233`), `TASK-API-0420`
  (`src/orm/fields_misc.py:62`), `TASK-GEN-0559` (`apply_except_missing` en
  `src/orm/fields.py:5516`, no en `:5510` como citaba el tramo; sus pruebas no
  nombran el símbolo); UNIT confirmados: `TASK-GEN-0058` (sin
  `is_initialized`/`initialize` en `src/modules/db.py`) y `TASK-GEN-0356`
  (`share` es `property`, `src/addons/base/models/res_users.py:1844`).
- Tramo 4: `TASK-API-0419` (`src/orm/fields.py:1186`), `TASK-API-0398`
  (comparadores en `src/orm/models.py:9855`).

Un CLOSED no cierra la TASK en el TaskStore: esta VM no escribe en él. Los
veredictos son evidencia para quien la cierre.

## Unidades candidatas

Las 15 filas `candidate-*.jsonl` de los tramos se copiaron a `candidates/`
sin colisión de id con `plan.jsonl` ni con candidatas previas. Entran al plan
de una en una, con su diseño y su prueba roja, cuando se admitan.
