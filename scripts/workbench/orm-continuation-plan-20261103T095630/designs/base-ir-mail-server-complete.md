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
