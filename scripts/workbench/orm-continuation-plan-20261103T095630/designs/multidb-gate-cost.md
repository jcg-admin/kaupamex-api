# Coste de ci-multidb: dónde se van las dos horas y cómo reducirlo

Creado: 2026-11-12T18:28:43 (UTC). TASK-API-0485. Origen: §1-§5 de la instrucción
operativa sobre el desperdicio de ci-multidb.

## Medición

Duración por caso, de los `junit_isolation.xml` de las dos ejecuciones
completas (`outputs/gates/ci-multidb-{0e674aed,5dc2e8c1}`):

| Caso | `0e674aed` | `5dc2e8c1` | Qué paga |
|---|---|---|---|
| `test_domain_write_without_any_company_alias_lands_in_default` (1.º) | 2 661,6 s | 2 585,2 s | la creación de `default` con `--create-db`: migraciones desde cero |
| `test_write_under_company_scope_lands_in_its_own_base` (2.º) | 5 585,0 s | 5 159,8 s | el fixture de módulo `two_company_databases`: **dos** `provision_company_database`, cada uno un `migrate` desde cero (`src/service/db.py:414-422`) |
| los otros 12 | < 4 s en total | < 4 s | las pruebas |

*Métrica:* `time` por `testcase` del junit. *Ciega a:* el reparto interno
entre migraciones de esquema y migraciones de datos (`RunPython`) — un
`migrate` completo tarda unos 45 min y no hay aún medida por migración.

Ejecución en curso (`7b597391`, medida 2026-11-12T18:28:43): mismo perfil. El caso 1 terminó
a los 43 min (16:29:50 → 17:12:55); el caso 2 llevaba 75 min con `pytest` al
98,8 % de CPU y 2 GB de RSS, `boot_id` sin cambios. **Decisión: no se cancela**;
progresa dentro de lo medido para este caso (5 160-5 585 s).

## Causa

Tres migraciones completas desde cero por ejecución: la de `default` y una por
base de empresa. Las pruebas de aislamiento tardan segundos. El gate paga
`migrate` tres veces para comprobar contratos funcionales, y sólo una de esas
veces —la de una base de empresa— es la que el contrato de aprovisionamiento
necesita.

## Reutilización: lo que ya existe

- `service.db.duplicate_database` (`src/service/db.py`, ≙
  `exp_duplicate_database`): `CREATE DATABASE dst TEMPLATE src`, con las
  conexiones del origen cerradas antes.
- `provision_company_database` es idempotente: sobre una base ya migrada sólo
  aplica lo nuevo y comprueba el esquema (`_check_applied_schema`).
- El esquema de empresa es el de `default` **sin** el plano de control
  (`orm/routers.py:199-208`), así que `default` no sirve de plantilla de una
  base de empresa.

## Diseño de la alternativa (dos verificaciones separadas)

**A. Aprovisionamiento** — sin cambios de contrato: la base de empresa **A** se
aprovisiona desde cero con `provision_company_database`. Sigue cubriendo
creación, migraciones, datos iniciales, `RunPython` en la empresa destino y
comprobación del esquema.

**B. Aislamiento funcional** — la base **B** se obtiene con
`duplicate_database(A, B)` y se pasa por `provision_company_database(B)`
(debe aplicar 0 migraciones y pasar `_check_applied_schema`). Es una base
física distinta, con su conexión, su registro y sus cachés; los identificadores
coinciden por construcción, que es justo la condición que las pruebas de cachés
por base necesitan.

Qué se reinicializa tras clonar: nada en la base (el clon es un esquema idéntico
sin conexiones activas); en el proceso, el alias se instala con
`install_company_aliases` y su registro se crea al primer uso
(`registry_for_alias`), sin heredar caché ni invalidación de A.

Cuándo **no** sirve: si el cambio bajo prueba toca migraciones o el
aprovisionamiento, B también debe aprovisionarse desde cero (el gate actual).
El gate completo se conserva para esos cambios.

Ahorro esperado: una migración completa (~46 min de los ~93 del caso 2).

## Cobertura de la unidad de cachés por base en el gate

Ningún caso de `test_multidb_isolation.py` comprueba `ormcache` entre bases:
el gate en curso acredita aislamiento de datos y de entornos, **no** de cachés.
Las pruebas de cachés (`test_registry_caches_per_database.py`) usan dos alias
sobre la misma base física. Control que falta: con A y B físicas e
identificadores coincidentes, una entrada de `ormcache` sembrada en A no se
sirve en B, y una invalidación en A no aparece en el registro de B. Se añade
cuando el gate en curso termine (no se toca el árbol que verifica).

## Implementado (2026-11-12T18:35:51 UTC, sin integrar)

- `tests/integration/company/test_multidb_isolation.py`: `MULTIDB_SECOND_BASE`
  (`provision` por defecto, sin cambio de contrato; `clone` copia A con
  `duplicate_database` y exige que `provision_company_database(B)` no la cree).
- Control nuevo `test_ormcache_entries_and_invalidation_stay_in_their_base`:
  dos registros distintos, una entrada de `IrModel._get_id` de A no se sirve en
  B (fila renombrada en B dentro de una transacción revertida) y
  `clear_cache` en B no se anota en A.
- `scripts/run_multidb_isolation.py` registra el modo en `record.json`
  (`second_base`).

## Evidencia por etapas (§10)

El gate escribía directamente en `outputs/gates/<nombre>/` mientras corría: el
directorio aparecía sin seguimiento durante dos horas y era indistinguible de
evidencia pendiente de publicar. Etapas, con las piezas que ya existen:

| Etapa | Dónde | Quién |
|---|---|---|
| salida en curso | directorio de trabajo fuera del banco (scratchpad) | `probes/gate-procedure/run-gate-multidb-staged.sh` |
| finalizada | el mismo, con `record.json` y `EXIT=` en el log del lanzador | el lanzador |
| verificada | copia al banco con hash por archivo | `probes/persist_gate_evidence.py` |
| publicada | commit por pathspec | quien integra |

El gate en curso (`7b597391`) sigue con el lanzador anterior; no se toca.

## Resultado medido (2026-11-13T02:14:05)

Misma revisión `3342b8b2`, las dos ejecuciones conformes (15 passed):

| Fase | `provision` (`ci-multidb-3342b8b2`) | `clone` (`ci-multidb-clone-3342b8b2`) |
|---|---|---|
| prueba 1 (`--create-db`) | 2 424 s | 2 779 s |
| fixture de dos bases | 4 873 s | 2 793 s (−43 %) |
| resto (12 pruebas) | 4 s | 4 s |
| pytest total | 7 321 s | 5 594 s (−24 %) |

La diferencia de la prueba 1 (+355 s) no la explica el modo —el código y la
fase son idénticos—: es la variación de la máquina, y acota la precisión de la
comparación.

Decisión de uso, sin reducir cobertura: `clone` para cambios que no tocan
migraciones ni aprovisionamiento; `provision` obligatorio cuando los tocan
(como `3342b8b2`, por `base/0113`). La base A sigue aprovisionándose desde
cero en los dos modos.
