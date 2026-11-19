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

### Decisión del paso 2 (ítem `base-ir-mail-server-basemodel-0397`)

El guardián de archivado no estaba conectado a nada: `check_can_archive` y
`check_can_archive_many` sólo los llamaba la prueba. En la fuente vive en el
`write` del modelo (`odoo19c: odoo/addons/base/models/ir_mail_server.py:231-264`),
y `IrMailServer` no tenía `write` porque no es `BaseModel`. Por eso el paso
adopta el modelo:

- `IrMailServer(models.BaseModel, TimeStampedModel)` con la cabecera de la
  fuente (`odoo19c: odoo/addons/base/models/ir_mail_server.py:142-145`):
  `_name = 'ir.mail_server'`, `_description = 'Mail Server'`,
  `_order = 'sequence, id'` y `_allow_sudo_commands = False`;
- la fila `access_ir_mail_server` (`group_system`, 1,1,1,1) del CSV de
  `base`, derivada con `probes/derive_base_acl.py` y sembrada por una
  migración, como `0095_seed_attachment_acl`;
- `write`, con el guardián tal cual: `UserError`, los dos mensajes de la
  fuente (uno o varios servidores) y el encabezado «(Dedicated Outgoing Mail
  Server)» sólo con varios. `check_can_archive(_many)` se retiran: eran su
  porte bajo otro nombre;
- `_check_forced_mail_server` (`:546-548`), `_get_default_bounce_address`
  (`:646-654`, el `email_from` de arranque, que aquí es
  `settings.DEFAULT_FROM_EMAIL` como en `_get_default_from_address`) y
  `_find_mail_server_allowed_domain` (`:870-873`, `Domain.TRUE`).

RED en `tests/unit/base/test_ir_mail_server_basemodel.py`.

### Ejecución del paso 2 (2026-11-19)

- `IrMailServer` deriva de `BaseModel` con la cabecera de la fuente. Lleva
  `write` con el guardián, `_check_forced_mail_server`,
  `_get_default_bounce_address` y `_find_mail_server_allowed_domain`.
  `check_can_archive(_many)` se retiraron, porque su único consumidor era la
  prueba.
- `_ACCESS` se volvió a derivar con `probes/derive_base_acl.py`: 94 filas,
  iguales en conjunto y en orden al literal. Entran cinco: `ir_mail_server`
  (`odoo19c: odoo/addons/base/security/ir.model.access.csv:119-119`) y cuatro
  de modelos que ya tenían `_name` sin que nadie hubiera vuelto a derivar la
  lista: `ir_exports group_system`, `ir_exports_line group_system` y las dos
  de `res_groups_privilege`. La migración `0122_seed_derived_acl` las siembra
  en las bases existentes con `seed_base_acl`, que es idempotente. Su prueba
  es `test_the_system_group_has_the_source_acl` en
  `tests/unit/base/test_ir_mail_server_basemodel.py`.
- Pruebas en `tests/unit/base/test_ir_mail_server_basemodel.py`: 8.
- Consumidores derivados (`grep -rlE "IrMailServer|ir\.mail_server|ir_mail_server|send_email|MailMail|mail_mail|email_executor" tests/`): 5515 passed con `-n 4`. Ningún código vivo usa `IrMailServer` (el envío va por la configuración de Django), así que el ACL nuevo no deniega ninguna ruta de envío.

Anulaciones, cada una medida por separado:

| Se retira | Caen |
|---|---|
| `write` | las dos del guardián (uno y varios servidores) |
| la guarda de `_check_forced_mail_server` | sólo `test_an_archived_server_cannot_be_forced` |

**Lo que el paso no cierra.** Las constantes `NO_VALID_RECIPIENT`,
`NO_FOUND_FROM`, `NO_FOUND_SMTP_FROM` y `NO_VALID_FROM` llevan texto propio
en español, y la fuente las declara en inglés (`:147-155`). Sus
consumidores en la fuente son `send_email` y `_prepare_email_message__`, así
que se llevan a la forma de la fuente en el paso 3, que es cuando tienen
consumidor. Sucesor: el paso 3 de este diseño, bajo TASK-API-0397.

## Paso 3: el transporte (borrador)

### La prosa heredada, validada

| Afirmación del docstring del puerto | Medido | Veredicto |
|---|---|---|
| «Todo el transporte (…) no se porta: aquí el transporte es `django.core.mail`. Duplicarlo daría dos caminos de salida» | la regla del objetivo prohíbe declarar divergencia en lugar de portar; `IrMailServer` no tiene consumidores de envío (medido en el paso 2) | **no es un cierre válido**: es una divergencia declarada sobre un contrato que la fuente sí tiene |
| «`_verify_check_hostname_callback` (pyOpenSSL) pertenece al conector, que no se porta» | `pyOpenSSL` 26.2.0 y `urllib3.contrib.pyopenssl` se importan en `.venv` | la dependencia existe; el bloqueo no está medido |
| «`groups='base.group_system'` en los cuatro campos de credenciales (…) actúa en el serializer» | la restricción de campo de la fuente es del ORM; con `BaseModel` adoptado, el control de grupo por campo es del recordset | se mide en el paso 3: si el ORM ya aplica `groups=` a la lectura, se declara en el campo |

### Alcance

Por familias, cada una con su RED y su anulación:

1. **Mensaje**: `_build_email__`, `_prepare_email_message__`,
   `_alter_message__`, `_prepare_smtp_to_list`, más las constantes de error
   en el inglés de la fuente.
2. **Conexión**: `_connect__`, `_smtp_login__`, `_check_smtp_ssl_files`,
   `_verify_check_hostname_callback`, `_disable_send`.
3. **Envío y prueba**: `send_email`, `test_smtp_connection`,
   `action_retrieve_max_email_size`, `_get_test_email_to`,
   `_onchange_encryption`.
4. **Los parches de import** (`_print_debug`, `WriteToLogger`,
   `IdentificationFieldsNoFoldPolicy`): la fuente los aplica al importar
   `ir_mail_server`, y aquí se portan igual en el mismo módulo.

Y después `django.core.mail` deja de ser un segundo camino: quien envíe
correo pasa por `send_email`, como en la fuente.

### Un solo camino de salida, como en la fuente (corrección del ejecutor, 2026-11-19)

«Duplicarlo daría dos caminos de salida» no es razón para no portar: el
remedio es el de la fuente, donde **el único** camino de salida es
`ir.mail_server.send_email`. `mail.mail._send` lo llama
(`odoo19c: addons/mail/models/mail_mail.py:861`).

Consumidores de `django.core.mail` medidos con
`grep -rnE "django\.core\.mail|send_mail\(" src addons`:

- `addons/mail/models/mail_mail.py:59,429` (`send_mail`);
- `addons/mail/models/email_executor.py:25,58` (`send_mail`);
- `addons/website_mass_mailing/controllers/subscribe.py:10,34`
  (`mail.send_mail`).

Cada uno pasa a `IrMailServer.send_email`, en una unidad propia después del
porte del transporte.

**Modo de prueba.** En la fuente `send_email` no envía cuando `_disable_send()`
es verdadero (`odoo19c: odoo/addons/base/models/ir_mail_server.py:389-392`,
`modules.module.current_test or cls.pool._init`), y las pruebas capturan el
mensaje parcheando `send_email` (`MockEmail`,
`odoo19c: addons/mail/tests/common.py:51`). Aquí las pruebas leen
`django.core.mail.outbox`: 11 archivos y 60 lecturas
(`grep -rhoE "mail\.outbox" tests`). Al pasar los consumidores a
`send_email`, esas pruebas pasan a la captura de la fuente, con su fixture
portado.

### Ejecución del paso 3a: el mensaje (ítem `base-ir-mail-server-message-0397`, 2026-11-19)

- Las cuatro constantes de error, con el texto de la fuente
  (`odoo19c: odoo/addons/base/models/ir_mail_server.py:147-154`). No tenían
  consumidores en el árbol.
- `_build_email__` (`odoo19c: odoo/addons/base/models/ir_mail_server.py:562-644`),
  `_prepare_email_message__` (`odoo19c: odoo/addons/base/models/ir_mail_server.py:679-733`),
  `_alter_message__` (`odoo19c: odoo/addons/base/models/ir_mail_server.py:735-762`)
  y `_prepare_smtp_to_list` (`odoo19c: odoo/addons/base/models/ir_mail_server.py:764-797`),
  sobre `self.env.context` del recordset, como la fuente. La única
  adaptación: `datetime.utcnow()` está obsoleto en 3.12+, así que la fecha
  se toma con `datetime.now(UTC)` sin zona, que es el mismo valor.
- Los `# noqa: PLW3201` de la fuente no se copian: `PLW3201` es de pylint, y
  ningún linter de este repo lo aplica.
- Pruebas en `tests/unit/base/test_ir_mail_server_message.py`: 11.
- Consumidores derivados (`tests/unit/base`, `tests/unit/mail`, `tests/integration/mail`): 2054 passed con `-n 4`.

Anulaciones, cada una medida por separado:

| Se retira | Caen |
|---|---|
| la alternativa en texto plano de un cuerpo `html` | sólo `test_an_html_body_gets_a_plain_alternative` |
| el filtro `send_smtp_skip_to` | sólo `test_the_recipients_honour_the_validated_and_skip_lists` |
| el borrado de `Bcc` en `_alter_message__` | sólo `test_alter_message_forges_to_and_drops_bcc` |

### Paso 3b: la conexión (borrador, medido)

`_connect__` (`odoo19c: :394-544`) lee la configuración de arranque con
`tools.config.get(...)`: `smtp_server`, `smtp_port`, `smtp_user`,
`smtp_password`, `smtp_ssl`, `smtp_ssl_certificate_filename`,
`smtp_ssl_private_key_filename`; y `_get_default_from_filter` y
`_get_default_*_address` leen `from_filter` y `email_from`. Aquí
`src/tools/config.py` no expone ninguna (`grep smtp src/tools/config.py` → 0),
y la configuración de correo vive en los `EMAIL_*` de Django. Prerrequisito:
esos lectores en `tools/config.py`, con el mismo patrón que `test_enable()`.

`_disable_send` (`:389-392`) es `modules.module.current_test or
cls.pool._init`. `current_test` no existe en `src/modules/module.py`
(`odoo19c: odoo/modules/module.py:111` lo declara); el equivalente de este
árbol es `tools.config.test_enable()`, que ya consume
`ir_template_expressions.py:941`.

Dependencias medidas en `.venv`: `idna` 3.17, `pyOpenSSL` 26.2.0 y
`urllib3.contrib.pyopenssl` (`PyOpenSSLContext`).

### Ejecución del prerrequisito de 3b: los lectores de `tools.config` (ítem `base-ir-mail-server-config-0397`, 2026-11-19)

Nueve lectores en `src/tools/config.py`, uno por opción de la fuente
(`odoo19c: odoo/tools/config.py:350-366`), cada uno con el valor por defecto
de la fuente cuando el setting falta o es falsy:

| Lector | Setting | Por defecto |
|---|---|---|
| `email_from` | `DEFAULT_FROM_EMAIL` | `''` |
| `from_filter` | `EMAIL_FROM_FILTER` (nuevo) | `''` |
| `smtp_server` | `EMAIL_HOST` | `'localhost'` |
| `smtp_port` | `EMAIL_PORT` | `25` |
| `smtp_ssl` | `EMAIL_USE_TLS` (la fuente lo traduce a STARTTLS, `:490-491`) | `False` |
| `smtp_user` | `EMAIL_HOST_USER` | `''` |
| `smtp_password` | `EMAIL_HOST_PASSWORD` | `''` |
| `smtp_ssl_certificate_filename` | `EMAIL_SSL_CERTFILE` | `''` |
| `smtp_ssl_private_key_filename` | `EMAIL_SSL_KEYFILE` | `''` |

Y los tres valores por defecto de `ir.mail_server` pasan a leerlos, como la
fuente (`odoo19c: odoo/addons/base/models/ir_mail_server.py:645-677`):

- `_get_default_bounce_address` y `_get_default_from_address` devuelven
  `config.email_from()`. El primero devolvía `None` cuando faltaba el
  remitente; la fuente devuelve el valor de config, cuyo defecto es `''`.
- `_get_default_from_filter` devuelve
  `get_param('mail.default.from_filter', config.from_filter())`. Antes
  pasaba `''` como respaldo, aunque su docstring decía que caía al valor de
  arranque: la prosa heredada era falsa.

Pruebas: `tests/unit/tools/test_config_smtp_readers.py` y
`tests/unit/base/test_ir_mail_server_config_defaults.py`. Controles de
anulación: retirar el `or 'localhost'` tumba sólo el caso de valores por
defecto; quitar el respaldo `config.from_filter()` tumba sólo el caso del
respaldo.
