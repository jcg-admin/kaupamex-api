# `base.public_partner` y `base.public_user` en cada base

Creado: 2026-11-12T21:04:01 (UTC). TASK-API-0485. Diagnóstico del ci-multidb no conforme de
`d10ae3ad` (`outputs/gates/ci-multidb-d10ae3ad`).

## Causa medida

- `Transaction.flush` (`src/orm/environments.py:523-537`), sin
  `default_env` y con trabajo pendiente, vuelca como
  `ref('base.public_user')`, igual que la fuente
  (`odoo19c: odoo/orm/environments.py:591-597`).
- `base.public_user` **no existe en ninguna base de este árbol**: 0 filas en
  `ir_model_data` de `orm_x2hokp_qa` (medido). La fuente lo siembra en
  `odoo/addons/base/data/res_users_data.xml:28-37` y su contacto en
  `res_partner_data.xml:27-30`. `addons/authz_totp/controllers/main.py:50`
  ya registra el hueco (tarea #729).
- En `provision` el respaldo nunca se recorría: la transacción de la base A
  conservaba el `default_env` de superusuario de su aprovisionamiento. En
  `clone`, `duplicate_database` cierra y mata las conexiones de A
  (`src/service/db.py:465-466`), la transacción se descarta, y el COMMIT
  del desmontaje de `company_without_format_per_base` llega al respaldo:
  `ValueError: base.public_user`. La fila de prueba queda y las tres
  preparaciones siguientes chocan en `res_company_code_key`.
- Medido que no es nuevo lo pendiente: la misma sonda sobre `0e674aed` y
  sobre `HEAD` deja sucios `commercial_partner_id`,
  `commercial_company_name`, `parent_path` (crear) y `paperformat`,
  `write_uid` (`init`).

## Decisión

Portar la siembra (TRAE), no esquivar el respaldo: el respaldo es contrato de
la fuente y `_auth_method_public` también lo necesita.

- `seed_public_user(apps, alias)` en `addons/base/data/res_users_data.py`,
  junto a `seed_root_user`: contacto `Public user` inactivo, usuario
  `login='public'`, inactivo, sin grupos, contraseña inutilizable (misma
  divergencia declarada que el superusuario), con sus dos XML-ID.
  Idempotente: una fila `login='public'` existente recibe los XML-ID.
- Migración `base/0113_seed_public_user` y su entrada en `_SEEDERS`.
- Fuera de alcance: la imagen (`image_1920`) y el uso en
  `_auth_method_public` (#729).

## Pruebas

- RED: `ref('base.public_user')` resuelve, inactivo y sin grupos.
- RED: el respaldo de `Transaction.flush` vuelca como ese usuario.
- Anulación: sin la siembra caen las dos.
- Aprovisionamiento: cambia una migración ⇒ ci-multidb en `provision`.
