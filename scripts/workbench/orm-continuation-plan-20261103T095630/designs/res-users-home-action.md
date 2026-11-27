# res.users.action_id, _check_action_id y _unlink_check_home_action (paso 4b)

TASK-API-0397. Unidad: `res-users-home-action-0397`
(depende de `ir-actions-actions-basemodel-0397`).

## Referencia (odoo19c, odoo-tools@bf077302)

- `odoo/addons/base/models/res_users.py:229-230`: `action_id` Many2one
  `ir.actions.actions`, string `Home Action`, con su help.
- `res_users.py:183,193`: `action_id` en `SELF_READABLE_FIELDS` y en
  `SELF_WRITEABLE_FIELDS`.
- `res_users.py:512-533`: `_check_action_id` (`@api.constrains`) rechaza
  `base.action_open_website`, un `ir.actions.client` con `tag == 'reload'`
  y un `ir.actions.act_window` cuyo `context` contiene `active_id`.
- `ir_actions.py:134-136`: `_unlink_check_home_action`
  (`@api.ondelete(at_uninstall=True)`) vacía el `action_id` de los usuarios
  —también archivados— que apuntan a las acciones borradas.

## Estado del árbol (medido)

- `src/addons/base/models/res_users.py:575-578` declara
  `_check_action_id` BLOQUEADO por `action_id` («no hay campo que validar»),
  y `:1438` declara `action_id` fuera de `SELF_READABLE_FIELDS` por
  BLOQUEADO por `ir.actions.act_window`. Ese modelo existe desde el paso 3a,
  y `ir.actions.actions` es `BaseModel` desde 4a: los dos bloqueos caducaron.
- `ResUsers` no es `BaseModel` (`res_users.py:486`); sus restricciones corren
  en `clean()` (`:1294-1297`), que ya llama `_check_user_company` y
  `_check_disjoint_groups`.

## Cambio

1. `ResUsers.action_id` (forma C, `db_column='action_id'`), y `action_id`
   en las dos listas de autoacceso; se retiran las dos marcas de BLOQUEADO.
2. `ResUsers._check_action_id`, llamado desde `clean()` como sus dos
   hermanas.
3. `IrActionsBase._unlink_check_home_action` con `@api.ondelete(at_uninstall=True)`.
4. Migración con la columna `action_id`.
