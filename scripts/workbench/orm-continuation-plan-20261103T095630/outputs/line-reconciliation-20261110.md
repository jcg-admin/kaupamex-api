# Conciliación de las dieciocho líneas de trabajo (2026-11-10T22:13:12)

Directiva del ejecutor, «Continuidad persistente de completar-raiz-orm», §5.
No es una autoridad nueva: cada columna remite a una fuente canónica ya
existente.

| Columna | Fuente canónica |
|---|---|
| TASK | `outputs/obligation_classification.tsv` (`linked_tasks`) y el diseño de la línea |
| Unidad del plan / asentamiento | `plan.jsonl` y `outputs/continuation.jsonl` (filas `attempt`/`accepted`) |
| Estado del inventario | `orm-symbol-presence-census-20260910T175850/inventory_by_kind.py` ejecutado sobre `b7abe492` (referencia `abe4040ec1`) |
| Evidencia de comportamiento | `orm-symbol-presence-census-20260910T175850/outputs/verified_contracts.tsv` |
| Contrato y decisión | `designs/search-contract-analysis.md` (matriz de equivalencia), `designs/schema-and-translation-symbols-decision.md` |

## Lo que la conciliación destapó

1. **Trabajo sin asentamiento en el plan.** `plan.jsonl` tiene 183
   unidades; 180 con `accepted` y 3 sin fila (`misc-stripped-sys-argv`,
   `attachment-record-access`, `orm-raw-query-jsonb-0504`). Las unidades
   de `read_group`, `_write`/`_write_multi`, `modified`,
   `_get_placeholder_filename`, objetos de tabla, `_auto_init`,
   almacenados nuevos, traducciones y la Unidad L **no son filas del plan**:
   se trabajaron con su diseño y sus commits, pero sin `attempt`/`accepted`.
2. **Evidencia sin registrar.** Ese mismo trabajo no añadió su fila a
   `verified_contracts.tsv`, así que el inventario lo contaba
   `not_verified`. Se registraron 13 filas, cada una con su prueba
   ejecutada en `b7abe492` (87 passed). Las dos de Properties llevan
   control de anulación: retirar `_read_group_groupby_properties` tumba los
   6 casos de `test_read_group_properties.py`, y retirar
   `_read_group_format_result_properties` tumba sólo
   `test_a_many2one_property_is_formatted_with_its_name`, el único que
   llega a esa rama.

## Las dieciocho líneas

| # | Línea | TASK | Diseño | Implementación | Inventario en `b7abe492` | Pendiente |
|---|---|---|---|---|---|---|
| 1 | `BaseModel._search` | TASK-API-0485 | `search-contract-analysis.md` | unidades `orm-models-search-*-0485` (asentadas) | `satisfied` | la vía «B» de la matriz (reglas en el WHERE, una consulta) |
| 2 | `read_group` unidad 4 | TASK-API-0485 | `read-group-postprocess.md` | `c96d54bc`, `2b78cd90` | `_read_group_empty_value` `satisfied` | — |
| 3 | 6a `_read_group_expand_full`/`_read_group_fill_results` | TASK-API-0485 | `read-group-fill-results.md` | `23c243b9` | los dos `satisfied` | — |
| 4 | 6c `READ_GROUP_DISPLAY_FORMAT`/`_read_group_format_result` | TASK-API-0485 | `read-group-format-result.md` | `feb4a7a9`, `6733156a` | `satisfied` | — |
| 5 | 6d `regex_field_agg`/`read_group` | TASK-API-0485 | `read-group-public.md` | `59a8b2e8` | `read_group` `satisfied` | — |
| 6 | 6e Properties | TASK-API-0485 | `read-group-properties.md` | `d9e3555c` | los dos `satisfied`, con control | — |
| 7 | 6e-2 JSONB en consultas crudas | TASK-API-0504 | `orm-raw-query-jsonb.md` | `2d2eb633`, `ed3ec61f` | — | la unidad `orm-raw-query-jsonb-0504` del plan no tiene fila: falta asentarla |
| 8 | `_write`/`_write_multi`/`_flush` | TASK-API-0485 | `many2many-write-family.md` | `febd56b3`, `9bf521d1` | `_write`, `_write_multi` `satisfied`; `_flush` `not_verified` (`homonym`) | firma de `_flush` |
| 9 | `modified(vals)` y recómputo | TASK-API-0485 | — | `8f69391c`, `b68bff48` | `modified`, `_modified` `not_verified` (`homonym`) | firma; diseño no persistido como archivo propio |
| 10 | Many2one leído sin anunciar recómputo | TASK-API-0485 | — | `7a3f5b0a`, `4a88b6db` | (sin símbolo propio) | registrar su prueba en la línea 9 |
| 11 | `_get_placeholder_filename` | TASK-API-0513 | `placeholder-filename.md` | `d1209efe` | `not_verified` (`homonym`), con prueba | firma |
| 12 | `_table_objects`/`Meta`/`_add_sql_constraints` | TASK-API-0514 | `schema-and-translation-symbols-decision.md` | `7a9ed290` | `_table_objects` `not_verified` (`value`); `_add_sql_constraints` `absent` | `_add_sql_constraints` |
| 13 | `_auto_init`/`_check_removed_columns` | TASK-API-0515 | ídem | `0fa89cab` (sincronía modelos-migraciones) | los dos `absent` | portar los dos símbolos sobre la autoridad de migraciones |
| 14 | almacenados calculados sobre filas existentes | TASK-API-0515/0516 | `compute-new-stored-columns.md` | `ee950202` (`ComputeStoredFields`) | (operación de migración, sin símbolo de referencia) | — |
| 15 | TASK-GEN-0060 traducciones JSONB | TASK-GEN-0060 | `schema-and-translation-symbols-decision.md` | `ef86377b` | `Field.translate` `not_verified` (`installed_elsewhere`) | evidencia por símbolo |
| 16 | `_RelationalMulti` | TASK-API-0485 | `many2many-write-family.md` | `91721624`, `4a87a36a` | `not_verified` (`match`) | registrar su prueba |
| 17 | `Environment`/`Registry` | TASK-API-0485 | `environment-mapping.md`, `environment-getitem-recordset.md` | unidades `orm-environments-*-0485`, `orm-registry-*-0485` (asentadas) | `Environment.user`/`company`/`companies` `not_verified` | e8 (`module-install-cycle.md`) |
| 18 | Unidad L, seguridad HR | TASK-API-0397, TASK-API-0382 | `module-install-cycle.md` (L1–L5, e1–e8, L4f) | `8ab54be4`, `b7abe492` | (addons, fuera de las raíces del inventario) | gate multi-DB de `b7abe492`; e8 |

## Denominador de la raíz ORM (`src/orm` + `src/tools`, `b7abe492`)

| Tipo | Aplicables | Satisfechos | Ausentes | Divergentes | No verificados |
|---|---|---|---|---|---|
| Archivos | 78 | 18 | 8 | 0 | 52 |
| Clases | 159 | 50 | 43 | 0 | 66 |
| Funciones | 457 | 273 | 133 | 0 | 51 |
| Métodos | 1343 | 511 | 117 | 0 | 715 |
| Atributos | 399 | 96 | 45 | 0 | 258 |
| Propiedades | 76 | 32 | 14 | 0 | 30 |
| **Total** | **2512** | **980** | **360** | **0** | **1172** |

Contra el inventario registrado en `c338a12a` (2026-11-09): ausentes
392 → 360, satisfechos 969 → 980.

*Métrica:* categoría de cada símbolo de la referencia según
`inventory_by_kind.py`; `satisfied` exige firma coincidente y una prueba
registrada.
*Ciega a:* que la prueba registrada cubra todas las ramas del símbolo —por
eso las dos filas de Properties llevan control de anulación y las demás no—,
y a la integración y la aceptación, que el plan reserva al ejecutor (I-011).

## Asentamiento retrospectivo (2026-11-10T22:35:18)

Directiva del ejecutor del mismo día, §1: asentar sin inventar ejecuciones.

**Mecanismo.** La vía canónica es `probes/settle_item.py`, la vía
`preexisting` de `thyrox: src/session/task_continuation.py`. No reescribe
historia: ejecuta **ahora** el `verify` del ítem sobre un árbol limpio y anota
`attempt` y `accepted` con el commit real, `model: conversational-session` y
`source: preexisting`. El ítem tiene que estar en `plan.jsonl`; los que
faltaban entraron por `local_plan incorporate` (lee el store de Thyrox en
`mode=ro`; escribe sólo `plan.jsonl` y `plan.provenance.json` de este
Workbench), con las filas en `outputs/retro-settlement-rows-20261110.jsonl` y
`candidates: ["conversational-session"]` para no atribuirlas a un modelo
worker.

| Ítem | TASK | Obligaciones | `verify` en `ec302e0a` |
|---|---|---|---|
| `orm-search-returns-query-0485` | TASK-API-0485 | `BaseModel._search` | 18 passed |
| `orm-read-group-core-0485` | TASK-API-0485 | `BaseModel._read_group` | 7 passed |
| `orm-read-group-postprocess-0485` | TASK-API-0485 | `_read_group_empty_value` | 16 passed |
| `orm-read-group-fill-results-0485` | TASK-API-0485 | `_read_group_expand_full`, `_read_group_fill_results` | 8 passed |
| `orm-read-group-format-result-0485` | TASK-API-0485 | `_read_group_format_result` | 9 passed |
| `orm-read-group-public-0485` | TASK-API-0485 | `read_group` | 8 passed |
| `orm-read-group-properties-0485` | TASK-API-0485 | `_read_group_groupby_properties`, `_read_group_format_result_properties` | 6 passed |
| `orm-write-multi-0485` | TASK-API-0485 | `_write`, `_write_multi` | 8 passed |
| `orm-raw-query-jsonb-0504` (ya estaba en el plan) | TASK-API-0504 | la del plan | 5 passed |

Un primer lanzamiento coincidió con la recuperación de PostgreSQL tras el
reclamo del contenedor (arranque 22:27:48Z); se detuvo antes de escribir
ninguna fila —`continuation.jsonl` sin cambios, comprobado— y se relanzó con
`pg_isready` en verde, para que un fallo del entorno no quedara como
`attempt` fallido de la unidad.

**Idempotencia.** `settle_item.py` no comprueba si el ítem ya está
aceptado: relanzarlo añadiría otro `attempt`. La conciliación la hace
idempotente filtrando antes por estado: sólo se asienta un ítem sin fila
`accepted` en `continuation.jsonl`.

**Asentamiento no es aceptación.** `plan_coverage.json` sigue declarando
`acceptance: requires executor authority (I-011)`.

## Lo que queda `settlement_pending`, y por qué

| Línea | Motivo |
|---|---|
| 8 `_flush` | firma `homonym`: el inventario no la da por satisfecha; sin obligación verificable no se asienta |
| 9 `modified`/`_modified`, 10 Many2one sin recómputo | firma `homonym`; además el diseño no está persistido como archivo propio |
| 11 `_get_placeholder_filename` | firma `homonym` (TASK-API-0513) |
| 12 `_table_objects`/`_add_sql_constraints` | `_add_sql_constraints` ausente: unidad s2 en curso |
| 13 `_auto_init`/`_check_removed_columns` | s1 implementado sin llamador productivo; s3 y s4 en curso |
| 14 almacenados nuevos | operación de migración (`ComputeStoredFields`), sin símbolo de referencia propio que asentar |
| 15 TASK-GEN-0060 | `Field.translate` `installed_elsewhere`; evidencia por símbolo pendiente |
| 16 `_RelationalMulti` | sin prueba registrada como evidencia del símbolo |
| 17 `Environment.user`/`company`/`companies` | e8 |
| 18 Unidad L | sus obligaciones viven en addons (fuera de las raíces del inventario); depende de e8 para las tres reglas omitidas |

## Conciliación tras s1–s5 (2026-11-10T23:43:48, `e302630b`)

### El plan, por vía de ejecución

| Estado final en `outputs/continuation.jsonl` | Ítems | Vía |
|---|---|---|
| `accepted` | 189 | **todos** `source: preexisting`: implementados a mano y asentados después con `probes/settle_item.py` (vía `preexisting` de `task_continuation`), con su `verify` en verde y el árbol limpio |
| `hard_block` | 2 | `misc-stripped-sys-argv` (no hay parser que declare `-s/-u/-i`; depende de TASK-API-0382) y `attachment-record-access` (falta `create_uid` en `ir_attachment`) |
| ejecutados por un worker de Thyrox | **0** | ningún `attempt` del plan lleva otra fuente que `preexisting` |

Total: 191 ítems y 385 eventos (190 `attempt`, 189 `accepted`,
6 `hard_block`). No se ha escrito ninguna fila nueva en este pase.

### Las líneas `settlement_pending`, con su estado actual

| Línea | Diseño | Commit | Pruebas | Anulación | Gate | Estado en el inventario | Asentable hoy |
|---|---|---|---|---|---|---|---|
| 8 `_flush` | `write-multi-flush.md` | sí | sí | sí | completo | `homonym` | no: firma `homonym` |
| 9 `modified`/`_modified` | `write-announces-computed.md` | sí | sí | sí | completo | `homonym` | no |
| 10 Many2one sin recómputo | `many2one-deferred-read.md` | sí | sí | sí | completo | (fila del plan `accepted`) | ya asentada como ítem del plan |
| 11 `_get_placeholder_filename` | `placeholder-filename.md` | sí | `test_placeholder_filename.py` | sí | completo | `homonym` | no |
| 12 `_table_objects`/`_add_sql_constraints` | `schema-and-translation-symbols-decision.md` (s2) | `555ac073` | 7 casos | sí | completo + multidb 5/5 (`555ac073`) | `paired_by_name` / `value` | no: vía `RecordLoaderMixin` declarada (`models.py:4493`) |
| 13 `_auto_init`/`_check_removed_columns` | ídem (s1, s3, s4) | `555ac073` | 7 casos | sí | ídem | `paired_by_name` | no, por la misma vía |
| s5 `init` | ídem (s5) | `e302630b` + corrección en curso | 4 unitarias + 1 multidb | sí (2) | completo `e302630b`: 12 689 passed, 0 failed | `paired_by_name` | no, por la misma vía |
| 14 almacenados nuevos | `compute-new-stored-columns.md` | sí | sí | sí | completo | sin símbolo de referencia | no aplica asentamiento por símbolo |
| 15 TASK-GEN-0060 | `translate-jsonb-storage.md` | parcial | sí | — | — | `installed_elsewhere` | no |
| 16 `_RelationalMulti` | `many2many-write-family.md` | sí | sí | sí | completo | sin fila de evidencia | falta la fila en `verified_contracts.tsv` |
| 17 `Environment.user/company/companies` | `environment-*.md` | — | — | — | — | e8 | no: frontera e8 |
| 18 Unidad L / HR | `module-install-cycle.md`, `hr-basemodel-dependencies.md` | sí | sí | sí | completo | fuera de las raíces del inventario | no |

**Por qué `paired_by_name` impide asentar s1–s5.** El censo
(`inventory_by_kind.py`, §26) exige coincidencia estructural **con la
misma clase dueña**. En la fuente estos métodos cuelgan de `BaseModel`;
aquí viven en `RecordLoaderMixin`, porque `models.Model` es el de Django.
Esa divergencia de vía está declarada, así que el símbolo queda
`not_verified` por regla y no se fuerza a `satisfied`. **Obligación
abierta:** decidir si el censo debe aceptar la dueña declarada del mixin
como coincidencia estructural. Es una regla del inventario, no de este
pase.

### Ninguna unidad se reimplementó por faltarle el asentamiento

Las líneas 8, 9, 11 y 16 tienen implementación, pruebas y gate. Sólo les
falta el estado del inventario o la fila de evidencia. No se repitió su
trabajo.
