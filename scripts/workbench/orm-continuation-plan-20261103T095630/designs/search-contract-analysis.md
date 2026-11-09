# Análisis — el contrato de `BaseModel._search` (Odoo 19 Community)

Directiva del ejecutor 2026-11-09: satisfacer el contrato de `_search` de la
referencia; la arquitectura se decide tras investigar la referencia, el stack
Django instalado y PostgreSQL, sin crear una clase `Query` nueva ni sustituir
`QuerySet` de forma mecánica.

Evidencia: `probes/search_compiler_parity.py` (EXPERIMENTAL, ejecuta en la base
de prueba y descarta sus filas) y `outputs/search-contract/`.

## 1. Referencia funcional

Procedencia: `odoo-tools@abe4040ec1a45beee90fb694e4eae4453e46b389`, Odoo 19
Community, árbol `19.x/odoo-19.0/odoo-19.0/odoo-19.0`. Sólo lectura; no se
importa ni se ejecuta.

| Pieza | Ubicación | Firma / contrato |
|---|---|---|
| `_search` | `odoo/orm/models.py:5324-5394` | `(domain, offset=0, limit=None, order=None, *, active_test=True, bypass_access=False) -> Query` |
| `_as_query` | `:5396-5404` | `(ordered=True) -> Query` |
| `search_count` | `:1347-1360` | `len(self._search(domain, limit=limit))` |
| `search_fetch` | `:1383-1428` | `_search(...)`; `query.is_empty()` evita consultar; `_fetch_query(query, …)` lee en **una** consulta |
| `Query` | `odoo/tools/query.py:46-280` | `where_clause`, `subselect`, `select`, `is_empty`, `get_result_ids`, `set_result_ids`, `__len__`, `__iter__`, `add_join`, `make_alias`, `groupby`, `having`, `order`, `limit`, `offset` |
| `Query` como valor de dominio | `odoo/orm/domains.py:1064-1066`, `fields_relational.py:524,828-830`, `fields.py:1357` | `('campo', 'in'/'any', query)` se compila a `IN (subselect)` sin ejecutar la consulta |
| reglas | `odoo/addons/base/models/ir_rule.py:141-173` | `_compute_domain(model_name, mode) -> Domain` |
| `_read_group` | `models.py:1861-1952` | empieza con `query = self._search(domain)` y añade `SELECT`/`GROUP BY`/`HAVING` sobre ese `Query` |
| `_read_group_groupby` | `models.py:2015-2119` | rama many2one en cadena y many2many: `comodel._search(...)`, `coquery.where_clause`, `coquery.subselect(...)`, `query.add_join('LEFT JOIN', alias, subselect, condition)` |

Pasos de `_search`, en orden: ACL de lectura salvo `su` o `bypass_access`;
`Domain(domain)`; `active_test` añade `(active, '=', True)` salvo que el
dominio nombre el campo o el contexto lo apague; `optimize_full`; `FALSE` →
`browse()._as_query()`; `domain._to_sql` en el `WHERE`; dominio de `ir.rule`
optimizado con `sudo().with_context(active_test=False)` y añadido al `WHERE`
(`FALSE` → consulta vacía); `order` → `_order_to_sql`; `limit` (con `False`
como «sin límite») y `offset`. **La consulta no se ejecuta.**

Consumidores en la referencia: 14 en `odoo/orm` y 631 en 115 archivos de
addons. Pruebas originales que lo ejercitan:
`odoo/addons/test_orm/tests/{test_search,test_domain,test_many2many,test_one2many,test_fields,test_properties,test_indexed_translation,test_performance,test_timeit}.py`.

## 2. Stack Django instalado

Django 6.0.5, psycopg 3.3.4, Python 3.13.18 (`outputs/search-contract/django-inventory.txt`).

| Capacidad Django | Satisface | Por qué |
|---|---|---|
| `QuerySet.filter(Q)` | el filtro de un dominio, **no** su semántica | `Domain._to_q` diverge de la referencia en 30 condiciones de borde (sección 4) |
| `sql.Query.sql_with_params()` | compilar a `SQL` | ya se usa en `_queryset_subselect` |
| `ExtraWhere` / `QuerySet.extra(where=…)` | inyectar un `WHERE` crudo | sólo `WHERE`: no aporta uniones |
| `Join` (`sql/datastructures.py:27-160`) | **no** | `table_name` se cita como identificador (`:127`) y la condición sale de `join_field`: `LEFT JOIN (subconsulta) AS alias ON <SQL>` —el `add_join` de la referencia— exige API privada |
| `Subquery`, `Exists`, `OuterRef` | subconsultas dentro de Django | operan sobre expresiones de Django, no sobre el `SQL` que emite `_to_sql` |
| `RawSQL` | una expresión cruda | sin alias registrados en el `Query` de Django |
| alias de Django (`T2`, `U0`) | **no equivalentes** | `_to_sql`, `_order_to_sql` y `_read_group_*` nombran alias propios (`tabla__campo`) y los registran con `make_alias`/`add_join`; dos sistemas de alias en una consulta no se reconcilian por API pública |

## 3. PostgreSQL instalado

PostgreSQL 16.15 (Ubuntu), cluster `16/main`; `psql`, `pg_config`, `pg_dump`,
`pg_lsclusters`, `pg_ctlcluster`. Extensiones instaladas: `pg_trgm 1.6`,
`unaccent 1.1`, `plpgsql`; disponibles `btree_gin`, `btree_gist`, `hstore`,
`intarray`, `pg_stat_statements`. Configuración por defecto (`work_mem=4MB`,
`read committed`, `jit=on`). Sin cambios en el servidor
(`outputs/search-contract/postgres-inventory.txt`). Las construcciones del
contrato —`IN (subconsulta)`, `LEFT JOIN (subconsulta) AS … ON …`,
`COALESCE`, `DISTINCT ON`, `ARRAY_AGG … ORDER BY`, `GROUP BY`/`HAVING`— son
SQL estándar de PostgreSQL 16; ninguna exige extensión.

## 4. SQL ejecutable

Los dos compiladores que conviven hoy, condición por condición, sobre filas
sembradas en la base de prueba:

| Escenario | Resultado | Archivo |
|---|---|---|
| Rejilla de `model_domain_grid` sobre campos `BaseModel` (char, boolean, integer, many2one, many2many) | 178 iguales · 30 distintas · 8 sólo Django · 4 sólo SQL · 22 ninguno | `grid-basemodel.json` |
| Caminos, `any`/`not any`, `active` en `test_orm.message` | 10 de 10 iguales (la 11.ª es inválida en los dos) | `grid-test-orm-message.json` |
| Regla `value1 >= 2` para un usuario normal | mismas filas | `rules-plain-user.json` |
| `_search` con regla: SQL y plan | hoy **10 consultas**, ids prohibidos **materializados como literales** (120) y anti-unión `hashed SubPlan`; referencia **1 consulta**, un solo filtro; mismas filas | `rule-path-sql-and-plan.json` |

**Las 30 distintas: el camino SQL es el fiel.** Cada una se resuelve con la
regla de la referencia:

- `in`/`not in` con valor falso escalar (`False`, `''`, `0`, `[]`):
  `_optimize_in_set` (`domains.py:1304-1316`) da `FALSE`/`TRUE`. SQL devuelve
  `[]`/todo; Django devuelve las filas con `NULL`.
- `like`/`ilike`/`not like` con valor falso: `_optimize_like_str`
  (`:1391-1401`) da `TRUE`/`FALSE`; `=like` falso da `('campo', '=', False)`.
  SQL coincide; Django no.
- `=like` con `True` o lista: la referencia lanza `TypeError` (`:1407-1408`);
  SQL lo lanza, Django devuelve `[]` (5 de las 8 «sólo Django»).
- `<`/`>=` con `'3'` o `[]`: SQL convierte u optimiza; Django lanza `TypeError`
  de Python (las 4 «sólo SQL»).
- `id < False`: SQL falla en PostgreSQL (`bigint < boolean`); Django devuelve
  vacío. **Pendiente:** confirmar la conducta de la referencia para este caso.

*Métrica:* el conjunto de ids de cada compilador por condición.
*Ciega a:* el orden de las filas; el coste en tablas grandes (el plan se midió
con 200 filas); y los modelos de Django que no son `BaseModel`, cuyo camino SQL
no compila (`_check_field_access` exige un recordset): el contrato de `_search`
es de `BaseModel`.

## 5. Consumidores

Llamadas directas a `BaseModel._search` (medido con `grep` y la función que las
contiene):

| Sitio | Propiedad de `QuerySet` usada | En la referencia |
|---|---|---|
| `models.py` `search` | `values_list('pk')` | `search_fetch(domain, [])` |
| `models.py` `search_count` | `.count()` | `len(query)` |
| `models.py` `search_fetch` | `values_list('pk')` + segunda consulta `_as_query` | `query.is_empty()` + `_fetch_query(query, …)` en una consulta |
| `models.py` `fetch` | `values_list('pk')` | `self._search([('id','in',ids)], active_test=False)` como `Query` |
| `fields_relational.py` `_many2one_condition_to_sql` | rama `QuerySet` → `_queryset_subselect` | `value.subselect()` |
| `fields_relational.py` `_multi_condition_to_sql` | `_queryset_query` (envoltura `id IN (SELECT …)`) | el `Query` directo |
| `fields_relational.py` `_multi_get_query_for_condition_value` | `_queryset_query` | el `Query` directo |

Pruebas que consumen el resultado: `tests/integration/test_orm/test_many2many.py`
(`test_not_in_relation_as_query`, inyecta el resultado como valor de dominio:
la rama `Query` ya existe) y el ayudante `_check_search` de `test_domain.py`
(vía `search`).

Homónimos fuera del contrato (modelos de Django, firma propia, no heredan de
`BaseModel`): `ResGroups._search(queryset=None, order=None)`
(`src/addons/base/models/res_groups.py:351`, con sus pruebas en
`test_res_groups_port.py`), `StockQuant._search(domain=None, **kwargs)`
(`addons/stock/models/stock_quant.py:702`) y `tools.convert._search`. No
cambian.

Dependencia indirecta: `ir.rule._compute_domain` y `_build_domain` devuelven un
`Q` (`src/addons/base/models/ir_rule.py:414-490`, vía `to_q`); la referencia
devuelve un `Domain`. `_search` necesita el `Domain` para `_to_sql`. Llamadores
de `_compute_domain`: `ir_rule.py:516` (padres `_inherits`), `:537` y `:829`
(`for_current_company`), más `_check_access`/`_filtered_access` por la vía de
`Q`.

## 6. Alternativas

| Eje | A — `sql.Query` y compilador de Django | B — el `Query` portado + `Domain._to_sql` | C — conservar `QuerySet` con adaptación |
|---|---|---|---|
| Capacidades existentes | compilador, `ExtraWhere`, `Subquery` | **`tools.query.Query` ya es el de la referencia** y lo usan `_as_query`, `_fetch_query`, `lock_for_update`, `try_lock_for_update`, `_order_to_sql`, `_field_to_sql`, `_read_group_select/having`, `fields_relational`; `Domain._to_sql` está portado para todos los nodos | lo que hay |
| Código nuevo | subclases de `Join`/compilador sobre API privada para uniones con subconsulta y alias propios | `_search` con los pasos de la referencia; `ir.rule` que devuelva `Domain`; consumidores a la API de `Query` | un adaptador `QuerySet` → `Query` para `_read_group` |
| Seguridad | reglas por `Q` o por SQL crudo en `ExtraWhere`: dos caminos | reglas en el `WHERE` como la referencia, una sola consulta, sin ids materializados | hoy: ids prohibidos materializados en la consulta, 10 consultas |
| Fidelidad | `to_q` conserva las 30 divergencias | coincide con la referencia en las 30 | conserva las 30 divergencias |
| Impacto | todo el árbol de consultas | 7 sitios de `_search`, `ir.rule`, y lo que use `search` (suite completa) | mínimo |
| Compatibilidad | atada a internos de Django 6.0 | API pública de psycopg y del `Query` portado | sí |
| Mantenimiento | dos sistemas de alias | un sistema, el de la referencia | dos compiladores para lo mismo |
| Pruebas necesarias | — | contrato de `_search` (ACL, `active_test`, reglas, `FALSE`, orden, ventana, `bypass_access`, `su`), `search*`, `Query` como valor, regresión completa | — |

C sólo se admitía si una restricción técnica impidiera B en esta unidad. No la
hay: B reutiliza piezas que ya existen y están probadas.

## 7. Decisión

**B.** `BaseModel._search` devuelve el `Query` de la referencia, construido con
`Domain.optimize_full` + `_to_sql` y el `Domain` de `ir.rule` en el `WHERE`. Los
consumidores pasan a la forma de la referencia (`len`, `is_empty`,
`_fetch_query`, `subselect`). No se crea ninguna clase: el `Query` es el
portado; no se toca el compilador de Django.

Orden de implementación (cada paso con RED/GREEN, control de anulación y
regresión por impacto):

1. `ir.rule`: `_build_domain`/`_compute_domain` devuelven `Domain`, y los
   consumidores de `Q` lo convierten con `to_q` en su sitio.
2. `_search` con los pasos de la referencia; `search_count`, `search`,
   `search_fetch` y `fetch` en su forma de referencia; `fields_relational`
   deja de envolver el resultado de `_search` (la rama `QuerySet` queda para
   valores que lleguen como `QuerySet` desde fuera).
3. `_read_group_groupby` y `_read_group` (unidades 2 y 5).

Lo que este análisis no cierra: la conducta de la referencia para `id < False`
(sección 4) y las condiciones de la rejilla que ninguno de los dos compiladores
acepta (22), que son entradas inválidas en los dos.
