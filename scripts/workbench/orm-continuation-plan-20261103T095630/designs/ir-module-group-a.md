# ir.module.module, grupo A: estado y siguiente paso

Sucesora de `designs/basemodel-adoption-ir-module.md`. TASK-API-0397.

## Contrato medido en la referencia

`odoo19c: odoo/addons/base/models/ir_module.py`:

- `:57-80` `assert_log_admin_access`: decorador de módulo; exige
  `self.env.is_admin()`, registra la llamada y levanta `AccessDenied` si no.
- `:347-349` `_get_modules_to_load_domain`: `[('state', '=', 'installed')]`.
- `:495-501` `button_reset_state` (`@assert_log_admin_access`,
  `@api.model`): `to install` vuelve a `uninstalled`; `to upgrade` y
  `to remove`, a `installed`.
- `:503-505` `check_module_update`: si hay algún módulo en estado transitorio.
- `:581-597` `next`: lanza el paso abierto de `ir.actions.todo`
  (`action_launch`) o redirige a `/odoo`.
- `:912-919` `_installed` (`@tools.ormcache(cache='stable')`): `{name: id}`
  de los instalados, con `sudo()`.

## Pruebas (RED)

Una por método, más el rechazo de `button_reset_state` a un usuario que no es
administrador.

## Medido

| Símbolo | Archivo | Fuente |
|---|---|---|
| `assert_log_admin_access` y su envoltura `assert_log_admin_access.check_and_log` (decorador de módulo, con `T` y `_logger`) | `src/addons/base/models/ir_module.py` | `odoo19c: odoo/addons/base/models/ir_module.py:57-74` |
| `IrModule._get_modules_to_load_domain` | ídem | `odoo19c: odoo/addons/base/models/ir_module.py:347-349` |
| `IrModule.button_reset_state` | ídem | `odoo19c: odoo/addons/base/models/ir_module.py:495-501` |
| `IrModule.check_module_update` | ídem | `odoo19c: odoo/addons/base/models/ir_module.py:503-505` |
| `IrModule.next` | ídem | `odoo19c: odoo/addons/base/models/ir_module.py:581-597` |
| `IrModule._installed` | ídem | `odoo19c: odoo/addons/base/models/ir_module.py:912-919` |
| `Field.__set__` sobre un recordset de varios registros: protegidos y nuevos de uno en uno, persistidos a `write` | `src/orm/fields.py` | `odoo19c: odoo/orm/fields.py:1807-1841` |

El `request.httprequest.remote_addr` del decorador es aquí el `REMOTE_ADDR`
de la petición Django en curso (`addons.base.models.ir_http.get_current_request`).

Medido al implementar: `button_reset_state` asigna `state` sobre el resultado
de `search`, un recordset de varios registros. El `Field.__set__` del puerto
sólo atendía un registro y levantaba `Expected singleton`; se porta el reparto
de la fuente.

El entorno de las pruebas es el de instalación de la fuente,
`Environment(uid=SUPERUSER_ID)`: el decorador lee `env.user.login`, y en la
fuente `env.user` existe siempre.

Pruebas: `tests/unit/base/test_ir_module_group_a.py` (7 casos, RED 7 de 7) y
`tests/unit/orm/test_field_set_recordset.py` (2).

Anulación (copias restauradas y comparadas con `cmp`): sin la rama de varios
registros de `Field.__set__` caen exactamente los dos casos de
`test_field_set_recordset.py` y el de `button_reset_state` (3 de 9); sin la
comprobación de `is_admin` del decorador cae exactamente el caso de rechazo
(1 de 7).
