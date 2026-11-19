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

### Paso 3b: la conexión (ítem `base-ir-mail-server-connect-0397`), diseño

**Prosa heredada que este paso corrige.** El docstring del módulo tiene una
sección «Qué NO se porta» que declara tres divergencias, y las tres son
falsas a la luz de la corrección del ejecutor del 2026-11-19:

- «todo el transporte… Duplicarlo daría dos caminos de salida». El paso 3a ya
  portó cuatro de esos métodos, y el remedio a los dos caminos es que haya uno
  solo, `send_email` (paso 3d), no que falte;
- «los tres parches globales… una decisión de plataforma». La fuente los
  aplica al importar el módulo (`odoo19c: odoo/addons/base/models/
  ir_mail_server.py:68-98`), y portarlos completos es aplicarlos igual;
- «`_verify_check_hostname_callback` pertenece al conector, que no se porta».
  El conector se porta en este paso.

**Qué se porta** (`odoo19c: odoo/addons/base/models/ir_mail_server.py`):

| Símbolo | Líneas | Nota |
|---|---|---|
| imports de pyOpenSSL, `cryptography`, `urllib3.contrib.pyopenssl`, `idna` | 16-56 | rama `OpenSSL >= 24.3.0` (aquí 26.2.0); la rama vieja se porta igual, con la misma condición |
| `_print_debug` + `smtplib.SMTP._print_debug = …` | 68-71 | parche al importar |
| `RFC5322_IDENTIFICATION_HEADERS`, `USER_DEFINED_HEADERS`, `_noFoldPolicy`, `_maxFoldPolicy`, `IdentificationFieldsNoFoldPolicy` + `email.policy.SMTP = …` | 73-92 | parche al importar |
| `WriteToLogger` + `smtplib.stderr = …` | 94-98 | parche al importar |
| `_verify_check_hostname_callback` | 122-137 | |
| `_disable_send` | 388-392 | `current_test or pool._init` → `tools.config.test_enable() or env().registry._init` (`orm/registry.py:1812,1919`) |
| `_connect__` | 394-534 | |
| `_smtp_login__` | 541-551 | |

**Dependencias.** `pyOpenSSL`, `idna` y `urllib3` están en `uv.lock` sólo como
transitivas (26.2.0, 3.17, 2.7.0). La fuente las importa en su módulo, así que
pasan a declararse en `pyproject.toml` con la versión ya resuelta: sin
descarga nueva.

**Pruebas** (`tests/unit/base/test_ir_mail_server_connect.py`): `_connect__`
devuelve `None` bajo pruebas; con `_disable_send` en falso y `smtplib.SMTP`
sustituido por un doble, la conexión recibe el host, el puerto y el `from_filter`
del servidor y, sin servidor, los de `tools.config`; STARTTLS se activa por
`smtp_ssl`; el usuario con dominio internacional se codifica con `idna`;
servidor ausente → `UserError` «Missing SMTP Server»; los tres parches están
aplicados tras importar el módulo (`smtplib.SMTP._print_debug`,
`smtplib.stderr`, `email.policy.SMTP`), y un `Message-ID` largo no se pliega.

### Ejecución del paso 3b (ítem `base-ir-mail-server-connect-0397`, 2026-11-19)

Portados `_print_debug`, `IdentificationFieldsNoFoldPolicy`, `WriteToLogger`
y sus tres parches al importar, `_verify_check_hostname_callback`,
`_disable_send`, `_connect__` y `_smtp_login__`. `pyOpenSSL`, `urllib3` e
`idna` quedan declaradas en `pyproject.toml`. El lock sólo gana las seis
líneas de dependencia; la línea `revision = 5`, escrita por un uv más nuevo
que el de esta VM (0.11.32), se conserva.

Divergencia declarada: las ramas de versión antigua de los imports
(`odoo19c: odoo/addons/base/models/ir_mail_server.py:36-56`) no se portan,
porque con los pisos declarados no se pueden ejecutar, y además el checker de
estilo rechaza un import condicional.

Lo que la medición corrigió:

- La primera prueba del plegado usaba un `Message-ID` largo y pasaba **sin**
  el parche: Python ya no lo pliega. Se cambió a un `Subject` largo, que la
  política de 998 columnas deja en una línea y la de 78 pliega.
- urllib3 2.x ya no cae al `commonName` cuando el certificado no tiene SAN
  (`no appropriate subjectAltName fields were found`). Es la conducta real del
  código portado con la dependencia instalada; la prueba emite el certificado
  con SAN.

Controles de anulación: quitar la codificación `idna` del usuario tumba sólo
la prueba de `idna`; quitar el parche de `email.policy.SMTP` tumba sólo las
dos pruebas que dependen de él (la de los parches y la del plegado).

Pendiente, fuera de este paso: `extract_rfc2822_addresses` sigue capturando
`UnicodeEncodeError` de `email.utils.formataddr`, y no `idna.IDNAError` del
`formataddr` de `tools`, como hace la fuente (`:105-119`). Ahora que `idna` es
una dependencia declarada, se corrige con el paso 3c.

### Paso 3c: el envío y la prueba de conexión (borrador, medido)

`odoo19c: odoo/addons/base/models/ir_mail_server.py`:

| Símbolo | Líneas | Estado aquí |
|---|---|---|
| `_test_logger` | 59 | ausente |
| `send_email` | 798-868 | ausente |
| `test_smtp_connection` | 300-382 | ausente |
| `action_retrieve_max_email_size` | 384-386 | ausente |
| `_get_test_email_to` | 297-298 | ausente |
| `_get_test_email_from` | 280-295 | firma divergente: aquí recibe `fallback_email`; la fuente cae a `self.env.user.email` |
| `extract_rfc2822_addresses` | 105-119 | captura `UnicodeEncodeError` de `email.utils.formataddr`; la fuente usa el `formataddr` de `tools` y captura `idna.IDNAError` |

### Paso 3e: la superficie del modelo (borrador, medido)

Tres divergencias que el docstring presenta como equivalentes y no lo son:

| Fuente | Aquí | Diferencia medida |
|---|---|---|
| `smtp_authentication_info`: campo calculado no almacenado, `@api.depends('smtp_authentication')`, texto inglés (`:204-220`) | `@property` con texto español reescrito | el valor no es el de la fuente, y `False` pasa a `''` |
| `_check_smtp_ssl_files`: `@api.constrains`, `UserError` en inglés (`:222-229`) | `clean()`, `ValidationError` en español | otro mecanismo, otra excepción y otro mensaje; `clean()` no corre en `create`/`write` del ORM |
| `_onchange_encryption`: `@api.onchange('smtp_encryption')`; `ssl` → 465 con aviso si falta `SMTP_SSL`; cualquier otro → **25** (`:979-990`) | `suggested_port()`, que devuelve el puerto actual fuera de `ssl` | la rama `else` no fija 25, y no hay aviso |

### Ejecución del paso 3c (ítem `base-ir-mail-server-send-0397`, 2026-11-19)

Portados `_test_logger`, `send_email`, `test_smtp_connection`,
`action_retrieve_max_email_size` y `_get_test_email_to`, y corregidos
`_get_test_email_from` y `extract_rfc2822_addresses` a la forma de la fuente:

- `_get_test_email_from` deja de recibir `fallback_email` y cae a
  `self.env.user.email`, con el `UserError` de la fuente. La prueba vieja
  (`ValidationError` sin usuario) codificaba la firma retirada y se borra; la
  negativa la cubre la prueba nueva, con el mensaje de la fuente.
- `extract_rfc2822_addresses` usa el `formataddr` de `tools` y captura
  `idna.IDNAError`: un dominio internacional se conserva codificado
  (`ana@xn--bcher-kva.mx`), donde antes se descartaba.
- El tamaño máximo detectado se guarda con `write`: en la fuente asignar el
  campo escribe, y aquí una asignación no persiste.

Lo que la medición corrigió en las pruebas, no en el porte: el remitente de
sobre es la dirección de rebote antes que `From`
(`_prepare_email_message__`), y la prueba de conexión lee el registro con las
ACL, así que se ejecuta como sistema.

Controles de anulación: quitar el corte de `_disable_send` en `send_email`
tumba sólo la prueba de modo de prueba; quitar el `quit()` tumba sólo la
prueba de la sesión propia.

### Paso 3d: un solo camino de salida (borrador, medido)

**Los remitentes que hoy salen por `django.core.mail`** (medido con
`grep -rln "from django.core.mail\|from django.core import mail" src addons`):

| Sitio | Qué hace |
|---|---|
| `addons/mail/models/email_executor.py:25,58,65` | `dispatch_email`: `send_mail` de Django en un hilo del pool (o síncrono con `DISPATCH_EMAIL_SYNC`) y reencola en `mail.mail` si falla; **23 llamadas** en 12 archivos de producción |
| `addons/mail/models/mail_mail.py:59,429` | la cola de `mail.mail` (`process_email_queue`) |
| `addons/website_mass_mailing/controllers/subscribe.py:10,34` | confirmación de la newsletter, con `fail_silently=True` |

Los tres construyen el mensaje con `_build_email__` y lo envían con
`send_email`. `dispatch_email` conserva su hilo y su reencolado (no es un
símbolo de la fuente, es la cola de este árbol), pero su transporte pasa a ser
`send_email`.

**La captura en las pruebas.** Hoy 12 archivos de pruebas leen
`django.core.mail.outbox` (60 lecturas), que llena el backend `locmem` de
`config/settings/testing.py:133`. Con `send_email`, bajo pruebas
`_disable_send` corta antes de enviar, como en la fuente, y `outbox` queda
vacío. El equivalente de la fuente es `MockSmtplibCase.mock_smtplib_connection`
(`odoo19c: odoo/addons/base/tests/common.py:378-460`): sustituye
`smtplib.SMTP` y `SMTP_SSL` por una sesión que registra cada `send_message` en
`emails` (mensaje, `From`, `To`, `Cc`, `smtp_from`, `smtp_to_list`,
`from_filter`) y pone `_disable_send` en falso. Se porta como fixture de pytest
con el mismo nombre y la misma forma de registro, y las 60 lecturas de
`outbox` pasan a leer `emails`. Después, `EMAIL_BACKEND` de pruebas queda sin
consumidor y se retira.

**Por medir antes de implementar:**

- `send_email` dentro del hilo del pool. **Medido:** `env()` se arma con
  `ContextVar` (`src/orm/environments.py:143-149,2106-2128`), y un hilo de
  `ThreadPoolExecutor` arranca con sus valores por defecto: `uid=None`,
  `su=False`. Dentro del hilo el modelo se obtiene con
  `Environment(uid=SUPERUSER_ID)['ir.mail_server']`, como la cola de la fuente,
  que corre bajo el cron del superusuario.
- `fail_silently=True` de la newsletter: la fuente no tiene ese parámetro; el
  equivalente es capturar `MailDeliveryException` en el llamador, y se decide
  al medir qué hace hoy el controlador cuando el envío falla.

### Ejecución del paso 3d-1 (ítem `base-ir-mail-server-senders-0397`, 2026-11-19)

El paso 3d se parte en dos ítems por su radio: 3d-1 lleva la captura de las
pruebas y dos de los tres remitentes; 3d-2, `dispatch_email` y las ocho
pruebas que lo leen por `outbox`.

- `tests/mocks/mail_server.py`: porte de `MockSmtplibCase` con
  `mock_smtplib_connection` y la forma de registro de la fuente; el fixture del
  mismo nombre vive en `tests/conftest.py`. `_find_mail_server` es aquí un
  `classmethod`, así que la envoltura que registra sus argumentos conserva el
  descriptor. `parsed_message` vuelve a analizar `message` para leer el asunto.
- La cola de `mail.mail`: `MailMail._send_one` construye el mensaje con
  `_build_email__` (cuerpo `html`) y lo envía con `send_email`, como
  `mail.mail._send` de la fuente (`odoo19c: addons/mail/models/mail_mail.py:763-870`).
  Prueba: `tests/integration/mail/test_resend_failed_emails.py`.
- La confirmación de la newsletter sale por `send_email`. `fail_silently=True`
  tragaba `SMTPException` y `OSError`; el equivalente captura esas dos y
  `MailDeliveryException`, y deja el fallo en el log.
- Pruebas migradas: `test_resend_failed_emails.py` (las lecturas de `outbox`
  pasan a `emails`, y el fallo se simula haciendo fallar `send_email`) y la
  confirmación de `test_newsletter_endpoints.py`.

Control: con los remitentes aún en `django.core.mail`, las pruebas migradas
fallan (4 de 6). Retirar del fixture el parche de `_disable_send` tumba sólo
la prueba de captura.

### Paso 3d-2: `dispatch_email` por `send_email` (borrador, medido)

- `dispatch_email` construye el mensaje con `_build_email__` y lo envía con
  `send_email`, en el hilo del pool o síncrono, con
  `Environment(uid=SUPERUSER_ID)` (ver la medición del hilo, arriba). Los
  llamadores pasan `html_message` en 8 sitios y `notification` en 2 (medido
  con `grep -A7 "dispatch_email("`). `send_mail` de Django arma
  `multipart/alternative` con `message` y `html_message`; el equivalente es
  `body=html_message, subtype='html', body_alternative=message`.
- Las lecturas de `outbox` que quedan, por forma (medido con `grep -oE`):
  `django_mail.outbox` 16, `.clear()` 13, `mail.outbox` 11, `[0].to` 6,
  `[0].subject` 4, `[0].body` 1. Pasan a `emails[i]['smtp_to_list']` y a
  `parsed_message(...)`.
- Después, `EMAIL_BACKEND` de pruebas (`config/settings/testing.py:133`) queda
  sin consumidor y se retira.

Funciones que cambia el paso 3d-2, en `addons/mail/models/email_executor.py`:
`dispatch_email` deja de llamar a `send_mail` de Django y llama a `_send_mail`,
una función nueva que arma el mensaje con `_build_email__` y lo envía con
`send_email`, como `mail.mail._send` de la fuente
(`odoo19c: addons/mail/models/mail_mail.py:763-870`). `_finalize_failure`
reencola el cuerpo HTML cuando lo hay, en vez del texto plano. Pruebas:
`tests/integration/mail/test_transactional_notifications.py` y las otras siete
que leen `outbox`.

### Ejecución del paso 3d-2 (ítem `base-ir-mail-server-dispatch-0397`, 2026-11-19)

- `dispatch_email` envía con `_send_mail`, que arma el mensaje con
  `_build_email__` (con `html_message`, cuerpo HTML y `message` como su
  alternativa en texto plano) y lo envía con `send_email` como superusuario.
  Si el envío falla, se reencola el cuerpo HTML cuando lo hay.
- Con esto ningún código de producción usa `django.core.mail`. Medido con
  `grep -rnE "django\.core\.mail|from django\.core import (.*\b)?mail\b"
  src addons --include=*.py`: sólo quedan menciones en prosa.
- `EMAIL_BACKEND` de pruebas (`locmem`) se retira de
  `config/settings/testing.py`. El de `development.py`, `production.py` y
  `options.py` también queda sin consumidor; retirarlo toca la configuración
  de despliegue y se registra como pendiente, no se hace de rebote aquí.
  `addons/helpdesk/tests_uc_not_08.py` lo sobreescribe en un caso, pero está
  fuera de `testpaths` y no lee `outbox`.
- Ocho archivos de pruebas más pasan de `outbox` y de `mailoutbox` a
  `mock_smtplib_connection` y `sent_mails`. En los dos de avisos de 2FA, los
  ayudantes sin parámetros leen la captura de un fixture `autouse`, como antes
  leían la bandeja global.
- Prosa corregida: los docstrings de `ir_mail_server.py`,
  `base/models/__init__.py` y `email_executor.py` ya no dicen que el
  transporte sea `django.core.mail`.

Control: con `dispatch_email` aún en Django, las pruebas migradas fallan
(23 de 167).

**Qué cambia el paso 3e** (ítem `base-ir-mail-server-surface-0397`), en
`src/addons/base/models/ir_mail_server.py`:

- `smtp_authentication_info` pasa de `@property` a campo `Char` calculado no
  almacenado con `_compute_smtp_authentication_info`, con el texto de la fuente
  (`odoo19c: odoo/addons/base/models/ir_mail_server.py:204-220`).
- `clean()` se retira y su comprobación vuelve a ser `_check_smtp_ssl_files`
  con `@api.constrains` y `UserError`
  (`odoo19c: odoo/addons/base/models/ir_mail_server.py:222-229`).
- `suggested_port()` y `SSL_PORT` se retiran por `_onchange_encryption` con
  `@api.onchange('smtp_encryption')`
  (`odoo19c: odoo/addons/base/models/ir_mail_server.py:979-990`).

Ninguno tiene consumidores fuera del modelo (medido con `grep -rn
"smtp_authentication_info\|suggested_port\|\.clean()" src addons tests`).
Prueba: `tests/unit/base/test_ir_mail_server_surface.py`.

### Ejecución del paso 3e (ítem `base-ir-mail-server-surface-0397`, 2026-11-19)

`smtp_authentication_info` es un `Char` calculado no almacenado con
`_compute_smtp_authentication_info` y el texto de la fuente;
`_check_smtp_ssl_files` vuelve a ser `@api.constrains` con `UserError`; y
`_onchange_encryption` sustituye a `suggested_port()`, con la rama `else`
que fija 25. Se retiran `clean()`, `suggested_port()` y `SSL_PORT`.
`makemigrations base --check` no detecta cambios: el campo no lleva columna.

Control: quitar la rama `else` de `_onchange_encryption` tumba sólo la prueba
del puerto 25.

Con este paso, lo que la fuente declara en
`odoo19c: odoo/addons/base/models/ir_mail_server.py` queda portado, salvo dos
divergencias declaradas en el docstring del módulo: las ramas de versión
antigua de los imports y `groups='base.group_system'` en los cuatro campos
secretos. Queda pendiente `addons/mail/models/ir_mail_server.py` (el
`owner_user_id` y sus ocho métodos).

## Paso 4: el contrato de `_find_mail_server` (borrador, medido)

Prerrequisito de la extensión de `mail`
(`odoo19c: addons/mail/models/ir_mail_server.py`), que sobreescribe
`_find_mail_server_allowed_domain` para limitar la búsqueda a los servidores
públicos y `_filter_mail_servers_fallback` para filtrar por propietario. Hoy
ninguna de las dos sobreescrituras tendría efecto:

| Fuente (`odoo19c: odoo/addons/base/models/ir_mail_server.py:874-948`) | Aquí |
|---|---|
| `_find_mail_server(self, email_from, mail_servers=None)` | `(cls, email_from, servers=None, notifications_email=None)` |
| el correo de notificaciones sale de `self.env.context['domain_notifications_email']` o de `_get_default_from_address()` | parámetro `notifications_email` propio |
| busca con `self.sudo().search(self._find_mail_server_allowed_domain(), order='sequence')` | `cls.objects.order_by('sequence', 'id')`, sin el dominio |
| `mail_servers.filtered('active')`, recordsets en toda la cascada | listas |

Único llamador de producción: `_connect__` (`self.sudo()._find_mail_server(
smtp_from)`), que ya tiene la forma de la fuente. Las pruebas de
`tests/unit/base/test_ir_mail_server_from_filter.py` pasan `servers=` y
`notifications_email=`; pasan a `mail_servers=` y a
`with_context(domain_notifications_email=...)`.
