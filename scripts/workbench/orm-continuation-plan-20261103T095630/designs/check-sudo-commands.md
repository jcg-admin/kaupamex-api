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

## Medición pendiente (precede al diseño de la solución)

Con qué entorno corren hoy los comandos cuando el registro está en
`sudo()`/`with_user` y el ambiente no: si heredan el ambiental, el defecto
actual tiene dos mitades (no se propaga el entorno del registro, y no se
aplica la restricción). Se mide con una sonda que no toca la base compartida
mientras corre la suite.
