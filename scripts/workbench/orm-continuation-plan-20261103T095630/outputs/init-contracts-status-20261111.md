# Estado de los contratos init y de los seis errores del gate

Fecha: 2026-11-11T05:23:15. HEAD = origin = `d2b87463`; candidato en verificación:
`local/init-alias-candidate` = `c5adb3ee` (snapshot, árbol idéntico
verificado por blob).

## Los seis errores del gate completo, identificados

Gate `full-bb515cdf` (`outputs/gates/full-bb515cdf/full-bb515cdf.log`):
los seis `ERROR` son los seis casos de
`tests/integration/company/test_multidb_isolation.py`, todos con la misma
causa, contada en el log (6 apariciones):

    RuntimeError: Isolation fixture requires an explicitly owned disposable default

Es `_require_disposable_default()`, que rehúsa a propósito la base de QA
compartida: esos casos sólo corren por el procedimiento ci-multidb sobre una
base `orm_bootstrap_*` propia.

| Caso | Cubierto por |
|---|---|
| test_domain_write_without_any_company_alias_lands_in_default | ci-multidb-8c1330eb (PASSED) |
| test_write_under_company_scope_lands_in_its_own_base | ídem |
| test_rows_from_company_a_not_visible_under_company_b_scope | ídem |
| test_row_scoping_filters_by_row_and_fk_resolves_intra_base | ídem |
| test_company_schemas_and_native_connections | ídem |
| test_init_creates_the_view_only_in_the_selected_database | ídem |

Diferencia con la línea base (columna `errors` de `index.tsv`): 5 en
`full-555ac073` y `full-e302630b`; 6 desde `full-tree-38e71182`, el
primer árbol con `test_init_creates_the_view_only_in_the_selected_database`
(`3d7faad3`). No es un error ambiental nuevo: es un caso multidb más.

Con `c5adb3ee` el archivo tiene 12 casos; el gate completo debe reportar
**12** errores de esa misma causa y ninguno de otra. Una cifra distinta, o
un error con otro mensaje, es una regresión.

*Métrica:* líneas `ERROR` del log y apariciones del mensaje del fixture.
*Ciega a:* un error de setup distinto con el mismo nombre de caso (se
descarta comparando el mensaje, no sólo el nombre).

## Columna password: obligación de esquema sin TASK propia todavía

La fuente declara `password` anulable (`fields.Char` sin `required`,
`odoo19c: res_users.py:217-219`); aquí es `NOT NULL` (medido en
`designs/res-users-init.md`, «Divergencia de esquema»). Es una obligación
de esquema (migración + qué significa NULL frente al marcador `!`),
independiente de `init`.

TASK: **no acuñada**. El único mecanismo de acuñación es
`thyrox: bin/task_ids`, que escribe en el TaskStore de Thyrox, y escribir
en él desde esta VM no está autorizado. Lectura `?mode=ro` del store:
existe la fila de `TASK-API-0516` y ninguna para esta obligación. No se
inventa un número. Condición de cierre: que una sesión autorizada acuñe la
TASK (capa api) y la cite aquí y en `res-users-init.md`.
