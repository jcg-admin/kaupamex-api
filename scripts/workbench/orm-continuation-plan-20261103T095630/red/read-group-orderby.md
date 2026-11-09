# RED, GREEN y controles — `_read_group_orderby` (unidad 3 de `read_group`)

Diseño: `designs/read-group-orderby.md`. Referencia: odoo-tools `abe4040ec`.

Comando: `uv run --frozen pytest tests/unit/orm/test_read_group_orderby.py -q --reuse-db -p no:cacheprovider`

- RED: 8 failed (`AttributeError: ... '_read_group_orderby'`).
- GREEN: 8 passed.
- Controles de anulación (cae exactamente su caso):
  - sin recorrer el many2one → `test_a_many2one_ordered_by_name_orders_by_the_comodel`;
  - sin el desplazamiento de `day_of_week` → `test_day_of_week_shifts_by_the_first_day_of_the_language`;
  - sin el orden por defecto de los agrupados → `test_without_order_the_groupby_terms_order`.
- Admisión de estilo: PASS.

Se porta además `regex_order_part_read_group` (`:105-111`), verbatim.

## Matriz de impacto

| Eje | Contenido |
|---|---|
| Changed symbols | `BaseModel._read_group_orderby`, `orm.models.regex_order_part_read_group` (nuevos). |
| Changed behavior | Ninguno previo. |
| Direct consumers | `_read_group` (unidad 5). |
| Required contract tests | `test_read_group_orderby.py`. |
| Required regression tests | `tests/unit/orm`. |
| Required integration gates | Suite completa y multidb en el corte de publicación. |
| Uncovered risks | Ninguno conocido; sin consumidores hasta la unidad 5. |

## Regresión de impacto (nivel 2)

Pendiente con la de la unidad 2: espera a que el gate de `6d4c1764` libere las
bases `_gw*`.

## Nivel 2 — `318e06a1` (2026-11-09, boot `3428adc4`)

Alcance derivado (`grep -rlE "_read_group|regex_order_part_read_group|property_to_sql|_base_date_property_to_sql" tests/`):
`tests/unit/orm tests/unit/account tests/unit/tools tests/unit/web`.

```
uv run --frozen pytest -n 4 -q --reuse-db -p no:cacheprovider <alcance>
4658 passed, 39 skipped, 882 warnings in 219.74s
EXIT=0
```

Los 39 omitidos son pruebas de la referencia cuyo árbol no se carga en esta
ejecución (el propio informe lo declara). El nivel 3 (suite entera y
multidb) de la revisión que contiene esta unidad sigue pendiente.
