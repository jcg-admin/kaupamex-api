# `_check_sudo_commands` — comandos x2many bajo `sudo()` o `with_user`

Referencia: `odoo-tools@abe4040ec1a45beee90fb694e4eae4453e46b389`, Odoo 19 Community.

## Contrato de la referencia (lectura del código)

- `odoo/orm/fields_relational.py:772-777` — `_RelationalMulti._check_sudo_commands(comodel)`:
  si `comodel._allow_sudo_commands` es falso, devuelve
  `comodel.sudo(False).with_user(comodel.env.transaction.default_env.uid)`;
  si no, el comodelo tal cual.
- Se aplica al comodelo derivado del entorno del REGISTRO
  (`model.env[self.comodel_name].with_context(**self.context)`) en los cuatro
  escritores: `One2many.write_real` (:977), `One2many.write_new` (:1084),
  `Many2many.write_real` (:1420), `Many2many.write_new` (:1603).
- `default_env` es el primer entorno de la transacción con uid válido
  (`environments.py`, `Transaction.default_env`): el usuario de la petición.
- Efecto observable (`odoo/addons/test_orm/tests/test_fields.py:3677`,
  `test_sudo_commands`, usuario `portal`): sobre `res.partner.user_ids`
  (One2many a `res.users`, `_allow_sudo_commands = False`), con el registro en
  `sudo()` o en `with_user(admin)`:
  - CREATE → `AccessError` "not allowed to create 'User'";
  - UPDATE, UNLINK, LINK, CLEAR, SET → "not allowed to modify 'User'"
    (escriben el inverso o los valores en líneas del comodelo);
  - DELETE → "not allowed to delete 'User'".
  - Many2many `test_orm.user.group_ids` → `test_orm.group`
    (`_allow_sudo_commands = False`): CREATE/UPDATE/DELETE con el mismo
    mensaje por operación; LINK sólo exige lectura de los corregistros
    (`:1499-1503`).
- Comodelos con `_allow_sudo_commands = True` (el defecto, `models.py`) no
  cambian: los comandos corren con el entorno del registro.

## Estado de Kaupamex (antes de implementar)

- `_allow_sudo_commands` declarado (`src/orm/models.py:5813`, defecto True;
  False en `ir.actions`, `ir.config_parameter`, `res.groups`, `res.users`,
  varios `ir.model*`, `ir.asset`, `ir.ui.view`, `ir.actions.report`,
  `res.lang`). Ningún consumidor lo lee: grep `_allow_sudo_commands` en
  `src/` sólo da declaraciones.
- Los comandos se aplican en `src/orm/commands.py`
  (`apply_many2many_commands`, `apply_one2many_commands`) llamados desde
  `src/orm/models.py:959,1142,1146,2831` y
  `src/orm/fields_relational.py:596`. Las operaciones del comodelo usan la
  clase (`comodel.create`, `comodel.browse`), que resuelve el entorno
  AMBIENTAL (`orm.environments.env()`), no el del registro.
- `Transaction.default_env` está portado (`environments.py:904`).

## Medición (sonda ejecutada, no inferencia)

Sonda temporal sobre `kaupamex_core_qa`, usuario sin ACL alguna:

| Caso | Kaupamex hoy | Referencia |
|---|---|---|
| `foo.sudo().write({'bar_ids': [Command.create(..)]})` (`test_orm.related_foo` → `related_bar`, bandera True) | `AccessError` crear `related_bar` | permitido: el comodelo hereda el entorno `sudo` del registro |
| lo mismo dentro de `with sudo():` ambiental | permitido | permitido |
| `res.users.group_ids` → `res.groups` (bandera False) sin `sudo` | permitido | `AccessError` |

Dos defectos, no uno:

1. **Los comandos no heredan el entorno del registro.** `apply_many2many_commands`
   y `apply_one2many_commands` operan sobre la clase del comodelo, que resuelve
   el entorno ambiental. Un registro BaseModel en `sudo()`/`with_user` no
   transmite su entorno.
2. **`_allow_sudo_commands` no tiene consumidor.**

Los treinta modelos con la bandera en False son modelos de Django sin
`BaseModel` (medido sobre `MODELS_BY_NAME`), y sus `create`/`write` no pasan
por la ACL: `ResGroups` no tiene `create` y el intérprete cae en
`objects.create`. En ellos el efecto de la referencia no es observable hasta
que adopten la ACL (decisión abierta de las columnas propias de `res.users`,
BaseModel en los 389 modelos). La única arista BaseModel → bandera False es
`test_orm.discussion.participants` → `res.users`, con el mismo límite.

## Diseño

- En los dos intérpretes de comandos, el comodelo se resuelve contra el
  entorno del registro: `record.env` si el registro es BaseModel, el
  ambiental si no. Los comandos corren dentro de `with <entorno>:`, que es
  como este árbol hace que la clase lea los canales.
- `_check_sudo_commands(comodel_env, comodel)`: si la bandera es False y el
  entorno está en `su` o su uid difiere del usuario por defecto, el entorno
  pasa a `su=False` con el usuario por defecto.
- Usuario por defecto: `Transaction.default_env.uid`; sin `default_env`
  (lo normal aquí, porque el entorno ambiental no fija uno), el uid del canal
  ambiental. **Divergencia declarada**: sin `default_env`, un `user_scope`
  ambiental que cambie de usuario no se detecta; sí un `with_user` de
  registro (su uid difiere del ambiental) y todo `sudo`.
- Hogar: el método del campo en la referencia (`_RelationalMulti`). Aquí los
  intérpretes reciben el campo de Django; la función vive en
  `orm/commands.py` junto a ellos, con su cita.
- Observabilidad: se portan `test_orm.user` y `test_orm.group`
  (`test_orm.py:1770-1792`, bandera False en los dos) con su migración, y la
  prueba reproduce la sección 2 de `test_sudo_commands`; la sección 1
  (`res.partner.user_ids`) queda bloqueada por la ACL de los modelos Django.
- Controles de anulación: sin herencia del entorno cae el caso permitido; sin
  la guarda caen CREATE/UPDATE/DELETE sobre `test_orm.group`.

## Implementación y verificación

- `src/orm/commands.py`: `_record_env`, `_check_sudo_commands`, y los dos
  intérpretes corren sus triples dentro de `with <entorno>`. El `DELETE` de
  Many2many pasa por `comodel.browse(ids).unlink()` (`:1491`) cuando el
  comodelo es BaseModel; antes borraba por el manager de Django sin ACL.
- `src/addons/test_orm/models/test_orm.py` + migración `0038_user_group`:
  `test_orm.user`/`test_orm.group` de la referencia.
- RED, GREEN y controles: `red/sudo-commands.txt`.
- `Transaction.default_env` persiste entre pruebas (el corte de savepoint no
  lo limpia): la prueba arranca cada caso con una transacción nueva, como
  `test_environments_pooling_and_flush.py`.

## Lo que esta unidad no cierra

- La sección 1 de `test_sudo_commands` (`res.partner.user_ids` → `res.users`)
  y los treinta modelos con bandera False: son modelos de Django sin ACL en
  `create`/`write`; la guarda corre pero no tiene efecto observable hasta que
  adopten `BaseModel` (decisión abierta de las columnas propias de
  `res.users`).
- El usuario por defecto en producción: la petición fija el canal
  (`ir_http.py:446`) sin construir `default_env`; dentro de un `create` que
  ya entró en el entorno del registro, un `with_user` no se distingue del
  usuario de la petición. Condición de cierre: que la capa de petición
  establezca `Transaction.default_env` con el usuario autenticado.
- `write_new` (registros nuevos, `:1084`, `:1603`): sus equivalentes aquí
  (`fields_relational.py:1715-1740`, `models.py:5340-5365`) sólo tocan la
  caché (`new`, `_update_cache`), que no consulta la ACL; la guarda no cambia
  nada observable ahí y no se cablea. `_set_computed`
  (`fields_relational.py:474-500`) escribe por la clase del comodelo y queda
  con el mismo límite que los modelos de Django.
