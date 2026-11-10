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
