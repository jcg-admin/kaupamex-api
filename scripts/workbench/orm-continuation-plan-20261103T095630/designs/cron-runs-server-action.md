# cron-runs-server-action-0397 — el cron ejecuta su acción de servidor

Fecha: 2026-11-22T04:53:26. Sucesora de `server-action-code-runner-0397`
(`designs/server-action-code-runner.md`): con el modo `code` portado, el cron
puede ejecutar lo que la fuente ejecuta, y `job_count=20` de
`account_edi.ir_cron_edi_network` deja de ser inexpresable.

## Referencia

- `odoo19c: odoo/addons/base/models/ir_cron.py:671-696` — `_callback`: corre
  `self.env['ir.actions.server'].browse(server_action_id).run()` bajo el
  entorno del job.
- `odoo19c: odoo/addons/base/models/ir_cron.py:481-505` — ese entorno lleva el
  usuario del cron y el contexto `lastcall`/`cron_id`.
- Todo cron de la fuente se declara con `state = code` y su `code`, p. ej.
  `odoo19c: addons/account_edi/data/cron.xml:2-10`:
  `model._cron_process_documents_web_services(job_count=20)`.

## Estado heredado (consumidor en `a973637b`)

| Contrato | Consumidor | Clase |
|---|---|---|
| `_callback` ejecuta la acción con `run()` | `getattr(apps.get_model(model_name), method_name)()` (`ir_cron.py:775`) | DIVERGENT |
| cada acción de cron lleva su `code` | la siembra la crea con `code=''` (`src/addons/base/data/cron.py:47-55`) | ABSENT |
| `job_count=20` del cron EDI | inexpresable sin `code` | ABSENT |

## Cambio previsto

1. `IrCron._callback` ejecuta `self.ir_actions_server.run()` bajo los mismos
   `user_scope`, `sudo` y `context_scope` de hoy.
2. La siembra (`sembrar_cron`, `sembrar_cron_vivo`) escribe `code`: el que
   declare el `spec`, o `model.<method_name>()`, que es lo que el corredor
   llamaba hasta ahora; una acción ya sembrada con `code` vacío se completa.
3. Migración de datos en `base`: rellena `code = 'model.<method_name>()'` en las
   acciones de cron que lo tienen vacío y llevan `method_name`.
4. `CRON_EDI_NETWORK` declara `code` con `job_count=20`, y una migración de
   `account_edi` lo escribe en su acción.

`method_name` sigue como **clave natural** con la que la siembra,
`base_automation` y `auto_backup` encuentran la acción de su cron; ya no
decide qué se ejecuta. Retirarlo exige otra clave (el `xml_id` de cada cron,
como en la fuente): sucesora **`cron-xml-id-natural-key-0397`**.

## Símbolos, referencia y prueba

Pruebas: `tests/unit/base/test_cron_runs_server_action.py` y
`tests/unit/account_edi/test_account_edi_network_cron.py`.

| Símbolo | Referencia |
|---|---|
| `IrCron._callback` | `odoo19c: odoo/addons/base/models/ir_cron.py:671-696` |
| `sembrar_cron`, `sembrar_cron_vivo` | `odoo19c: addons/account_edi/data/cron.xml:2-10` |
| `0126_fill_cron_action_code` | `odoo19c: odoo/addons/base/models/ir_cron.py:671-696` |
| `0008_cron_edi_network_job_count` (`CRON_EDI_NETWORK`) | `odoo19c: addons/account_edi/data/cron.xml:6` |

## Casos de prueba

- un cron cuya acción lleva `code` lo ejecuta (efecto en la base);
- el código del cron ve `env.context['cron_id']`;
- una acción sembrada sin `code` en el `spec` recibe `model.<method_name>()`;
- la migración rellena el `code` vacío y respeta uno ya escrito;
- el cron EDI pasa `job_count=20` al método.
