# res.users.deletion sobre BaseModel, con su barrido

Unidad de `basemodel-adoption-0397` (TASK-API-0397). Mapa de consumidores
preparado por un subagente de sólo lectura y verificado contra la fuente.

## Fuente medida

`odoo19c: odoo/addons/base/models/res_users_deletion.py:11-100`:

- `_name = 'res.users.deletion'`, `_description = 'Users Deletion Request'`,
  `_rec_name = 'user_id'` (`:20-22`); sin `_order`.
- `user_id` Many2one con `ondelete='set null'`, `user_id_int` calculado y
  almacenado desde `user_id` (`:25-34`), `state` requerido con
  `todo`/`done`/`fail` (`:27-28`).
- `_gc_portal_users(batch_size=50)` (`:36-100`), el cron
  `ir_cron_res_users_deletion` (`odoo19c: odoo/addons/base/data/ir_cron_data.xml:13-17`):
  las solicitudes `todo` sin usuario pasan a `done`; de las demás, hasta
  `batch_size`, cada una se bloquea con `try_lock_for_update`, borra el
  usuario (fallo → `fail` y `rollback`) y después intenta borrar su
  partner (fallo → aviso), avisando el avance con `ir.cron._commit_progress`.

ACL (`odoo19c: odoo/addons/base/security/ir.model.access.csv:87-88`): todos
los usuarios 0,0,0,0 y `group_erp_manager` 1,1,1,1. Sin reglas.

El creador de la solicitud es el propio usuario de portal
(`odoo19c: odoo/addons/base/models/res_users.py:987`), que con esa ACL no
tiene permiso. La fuente lo resuelve en el llamador: el controlador de
portal invoca `request.env.user.sudo()._deactivate_portal_user(**post)`
(`odoo19c: addons/portal/controllers/portal.py:926`), así que la creación
ocurre elevada.

## Puerto antes de la unidad

`src/addons/base/models/res_users_deletion.py`: campos `user`, `user_int`
(fijado en `save()`), `state`; `Meta.ordering = ['-id']`. Su docstring dice
«Fiel» y **falta `_gc_portal_users`**: la prosa heredada no se sostiene.
Ningún atributo de clase; sin filas de ACL.
`ResUsers._deactivate_portal_user` crea la solicitud con
`deletion.objects.create` (`src/addons/base/models/res_users.py:373`).

## Cambio

1. `ResUsersDeletion(models.BaseModel, TimeStampedModel)` con `_name`,
   `_description` y `_rec_name = 'user'` (el campo se llama `user`).
2. `_gc_portal_users(batch_size=50)` portado sobre `try_lock_for_update` e
   `IrCron._commit_progress`, que ya existen
   (`src/orm/models.py:9448`, `src/addons/base/models/ir_cron.py:1174`).
3. Las dos filas de ACL y su migración de siembra; el cron
   `ir_cron_res_users_deletion` si la siembra de crons de `base` lo admite.
4. La creación de la solicitud en `_deactivate_portal_user` corre elevada.
5. El docstring del módulo deja de afirmar fidelidad completa hasta que el
   barrido esté portado.

## Controles previstos

- una solicitud cuyo usuario ya no existe pasa a `done`;
- una solicitud `todo` borra su usuario y su partner y queda `done`;
- si el borrado del usuario falla, la solicitud queda `fail`;
- `batch_size` limita cuántas se procesan;
- un usuario de portal que se da de baja deja su solicitud (creación
  elevada) y no puede leerla después (ACL nula).

Prueba: `tests/unit/base/test_res_users_deletion_basemodel.py`.

## Medido

| Símbolo | Archivo | Fuente |
|---|---|---|
| `ResUsersDeletion` sobre `models.BaseModel` con `_name`, `_description`, `_rec_name` | `src/addons/base/models/res_users_deletion.py` | `odoo19c: odoo/addons/base/models/res_users_deletion.py:20-22` |
| `ResUsersDeletion._gc_portal_users` | ídem | `odoo19c: odoo/addons/base/models/res_users_deletion.py:36-100` |
| `ResUsers._deactivate_portal_user` crea la solicitud elevada | `src/addons/base/models/res_users.py` | `odoo19c: addons/portal/controllers/portal.py:926` y `odoo/addons/base/models/res_users.py:987` |
| dos filas de `_ACCESS` y migración `0136_seed_res_users_deletion_access` | `src/addons/base/security/ir_model_access.py`, `src/addons/base/migrations/0136_seed_res_users_deletion_access.py` | `odoo19c: odoo/addons/base/security/ir.model.access.csv:87-88` |
| `CRON_RES_USERS_DELETION` y migración `0137_seed_cron_res_users_deletion` | `src/addons/base/data/__init__.py`, `src/addons/base/migrations/0137_seed_cron_res_users_deletion.py` | `odoo19c: odoo/addons/base/data/ir_cron_data.xml:13-21` |

Prueba: `tests/unit/base/test_res_users_deletion_basemodel.py`.

**Dos divergencias de mecanismo, declaradas en el docstring.** El
`self.env.cr.rollback()` de la fuente tras un borrado fallido es un
`savepoint` alrededor de cada borrado: Django prohíbe el `rollback` de la
transacción dentro de un `atomic`, y el `savepoint` deshace sólo el intento.
Y tras borrar el usuario la solicitud se relee (`self.browse(ids)`): la
columna quedó a `NULL` por `ondelete='set null'`, pero la instancia en
memoria conservaba el id y el `write` siguiente lo releía
(`ResUsers matching query does not exist`, medido); en la fuente el caché se
invalida al borrar.

El cron se siembra en `0137` y no en `0136`: la base de pruebas ya había
aplicado `0136` antes de añadirle el cron, y una migración aplicada no se
vuelve a ejecutar. Su prueba fallaba con `Identificador externo no
encontrado: base.ir_cron_res_users_deletion` antes de `0137`.

Anulaciones, restauradas con `cmp`:

- la creación sin elevar: caen los 10 casos de
  `test_res_users_deactivate_portal.py` que recorren la baja y
  `TestBaja::test_baja_desactiva_y_registra_la_solicitud`; pasan los 24
  restantes;
- sin el cambio de base: caen los 5 casos del barrido y la ACL;
- sin marcar `done` las solicitudes huérfanas: cae exactamente
  `test_a_request_without_user_is_marked_done`.
