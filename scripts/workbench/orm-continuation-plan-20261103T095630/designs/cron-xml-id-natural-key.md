# cron-xml-id-natural-key-0397 — cada cron se identifica por su xml_id

Fecha: 2026-11-22T09:50:49. Sucesora de `cron-runs-server-action-0397`
(`designs/cron-runs-server-action.md`): con el cron ejecutando su `code`,
`method_name` ya no decide qué corre, pero seguía siendo la **identidad** del
cron para la siembra y para cuatro consumidores. La fuente identifica cada
cron por el `id` de su `<record model="ir.cron">` y lo pide con `env.ref`.

## Referencia

| Cron del consumidor | `<record id>` de la fuente |
|---|---|
| `CRON_AUTOVACUUM` | `odoo19c: odoo/addons/base/data/ir_cron_data.xml:3-11` — `base.autovacuum_job` |
| `CRON_EMAIL_QUEUE` | `odoo19c: addons/mail/data/ir_cron_data.xml:4-13` — `mail.ir_cron_mail_scheduler_action` |
| `CRON_BASE_AUTOMATION_CHECK` | `odoo19c: addons/base_automation/data/base_automation_data.xml:4-12` — `base_automation.ir_cron_data_base_automation_check`, `active=False` |
| `CRON_SEND_ABANDONED_CART_EMAIL` | `odoo19c: addons/website_sale/data/ir_cron_data.xml:3-10` — `website_sale.ir_cron_send_availability_email` |
| `CRON_AUTO_CLOSE_TICKETS` | `odoo19e: helpdesk/data/ir_cron_data.xml:4-13` — `helpdesk.ir_cron_auto_close_ticket` |
| `CRON_BACKUP` | `odoo18c: app_auto_backup/data/backup_data.xml:4` — `backup_scheduler`; el módulo aquí es `auto_backup` |
| `CRON_EDI_NETWORK` | ya declarado: `account_edi.ir_cron_edi_network` |
| `CRON_EXPIRE_VOUCHERS` | **sin contraparte**: `loyalty` de la fuente no siembra ningún cron (`odoo19c: addons/loyalty/data/loyalty_data.xml`). Su xml_id es propio del proyecto, `loyalty.ir_cron_expire_vouchers`, con el prefijo `ir_cron_` de la convención de la fuente |

Consumidores de la fuente que piden el cron por xml_id:

- `odoo19c: addons/base_automation/models/base_automation.py:531-541` —
  `action_open_scheduled_action`.
- `odoo19c: addons/base_automation/models/base_automation.py:647-660` —
  `_update_cron`.
- `odoo18c: app_auto_backup/models/db_backup.py:287-292` — `_take_dump` lee
  `env.ref('app_auto_backup.backup_scheduler').user_id`.
- `odoo18c: app_auto_backup/models/db_backup.py:355-360` — `action_run_cron`.

## Estado heredado (consumidor en `892034dd`)

| Contrato | Consumidor | Clase |
|---|---|---|
| todo cron sembrado lleva su xml_id | 1 de 8 specs (`CRON_EDI_NETWORK`) | DIVERGENT |
| la siembra encuentra el cron por su xml_id | por `(model_name, method_name)` (`src/addons/base/data/cron.py:15`) | DIVERGENT |
| `base_automation` y `auto_backup` piden su cron con `env.ref` | filtran `IrCron` por `ir_actions_server__method_name` (`base_automation.py:1150-1156,1365-1371`, `db_backup.py:557-560,670-673`) | DIVERGENT |
| el cron de `base_automation` existe en la base | sólo lo siembra el fixture de `tests/conftest.py:391`; ninguna migración | ABSENT |
| ese cron nace inactivo | el spec no declara `active` y su comentario dice lo contrario | DIVERGENT |

La prosa de `addons/base_automation/data/__init__.py:5-9` dice que falta
`migrations/0001_initial.py`; medido: la app llega a `0007`. Se corrige.

## Cambio previsto

1. Cada spec declara `xml_id` (tabla de arriba); `CRON_BASE_AUTOMATION_CHECK`
   declara además `active: False`.
2. `sembrar_cron` y `sembrar_cron_vivo` comparten `_find_seeded_action`: con
   `xml_id` declarado, la acción del cron que `ir.model.data` nombra; si no
   hay fila de `ir.model.data` todavía (base sembrada antes de esta unidad),
   la del par `(model_name, method_name)`, y `_register_xml_id` la vincula. Un
   spec sin `xml_id` conserva la clave antigua.
3. Una migración de datos por addon vuelve a sembrar su spec, que ahora
   registra el xml_id sobre la fila existente: `base/0127`,
   `auto_backup/0008`, `helpdesk/0007`, `loyalty/0006`, `mail/0014`,
   `website_sale/0008`; `base_automation/0008` siembra su cron por primera
   vez.
4. `BaseAutomation.action_open_scheduled_action`, `BaseAutomation._update_cron`
   y los dos sitios de `DbBackup` piden el cron con
   `env().ref(<xml_id>, raise_if_not_found=False)`.

## Fuera de esta unidad (sucesoras)

- `helpdesk`: la fuente corre `helpdesk.team._cron_auto_close_tickets()`,
  inactivo; aquí `SupportTicket.auto_close_stale()`, activo — sucesora
  **`helpdesk-auto-close-cron-0397`**.
- `mail`: la fuente pasa `batch_size=1000`; aquí el default `_BATCH_SIZE = 50`
  — sucesora **`mail-queue-cron-batch-0397`**.
- Los `name` de cron en español frente a los de la fuente.

## Símbolos, referencia y prueba

Pruebas: `tests/unit/base/test_cron_xml_id_identity.py`.

| Símbolo | Referencia | Prueba |
|---|---|---|
| `sembrar_cron`, `sembrar_cron_vivo`, `_find_seeded_action`, `_register_xml_id` | `odoo19c: odoo/addons/base/data/ir_cron_data.xml:3-11` | `test_seed_finds_cron_by_xml_id`, `test_seed_links_xml_id_to_legacy_row` |
| `CRON_AUTOVACUUM`, `0127_cron_xml_ids` | `odoo19c: odoo/addons/base/data/ir_cron_data.xml:3-11` | `test_every_seeded_cron_has_its_xml_id` |
| `CRON_EMAIL_QUEUE`, `0014_cron_xml_id` | `odoo19c: addons/mail/data/ir_cron_data.xml:4-13` | `test_every_seeded_cron_has_its_xml_id` |
| `CRON_SEND_ABANDONED_CART_EMAIL`, `0008_cron_xml_id` | `odoo19c: addons/website_sale/data/ir_cron_data.xml:3-10` | `test_every_seeded_cron_has_its_xml_id` |
| `CRON_AUTO_CLOSE_TICKETS`, `0007_cron_xml_id` | `odoo19e: helpdesk/data/ir_cron_data.xml:4-13` | `test_every_seeded_cron_has_its_xml_id` |
| `CRON_EXPIRE_VOUCHERS`, `0006_cron_xml_id` | `odoo19c: addons/loyalty/data/loyalty_data.xml:1-3` | `test_every_seeded_cron_has_its_xml_id` |
| `CRON_BACKUP`, `0008_cron_xml_id`, `DbBackup` | `odoo18c: app_auto_backup/models/db_backup.py:287-292` | `test_backup_reads_its_cron_by_xml_id` |
| `CRON_BASE_AUTOMATION_CHECK`, `0008_seed_cron_check` | `odoo19c: addons/base_automation/data/base_automation_data.xml:4-12` | `test_base_automation_cron_is_seeded_inactive` |
| `BaseAutomation.action_open_scheduled_action`, `BaseAutomation._update_cron` | `odoo19c: addons/base_automation/models/base_automation.py:647-660` | `test_base_automation_finds_its_cron_by_xml_id` |

## Casos de prueba

- cada spec del árbol declara un xml_id, y tras sembrar `env().ref` lo resuelve
  a su cron;
- un cron sembrado sin xml_id (base anterior) gana el xml_id al volver a
  sembrar, sin duplicar acción ni cron;
- con el xml_id apuntando a un cron cuyo `method_name` cambió, la siembra
  encuentra ese cron y no crea otro (la clave ya no es el método);
- `_update_cron` y `action_open_scheduled_action` encuentran el cron aunque su
  acción no lleve `method_name`;
- `DbBackup` lee el usuario del cron por xml_id;
- el cron de `base_automation` se siembra inactivo.

Control de anulación: con `_find_seeded_action` reducido a la clave
`(model_name, method_name)` caen `test_seed_finds_cron_by_xml_id` y el caso del
método cambiado; con los consumidores de vuelta al filtro por método cae
`test_base_automation_finds_its_cron_by_xml_id`.
