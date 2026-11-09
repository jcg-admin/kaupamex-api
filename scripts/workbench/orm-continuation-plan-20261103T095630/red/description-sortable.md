# RED, GREEN y controles — `Field._description_sortable`

Comando: `uv run pytest tests/unit/orm/test_description_sortable.py -q --reuse-db -p no:cacheprovider -W ignore`

- RED: 1 failed (`foo_name` → `False`), 2 passed (los controles de columna y
  de calculado sin columna).
- GREEN: 3 passed.
- Controles: responder por la columna → cae el `related`; capturar sólo
  `AccessError` → cae el calculado (el `ValueError` sube).
- Admisión de estilo: PASS.

## Matriz de impacto

| Eje | Contenido |
|---|---|
| Changed symbols | `orm.fields._field_description_sortable`. |
| Changed behavior | Un `related` no almacenado de un `BaseModel` se publica como ordenable. |
| Direct consumers | `fields_get` (`sortable`). |
| Indirect consumers | El cliente web, que ofrece ordenar por esas columnas. |
| Required contract tests | `test_description_sortable.py`. |
| Required regression tests | `tests/unit/{orm,base,web}`, `tests/integration/base` (grep de `sortable`, `fields_get`). |
| Required integration gates | Suite completa y multidb en el corte de publicación. |
| Previously valid evidence | Ninguna. |
| Uncovered risks | Un `related` cuyo recorrido falle con otra excepción: la fuente tampoco la captura. |
