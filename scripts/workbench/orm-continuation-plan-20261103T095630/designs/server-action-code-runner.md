# server-action-code-runner-0397 — el corredor del modo `code` de `ir.actions.server`

Fecha: 2026-11-22T03:52:20. Abierta como sucesora de
`account-edi-network-cron-0397` (`designs/account-edi-network-cron.md`, «Lo que
esta unidad no cierra»): el cron de la fuente se ejecuta como
`model._cron_process_documents_web_services(job_count=20)`, que es **código** de
una acción de servidor, no un método sin argumentos.

## Referencia

- `odoo19c: odoo/addons/base/models/ir_actions.py:1013-1017` —
  `_run_action_code_multi`: con `code` vacío no hace nada; si no,
  `safe_eval(self.code.strip(), eval_context, mode="exec", filename=str(self))`
  y devuelve `eval_context.get('action')`.
- `odoo19c: odoo/addons/base/models/ir_actions.py:30-54` — `LoggerProxy`: el
  `_logger` que ve el código, restringido a `log`/`info`/`warning`/`error`/
  `exception` sobre el hijo `server_action_safe_eval`
  (`odoo19c: odoo/addons/base/models/ir_actions.py:27`).
- `odoo19c: odoo/addons/base/models/ir_actions.py:140-153` — el
  `_get_eval_context` base de `ir.actions.actions`: `uid`, `user`, `time`,
  `datetime`, `dateutil`, `timezone`, `float_compare`, `b64encode`,
  `b64decode`, `Command`.
- `odoo19c: odoo/addons/base/models/ir_actions.py:1111-1149` — el de
  `ir.actions.server` añade `env`, `model`, `UserError`, `record`, `records`,
  `log` y `_logger` (= `LoggerProxy`) sobre el de la base.

## Estado heredado (consumidor en `054bcd51`)

| Contrato | Consumidor | Clase |
|---|---|---|
| `_run_action_code_multi` | ausente; `scripts/divergencias_declaradas.txt:1281` lo declara divergencia | ABSENT |
| `LoggerProxy` | ausente; `_logger` del módulo expuesto tal cual | ABSENT |
| `_get_eval_context` base (diez claves) | ausente en `IrActionsBase` | ABSENT |
| `_get_eval_context` de servidor | portado sin `env` y con `_logger` crudo (`ir_actions.py:2437`) | DIVERGENT |
| `run` / `_run` / `_get_runner` | portados | SATISFIED |

## La prosa heredada que sostenía la divergencia es falsa

La divergencia se justificaba como «la misma decisión que
`ir_rule.domain_force` (`api@020e965`): montar un evaluador sobre entrada
almacenada exige decidir explícitamente el evaluador y su contexto»
(`ir_actions.py:77-83`, `divergencias_declaradas.txt:1277-1280`). Medido: esa
decisión ya se tomó y en sentido contrario — `ir_rule` evalúa `domain_force`
con `tools.safe_eval.safe_eval` y su `_eval_context` explícito desde
`4c3a992e` (2026-10-29; `ir_rule.py:305`, `:444`). El evaluador está portado
(`src/tools/safe_eval.py:430`) y el contexto es el de la fuente. No queda
decisión pendiente: se porta.

## Cambio previsto

1. `IrActionsBase._get_eval_context` con las diez claves de `:140-153`; `uid` y
   `user` del entorno ambiental, los módulos envueltos de `tools.safe_eval`.
2. `IrActionsServer._get_eval_context` parte del de la base y añade `env`
   (`orm.environments.env()`) y `_logger = LoggerProxy`.
3. `LoggerProxy` y `_server_action_logger` como en la fuente.
4. `_run_action_code_multi` verbatim sobre `safe_eval`.
5. Se retira la entrada de `divergencias_declaradas.txt` y se corrige la prosa
   del módulo.

`model` sigue siendo la clase que resuelve `apps.get_model(model_name)`: es lo
que el corredor de métodos del cron ya invoca, y `model._metodo(...)` sobre esa
clase llama al mismo método que hoy. Pasar a `env[model]` para los modelos
`BaseModel` es otra unidad (la de `model_id` como `Many2one`, **#139**).

## Símbolos, referencia y prueba

Prueba: `tests/unit/base/test_server_action_code_runner.py`.

| Símbolo | Referencia |
|---|---|
| `IrActionsServer._run_action_code_multi` | `odoo19c: odoo/addons/base/models/ir_actions.py:1013-1017` |
| `LoggerProxy` | `odoo19c: odoo/addons/base/models/ir_actions.py:30-54` |
| `IrActionsBase._get_eval_context` | `odoo19c: odoo/addons/base/models/ir_actions.py:140-153` |
| `IrActionsServer._get_eval_context` | `odoo19c: odoo/addons/base/models/ir_actions.py:1111-1149` |

## Casos de prueba

- una acción `code` vacía devuelve `None` sin evaluar;
- el código ve `model`, `env`, `record`/`records` con `active_model`/`active_id`,
  `Command`, `datetime` y `UserError`;
- `action = {...}` en el código es lo que devuelve `run()`;
- el código no puede importar (`safe_eval` rehúsa `import os`);
- `_logger` es `LoggerProxy` y escribe en `…server_action_safe_eval`.

## Lo que esta unidad no cierra

- Que `ir.cron._callback` ejecute la acción con `run()` como la fuente
  (`odoo19c: odoo/addons/base/models/ir_cron.py:671-696`) en vez de
  `getattr(model, method_name)()`, y que las siembras lleven `code`: sucesora
  **`cron-runs-server-action-0397`** (TASK-API-0397), que es la que pasa
  `job_count=20`.
