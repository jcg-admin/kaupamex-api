# RED, GREEN y controles — valor vacío y posproceso de `read_group`

Diseño: `designs/read-group-postprocess.md`. Referencia odoo-tools
`abe4040ec`, `odoo/orm/models.py`.

Comando: `uv run --frozen pytest tests/unit/orm/test_read_group_postprocess.py -q --reuse-db -p no:cacheprovider`

- RED: 16 failed, todos `AttributeError` por los tres métodos ausentes.
- GREEN: 16 passed.
- Controles de anulación (cae exactamente su caso):
  - sin `unique` en el agregado `recordset` → `test_recordset_aggregate_drops_repeats_and_nulls`;
  - `prefetch` propio por registro → `test_groupby_values_become_singletons_sharing_the_prefetch`;
  - sin la rama de cadena many2one → `test_a_many2one_chain_asks_the_comodel`.
- Admisión de estilo: PASS.

## Matriz de impacto

| Eje | Contenido |
|---|---|
| Changed symbols | `BaseModel._read_group_empty_value`, `_read_group_postprocess_groupby`, `_read_group_postprocess_aggregate`; ayudante `orm.models._read_group_recordset`. |
| Changed behavior | Símbolos nuevos; ningún consumidor previo. |
| Direct consumers | `_read_group` (unidad 5). |
| Indirect consumers | Ninguno. |
| Required contract tests | `test_read_group_postprocess.py`. |
| Required regression tests | `tests/unit/orm` (grep de `_read_group_`). |
| Required integration gates | Suite completa y multidb en el corte de publicación. |
| Previously valid evidence | Ninguna. |
| Uncovered risks | Una cadena `m2o.m2o` cuyo primer comodelo sea de Django: `browse` devuelve un `QuerySet` sin `_read_group_empty_value`. La fuente no tiene modelos de Django; en el árbol actual las cadenas de `test_orm` arrancan en un `BaseModel`. |
