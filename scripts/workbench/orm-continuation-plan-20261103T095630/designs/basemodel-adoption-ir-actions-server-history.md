# Adopción de BaseModel: ir.actions.server.history (basemodel-adoption-0397)

## Referencia

- `odoo19c: odoo/addons/base/models/ir_actions.py:503` — `class IrActionsServerHistory(models.Model)`, `_name = 'ir.actions.server.history'`.
- ACL (`ir.model.access.csv:108`): `access_ir_actions_server_history_group_system`
  (1,1,1,0), ya sembrada. Sin record rules en `base_security.xml`.

## Cambio

- `src/addons/base/models/ir_actions.py`: `IrActionsServerHistory(models.BaseModel,
  TimeStampedModel)`. Sin migración (`./kaupamex-bin makemigrations base
  --check --dry-run` → sin cambios).
- Consumidores (`IrActionsServer.save` al cambiar el código, el asistente de
  historial, `_gc_histories`): todos por el gestor de Django. El gestor no
  filtra consultas (sonda de `designs/basemodel-adoption-ir-module-category-privilege.md`),
  y ningún modelo recorre un `Many2one` hacia el historial bajo un usuario.

## Pruebas

- `tests/unit/base/test_server_action_history_basemodel.py` (nuevo).
- Subconjunto derivado (`IrActionsServer|ir.actions.server|server_action|ServerActionHistoryWizard|_gc_histories|autovacuum`,
  43 archivos, `-n 4`): 665 passed, 2 xfailed, 1 failed. El fallo,
  `tests/unit/orm/test_default_get.py::TestRecNameResolution::test_a_model_with_name_resolves_to_name`,
  es **previo**: sale igual con el cambio revertido en el mismo subconjunto
  paralelo, y el archivo solo da 41 passed. Depende del orden de los
  trabajadores; el F2 completo lo ejecuta en verde.

## Anulación

Revertir la base a `TimeStampedModel`: cae exactamente
`test_server_action_history_is_basemodel` (1 de 1). Restaurado y verificado con
`cmp`.
