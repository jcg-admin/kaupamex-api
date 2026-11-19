# `authz_totp` sobre `BaseModel`, con su seguridad

Unidad hija `basemodel-adoption-authz-totp-0397` del paraguas
`basemodel-adoption-0397` (TASK-API-0397), con la forma de
`basemodel-adoption-purchase-requisition.md`.

## Contrato medido en la referencia

- `auth_totp.device` (`odoo19c: addons/auth_totp/models/auth_totp.py:15-16`):
  `_inherit = ["res.users.apikeys"]`, `_description = "Authentication Device"`.
- `auth.totp.rate.limit.log`
  (`odoo19c: addons/auth_totp/models/auth_totp_rate_limit_log.py:5`).
- `odoo19c: addons/auth_totp/security/ir.model.access.csv`: 3 filas; la del
  registro de intentos niega todo a `base.group_user` (`0,0,0,0`).
- `odoo19c: addons/auth_totp/security/security.xml`: el acceso y la regla de
  `auth_totp.wizard`, y las reglas `api_key_public`, `api_key_user` y
  `api_key_admin` de `auth_totp.device`.
- `_totp_rate_limit` y `_totp_rate_limit_purge`
  (`odoo19c: addons/auth_totp/models/res_users.py:118-152`) leen y escriben el
  registro con `sudo()`: la ACL vacía protege la tabla, no el conteo.

## La prosa heredada, validada

`res_users.py` dice que *«el ORM de Django no interpone ACL sobre el
queryset»*, y por eso el conteo no necesita `sudo()`. Medido con la adopción
hecha: sigue siendo cierto, porque `objects` no pasa por `check_access`; un
usuario interno cuenta y purga sus intentos aunque la ACL del registro sea
`0,0,0,0`. El conteo no cambia.

## Cambios

1. `AuthTotpDevice` deriva de `(models.BaseModel, _ResUsersApikeysBase)` y
   `AuthTotpRateLimitLog` de `(models.BaseModel, TimeStampedModel)`.
2. `addons/authz_totp/security/`: el CSV y el XML, copia fiel, en `data` del
   manifiesto en el orden de la fuente. Del XML salen el acceso y la regla de
   `auth_totp.wizard`, que este árbol no porta como modelo (el asistente vive
   en `services.py`); se declaran en el manifiesto.
3. `test_basemodel_reach.py`: `authz_totp` sale de `PENDING`.

## Fuera de esta unidad, con su sucesor

- El asistente `auth_totp.wizard` como modelo, con su acceso y su regla —
  `authz-totp-wizard-model-0397`.

## Pruebas

`tests/unit/authz_totp/test_authz_totp_basemodel.py`: los dos modelos son
`BaseModel` con su `_description`; las 3 filas del CSV; las 3 reglas del
dispositivo; un usuario interno no lee el registro de intentos por el
entorno, y su intento se cuenta y se purga (guarda de que la ACL vacía no
rompe el conteo).
