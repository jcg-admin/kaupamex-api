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
