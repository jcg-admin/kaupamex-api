# Corte de la instrucción 3.2.14-C (A–H)

Fecha: 2026-11-09T02:32:01 · rama `feature/vm-x2hokp-orm-root` (los tres repos, sin publicar).

## A. Implementación contractual

| Unidad (TASK) | Contrato | Código | Asentada |
|---|---|---|---|
| `orm-flush-convergence-auto-now-0485` | `flush_all` converge (`environments.py:380-390`) | `BaseModel.save` limpia lo que escribió | `c5e9ed15` |
| `base-inherits-multiple-parents-0182` | gana el último padre (`models.py:422-425`) | `orm.inherits`, `_delegated_origin`, `_inherits_fk_for` | `12936f2b` (fix `e1afcf32`) |
| `orm-field-groups-write-0485` | groups al escribir (`models.py:4377-4382`) | `FieldDescriptor.__set__` | `4df49fad` |
| `base-timestamped-transaction-now-0485` | fechas con `cr.now()` (`models.py:4396,4803-4805`) | `TransactionDateTimeField` | `94930e21` |
| contrato `res.groups` implicados (sin unidad propia) | clausuras y pertenencia | ninguno (5/7 coinciden) | — |

## B. Advertencias

Registro completo en `designs/warning-dispositions.md`:
- flush: defecto demostrado → corregido (H-API-1188).
- `country should be searchable`: divergencia (`ResConfig` sin `_transient`) → decisión de arquitectura (`designs/resconfig-transient.md`).
- `fields.W342` en `account_fleet`: restricción `unique` que la referencia no impone → unidad pendiente.
- `UV_NATIVE_TLS`: configuración del entorno, fuera del Consumer.

## C. Matriz

Cuatro unidades asentadas (arriba). Abiertas con evidencia:
`users own login` (389 de 437 modelos con `AccessQuerySet` no derivan de
`BaseModel`, `designs/res-users-own-columns.md`), dos búsquedas de grupos
(`OPEN`, requieren `Many2many` sin columna, `designs/many2many-non-stored.md`),
21 `order_by` + 49 `latest/earliest` por `created_at`, propagación de
`_inherits` en varios niveles. El contador del plan sigue en 70 TASK
asentadas: cuenta TASK, no unidades, y 0182/0485 siguen abiertas.

## D. Arquitectura

- `_inherits`: la autoridad canónica es `_add_inherited_fields`; tres
  recorridos propios no la leían y la idempotencia declarada era falsa.
  Corregido.
- `BaseModel.create` ya hacía el alta delegada (H-API-1187); no se duplicó.
- `setup_related`: comentario falso sobre `_modules` corregido; ramas
  restantes sin sujeto o sin receptor (`designs/field-setup-related.md`).

## E. Pruebas

| Revisión | Prueba | Resultado |
|---|---|---|
| `c5e9ed15` | suite completa | 12216 passed, 5 errores multidb conocidos |
| `c5e9ed15` | multidb (base desechable) | `pytest_exit 0` |
| antes de `e1afcf32` | suite completa | 12223 passed, 5 conocidos |
| antes de `4df49fad` | suite completa | 12225 passed, 5 conocidos |
| `995e1b52` (incluye `e1afcf32`, `4df49fad`) | multidb | `pytest_exit 0` |
| antes de `94930e21` | suite completa | 12226 passed, 2 failed (corregidos en `94930e21`, verificados focalmente), 5 conocidos |
| `f7cbd1fe` (incluye `94930e21`) | multidb | `pytest_exit 0` |

| `e064fa7b` (incluye `94930e21`) | suite completa | 12228 passed, 0 failed, 5 errores multidb conocidos |

Cierra el hueco de `94930e21`: sus dos arreglos verificados por la suite
completa. Los 3 skipped de más frente a la ejecución anterior son los
contratos de referencia nuevos, que la suite salta sin las variables
`CONTRACT_REFERENCE_*`.

## F. Git

Commits locales sin publicar, frente a `origin/claude/bold-fermat-x2hokp`:
api 35, docs 6, thyrox 33. `feature/vm-x2hokp-orm-root` no existe en
ningún remoto. Referencia `recovery/vm-x2hokp-20261108` → `e9b9064cd9`,
intacta. `thyrox/bin/binary-codex` sin tocar.

## G. Thyrox

Usado: `session.local_plan supply` (abastecimiento y claims),
`settle_item.py` del banco, `bin/agent_store agregar-hallazgo`,
`bin/hallazgo_ids propose-id`, `bin/replace_literal`. No se usaron workers
de modelo local ni `headless-pool`: la implementación la hizo esta sesión.
Nueva regla del Provider: `.claude/rules/diseno-persistido-antes-de-implementar.md`.

## H. Continuidad

Asentadas cuatro unidades; abiertas las de la sección C. Siguiente unidad
admisible preparada: `Many2many` sin columna (mediciones 1-3 hechas).
Decisiones que esperan al ejecutor: `res.config` con tabla o no; cómo
cerrar la lectura de columnas propias en los 389 modelos.
