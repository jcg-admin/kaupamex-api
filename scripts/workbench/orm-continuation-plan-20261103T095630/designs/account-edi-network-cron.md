# account-edi-network-cron-0397 — el cron de web-services de `account_edi`

## Referencia

- `odoo19c: addons/account_edi/data/cron.xml:2-10` — `ir_cron_edi_network`:
  `model._cron_process_documents_web_services(job_count=20)`, cada día,
  **inactivo** (`active=False`), `noupdate="1"`; cargado por el manifiesto
  (`odoo19c: addons/account_edi/__manifest__.py:16-21`).
- Lo activan o disparan cuatro sitios: `account_edi_format.py:40-42` (crear un
  formato con web-service lo activa), `account_move.py:264` y `:283`, y
  `account_edi_document.py:251` (`_trigger()`).

## Estado heredado (consumidor en `9ef1a21b`)

| Contrato | Consumidor | Clase |
|---|---|---|
| el cron sembrado, inactivo, con su identificador externo | ausente; el manifiesto dice «el cron de la fuente no se carga aquí» | ABSENT |
| activarlo al crear un formato con web-service | ausente (`account_edi_format.py`, paso (b)) | ABSENT |
| `_trigger()` desde el asiento y el documento | declarado bloqueado (`account_move.py:282`, `account_edi_document.py:74`) | ABSENT |
| `_cron_process_documents_web_services` | portado (`account_edi_document.py:508`) | SATISFIED |

## Mecanismo canónico (Search Existing)

`src/addons/base/data/cron.py::sembrar_cron` desde una migración de datos por
addon (`addons/mail/migrations/0004_seed_cron_email_queue.py`,
`addons/auto_backup/migrations/0003_seed_cron_backup.py`), con
`sembrar_cron_vivo` para el fixture de restauración (H-API-22). Le faltan dos
cosas para este cron, medidas en el código:

1. siembra siempre con `active=True` (`cron.py:60`); la fuente lo crea
   inactivo — `spec` necesita `active`;
2. no registra identificador externo, y los cuatro consumidores de la fuente lo
   piden por `env.ref('account_edi.ir_cron_edi_network')` — `spec` necesita un
   `xml_id` que cree su fila de `ir.model.data`.

Decisión: EXTEND `sembrar_cron`/`sembrar_cron_vivo` (los dos claves opcionales,
sin cambiar a los consumidores actuales), luego la migración de `account_edi`,
luego los tres consumidores de `_trigger`/`active`.
