# `ir.mail_server` de `base`: porte completo, con sus guiones bajos

Creado: 2026-11-18T23:29:32 (UTC). Ítem del plan `base-ir-mail-server-underscore-0397` (paso 1).

TASK-API-0397, prerrequisito de `mail/models/ir_mail_server.py`, que a su vez
lo es de `mail.alias.domain` (`basemodel-adoption-helpdesk.md`). Referencia:
odoo-tools `abe4040ec1`, `odoo19c: odoo/addons/base/models/ir_mail_server.py`
(991 líneas, LGPL-3).

## La prosa heredada, validada

| Afirmación | Medido | Veredicto |
|---|---|---|
| «`_match_from_filter` sí está portado (`base/models/ir_mail_server.py:479`)» (docstring de `addons/mail/models/mail_alias_domain.py`) | el puerto lo declara como `match_from_filter`, sin guion bajo, en la línea 508 | **falso en el nombre y en la línea**: es un símbolo privado promovido a público |

## Lo que mide el puerto (626 líneas)

Métodos de la clase de la fuente, por AST: 28. En la clase del puerto: 15.

**Despromovidos** (la fuente los declara privados; aquí van sin guion bajo):
`get_default_from_address`, `get_default_from_filter`,
`get_test_email_from`, `parse_from_filter`, `match_from_filter`,
`filter_servers_fallback`, `find_mail_server`, `get_max_email_size`,
`active_usages`, `smtp_authentication_info`. Consumidores fuera del archivo,
medidos con `grep -rlw`: sólo `tests/unit/base/test_ir_mail_server_from_filter.py`,
para `match_from_filter` y `find_mail_server`.

**Ausentes**: `send_email`, `_build_email__`, `_connect__`, `_smtp_login__`,
`_prepare_email_message__`, `_alter_message__`, `_prepare_smtp_to_list`,
`_get_default_bounce_address`, `_get_test_email_to`, `test_smtp_connection`,
`action_retrieve_max_email_size`, `_disable_send`, `_check_forced_mail_server`,
`_find_mail_server_allowed_domain`, `_check_smtp_ssl_files`, `write`,
`_onchange_encryption`. Y a nivel de módulo: `_print_debug`,
`IdentificationFieldsNoFoldPolicy` (con `_fold`), `WriteToLogger` y
`_verify_check_hostname_callback`.

## Orden

1. Restaurar los guiones bajos (renombre por token, más sus dos consumidores
   en la prueba), sin cambio de conducta.
2. Portar por familias, cada una con su RED: envío (`send_email`,
   `_build_email__`, `_prepare_*`, `_alter_message__`), conexión
   (`_connect__`, `_smtp_login__`, `test_smtp_connection`, el TLS), y los
   pequeños (`_get_default_bounce_address`, `_check_forced_mail_server`,
   `_find_mail_server_allowed_domain`, `write`).
3. Después, la extensión de `mail` (`owner_user_id` y sus 8 métodos), que
   llama a `super()` sobre los de este archivo.

## Paso 1: los guiones bajos (2026-11-18)

Renombre por token, con el intérprete del proyecto (3.12+, que tokeniza el
interior de las f-strings), en el puerto y en su prueba, más las menciones
entre dobles acentos graves en la prosa:

| Antes | Ahora (nombre de la fuente) |
|---|---|
| `active_usages` | `_active_usages_compute` (`odoo19c: odoo/addons/base/models/ir_mail_server.py:266-273`) |
| `get_max_email_size` | `_get_max_email_size` (`odoo19c: odoo/addons/base/models/ir_mail_server.py:275-278`) |
| `get_test_email_from` | `_get_test_email_from` (`odoo19c: odoo/addons/base/models/ir_mail_server.py:280-295`) |
| `get_default_from_address` | `_get_default_from_address` (`odoo19c: odoo/addons/base/models/ir_mail_server.py:656-664`) |
| `get_default_from_filter` | `_get_default_from_filter` (`odoo19c: odoo/addons/base/models/ir_mail_server.py:666-677`) |
| `parse_from_filter` | `_parse_from_filter` (`odoo19c: odoo/addons/base/models/ir_mail_server.py:976-978`) |
| `match_from_filter` | `_match_from_filter` (`odoo19c: odoo/addons/base/models/ir_mail_server.py:956-974`) |
| `filter_servers_fallback` | `_filter_mail_servers_fallback` (`odoo19c: odoo/addons/base/models/ir_mail_server.py:951-954`): la fuente lo nombra también distinto |
| `find_mail_server` | `_find_mail_server` (`odoo19c: odoo/addons/base/models/ir_mail_server.py:874-949`) |

`smtp_authentication_info` se queda: en la fuente es un **campo**
(`:168`), y lo privado es su `_compute_…`.

Cambian también, sólo porque llaman a los nombres nuevos:
`_find_mail_server.first_match` (la función interna de `_find_mail_server`),
`check_can_archive` y `check_can_archive_many`, que portan el guardián de
archivado del `write` de la fuente
(`odoo19c: odoo/addons/base/models/ir_mail_server.py:231-264`) y leen
`_active_usages_compute`.

Sin cambio de conducta. Las pruebas son la existente,
`tests/unit/base/test_ir_mail_server_from_filter.py` (filtro de remitente y
selección de servidor), y una nueva,
`tests/unit/base/test_ir_mail_server_private_contract.py`, para los métodos
que ninguna prueba ejercía: `_active_usages_compute`, el guardián de
archivado, `_get_max_email_size` y `_get_test_email_from` (9 pruebas).
Anulación: devolver `_get_max_email_size` a su nombre viejo hace caer
exactamente sus dos pruebas.

Consumidores derivados (`grep -rlE "IrMailServer|ir\.mail_server|ir_mail_server" tests/`):
`tests/unit/base` y `tests/unit/orm`, con `-n 4`.

- Primera ejecución, tras un reinicio del contenedor: 4520 passed y **783
  errores**, todos en la preparación de la prueba y con la misma causa:
  `system_parameter.create_uid = 1` violaba su FK porque `res_users` no
  tenía la fila 1 en la base de ese worker. Medido después, las cinco bases
  (`orm_x2hokp_qa` y `_gw0` a `_gw3`) sí la tenían.
- Segunda ejecución, mismo código y mismo comando: **5287 passed**, 0
  errores.

El renombre no toca `res_users` ni `system_parameter`. Lo más probable es
que una prueba que vacía tablas al terminar dejara sin usuarios a un worker
y que las pruebas que le tocaron después fallaran. Que ocurra depende del
reparto entre workers, y eso explica que la segunda ejecución pasara.
DESCONOCIDO con condición de cierre: identificar la prueba repitiendo con
`-p xdist --dist loadfile` y `-v` hasta reproducirlo, y ver qué prueba
precede a la primera fallida en su worker. Sucesor bajo TASK-API-0485.

## Paso 2: los métodos pequeños (borrador)

| Símbolo | Fuente | Puerto |
|---|---|---|
| `write` (guardián de archivado) | `:231-264`: `UserError`, mensajes en inglés, `display_name`, encabezado «(Dedicated Outgoing Mail Server)» sólo con varios | `check_can_archive(_many)`: `ValidationError`, mensajes propios en español |
| `_check_forced_mail_server` | `:546-548`: rehúsa un servidor archivado salvo `allow_archived` | ausente |
| `_get_default_bounce_address` | `:646-654`: el `email_from` de la config | ausente |
| `_find_mail_server_allowed_domain` | `:870-873`: `Domain.TRUE`, punto de extensión de `mail` | ausente |

El guardián se lleva a la forma de la fuente (excepción y texto), y los otros
tres se portan, con sus consumidores medidos en `_find_mail_server` y en
`send_email`, que llega en el paso 3.
