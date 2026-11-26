# Adopción de BaseModel: res.device y res.device.log (basemodel-adoption-0397)

## Referencia

- `odoo19c: odoo/addons/base/models/res_device.py:16-199` — `ResDeviceLog`
  (`models.Model`) y `ResDevice` (`_inherit = ['res.device.log']`,
  `_auto = False`, vista).
- Escritura del log por SQL crudo, fuera de la ACL (`:98-104`); `_revoke`
  escribe el log con `sudo()` (`:186-196`); orden por `is_current` en
  `_order_field_to_sql` (`:65-68`).
- ACL: `ir.model.access.csv:145-146` (`group_user`, sólo lectura), ya sembrada
  (`designs/basemodel-adoption-properties-base-definition.md`).
- Reglas: `base_security.xml:229-252` — cada usuario lee sus dispositivos y
  sus logs (`[('user_id', '=', user.id)]`, `group_user`); el administrador
  todos (`[(1, '=', 1)]`, `group_system`).
- `res.users.device_ids = fields.One2many('res.device', 'user_id')`
  (`res_users.py:232`), en `SELF_READABLE_FIELDS` (`:185`).

## Estado heredado (medido por un subagente de sólo lectura, verificado contra la fuente)

- Los dos modelos son de Django; ningún consumidor pasa por la ACL ni por
  reglas (`AccessQuerySet` sólo comprueba con `check_access` explícito).
- Las cuatro reglas no están portadas (0 coincidencias en `src/` y `addons/`).
- Escritores que dependen de saltarse la ACL: `_update_device`
  (`bulk_create` desde `DeviceLogMiddleware`, que atrapa la excepción: el
  log dejaría de escribirse en silencio), `_revoke`, `__update_revoked` y
  `_gc_device_log`.
- `_revoke` y `order_by_is_current` viven en `ResDeviceQuerySet`; en la fuente
  son método del modelo y gancho de orden.
- La inversa se llama `devices` / `device_logs`; la fuente la llama
  `device_ids`, y `SELF_READABLE_FIELDS` ya pide `device_ids`.
- 31 pruebas crean filas del log sin usuario; dos casos fijan
  `ResDevice._meta.managed is False` (se conserva: la vista sigue siendo
  vista).

## Cambio

1. `ResDeviceLog` y `ResDevice` derivan de `models.BaseModel` (la vista sigue
   `managed = False`, como `hr.employee.public`).
2. Los escritores del log corren elevados, que es lo que el SQL crudo y el
   `sudo()` de la fuente garantizan: `_update_device`, `__update_revoked`,
   `_gc_device_log` y la escritura de `revoked` en `_revoke`.
3. `_revoke` pasa a método del recordset de `res.device`; `order_by_is_current`
   al gancho de orden de `is_current`.
4. Las cuatro reglas entran en `_RULES`, con su migración de datos.
5. `device_ids` como nombre de la inversa en `res.users`.
6. Las pruebas que crean filas sin usuario se elevan.

## Orden de trabajo

Por el radio (6 archivos de consumo directo, 31 pruebas), la unidad se parte:
primero los escritores elevados y las reglas sobre el modelo actual (no cambia
la base); después el cambio de base con `_revoke` y el orden en el modelo.

## Primer paso — medido (reglas e inversa)

Los escritores elevados se mueven al segundo paso: elevar sólo tiene efecto
cuando la ACL aplica, y la ACL aplica sólo con `models.BaseModel`. Sobre el
modelo de Django actual el `sudo()` no cambiaría ninguna consulta, así que
escribirlo ahora sería código sin control que lo discrimine.

| Símbolo | Archivo | Fuente |
|---|---|---|
| cuatro reglas de dispositivo en `_RULES` | `src/addons/base/security/base_security.py` | `odoo19c: odoo/addons/base/security/base_security.xml:229-252` |
| migración `0134_seed_device_rules` (siembra con `seed_base_rules`) | `src/addons/base/migrations/0134_seed_device_rules.py` | ídem |
| campo `user` de `ResDevice`, inversa `device_ids` | `src/addons/base/models/res_device.py` | `odoo19c: odoo/addons/base/models/res_users.py:232` |

Prueba: `tests/unit/base/test_res_device_rules.py` (dominio y grupo de cada
regla, y el nombre de la inversa).

Anulaciones, restauradas con `cmp`:

- reglas retiradas de `_RULES` y sus filas borradas (`rule_group_rel`, luego
  `ir_rule`): caen exactamente los 4 casos de regla y pasa el de la inversa;
- inversa devuelta a `devices`: cae exactamente
  `test_the_user_inverse_is_device_ids` y pasan los 4 de regla.

Consumidores del nombre anterior `devices`: 0 en `src/`, `addons/` y `tests/`
(la única coincidencia es un comentario de `html_editor`).

## Segundo paso — plan (base, escritores, `is_current`, orden)

Medido en la fuente (`odoo19c: odoo/addons/base/models/res_device.py:17-19,34-68,175-196`):

- `res.device.log` declara `_name`, `_description`, `_rec_names_search =
  ['platform', 'browser']`; `res.device` hereda con `_inherit`, `_auto = False`
  y `_order = 'last_activity desc'`.
- `is_current` es un **campo** calculado (`:34,46-48`), no un método con
  la petición como argumento: lo leen `_revoke` (`self.filtered('is_current')`,
  `:193`) y el orden.
- El orden por `is_current` es el gancho `_order_field_to_sql` (`:65-68`).
  `models.BaseModel._order_field_to_sql` existe aquí (`src/orm/models.py:4568`),
  así que la divergencia declarada de `order_by_is_current` deja de tener causa:
  se porta el gancho y el método explícito se retira.
- `_revoke` (`:185-196`) busca el log con `sudo()`, escribe `revoked` y cierra
  la sesión si estaba el dispositivo actual. Va al recordset del modelo.

Escritores que pasan a `with sudo():` (`orm.environments.sudo`), porque la
fuente los hace con SQL crudo o `sudo()`: `_update_device` (`:92-113`),
`_gc_device_log` (`:120-128`), `__update_revoked` (`:143-169`, cron) y la
búsqueda del log en `_revoke` (`:189`).

Consumidores que cambian (medido con
`grep -rnE "is_current\(|order_by_is_current|_revoke\(|ResDevice(Log)?\.objects"`):
`src/addons/base/models/res_users.py` (2) y las pruebas
`tests/unit/base/test_res_device.py`, `test_res_device_port_closure.py` y
`test_res_device_revoke.py`. Las coincidencias de `hr` y `account` son otro
`is_current`.

Controles previstos: un usuario sin grupo de sistema lee sólo sus
dispositivos (regla), `_update_device` escribe sin usuario elevado (la
anulación del `sudo()` tiene que hacer caer exactamente ese caso), y
`search([], order='is_current desc')` pone primero el dispositivo actual.

## Segundo paso — medido (cambio de base y escritores)

El paso se acota al cambio de base y a lo que ese cambio exige: `is_current`
como campo y su gancho de orden van a un tercer paso, porque el método actual
recibe la petición y sus consumidores no cambian por la ACL.

| Símbolo | Archivo | Fuente |
|---|---|---|
| `ResDeviceLog` y `ResDevice` derivan de `models.BaseModel` | `src/addons/base/models/res_device.py` | `odoo19c: odoo/addons/base/models/res_device.py:17-19` |
| `__update_revoked` escribe `revoked` elevado | ídem | `odoo19c: odoo/addons/base/models/res_device.py:143-169` |
| `ResDeviceQuerySet._revoke` busca y escribe el log elevado | ídem | `odoo19c: odoo/addons/base/models/res_device.py:185-196` |
| `_update_device` y `_gc_device_log`: comentario de por qué no se elevan | ídem | `odoo19c: odoo/addons/base/models/res_device.py:92-113,120-128` |

Prueba: `tests/unit/base/test_res_device_basemodel.py`.

**Lo que la medición corrigió del plan.** El plan elevaba los cuatro
escritores. Con la base cambiada, sólo dos fallan sin elevar: los que
escriben por `write` (`__update_revoked` y `_revoke`). `bulk_create` y
`QuerySet.delete` no consultan la ACL, igual que el `INSERT` y el
`DELETE ... USING` crudos de la fuente, así que un `sudo()` ahí no tenía
ningún control que lo discriminara y se retiró. Las pruebas de
`_update_device` y `_gc_device_log` bajo un usuario interno fijan esa
conducta.

Anulaciones, restauradas con `cmp`:

- sin el cambio de base: caen exactamente los dos casos que dependen de la
  ACL (escritura directa rechazada y lectura sólo de lo propio);
- sin la elevación de `__update_revoked` y `_revoke`: caen exactamente los
  9 casos de esos dos escritores en `test_res_device_port_closure.py` y
  `test_res_device_revoke.py`, y pasan los otros 42;
- sin elevar `_update_device` y `_gc_device_log`: no cae ninguno (de ahí que
  no se eleven).

Tercer paso, pendiente: `is_current` como campo calculado (`:34,46-48`) y el
gancho `_order_field_to_sql` (`:65-68`) en lugar de `order_by_is_current`.

## Tercer paso — medido (`is_current` y su orden)

| Símbolo | Archivo | Fuente |
|---|---|---|
| campo `is_current` y `_compute_is_current` (lee la petición del contexto) | `src/addons/base/models/res_device.py` | `odoo19c: odoo/addons/base/models/res_device.py:34,46-48` |
| `_IsCurrentOrder._order_field_to_sql` | ídem | `odoo19c: odoo/addons/base/models/res_device.py:65-68` |
| `is_current_session(request, identifier)` para quien tiene la petición explícita | ídem | `odoo19c: odoo/addons/base/models/res_device.py:48` |
| `ResDeviceQuerySet._revoke` decide el cierre con `is_current_session` | ídem | `odoo19c: odoo/addons/base/models/res_device.py:193` |
| retirados `ResDeviceQuerySet.order_by_is_current` y el método `ResDevice.is_current(request)` | ídem | — |
| `ResUsers._action_revoke_all_devices` excluye el dispositivo actual con `is_current_session` | `src/addons/base/models/res_users.py` | `odoo19c: odoo/addons/base/models/res_users.py:1023-1026` |
| `_session_key(request)`, la clave de la sesión de la petición, compartida por el gancho y `is_current_session` | `src/addons/base/models/res_device.py` | `odoo19c: odoo/addons/base/models/res_device.py:48,66` |

Pruebas: `tests/unit/base/test_res_device.py` (el campo contra la petición del
contexto) y `tests/unit/base/test_res_device_port_closure.py` (el orden por
`search(order='is_current, last_activity desc')`).

El gancho vive en una clase propia (`_IsCurrentOrder`) delante de
`models.BaseModel` en las bases: sobre `_ResDeviceFields`, que va detrás, el
`_order_field_to_sql` del ORM lo taparía.

Sin sesión en curso, la fuente pasa `is_current` al `_order_field_to_sql` del
ORM, que rehúsa un campo sin columna; aquí también (`ValueError: Cannot
convert base.ResDevice.is_current to SQL because it is not stored`). La
prueba sin sesión mide por eso el orden por defecto (`_order = 'last_activity
desc'`), no un orden por `is_current`.

Anulaciones, restauradas con `cmp`:

- el gancho sin efecto: cae exactamente
  `test_the_current_device_is_ordered_first`, y pasan los otros 49;
- el cálculo a `False`: cae exactamente
  `test_is_current_compara_contra_la_sesion_de_la_peticion`, y pasan los
  otros 49.

Con el tercer paso, los 15 métodos de la fuente tienen contraparte y las dos
divergencias de forma que quedaban (`is_current` como método,
`order_by_is_current`) se retiran.
