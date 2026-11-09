# RED, GREEN y controles — `BaseModel._search` devuelve `Query`

Diseño: `designs/search-returns-query.md`; decisión y evidencia:
`designs/search-contract-analysis.md`. Referencia: odoo-tools `abe4040ec`,
`odoo/orm/models.py:5324-5394` y `:1347-1428`.

Comando: `uv run --frozen pytest tests/unit/orm/test_search_returns_query.py -q --reuse-db -p no:cacheprovider`

- RED: 7 failed, cada uno por su razón (`AccessQuerySet` en vez de `Query`;
  sin `is_empty`, `limit`, `offset`; filas archivadas de un `QuerySet`; la
  comparación `value1 >= '3'` lanzaba `TypeError` en el filtro de Django).
  Tres casos pasan en los dos lados y quedan como guardas de regresión: el
  `Query` como valor de dominio (la rama ya existía), `search_count` y el
  `AccessError` sin permiso de lectura.
- Corrección durante el RED: el primer caso de borde
  (`('name', 'in', False)`) pasaba con el código anterior. Eso destapó un
  defecto de la sonda del análisis (comparaba `_to_q` sin optimizar), que se
  corrigió en `api@c2481c06`; el caso se sustituyó por uno que sí discrimina.
- GREEN: 10 passed.
- Controles de anulación (cae exactamente su caso):
  - sin el dominio de `ir.rule` en el `WHERE` → caen `test_the_rule_goes_into_the_where_of_one_query` y `test_bypass_access_skips_the_rules`;
  - sin el filtro de archivados → `test_active_test_filters_archived_unless_asked`;
  - sin `limit`/`offset` → `test_order_limit_and_offset_are_set_on_the_query`;
  - sin la salida temprana de `FALSE` → `test_a_false_domain_is_an_empty_query`.
  Un primer intento del control de `limit` no se aplicó (patrón repetido en el
  archivo) y dio 10 passed: no cuenta; se repitió con un ancla única.
- Admisión de estilo: PASS.

## Cambios en los consumidores

`search` → `search_fetch(domain, [])`; `search_count` → `len(query)`;
`search_fetch` → `is_empty()` + `_fetch_query(query, …)` en una consulta;
`fetch` → el `Query` de `_search` directo. En `fields_relational` el resultado
de `_search` entra sin envolver y `_queryset_query` desaparece (sin
consumidores); `_queryset_subselect` se queda para valores `QuerySet` que
lleguen desde código de Django.

## Matriz de impacto

| Eje | Contenido |
|---|---|
| Changed symbols | `BaseModel._search`, `search`, `search_count`, `search_fetch`, `fetch`; `fields_relational._multi_condition_to_sql`, `_multi_get_query_for_condition_value`; retirado `_queryset_query`. |
| Changed behavior | `_search` devuelve `Query` sin ejecutar; las reglas van al `WHERE` (una consulta, sin ids materializados); `search_fetch` lee en una consulta. |
| Direct consumers | Los de arriba. |
| Indirect consumers | Todo `search`/`search_count`/`search_read`/`fetch` de `BaseModel`, y cada condición x2many o many2one con dominio. |
| Required contract tests | `test_search_returns_query.py`. |
| Required regression tests | Suite completa: mecanismo transversal. |
| Required integration gates | Suite completa y multidb sobre la revisión. |
| Previously valid evidence | Ninguna: cambia el camino de toda búsqueda. |
| Uncovered risks | `id < False` falla ahora en PostgreSQL, como en la referencia leída (sección 4 del análisis); un llamador que dependiera de que devolviera filas lo verá en la suite. |
