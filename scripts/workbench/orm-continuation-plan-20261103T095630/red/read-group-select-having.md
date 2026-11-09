# RED, GREEN y controles — `_read_group_select` y `_read_group_having`

Unidad 1 de `designs/read-group-family-plan.md`. Referencia:
`odoo19c: odoo/orm/models.py:1953-2013`, `:2121-2148` y
`READ_GROUP_AGGREGATE` (`:300-313`), odoo-tools `abe4040ec`.

Comando: `uv run --frozen pytest tests/unit/orm/test_read_group_select_having.py -q --reuse-db -p no:cacheprovider`

- RED: 25 failed (`AttributeError: ... '_read_group_select'` y
  `'_read_group_having'`).
- GREEN: 25 passed. El caso `sum_currency` declara una empresa con
  `company_scope`: la fuente lee `env.company.root_id`, y aquí `env.company`
  es `None` sin empresa activa (en la referencia siempre hay una).
- Controles de anulación (cada uno deja caer exactamente su caso):
  - sin el `AND` implícito final → cae `test_having_terms_are_and_by_default`;
  - sin la guarda de `recordset` → cae `priority:recordset`;
  - sin `query.add_join` de las tasas → cae `test_sum_currency_joins_the_latest_rate`.
- Admisión de estilo: PASS. Las líneas largas de la fuente se envolvieron;
  los mensajes de error son idénticos y el SQL de la subconsulta sólo cambia
  en espacios en blanco.

## Adaptaciones declaradas

- `res.currency.rate` es un modelo de Django: `env[...]` devuelve la clase y
  `_field_to_sql` se llama sobre una instancia (`env['res.currency.rate']()`).
- Las firmas pierden las anotaciones `str`/`Query`/`list`/`SQL`; el contrato
  no cambia.

## Matriz de impacto

| Eje | Contenido |
|---|---|
| Changed symbols | `orm.models.READ_GROUP_AGGREGATE`, `BaseModel._read_group_select`, `BaseModel._read_group_having`. |
| Changed behavior | Símbolos nuevos: ningún consumidor previo los recibe. |
| Direct consumers | Ninguno todavía; lo serán `_read_group` (unidad 5) y `_read_group_orderby`. |
| Indirect consumers | `stock.quant` y `account.invoice.report` declaran su propio `_read_group_select`, pero heredan de Django `Model`, no de `BaseModel`: no cambian. |
| Required contract tests | `test_read_group_select_having.py`. |
| Required regression tests | `tests/unit/orm`, `tests/unit/account`, `tests/unit/stock`, `tests/unit/tools/test_sql.py` (grep de `_read_group_select`). |
| Required integration gates | Suite completa y multidb en el corte de publicación (ORM espejado). |
| Previously valid evidence | Ninguna. |
| Uncovered risks | El desbloqueo de `account.invoice.report._read_group_select` depende de `read_group` (unidad 5), no de esta unidad. |

## Regresión de impacto (nivel 2)

Sobre `a5ce8acd`, `-n 4`: `tests/unit/orm tests/unit/account tests/unit/stock tests/unit/tools/test_sql.py` → 3551 passed, 39 skipped, EXIT=0.
