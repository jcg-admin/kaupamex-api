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

## Investigación del mecanismo (2026-11-22, sólo lectura)

- La razón heredada de declarar el M2M en `account.edi.format`
  («`account/models/account_journal.py` está fuera del write-set de este
  agente», `addons/account_edi/models/account_edi_format.py:100-104`) ya no
  rige: es prosa de una ejecución paralela pasada, no un contrato.
- Precedente para declararlo en el diario sin tocar su archivo:
  `addons/purchase_stock/models/stock_reference.py:68-84` cuelga
  `purchase_ids` sobre `stock.StockReference` con
  `extend_model(campos=...)` y `db_table` explícito, y su migración vive en la
  app dueña del modelo (`addons/stock/migrations/0018_...`).
- Consumidores del lado `journals` hoy: uno,
  `tests/unit/account_edi/test_account_edi_basemodel.py:102`.
- Conservar la tabla `through` existente con `db_table` hace que el cambio
  sea de estado, no de datos: migración con `SeparateDatabaseAndState`
  (estado: quitar `journals` de `account_edi`, añadir `edi_format_ids` en
  `account`; base de datos: nada). Se mide con `sqlmigrate` antes de
  aplicarla.

## Símbolos, referencia y prueba

Pruebas: `tests/unit/account_edi/test_account_journal_computes.py` y
`tests/unit/account_edi/test_account_edi_basemodel.py`.

| Símbolo | Referencia |
|---|---|
| `_compute_compatible_edi_ids` | `odoo19c: addons/account_edi/models/account_journal.py:46-52` |
| `_compute_edi_format_ids` | `odoo19c: addons/account_edi/models/account_journal.py:54-79` |
| `apply_account_edi_extensions` (los dos campos) | `odoo19c: addons/account_edi/models/account_journal.py:11-20` |
| `AccountEdiFormat.create` (paso (a)) | `odoo19c: addons/account_edi/models/account_edi_format.py:24-39` |
| `0006_journal_edi_format_ids_state`, `0052_accountjournal_edi_format_ids` | `odoo19c: addons/account_edi/models/account_journal.py:11-16` |

## Dependencia descubierta al integrar

Escribir `edi_format_ids` (calculado, almacenado y editable) se perdía en el
volcado siguiente: el `write` del ORM aplicaba los comandos sin descartar el
recálculo pendiente ni la marca de sucio. Se cerró como unidad propia,
`write-many2many-discards-recompute-0397` (`28e327b3`).

## Lo que esta unidad no cierra

El paso (b) del `create` del formato —activar el cron
`account_edi.ir_cron_edi_network` cuando un formato necesita web-service
(`odoo19c: addons/account_edi/models/account_edi_format.py:40-42`)— exige
sembrar el cron en datos. Sucesor: `account-edi-network-cron-0397`, en esta
misma TASK.
