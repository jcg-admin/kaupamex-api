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

## Regresión amplia sobre `95ec4213`: 16 fallos reales, y su corrección

`-n 4` sobre `tests/unit/orm tests/integration/test_orm tests/unit/base
tests/integration/base`: **16 failed, 5596 passed**, EXIT=1 (no publicado).
Cuatro causas, todas de consumidores que el camino de Django resolvía por su
cuenta:

| Causa | Casos | Corrección |
|---|---|---|
| el uno-a-muchos implícito de Django (`ManyToOneRel`) no tenía compilador SQL | 10 | `ManyToOneRel` recibe las piezas del `One2many` declarado e `inverse_name` = su FK |
| many2one a un comodelo de Django (`res.partner`): sin `browse`/`_search` | 4 | `django_comodel_rows`: el mismo bloque que usaba `orm.domains` (filas del comodelo con `_filtered_access('read')` salvo `!`), compartido por los dos caminos; entra por la rama `QuerySet` |
| el dominio declarado de un many2many de Django no llegaba a la subconsulta | (en los 10) | una sola definición de `get_comodel_domain` (`_multi_comodel_domain`), que lee `domain` como la referencia; `orm.domains._comodel_domain` delega en ella |
| `child_of`/`parent_of` recibía el recordset (como en la referencia) y usaba el manager de la clase | 1 | el optimizador toma la clase del recordset |
| `ir.attachment` hereda de `BaseModel` sin `OrderMixin` | 1 | `BaseModel` adopta `OrderMixin`: `_order_to_sql` es método de `BaseModel` en la referencia; 50 de 50 modelos con MRO resuelto, sin migraciones |

*Lo que la sonda del análisis no veía:* su rejilla no tenía one2many
implícitos, comodelos de Django ni many2many con `domain`. Las 208 condiciones
equivalentes no son cobertura exhaustiva.

## Seguridad: pruebas negativas y sus controles

Añadidas a `test_search_returns_query.py` (18 passed): un `OR` no escapa la
regla; regla `FALSE` → consulta vacía; global con `AND` y de grupo sólo la del
grupo del usuario; la regla del comodelo acota la subconsulta many2one
(`BaseModel` y de Django); un `Query` de un usuario restringido sigue
restringido como valor de dominio; el superusuario ve todo; los valores viajan
como parámetros (un valor hostil no aparece en el código SQL).

- Sin la regla en el `WHERE` de `_search` → caen 6 (todas las que dependen de
  ella).
- Sin `_filtered_access` en `django_comodel_rows` → con las suites previas no
  caía **ninguna**; la prueba nueva del comodelo de Django es la que cae.
