# Liquidación por unidad — 2026-11-12

Creado: 2026-11-12T11:25:16 (UTC). TASK-API-0485 salvo indicación. Estados
separados: **Implementado** (código en el árbol), **Verificado** (RED,
GREEN, anulación y suite que lo cubre), **Integrado** (commit publicado en
`feature/vm-x2hokp-orm-root`), **Aceptado** (decisión del ejecutor; ninguna
unidad de esta tabla lo está).

Las suites citadas están en `outputs/gates/index.tsv` con el hash de cada
archivo. Seis commits de un mismo lote **no** son seis verificaciones
independientes: comparten la suite del lote que los cubrió.

## Lote 4 (instantánea `fullgate-batch4` sobre `2d574be0`)

Suite integral: 13 099 passed, 0 failed, 24 errors (14 del aislamiento
multidb, que exige base desechable propia; 10 por tablas de sonda residuales
en `orm_x2hokp_qa_gw0` de la sesión del lote 2, retiradas después). Los 16
casos de `test_modified_engine` que no ejecutó se verificaron con
`tests/unit/orm` completo sobre la misma instantánea (3 194 passed). La
revisión publicada `5dc2e8c1` coincide byte a byte con la instantánea.

| Unidad | Contrato de referencia | Commit | Anulación | Multidb | Pendiente |
|---|---|---|---|---|---|
| Escritura de columnas en `_flush` | `_flush` → `_write_multi` (`models.py:4520-4608`, `:6387`) | `26122062` | `test_flush_write_contract` (envejecida `write_date`) | ci-multidb `5dc2e8c1` en curso | — |
| Volcado dentro del entorno dueño | `flush_all` (`environments.py:380-390`), `flush_model`/`flush_recordset` (`models.py:6353-6384`) | `26122062` | tres controles de `test_creation_marks_on_alias` | idem | pruebas extendidas (`drafts/test_environment_ownership_extended.py`) |
| Sin doble cómputo en la creación | `_create` + `modified(create=True)` | `26122062`, `d92098e1`, `d0beaedf` | `test_compute_before_insert` | idem | — |
| Protección de valores explícitos | `create`: `fname not in vals` | `26122062` | `test_chart_template` | — | — |
| Reintento por fila en `load` | `load` (`models.py:985-1022`) | `26122062` | `test_load` (2) | — | — |
| `Savepoint.rollback` | `Atomic.__exit__` (`django/db/transaction.py:273-283`) | `26122062` | cae 2 | — | — |
| Barreras `to_flush` | `_read_group` (`environments.py:517-523`) | `d92098e1` | cae 2 | — | — |
| Fusión de `depends` | `get_depends` (`fields.py:584-599`) | `cb483f8b` | `test_method_chain_depends` | — | dependencia de `payment_provider_id.name` (puerto de Many2one) |
| Datos y cabecera de `uom` | `uom/__manifest__.py`, `uom_data.xml` | `e5ef3952` | `test_uom_data` (4) | — | `record-loader-universality-0485` |
| `_update_xmlids` | `ir_model.py:2402` | `e5ef3952` | el RED del lote 3 | — | cachés por base (`designs/registry-caches-per-database.md`) |
| Hora de transacción del CRM | `cr.now()` (`sql_db.py:271-278`) | `d0beaedf` | `test_lead_dates_and_recurring` | — | igualdad exacta con `create_date`/`write_date` y entre transacciones |
| Aislamiento de prueba de `default_env` | ciclo del cursor por caso (`odoo/tests/common.py`) | `26122062` | cae 2 + el error del lote 3 | — | sustituido como garantía por la unidad siguiente |

El lote 3 (`full-batch3-2d574be0`) se conserva como **fallido**.

## Unidad `registry-cursor-unit-of-work-0485`

| Campo | Valor |
|---|---|
| Contrato | `Registry.cursor` (`registry.py:1165-1186`), `BaseCursor`/`Cursor` (`sql_db.py:156-588`), `Environment.__new__` (`environments.py:64-89`), `TestCursor` (`odoo/tests/test_cursor.py`) |
| Diseño | `designs/registry-cursor-unit-of-work.md` (`8507e89f`) |
| Implementación | `src/sql_db.py`, `src/orm/registry.py`, `src/orm/environments.py`, `src/service/db.py`, `tests/conftest.py`, `tests/cursor_support.py` |
| RED | 5 de 5 en `test_registry_cursor.py` |
| GREEN | 8 de 8 |
| Anulación | N1 cae 1, N2 cae 5, N3 cae 1, N4 cae 1 |
| Regresión derivada | 6 350 passed (`derived-registry-cursor-8507e89f`) |
| Suite integral | 13 117 passed, 0 failed, 14 errors multidb (`full-registry-cursor-8507e89f`) |
| Multidb | no ejecutado sobre esta revisión |
| Commit | `663aac8b`; evidencia `4f087301` |
| Pendiente | ci-multidb sobre la revisión que integre esta unidad y la del cron |

## Unidad del cron con cursor por trabajo (en verificación)

RED: `test_ir_cron_job_cursor` vuelca con `write_uid` 1 en lugar del usuario
del trabajo. GREEN tras portar `_run_job` con `job_cr` por trabajo. La
anulación (conexión compartida sin COMMIT propio) tumba exactamente esa
prueba. Suite completa en curso sobre la instantánea `fullgate-cron`.
