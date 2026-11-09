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

## Nivel 2 ampliado — `23c243b9` (2026-11-09): un rojo que el derivado no vio

`tests/unit tests/integration/test_orm tests/integration/base`, `-n 4`:
`1 failed, 10886 passed, 66 skipped, 4 xfailed in 373.78s`, `EXIT=1`.

El rojo, `test_check_stale_zero_claims.py::test_the_frozen_debt_does_not_block`,
es de **esta** unidad: el docstring de `addons/base_vat/models/res_partner.py`
afirmaba con `grep -rc "def _read_group(" --include=*.py src/orm/` que el
agregador no existía, y portarlo hizo que el comando dé 1. El alcance
derivado del nivel 2 en `318e06a1` buscaba consumidores del símbolo en
`tests/` y no podía ver un reclamo en prosa de otro árbol; el gate de
reclamos de cero vive en `tests/unit/scripts`.

Corregido en `05431171` (el reclamo nombra ahora la razón real: `res.partner`
es un modelo de Django que no hereda `BaseModel`). Tras el arreglo:
`test_check_stale_zero_claims.py` → `24 passed`; el gate → `0 reclamo(s)
caducado(s)` sobre 29 citas.

Lección de procedimiento: un símbolo **nuevo** en `src/orm` incluye en su
alcance derivado `tests/unit/scripts/test_check_stale_zero_claims.py`.
