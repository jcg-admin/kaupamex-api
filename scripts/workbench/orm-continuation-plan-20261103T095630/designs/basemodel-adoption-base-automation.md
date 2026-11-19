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
  accesores): `_onchange_on_change_field_ids` (`:737`), la porción de
  `_compute_trigger_and_trigger_field_ids` que fija `trigger_field_ids` y
  `on_change_field_ids` (`:777-790`) y `_check_trigger_fields` (`:1194`).
  Con `BaseModel` el accesor es un recordset, así que pasan a la verdad del
  recordset, `write` con `Command` y `mapped`
  (`odoo19c: addons/base_automation/models/base_automation.py`).

## Cambios

1. `BaseAutomation` deriva de `(models.BaseModel, MailThread,
   MailActivityMixin, TimeStampedModel)`.
2. `addons/base_automation/security/ir.model.access.csv`, copia fiel, en
   `data` del manifiesto.
3. Los consumidores de arriba, al API de recordset.
4. `test_basemodel_reach.py`: `base_automation` sale de `PENDING`.

## Pruebas

`tests/unit/base_automation/test_base_automation_basemodel_acl.py`: el modelo
es `BaseModel`; la fila de ACL es la del CSV; un usuario interno no lee una
regla.
