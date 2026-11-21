# account-edi-journal-computes-0397 — los dos cómputos de `account.journal` en `account_edi`

## Referencia

- `edi_format_ids` (`odoo19c: addons/account_edi/models/account_journal.py:11-16`):
  `Many2many` calculado y **almacenado**, `readonly=False`, con
  `@api.depends('type', 'company_id', 'company_id.account_fiscal_country_id')`;
  `_compute_edi_format_ids` (`:54-79`) protege los formatos con documentos
  `to_send`/`to_cancel` con una sola consulta agregada por lote.
- `compatible_edi_ids` (`:18-20`): calculado sin almacenar, mismas
  dependencias; `_compute_compatible_edi_ids` (`:46-52`).

## Estado heredado (consumidor en `f1111d99`)

| Contrato | Consumidor | Clase |
|---|---|---|
| `edi_format_ids` calculado y almacenado, reactivo a `type`/`company_id` | M2M inverso declarado en `account_edi_format.py`; `compute_edi_format_ids(journal)` se invoca a mano | DIVERGENT |
| protección por lote (`ARRAY_AGG` sobre los diarios del recordset) | filtro por un diario | DIVERGENT |
| `compatible_edi_ids` como campo calculado (recordset) | `property` que devuelve una lista | DIVERGENT |
| `write` (`:25-41`) | override por `extend_model` | SATISFIED (`account-edi-journal-write-0397`) |

## Cambio previsto

`edi_format_ids` y `compatible_edi_ids` declarados sobre `account.journal`
por `extend_model(campos=...)` con `compute`, `store` y `@api.depends` de la
fuente; los dos cómputos como métodos del recordset. Consumidores:
`account_edi_format.py` (que hoy declara el M2M inverso y llama a la
función) y `account_move.py:285`.

Prueba prevista: `tests/unit/account_edi/test_account_journal_computes.py` —
cambiar `type` recalcula `edi_format_ids`; dos diarios en un recordset
conservan cada uno sus formatos protegidos; `compatible_edi_ids` es un
recordset.
