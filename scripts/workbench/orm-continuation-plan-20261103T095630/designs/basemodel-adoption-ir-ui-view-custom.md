# Adopción de BaseModel: ir.ui.view.custom (basemodel-adoption-0397)

## Referencia

- `odoo19c: odoo/addons/base/models/ir_ui_view.py:66-67` — `class IrUiViewCustom(models.Model)`,
  `_name = 'ir.ui.view.custom'`.
- Regla global `ir_ui_view_custom_personal`
  (`odoo19c: odoo/addons/base/security/base_security.xml:50-54`):
  `[('user_id','=',user.id)]`, sin grupos, los cuatro permisos.
- ACL (`ir.model.access.csv:38`): `access_ir_ui_view_custom_group_user`,
  `group_system` 1,1,1,1; ya sembrada (`ir_model_access.py`).

## Cambio

- `src/addons/base/models/ir_ui_view.py`: `IrUiViewCustom(models.BaseModel,
  TimeStampedModel)` en lugar de `TimeStampedModel` a secas.
- `src/addons/base/security/base_security.py`: la regla entra en `_RULES` como
  entrada de diccionario (la forma de `designs/base-security-group-rules-seed.md`),
  con su dominio verbatim. El nombre del campo en el dominio es `user_id`,
  como en la fuente: el FK de Django se llama `user` y su columna `user_id`,
  y el motor de dominios resuelve ese nombre (la prueba de aislamiento lo
  ejercita).
- Migración de datos `0130_seed_view_custom_rule.py`: `RunPython` con
  `seed_base_rules`, idempotente por nombre; las bases que ya pasaron por
  `0059` reciben la regla. Sin cambio de esquema
  (`./kaupamex-bin makemigrations base --check --dry-run` → sin cambios).

## Pruebas

- `tests/integration/base/test_ir_ui_view_custom_basemodel.py` (nuevo, 3 casos):
  la clase es `BaseModel`; la regla queda sembrada global con su dominio y
  permisos; dos usuarios de `group_system` ven sólo su personalización.
- Subconjunto derivado (`IrUiViewCustom|ir\.ui\.view\.custom|custom_views|base_security|IrRule|IrUiView\b`,
  54 archivos, `-n 4`): 919 passed, 26 skipped.

## Anulación

- A — revertir la base: caen exactamente los 2 casos que dependen de
  `BaseModel` (la herencia y `search`); el de la regla sobrevive.
- B — retirar la entrada de `_RULES` y borrar la fila (la sesión de pruebas
  vuelve a sembrar `_RULES`, `tests/conftest.py:452`): caen exactamente los 2
  casos de la regla (`[10, 9] == [9]` en el de aislamiento); sobrevive el de
  la herencia.
- Los dos restaurados y verificados con `cmp`.
