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

## Medido

| Símbolo | Archivo | Fuente |
|---|---|---|
| `ResUsers.action_id` (forma C, sin clave foránea) y `ResUsers._check_action_id`, llamado desde `ResUsers.clean` | `src/addons/base/models/res_users.py` | `odoo19c: odoo/addons/base/models/res_users.py:229-230,512-533` |
| `action_id` en `ResUsers.SELF_READABLE_FIELDS` y `ResUsers.SELF_WRITEABLE_FIELDS` | ídem | `odoo19c: odoo/addons/base/models/res_users.py:183,193` |
| `IrActionsBase._unlink_check_home_action` | `src/addons/base/models/ir_actions.py` | `odoo19c: odoo/addons/base/models/ir_actions.py:134-136` |
| `type` con su valor por defecto en `IrActionsActWindow`, `IrActionsActUrl`, `IrActionsClient` e `IrActionsServer`; se retiran las constantes `TYPE` | ídem | `odoo19c: odoo/addons/base/models/ir_actions.py:308,453,607,1434` |
| `IrActionsServer.action_open_parent_action` con `self._name` y el id del padre | ídem | `odoo19c: odoo/addons/base/models/ir_actions.py:1328-1335` |
| `type` y `binding_type` con su valor por defecto en `IrActionsReport`; se retira `IrActionsReport.save` | `src/addons/base/models/ir_actions_report.py` | `odoo19c: odoo/addons/base/models/ir_actions_report.py:165-166` |
| migración `0146_res_users_home_action` | `src/addons/base/migrations/0146_res_users_home_action.py` | ídem |

Prueba: `tests/unit/base/test_res_users_home_action.py`, 12 casos.
RED antes del cambio: 5 fallidos de 6; el caso de la acción de ventana sin
`active_id` pasa por construcción, es la rama negativa.

- **El `type` por defecto entra en esta unidad porque sin él
  `_check_action_id` nunca ve un `ir.actions.client`.** Medido con una sonda:
  `IrActionsClient.create({'name': 'R', 'tag': 'reload'})` dejaba `type`
  vacío. Sólo `IrActionsReport` lo fijaba, desde `save()`, cuyo docstring
  decía que un subtipo no puede redefinir el `default` «sin duplicar la
  columna». Para un campo heredado de una base abstracta Django lo admite:
  `act_window_close` ya lo redeclaró en 4a y la migración sólo cambia el
  estado.
- **`action_open_parent_action`** usaba la constante `TYPE` y el entero
  `parent_id`; la fuente usa `self._name` y `self.parent_id.id`. Aquí el
  `Many2one` se llama `parent` (columna `parent_id`), así que es
  `self.parent.id`. Lo destapó el subconjunto derivado, con dos fallos en
  `test_ir_actions_server_open.py`.
- **El orden en `res_users.py`.** El portero de estilo identifica cada
  sentencia por su posición en el contenedor
  (`scripts/check_python_style_increment.py:144`): declarar `action_id` y el
  método a mitad de la clase, o añadir el import de `tools.translate`,
  desplazaba toda sentencia posterior y sus 72 incumplimientos heredados
  contaban como nuevos. Van al final de la clase, y los mensajes usan
  `Environment._`, que es el `Environment._` de la fuente.
- **`res.users` no es `BaseModel`**: `_check_action_id` corre en `clean()`
  como sus dos hermanas, y `_unlink_check_home_action` busca con el gestor
  de Django, que no filtra por `active`, y escribe con el `write` de cada
  usuario bajo `sudo()`: el queryset no declara `write`. Un primer `update`
  pasaba las pruebas y lo rechazó `check_write_path` («se salta un enganche
  que la fuente usa»): la fuente escribe con `sudo().write(...)`.
- Anulación: sin la rama `reload`, sin la de `active_id`, sin el `update`
  del gancho y sin el `type` por defecto de `client` caen exactamente sus
  cuatro casos.
- Subconjunto derivado (`grep` de `IrActions`, `ir.actions`, `act_window`,
  `binding_type`, `ResUsers`, `res.users`, `SELF_READABLE`,
  `SELF_WRITEABLE`, `action_open_parent_action` sobre `tests/`, 175
  archivos): 2542 pasados, 2 fallidos (corregidos arriba) y 15 errores del
  aislamiento multibase, que F2 excluye y corre aparte.
