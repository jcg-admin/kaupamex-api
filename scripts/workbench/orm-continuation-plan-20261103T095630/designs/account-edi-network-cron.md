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

## Lo que esta unidad no cierra

- **`job_count=20`.** La fuente llama
  `_cron_process_documents_web_services(job_count=20)`; el runner de este
  árbol (`IrCron._callback`) invoca el método sin argumentos, así que aquí se
  procesan todos los pendientes de una vez. Sucesor:
  **`cron-runner-method-arguments-0397`** (TASK-API-0397), que porta la
  invocación con argumentos del runner.

## Semántica medida durante la implementación

`IrCron._trigger_list` descarta los disparos ya vencidos cuando el cron está
inactivo, como `odoo19c: odoo/addons/base/models/ir_cron.py:764-792`. Por eso
la prueba del redisparo activa el cron antes de procesar: con el cron inactivo
la fuente tampoco deja disparo.

## Símbolos, referencia y prueba

Pruebas: `tests/unit/account_edi/test_account_edi_network_cron.py` y
`tests/unit/base/test_cron_seed_active_and_xml_id.py`.

| Símbolo | Referencia |
|---|---|
| `0007_seed_cron_edi_network` (`CRON_EDI_NETWORK`) | `odoo19c: addons/account_edi/data/cron.xml:2-10` |
| `AccountEdiDocument._cron_process_documents_web_services` | `odoo19c: addons/account_edi/models/account_edi_document.py:237-251` |
| `AccountEdiFormat.create` (paso (b)) | `odoo19c: addons/account_edi/models/account_edi_format.py:40-42` |
| `_create_edi_documents_after_post` (tramo de `_post`) | `odoo19c: addons/account_edi/models/account_move.py:233-264` |
| `button_cancel` | `odoo19c: addons/account_edi/models/account_move.py:275-283` |
| `sembrar_cron`, `sembrar_cron_vivo`, `_register_xml_id` | `odoo19c: addons/account_edi/data/cron.xml:2-10` |

`AccountMove` sigue siendo modelo de Django: los dos ganchos del asiento leen
el contexto y `env.ref` del entorno ambiental (`orm.environments.env`), no de
`self.env`. La primera versión usaba `self.env` y el subconjunto derivado la
rechazó (22 pruebas de `tests/unit/account` al publicar un asiento).
