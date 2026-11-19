# `base_automation` sobre `BaseModel`, con su ACL

Unidad hija `basemodel-adoption-base-automation-0397` del paraguas
`basemodel-adoption-0397` (TASK-API-0397), con la forma de
`basemodel-adoption-utm.md` y `basemodel-adoption-onboarding.md`.

## Contrato medido en la referencia

- `base.automation` (`odoo19c: addons/base_automation/models/base_automation.py:125-127`):
  `_name`, `_description = 'Automation Rule'`, `_inherit = ['mail.thread',
  'mail.activity.mixin']`. Aquí ya los declara.
- `odoo19c: addons/base_automation/security/ir.model.access.csv`: una fila,
  `access_base_automation_config`, los cuatro permisos para
  `base.group_system`.

## Estado de este árbol (medido)

- `BaseAutomation` deriva de `(MailThread, MailActivityMixin,
  TimeStampedModel)`, sin `BaseModel`. No hay `security/`.
- `BaseAutomationAction` es la tabla-liga con que este árbol sustituye el
  Many2one `ir.actions.server.base_automation_id` de la fuente (divergencia
  de mecanismo declarada en la cabecera del módulo). No tiene contraparte y no
  declara `_name`: queda fuera de esta unidad, como los «propios» de
  `basemodel-adoption-program.md`.
- Consumidores del API de gestor sobre relaciones de `base.automation`
  (`grep` de `.all|filter|exclude|exists|count|set|values_list` sobre los
  accesores): `_compute_trigger_field_ids` y `_compute_on_change_field_ids`
  fijaban el Many2many con `.set()`, y `_check_trigger_fields` lee nombres
  con `values_list`. Con `BaseModel` el accesor hacia `ir.model.fields` (que
  no es `BaseModel`) es un `AccessQuerySet` sin `.set()`.
- `create`, `write` y `unlink` de la fuente
  (`odoo19c: addons/base_automation/models/base_automation.py:491-521`)
  actualizan cron y dispatch; aquí lo hacía sólo `save()`, con la asimetría
  de `RANGE_FIELDS` a cargo de `write(**kwargs)`, una firma que choca con el
  `write(vals)` de `BaseModel`.

## Cambios

1. `BaseAutomation` deriva de `(models.BaseModel, MailThread,
   MailActivityMixin, TimeStampedModel)`.
2. `addons/base_automation/security/ir.model.access.csv`, copia fiel, en
   `data` del manifiesto.
3. `_compute_trigger_field_ids` y `_compute_on_change_field_ids` escriben con
   el `write` de `BaseModel` y `fields.Command.set`, como superusuario: en la
   fuente asignar un calculado no pasa por el `write` del modelo ni por su
   control de acceso. `_check_trigger_fields` sigue con `values_list`.
4. `create(vals_list)`, `write(vals)` y `unlink()` con la forma de la fuente:
   `write` actualiza cron **y** dispatch si toca `CRITICAL_FIELDS`, **sólo**
   el cron si toca `RANGE_FIELDS`, y llama a `_has_trigger_onchange`;
   `unlink` actualiza los dos. Mientras corre, una variable de contexto evita
   que el `save()` que alcanza `BaseModel.write` repita la actualización.
5. `_current_critical_snapshot` compara un x2many por sus ids: un conjunto de
   consulta se compara por identidad y daría «cambiado» en cada lectura.
6. `test_basemodel_reach.py`: `base_automation` sale de `PENDING`.

## Pruebas

`tests/unit/base_automation/test_base_automation_basemodel_acl.py`: el modelo
es `BaseModel`; la fila de ACL es la del CSV; un usuario interno no lee una
regla.

Las pruebas de `tests/unit/base_automation/` corren como superusuario
(`conftest.py`), ≙ `TransactionCase` de la fuente, que construye su entorno
con `SUPERUSER_ID`; `tests/unit/orm/test_fk_three_axes.py` lo hace en la
clase que lee un `BaseAutomation`. `test_crud_and_actions_server.py` pasa a
`write({...})`.
