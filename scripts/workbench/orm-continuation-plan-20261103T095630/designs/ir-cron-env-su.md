# El trabajo de un cron corre con el entorno de su usuario, elevación incluida

Creado: 2026-11-18T20:20:36 (UTC). TASK-API-0485, sigue a `ir-cron-user-root.md` y es
requisito de `basemodel-adoption-auto-backup.md`. Referencia: odoo-tools
`abe4040ec1`, Odoo 19 Community.

## El contrato de la fuente

- El trabajo corre en `env = api.Environment(job_cr, job['user_id'], {…})`
  (`odoo19c: odoo/addons/base/models/ir_cron.py:482`).
- `Environment.__new__`: `if uid == SUPERUSER_ID: su = True`; con otro
  usuario `su` vale `False`, el defecto
  (`odoo19c: odoo/orm/environments.py:64-67`). El trabajo del raíz va
  elevado; el de cualquier otro usuario, no, y no hereda la elevación de
  quien lo dispara.

## Este árbol, medido

`IrCron._callback` corre bajo `user_scope(self.user_id)`, que sólo fija el
uid: el canal `_su` queda como lo tenía quien llama. Medido con
`auto_backup` en `BaseModel`: `schedule_backup` bajo `user_scope(1)`
(el usuario del cron) es denegado al crear `db.backup.details`, porque el
bloque no está elevado; por el disparo HTTP pasa porque hereda la
elevación de la petición. Las dos conductas divergen de la fuente, una por
defecto y otra por exceso.

## Decisión

`_callback` fija también el canal de elevación como `Environment`:
`sudo(self.user_id == SUPERUSER_ID)` alrededor de la llamada.

## RED

1. El callback de un cron del raíz ve `is_su()` verdadero.
2. El de un cron de otro usuario ve `is_su()` falso aunque se dispare
   dentro de un bloque elevado.

## Ejecución (2026-11-18)

Símbolo: `IrCron._callback` ≙
`odoo19c: odoo/addons/base/models/ir_cron.py:482` con la regla de
`odoo19c: odoo/orm/environments.py:66`; envuelve la llamada en
`sudo(self.user_id == SUPERUSER_ID)`. `SUPERUSER_ID` entra por el import
de `orm.environments` que ya existía. Prueba:
`tests/unit/base/test_ir_cron_env_su.py` (2).

RED: 2 de 2. GREEN: 2 passed. Subconjunto derivado del cron (36 archivos y
la prueba nueva): 429 passed, 16 skipped.

**Anulación.** Sin el `sudo(...)` caen las 2 de la prueba nueva y ninguna
de `test_ir_cron_runner.py`.
