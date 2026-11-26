# res.users.log sobre BaseModel, con `create_uid` como dueño

Unidad de `basemodel-adoption-0397` (TASK-API-0397). Mapa de consumidores
preparado por un subagente de sólo lectura y verificado contra la fuente.

## Fuente medida

- `odoo19c: odoo/addons/base/models/res_users.py:134-152`: `_name`,
  `_order = 'id desc'`, `_description = 'Users Log'`; **un solo campo**,
  `create_uid` (Many2one indexado), y `_gc_user_logs` con un `DELETE`
  crudo que conserva la fila más reciente por `create_uid`.
- `odoo19c: odoo/addons/base/models/res_users.py:231-233`:
  `res.users.log_ids = One2many('res.users.log', 'create_uid')` y
  `login_date = Datetime(related='log_ids.create_date')`.
- `odoo19c: odoo/addons/base/models/res_users.py:742-746`:
  `_update_last_login` crea la fila vacía con `sudo()`; los campos mágicos
  ponen el dueño.
- Regla `res_users_log_rule`
  (`odoo19c: odoo/addons/base/security/base_security.xml:5-10`):
  `[('create_uid', '=', user.id)]`, `perm_read=False`.
- ACL `access_res_users_log_system`, `group_system`, 1,0,1,0
  (`odoo19c: odoo/addons/base/security/ir.model.access.csv:89`).

## Puerto antes de la unidad

`ResUsersLog(TimeStampedModel)` (`src/addons/base/models/res_users.py`)
declara una FK `user` (`related_name='logs'`) **además** del `create_uid`
que ya hereda de `TimeStampedModel`: el dueño vive en `user`, y su
docstring de `_update_last_login` lo declara divergencia. `_gc_user_logs`
correlaciona por `user`. Consumidores de `user`/`logs`:
`ResUsers._update_last_login`, la condición de huso en `_login`
(`user.logs.exists()`), `addons/digest/models/digest.py` (KPI de accesos) y
`addons/base_setup/controllers/main.py` (usuarios activos), más
`tests/unit/base/test_login_procedure.py` y
`tests/unit/digest/test_digest_kpi.py`.

## Cambio

1. `ResUsersLog(models.BaseModel, TimeStampedModel)` con `_name`, `_order`
   y `_description`.
2. El dueño pasa a `create_uid`, con índice y con `related_name='log_ids'`
   (el inverso de la fuente); la columna `user_id` se retira con una
   migración que copia su valor a `create_uid`.
3. `_update_last_login` crea elevado y fija el dueño por el contexto de
   usuario, como los campos mágicos de la fuente; `_gc_user_logs`
   correlaciona por `create_uid`.
4. Los consumidores leen `create_uid`/`log_ids`.
5. ACL de `group_system` y la regla, con su siembra.

## Controles previstos

- `_update_last_login` deja una fila cuyo `create_uid` es el usuario;
- `_gc_user_logs` conserva la última por `create_uid`;
- un usuario interno no lee filas (ACL 1,0,1,0 sólo para `group_system`);
- el KPI de digest y los usuarios activos de `base_setup` cuentan por
  `create_uid`.

Prueba: `tests/unit/base/test_res_users_log_basemodel.py`.
