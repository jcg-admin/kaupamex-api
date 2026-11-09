# RED, GREEN y controles — `_read_group` (unidad 5)

Diseño: `designs/read-group.md`. Referencia: odoo-tools `abe4040ec`,
`odoo/orm/models.py:1861-1952`.

Comando: `uv run --frozen pytest tests/unit/orm/test_read_group.py -q --reuse-db -p no:cacheprovider`

- RED: 7 failed (`AttributeError: ... '_read_group'`).
- GREEN: 7 passed, con SQL ejecutado sobre filas sembradas.
- Controles de anulación (cae exactamente su caso):
  - sin `HAVING` → `test_having_filters_groups`;
  - sin la fila de valores vacíos cuando no hay agrupado → `test_an_empty_domain_without_groupby_gives_the_empty_values`;
  - `_search` con `bypass_access=True` (sin reglas) → `test_a_rule_hides_the_groups_of_forbidden_rows`.
- Admisión de estilo: PASS.

## Matriz de impacto

| Eje | Contenido |
|---|---|
| Changed symbols | `BaseModel._read_group` (nuevo, `classmethod`). |
| Changed behavior | Ninguno previo: sin consumidores vivos (sólo un docstring de `base_vat`). |
| Direct consumers | `read_group`/`formatted_read_group` (unidad 6). |
| Required contract tests | `test_read_group.py`. |
| Required regression tests | `tests/unit/orm`. |
| Required integration gates | Suite completa y multidb en el corte de publicación. |
| Uncovered risks | Agrupados por propiedades y cadenas hacia comodelos de Django, declarados bloqueados en la unidad 2. |

## Regresión de impacto (nivel 2)

Pendiente con las unidades 2 y 3: espera a que el gate de `6d4c1764` libere las
bases `_gw*`.
