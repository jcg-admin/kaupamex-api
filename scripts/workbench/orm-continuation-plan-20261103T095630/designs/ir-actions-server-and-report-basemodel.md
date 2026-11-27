# ir.actions.server e ir.actions.report sobre BaseModel (paso 2)

Unidad de `basemodel-adoption-0397` (TASK-API-0397), paso 2 del plan de
`ir-actions-family-basemodel-and-inheritance.md`.

## Fuente medida

- `ir.actions.server`
  (`odoo19c: odoo/addons/base/models/ir_actions.py:567-592` atributos):
  `create` con `@api.model_create_multi` copia `model_id` y `group_ids` del
  padre cuando llega `parent_id`, y anota la primera revisión de cada acción
  que trae `code`; `write` anota una revisión si el código cambia
  (`odoo19c: odoo/addons/base/models/ir_actions.py:711-734`).
- `ir.actions.report` (`odoo19c: odoo/addons/base/models/ir_actions_report.py:157-163`).
- ACL de los dos, `group_system`, 1,1,1,1
  (`odoo19c: odoo/addons/base/security/ir.model.access.csv:103`,
  `odoo19c: odoo/addons/base/security/ir.model.access.csv:107`); ya están en
  `_ACCESS`. `mail` añade lectura de informes a `group_user`
  (`odoo19c: addons/mail/security/ir.model.access.csv:62`), y el puerto la
  tiene en `addons/mail/security/ir.model.access.csv:5`.

## Puerto antes del paso

- `IrActionsServer(IrActionsBase)`: modelo de Django sin `BaseModel`; sus
  atributos de clase existen pero ningún mecanismo los consume. La revisión
  se anota en `save` (`_record_code_revision`), no en `create`/`write`, y
  la copia desde el padre no está portada.
- `IrActionsReport(IrActionsBase)`: ídem.

## Cambio

1. `IrActionsServer(models.BaseModel, IrActionsBase)` y
   `IrActionsReport(models.BaseModel, IrActionsBase)`.
2. `IrActionsServer.create` y `IrActionsServer.write` como en la fuente; la
   revisión deja `save`.
3. Los caminos sin usuario que escriben acciones (cron, `base_automation`)
   se miden; los que no corren ya elevados se elevan con `sudo()`.

## Controles previstos

- un administrador del sistema crea y escribe acciones de servidor;
- un usuario interno no las lee (ACL de `group_system`);
- crear con `parent_id` copia el modelo y los grupos del padre;
- la primera revisión se anota al crear con código, y otra al cambiarlo;
- un usuario interno lee informes y no los escribe (la fila de `mail`);
- un usuario de portal no los lee.

Prueba: `tests/unit/base/test_ir_actions_server_basemodel.py`.

## Medido

| Símbolo | Archivo | Fuente |
|---|---|---|
| `IrActionsServer` sobre `models.BaseModel` | `src/addons/base/models/ir_actions.py` | `odoo19c: odoo/addons/base/models/ir_actions.py:567-592` |
| `IrActionsServer.create` | ídem | `odoo19c: odoo/addons/base/models/ir_actions.py:711-728` |
| `IrActionsServer.write` | ídem | `odoo19c: odoo/addons/base/models/ir_actions.py:730-733` |
| `IrActionsServer.save` sin la revisión; se retira `IrActionsServer._record_code_revision`, que la anotaba ahí | ídem | ídem |
| `IrActionsServer._check_children` recorre el padre mientras haya uno | ídem | `odoo19c: odoo/addons/base/models/ir_actions.py:967-973` |
| `IrActionsReport` sobre `models.BaseModel` | `src/addons/base/models/ir_actions_report.py` | `odoo19c: odoo/addons/base/models/ir_actions_report.py:157-163` |
| `sembrar_cron_vivo` como superusuario, cuerpo en `_seed_live_cron` | `src/addons/base/data/cron.py` | `odoo19c: odoo/addons/base/security/ir.model.access.csv:107` |

Prueba: `tests/unit/base/test_ir_actions_server_basemodel.py`, 9 casos.
RED antes del cambio: 8 fallidos (no eran `BaseModel`; sin `create` ni
`write` de recordset).

Tres hechos medidos al implementarlo:

- `_check_children` comparaba `current is not None`. Sobre `BaseModel` un
  `Many2one` vacío es un recordset vacío con `pk = None`, igual que el de
  un registro sin guardar, y el recorrido veía un ciclo en cada alta. La
  condición pasa a la verdad del valor, que vale para las dos formas. La
  mitad de los avisos usa `filtered('warning')` y `mapped('name')`, como
  la fuente.
- La siembra viva de crons lee la acción sin usuario; con la ACL activa
  rehusaba. La fuente carga `ir_cron_data.xml` como superusuario, y la
  siembra de reglas de este árbol ya lo hace igual (`base_security._seed`).
- El control de informes de la primera versión de la prueba afirmaba que un
  usuario interno no los lee: lo contradice la fila de `mail`. La prueba
  se corrigió a la fuente.
