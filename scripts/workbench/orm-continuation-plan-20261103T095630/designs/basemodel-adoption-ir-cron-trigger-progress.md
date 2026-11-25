# Adopción de BaseModel: ir.cron.trigger + ir.cron.progress (basemodel-adoption-0397)

## Referencia

- `odoo19c: odoo/addons/base/models/ir_cron.py:895` — `class IrCronTrigger(models.Model)`, `_name = 'ir.cron.trigger'`.
- `odoo19c: odoo/addons/base/models/ir_cron.py:916` — `class IrCronProgress(models.Model)`, `_name = 'ir.cron.progress'`.
- ACL (`ir.model.access.csv`): `group_system` 1,1,1,1 para los dos; ya
  sembrada en `src/addons/base/security/ir_model_access.py`.

## Cambio

- `src/addons/base/models/ir_cron.py`: `IrCronTrigger(BaseModel)` e
  `IrCronProgress(BaseModel, TimeStampedModel)`. Sin migración
  (`./kaupamex-bin makemigrations base --check --dry-run` → sin cambios).
- `IrCron` sigue fuera de BaseModel: su adopción es otra unidad.

## Divergencia declarada: los dos sitios de creación

La fuente crea con privilegio: `self.env['ir.cron.trigger'].sudo().create(...)`
(`:781`) y `self.env['ir.cron.progress'].sudo().create(...)` (`:813`). Aquí
`_trigger_list` y `_add_progress` siguen en `objects.create`: el gestor de
Django no pasa por la ACL, igual que `sudo()`, y ninguno de los dos modelos
declara cómputos, inversos ni onchange que el `create` del ORM dispararía. El
valor devuelto conserva la forma que sus llamadores leen (`progress.pk`).

## Pruebas

- `tests/unit/base/test_ir_cron_trigger_progress.py`:
  `test_trigger_and_progress_are_basemodel` (nuevo, por modelo).
- Subconjunto derivado (`grep -rlE "IrCronTrigger|IrCronProgress|ir_cron|IrCron\b" tests`,
  27 archivos): 300 passed.

## Anulación

Revertir sólo `IrCronProgress` a `TimeStampedModel`: cae exactamente
`test_trigger_and_progress_are_basemodel[IrCronProgress]` (1 de 25).
Restaurado y verificado con `cmp`.
