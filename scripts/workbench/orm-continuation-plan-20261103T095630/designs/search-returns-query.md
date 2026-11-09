# Diseño — `BaseModel._search` devuelve `Query` (paso 2 de `search-contract-analysis.md`)

Referencia: odoo-tools `abe4040ec`, `odoo/orm/models.py:5324-5394` (`_search`),
`:1347-1428` (`search_count`, `search`, `search_fetch`) y `fetch`
(`query = self._search([('id', 'in', self.ids)], active_test=False)`).
Requiere el paso 1 (`ir.rule` devuelve `Domain`, `api@1ae6b4a2`).

## Contrato que se porta

`_search(domain, offset=0, limit=None, order=None, *, active_test=True,
bypass_access=False) -> Query`, con los pasos de la referencia en su orden:

1. ACL de lectura salvo `su` o `bypass_access` (`browse().check_access('read')`).
2. `Domain(domain)`; `active_test` añade `(active, '=', True)` salvo que el
   dominio nombre el campo o el contexto lo apague.
3. `optimize_full`; `FALSE` → `browse()._as_query()`.
4. `Query(env, _table, _table_sql)` y `domain._to_sql` en el `WHERE`.
5. Reglas: `ir.rule._compute_domain` del usuario actual, optimizado con el
   recordset en `sudo()` y `active_test=False`; `FALSE` → consulta vacía; si no
   es `TRUE`, `_to_sql` en el `WHERE`.
6. `order` → `_order_to_sql`; `limit` (`False` = sin límite); `offset`.

La consulta **no se ejecuta**. Adaptaciones declaradas: `_search` sigue siendo
`classmethod` (la forma con que este archivo porta los métodos de modelo) y
toma el recordset vacío con `_from_ids(env(), (), ())`; `_compute_domain`
recibe `group_ids` y `user` explícitos, como ya lo llama `_check_access`.

## Consumidores, a su forma de referencia

| Consumidor | Antes | Después |
|---|---|---|
| `search_count` | `.count()` | `len(query)` |
| `search` | ids con `values_list` | `search_fetch(domain, [], …)` como la referencia |
| `search_fetch` | ids + segunda consulta `_as_query` | `query.is_empty()` + `_fetch_query(query, …)` en una consulta |
| `fetch` | ids con `values_list` y `_as_query` | el `Query` de `_search` directo a `_fetch_query` |
| `fields_relational` (`_multi_condition_to_sql`, `_multi_get_query_for_condition_value`) | `_queryset_query(comodel, _search(...))` | el `Query` de `_search` |
| `fields_relational` (`_many2one_condition_to_sql`) | rama `QuerySet` | rama `Query` (ya existe) |

La rama `QuerySet` de `fields_relational` se conserva para los valores que
llegan como `QuerySet` desde código de Django; deja de usarse para `_search`.

## Pruebas (RED)

`tests/unit/orm/test_search_returns_query.py`: tipo `Query` sin ejecutar
consultas; `active_test` en sus tres formas; `FALSE` → vacío; regla de un
usuario normal en el `WHERE` (una consulta); ACL denegada → `AccessError`;
`bypass_access` salta las reglas; orden, `limit=False` y `offset`; el `Query`
como valor de dominio; `search_count`; y dos condiciones de borde de la
sección 4 del análisis (`('name', 'in', False)` → vacío; `('name', 'like',
False)` → todo) a través de `search`.

Regresión: suite completa (mecanismo transversal) y multidb.
