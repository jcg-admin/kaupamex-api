"""``ir.mail_server`` — el registro declarativo de servidores SMTP salientes.

Adaptación de ``odoo/addons/base/models/ir_mail_server.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 991 líneas). Un registro por servidor
SMTP, con su prioridad y —lo que de verdad importa— su ``from_filter``: la
lista de direcciones o dominios para los que ese servidor puede enviar.

Qué añade sobre el transporte que este árbol ya tiene
====================================================

El envío ya existe: ``addons/mail/models/email_executor.py`` despacha por
``django.core.mail.send_mail`` sobre la config global ``EMAIL_*``
(``config/settings/development.py:22-28``, ``production.py:104-111``), y su
propio docstring dice que eso es *"análogo a ``ir.mail_server`` de
``addons/base``"*. Lo es en el transporte, no en el modelo.

La diferencia es que ``EMAIL_*`` describe **un** servidor. Este archivo aporta
lo que esa config no puede expresar:

- **varios** servidores con **prioridad** (``sequence``, menor = más alta);
- **enrutado por remitente**: qué servidor sirve para qué dirección o dominio
  (``from_filter``), que es la pregunta que aparece en cuanto hay un dominio
  transaccional y otro de marketing;
- el **fallback en cascada** de ``_find_mail_server``, que decide qué hacer
  cuando ningún servidor declara el remitente pedido.

Portar el registro **no** cambia por dónde sale hoy el correo. Cablear
``email_executor`` contra estas filas es un pase aparte, y hasta que ocurra
esta tabla es declarativa.

La cascada de selección, que es el corazón del archivo
=====================================================

``_find_mail_server`` devuelve **dos** cosas —el servidor y el remitente que
se acabará usando—, y esa segunda mitad es la que se pierde al resumirlo. Los
cinco pasos, en orden, y qué remitente sale de cada uno:

1. servidor cuyo ``from_filter`` casa el **correo exacto** pedido → el
   remitente pedido;
2. servidor cuyo ``from_filter`` casa el **dominio** del correo pedido → el
   remitente pedido;
3. (tras filtrar los candidatos de respaldo) lo mismo dos veces contra el
   **correo de notificaciones** → el remitente de notificaciones;
4. primer servidor **sin** ``from_filter`` → suplanta el remitente
   (notificaciones si lo hay, si no el pedido);
5. cualquier servidor, aun configurado para otro dominio, con aviso en el log.

Y si no hay ninguna fila, cae a la config global comparando contra su
``from_filter``. El detalle que no se puede omitir: **el remitente cambia
según el paso**. Un port que devolviera sólo el servidor haría que el correo
saliera con un ``From`` que su servidor no acepta, que es exactamente lo que
la cascada evita.

Normalizadores de correo — ya en su hogar canónico
=================================================

``_match_from_filter`` depende de ``email_normalize`` /
``email_domain_extract`` / ``email_domain_normalize``, que en la referencia
viven en ``odoo/tools/mail.py`` — **otro archivo**, no éste.

Este archivo las implementó como privadas propias mientras ``tools/mail.py``
no existía, y declaró que se borrarían al portarse. Cumplido: las tres se
importan de ``tools.mail`` y aquí no queda ninguna copia. Un segundo hogar
para una utilidad compartida es el error que el monolito modular existe para
evitar, y el intercambio cambia además el valor falso —de ``''`` a ``False``,
que es lo que la fuente devuelve—, así que va cubierto por
``tests/unit/base/test_ir_mail_server_from_filter.py``: los mismos 14 casos
pasan antes y después.

Qué NO se porta, con su medición
================================

- **Todo el transporte**: ``_connect__``, ``send_email``, ``_build_email__``,
  ``_prepare_email_message__``, ``_alter_message__``,
  ``_prepare_smtp_to_list``, ``test_smtp_connection``,
  ``action_retrieve_max_email_size``. Aquí el transporte es
  ``django.core.mail`` (ver arriba). Duplicarlo daría dos caminos de salida
  para el mismo correo.
- **Los tres parches globales al import** (líneas 71-99 de la fuente):
  ``smtplib.SMTP._print_debug``, ``smtplib.stderr = WriteToLogger()`` y
  ``email.policy.SMTP = IdentificationFieldsNoFoldPolicy(...)``. Mutan la
  **stdlib para todo el proceso** con sólo importar el módulo. Un archivo de
  modelos que cambia el comportamiento de ``email`` en toda la aplicación es
  una decisión de plataforma, no un detalle de portación, y no se toma de
  rebote aquí. La razón del tercero —no plegar ``Message-ID``, porque plegarlo
  rompe el hilo de conversación— es real y queda anotada para cuando se
  decida dónde vive.
- **``_verify_check_hostname_callback``** (pyOpenSSL): valida que el CN/SAN
  del certificado case el hostname SMTP. Pertenece al conector, que no se
  porta.
- **``groups='base.group_system'``** en ``smtp_user`` / ``smtp_pass`` /
  ``smtp_ssl_certificate`` / ``smtp_ssl_private_key``. En la referencia es una
  restricción **a nivel de campo**: sólo el grupo de sistema los lee. Aquí la
  autorización es por capacidad (DEC-11) y actúa en la vista y el serializer,
  no en la columna. **Esto es una obligación, no una omisión**: el serializer
  que exponga este modelo NO incluye esos cuatro campos en su ``Meta.fields``.
  Queda anotado en el ``help_text`` de cada uno para que se lea desde el
  modelo.
- **``_active_usages_compute``** devuelve ``{}`` en la fuente y está pensado
  para que **otros módulos** lo sobreescriban declarando qué usa cada
  servidor. Se porta con ese contrato —vacío y sobreescribible—, que es
  exactamente lo que la fuente hace; el guardián de archivado que lo consume
  sí se porta completo.

Nombre de la clase — divergencia declarada
==========================================

La referencia llama a la clase ``IrMail_Server``: el guion bajo codifica el
que lleva ``_name = 'ir.mail_server'``. Este árbol no deriva el nombre de
clase del ``_name``, así que ese guion bajo no transporta información y sí
rompe PEP 8. Se porta como ``IrMailServer``.
"""

import datetime
import email.policy
import logging
import re
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import formataddr, make_msgid

import fields
import models
from django.core.exceptions import ValidationError
from exceptions import UserError

from addons.base.models.ir_config_parameter import SystemParameter
from addons.base.models.timestamped_mixin import TimeStampedModel
from orm.domains import Domain
from tools.mail import (
    email_domain_extract,
    email_domain_normalize,
    email_normalize,
    email_normalize_all,
    email_split_and_format,
    encapsulate_email,
    generate_tracking_message_id,
    html2plaintext,
)
from tools import config
from tools.misc import unique
from tools.translate import _

_logger = logging.getLogger(__name__)

#: Segundos de espera de una sesión SMTP (``SMTP_TIMEOUT`` de la fuente).
SMTP_TIMEOUT = 60

#: Clave de ``SystemParameter`` con el tamaño máximo por defecto, en MB.
MAX_EMAIL_SIZE_PARAM = 'base.default_max_email_size'
DEFAULT_MAX_EMAIL_SIZE = 10.0

#: Clave de ``SystemParameter`` con el ``from_filter`` de la config global.
DEFAULT_FROM_FILTER_PARAM = 'mail.default.from_filter'

AUTH_LOGIN = 'login'
AUTH_CERTIFICATE = 'certificate'
AUTH_CLI = 'cli'
#: ``smtp_authentication`` — las tres opciones de la fuente.
AUTHENTICATION_CHOICES = [
    (AUTH_LOGIN, 'Usuario y contraseña'),
    (AUTH_CERTIFICATE, 'Certificado SSL'),
    (AUTH_CLI, 'Interfaz de línea de comandos'),
]

ENCRYPTION_NONE = 'none'
#: ``smtp_encryption`` — las cinco opciones, verbatim de la fuente. Las
#: variantes ``_strict`` son las que **además** validan el certificado del
#: servidor; sin ellas se cifra pero no se autentica al otro extremo.
ENCRYPTION_CHOICES = [
    (ENCRYPTION_NONE, 'Ninguno'),
    ('starttls_strict', 'TLS (STARTTLS), cifrado y validación'),
    ('starttls', 'TLS (STARTTLS), sólo cifrado'),
    ('ssl_strict', 'SSL/TLS, cifrado y validación'),
    ('ssl', 'SSL/TLS, sólo cifrado'),
]

#: Puerto convencional de SSL/TLS dedicado (``_onchange_encryption``).
SSL_PORT = 465

#: ``address_pattern`` de la fuente, verbatim.
_ADDRESS_PATTERN = re.compile(r'([^" ,<@]+@[^>" ,]+)')


class MailDeliveryException(Exception):
    """Error de entrega de correo (``MailDeliveryException`` de la fuente)."""


def is_ascii(text):
    """``is_ascii`` — verbatim de la fuente."""
    return all(ord(cp) < 128 for cp in text)


def extract_rfc2822_addresses(text):
    """Direcciones RFC 2822 válidas dentro de ``text``.

    Ignora las malformadas y las no-ASCII, igual que la fuente. Allá el
    descarte lo produce ``idna.IDNAError`` al formatear; aquí lo produce el
    ``UnicodeEncodeError`` del propio ``formataddr(charset='ascii')``, que es
    el mismo punto de fallo sin añadir la dependencia ``idna``.
    """
    if not text:
        return []
    valid_addresses = []
    for candidate in _ADDRESS_PATTERN.findall(text):
        try:
            valid_addresses.append(
                formataddr(('', candidate), charset='ascii')
            )
        except (UnicodeEncodeError, UnicodeError):
            continue
    return valid_addresses


class IrMailServer(models.BaseModel, TimeStampedModel):
    """``ir.mail_server`` — un servidor SMTP saliente declarado."""

    # ≙ la cabecera de la fuente (``odoo19c: ir_mail_server.py:142-145``).
    _name = 'ir.mail_server'
    _description = 'Mail Server'
    _order = 'sequence, id'
    _allow_sudo_commands = False

    #: Mensajes de la fuente, verbatim (``odoo19c: :147-154``).
    NO_VALID_RECIPIENT = ("At least one valid recipient address should be "
                          "specified for outgoing emails (To/Cc/Bcc)")
    NO_FOUND_FROM = (
        "You must either provide a sender address explicitly or configure "
        "using the combination of `mail.catchall.domain` and "
        "`mail.default.from` ICPs, in the server configuration file or with "
        "the --email-from startup parameter.")
    NO_FOUND_SMTP_FROM = ("The Return-Path or From header is required for "
                          "any outbound email")
    NO_VALID_FROM = ("Malformed 'Return-Path' or 'From' address. It should "
                     "contain one valid plain ASCII email")

    name = fields.Char(max_length=255, db_index=True, verbose_name='Nombre')
    from_filter = fields.Char(
        max_length=512,
        blank=True,
        default='',
        verbose_name='Filtro de remitente',
        help_text=(
            'Lista separada por comas de direcciones o dominios para los '
            'que este servidor puede usarse; p. ej. '
            '"notificaciones@kaupamex.com" o "kaupamex.com". Vacío = '
            'sirve para cualquiera.'
        ),
    )
    smtp_host = fields.Char(
        max_length=255,
        blank=True,
        default='',
        verbose_name='Servidor SMTP',
        help_text='Nombre de host o IP del servidor SMTP.',
    )
    smtp_port = fields.Integer(
        default=25,
        verbose_name='Puerto SMTP',
        help_text='Normalmente 465 para SSL, y 25 o 587 en el resto de casos.',
    )
    smtp_authentication = fields.Selection(
        max_length=16,
        choices=AUTHENTICATION_CHOICES,
        default=AUTH_LOGIN,
        verbose_name='Autenticar con',
    )
    smtp_user = fields.Char(
        max_length=255,
        blank=True,
        default='',
        verbose_name='Usuario',
        help_text=(
            'SECRETO. La referencia lo restringe a nivel de campo con '
            'groups="base.group_system"; aquí NO se expone en el '
            'Meta.fields de ningún serializer.'
        ),
    )
    smtp_pass = fields.Char(
        max_length=255,
        blank=True,
        default='',
        verbose_name='Contraseña',
        help_text=(
            'SECRETO. Mismo criterio que smtp_user: nunca en un serializer.'
        ),
    )
    smtp_encryption = fields.Selection(
        max_length=32,
        choices=ENCRYPTION_CHOICES,
        default=ENCRYPTION_NONE,
        verbose_name='Cifrado de la conexión',
        help_text=(
            'Las variantes "y validación" además autentican al servidor '
            'con su certificado; las de "sólo cifrado" no.'
        ),
    )
    smtp_ssl_certificate = fields.Binary(
        null=True,
        blank=True,
        verbose_name='Certificado SSL',
        help_text=(
            'SECRETO. Certificado usado para autenticar. Nunca en un '
            'serializer.'
        ),
    )
    smtp_ssl_private_key = fields.Binary(
        null=True,
        blank=True,
        verbose_name='Llave privada SSL',
        help_text=(
            'SECRETO. Llave privada usada para autenticar. Nunca en un '
            'serializer.'
        ),
    )
    smtp_debug = fields.Boolean(
        default=False,
        verbose_name='Depuración',
        help_text=(
            'Vuelca la sesión SMTP completa al log en nivel DEBUG. Muy '
            'verboso y puede incluir información confidencial.'
        ),
    )
    max_email_size = fields.Float(
        null=True, blank=True, verbose_name='Tamaño máximo del correo (MB)'
    )
    sequence = fields.Integer(
        default=10,
        verbose_name='Prioridad',
        help_text=(
            'Cuando un correo no pide un servidor concreto se usa el de '
            'mayor prioridad. Número menor = prioridad mayor.'
        ),
    )
    active = fields.Boolean(default=True, verbose_name='Activo')

    class Meta:
        db_table = 'ir_mail_server'
        ordering = ['sequence', 'id']
        verbose_name = 'Servidor de correo saliente'
        verbose_name_plural = 'Servidores de correo saliente'
        constraints = [
            # ``_certificate_requires_tls``: autenticar por certificado exige
            # un transporte TLS — sin él el certificado viaja en claro.
            models.CheckConstraint(
                condition=(
                    ~models.Q(smtp_encryption=ENCRYPTION_NONE)
                    | ~models.Q(smtp_authentication=AUTH_CERTIFICATE)
                ),
                name='ir_mail_server_certificate_requires_tls',
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def smtp_authentication_info(self):
        """``_compute_smtp_authentication_info`` — texto de ayuda del método.

        ``compute`` sin ``store`` en la fuente → propiedad derivada aquí.
        """
        if self.smtp_authentication == AUTH_LOGIN:
            return (
                'Conecta con el usuario y la contraseña habituales. Es el '
                'método más básico y no todos los proveedores lo aceptan.'
            )
        if self.smtp_authentication == AUTH_CERTIFICATE:
            return (
                'Autentica con certificados SSL del dominio. Un certificado '
                'autentica el servidor de correo para todo el nombre de '
                'dominio.'
            )
        if self.smtp_authentication == AUTH_CLI:
            return 'Usa la configuración SMTP global de la plataforma.'
        return ''

    def clean(self):
        """``_check_smtp_ssl_files`` — certificado y llave, o ninguno."""
        super().clean()
        if self.smtp_authentication != AUTH_CERTIFICATE:
            return
        if not self.smtp_ssl_private_key:
            raise ValidationError(
                f'Falta la llave privada SSL de {self.name}.'
            )
        if not self.smtp_ssl_certificate:
            raise ValidationError(f'Falta el certificado SSL de {self.name}.')

    def suggested_port(self):
        """``_onchange_encryption`` — puerto convencional según el cifrado.

        La fuente lo aplica como onchange del formulario; aquí es consulta,
        no efecto: quien edite decide si lo toma.
        """
        return SSL_PORT if self.smtp_encryption == 'ssl' else self.smtp_port

    # --- Guardián de archivado ------------------------------------------

    def _active_usages_compute(self):
        """``_active_usages_compute`` — qué usa este servidor.

        Devuelve ``{}``. **Es el contrato de la fuente**, no un hueco: los
        módulos que envíen por un servidor dedicado sobreescriben este método
        y devuelven ``{id: [descripción, ...]}``. Sin sobreescribirlo, nadie
        declara uso y el archivado no se bloquea.
        """
        return {}

    def write(self, vals):
        """≙ ``write`` (``odoo19c: ir_mail_server.py:231-264``).

        No se archiva un servidor en uso. Con uno solo, el mensaje lo nombra;
        con varios, los ordena por nombre y encabeza los usos de cada uno.
        """
        usages_per_server = {}
        if not vals.get('active', True):
            usages_per_server = self._active_usages_compute()

        if not usages_per_server:
            return super().write(vals)

        usage_details_per_server = {}
        is_multiple_server_usage = len(usages_per_server) > 1
        for server in self:
            if server.id not in usages_per_server:
                continue
            usage_details = []
            if is_multiple_server_usage:
                usage_details.append(str(_(
                    '%s (Dedicated Outgoing Mail Server):',
                    server.display_name)))
            usage_details.extend(
                f'- {usage}' for usage in usages_per_server[server.id])
            usage_details_per_server[server] = usage_details

        servers_ordered_by_name = sorted(
            usage_details_per_server, key=lambda r: r.display_name)
        error_server_usage = ', '.join(
            server.display_name for server in servers_ordered_by_name)
        error_usage_details = '\n'.join(
            line
            for server in servers_ordered_by_name
            for line in usage_details_per_server[server])
        if is_multiple_server_usage:
            raise UserError(_(
                'You cannot archive these Outgoing Mail Servers '
                '(%(server_usage)s) because they are still used in the '
                'following case(s):\n%(usage_details)s',
                server_usage=error_server_usage,
                usage_details=error_usage_details))
        raise UserError(_(
            'You cannot archive this Outgoing Mail Server (%(server_usage)s) '
            'because it is still used in the following case(s):\n'
            '%(usage_details)s',
            server_usage=error_server_usage,
            usage_details=error_usage_details))

    # --- Tamaño y remitentes por defecto --------------------------------

    def _get_max_email_size(self):
        """``_get_max_email_size`` — el del servidor, o el parámetro global."""
        if self.max_email_size:
            return float(self.max_email_size)
        return float(
            SystemParameter.get_param(
                MAX_EMAIL_SIZE_PARAM, str(DEFAULT_MAX_EMAIL_SIZE)
            )
        )

    @staticmethod
    def _get_default_from_address():
        """``_get_default_from_address`` — remitente por defecto.

        La fuente lee el parámetro de arranque ``--email-from``
        (``odoo19c: :656-664``); aquí lo lee ``tools.config.email_from``.
        """
        return config.email_from()

    @classmethod
    def _get_default_from_filter(cls):
        """``_get_default_from_filter`` — el de la config global.

        Primero el parámetro de sistema, luego el valor de arranque; mismo
        orden que la fuente.
        """
        return SystemParameter.get_param(
            DEFAULT_FROM_FILTER_PARAM, config.from_filter())

    def _get_test_email_from(self, fallback_email=''):
        """``_get_test_email_from`` — remitente para la prueba de conexión.

        Toma el primer correo completo del ``from_filter``; si el filtro sólo
        trae dominios, compone ``noreply@<primer dominio>``. La fuente cae al
        correo del usuario actual cuando no hay filtro — aquí ese usuario lo
        aporta el llamador, porque este archivo no conoce el request.
        """
        parts = self._parse_from_filter(self.from_filter)
        email_from = next((part for part in parts if '@' in part), '')
        if not email_from and parts:
            email_from = f'noreply@{parts[0]}'
        if not email_from:
            email_from = fallback_email
        if not email_from or '@' not in email_from:
            raise ValidationError(
                'Configure un correo para simular el envío por este servidor '
                'saliente.'
            )
        return email_from

    # --- Filtro de remitente y selección de servidor --------------------

    @staticmethod
    def _parse_from_filter(from_filter):
        """``_parse_from_filter`` — trocea el filtro y descarta lo vacío."""
        return [
            part.strip()
            for part in (from_filter or '').split(',')
            if part.strip()
        ]

    @classmethod
    def _match_from_filter(cls, email_from, from_filter):
        """``_match_from_filter`` — ¿el remitente casa el filtro?

        Un filtro vacío casa **siempre** — es "sin restricción", no "no casa
        nada". Cada parte se compara como correo completo si trae ``@``, y
        como dominio si no.
        """
        if not from_filter:
            return True
        normalized_from = email_normalize(email_from)
        normalized_domain = email_domain_extract(normalized_from)
        for part in cls._parse_from_filter(from_filter):
            if '@' in part:
                if email_normalize(part) == normalized_from:
                    return True
            elif email_domain_normalize(part) == normalized_domain:
                return True
        return False

    @classmethod
    def _filter_mail_servers_fallback(cls, servers):
        """``_filter_mail_servers_fallback`` — candidatos de respaldo.

        Devuelve todos. Igual que ``_active_usages_compute``, es el contrato
        de la fuente para que otro módulo lo acote, no un hueco.
        """
        return servers

    @classmethod
    def _find_mail_server(
        cls, email_from, servers=None, notifications_email=None
    ):
        """``_find_mail_server`` — servidor **y** remitente a usar.

        Devuelve ``(servidor_o_None, email_from)``. Ver el docstring del
        módulo: el remitente devuelto **cambia según el paso** de la cascada,
        y ésa es la mitad que no se puede omitir.

        ``None`` como servidor significa "usa la configuración global"
        (``EMAIL_*``), que es lo que la fuente expresa como "los argumentos de
        odoo-bin".
        """
        normalized_from = email_normalize(email_from)
        from_domain = email_domain_extract(normalized_from)
        if notifications_email is None:
            notifications_email = email_normalize(
                cls._get_default_from_address()
            )
        notifications_domain = email_domain_extract(notifications_email)

        if servers is None:
            servers = list(cls.objects.order_by('sequence', 'id'))
        # 0. Un servidor archivado nunca se usa.
        servers = [server for server in servers if server.active]

        def first_match(target, normalize):
            if not target:
                return None
            for server in servers:
                if not server.from_filter:
                    continue
                if any(
                    normalize(part) == target
                    for part in cls._parse_from_filter(server.from_filter)
                ):
                    return server
            return None

        # 1-2. Contra el remitente pedido: correo exacto, luego dominio.
        if normalized_from:
            server = first_match(normalized_from, email_normalize)
            if server is not None:
                return server, email_from
            server = first_match(from_domain, email_domain_normalize)
            if server is not None:
                return server, email_from

        servers = cls._filter_mail_servers_fallback(servers)

        # 3. Contra el correo de notificaciones: correo exacto, luego dominio.
        if notifications_email:
            server = first_match(notifications_email, email_normalize)
            if server is not None:
                return server, notifications_email
            server = first_match(notifications_domain, email_domain_normalize)
            if server is not None:
                return server, notifications_email

        # 4. Primer servidor sin filtro: suplanta el remitente, sin más
        # opción.
        unfiltered = [server for server in servers if not server.from_filter]
        if unfiltered:
            return unfiltered[0], notifications_email or email_from

        # 5. Cualquier servidor, aunque esté configurado para otro dominio.
        if servers:
            _logger.warning(
                'Ningún servidor de correo casa el filtro de remitente; se usa'
                ' %s como respaldo.',
                notifications_email or email_from,
            )
            return servers[0], notifications_email or email_from

        # Sin filas: cae a la configuración global.
        from_filter = cls._get_default_from_filter()
        if cls._match_from_filter(email_from, from_filter):
            return None, email_from
        if notifications_email and cls._match_from_filter(
            notifications_email, from_filter
        ):
            return None, notifications_email

        _logger.warning(
            'El filtro de remitente de la configuración global no casa el '
            'correo de notificaciones ni el del usuario; se usa %s como '
            'respaldo.',
            notifications_email or email_from,
        )
        return None, notifications_email or email_from

    def _check_forced_mail_server(self, mail_server, allow_archived,
                                  smtp_from):
        """≙ ``_check_forced_mail_server`` (``odoo19c: :546-548``).

        Un servidor archivado no se fuerza, salvo que se admita.
        """
        if not allow_archived and not mail_server.active:
            raise UserError(_(
                'The server "%s" cannot be used because it is archived.',
                mail_server.display_name))

    @classmethod
    def _get_default_bounce_address(cls):
        """≙ ``_get_default_bounce_address`` (``odoo19c: :646-654``).

        La fuente devuelve el ``email_from`` de arranque, el mismo que lee
        ``_get_default_from_address``.
        """
        return config.email_from()

    @classmethod
    def _find_mail_server_allowed_domain(cls):
        """≙ ``_find_mail_server_allowed_domain`` (``odoo19c: :870-873``).

        Todos los servidores: es el punto que ``mail`` acota a los públicos.
        """
        return Domain.TRUE

    def _build_email__(self, email_from, email_to, subject, body,
                       email_cc=None, email_bcc=None, reply_to=False,
                       attachments=None, message_id=None, references=None,
                       object_id=False, subtype='plain', headers=None,
                       body_alternative=None, subtype_alternative='plain'):
        """≙ ``_build_email__`` (``odoo19c: :562-644``): el mensaje RFC 2822.

        Un cuerpo ``html`` sin alternativa explícita sale como
        ``multipart/alternative`` con su versión en texto plano. Cada adjunto
        es ``(nombre, contenido, mime)``; un ``message/rfc822`` se adjunta
        como mensaje.
        """
        email_from = (email_from
                      or self.env.context.get('domain_notifications_email')
                      or self._get_default_from_address())
        assert email_from, self.NO_FOUND_FROM

        headers = headers or {}
        email_cc = email_cc or []
        email_bcc = email_bcc or []

        msg = EmailMessage(policy=email.policy.SMTP)
        if not message_id:
            if object_id:
                message_id = generate_tracking_message_id(object_id)
            else:
                message_id = make_msgid()
        msg['Message-Id'] = message_id
        if references:
            msg['references'] = references
        msg['Subject'] = subject
        msg['From'] = email_from
        del msg['Reply-To']
        msg['Reply-To'] = reply_to or email_from
        msg['To'] = email_to
        if email_cc:
            msg['Cc'] = email_cc
        if email_bcc:
            msg['Bcc'] = email_bcc
        msg['Date'] = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
        for key, value in headers.items():
            msg[key] = value

        email_body = body or ''
        if subtype == 'html' and not body_alternative:
            msg['MIME-Version'] = '1.0'
            msg.add_alternative(html2plaintext(email_body), subtype='plain',
                                charset='utf-8')
            msg.add_alternative(email_body, subtype=subtype, charset='utf-8')
        elif body_alternative:
            msg['MIME-Version'] = '1.0'
            msg.add_alternative(body_alternative, subtype=subtype_alternative,
                                charset='utf-8')
            msg.add_alternative(email_body, subtype=subtype, charset='utf-8')
        else:
            msg.set_content(email_body, subtype=subtype, charset='utf-8')

        if attachments:
            for (fname, fcontent, mime) in attachments:
                maintype, subtype = (mime.split('/') if mime and '/' in mime
                                     else ('application', 'octet-stream'))
                if maintype == 'message' and subtype == 'rfc822':
                    msg.add_attachment(BytesParser().parsebytes(fcontent),
                                       filename=fname)
                else:
                    msg.add_attachment(fcontent, maintype, subtype,
                                       filename=fname)
        return msg

    def _prepare_email_message__(self, message, smtp_session):
        """≙ ``_prepare_email_message__`` (``odoo19c: :679-733``).

        Devuelve ``(smtp_from, smtp_to_list, message)``. El remitente del
        sobre es la dirección de rebote cuando el filtro del servidor la
        admite, y sólo ASCII.
        """
        bounce_address = (self.env.context.get('domain_bounce_address')
                          or message['Return-Path']
                          or self._get_default_bounce_address()
                          or message['From'])

        smtp_from = message['From'] or bounce_address
        assert smtp_from, self.NO_FOUND_SMTP_FROM

        smtp_to_list = self._prepare_smtp_to_list(message, smtp_session)
        assert smtp_to_list, self.NO_VALID_RECIPIENT

        from_filter = getattr(smtp_session, 'from_filter', False)
        smtp_from = getattr(smtp_session, 'smtp_from', False) or smtp_from
        notifications_email = email_normalize(
            self.env.context.get('domain_notifications_email')
            or self._get_default_from_address()
        )
        if (notifications_email
                and email_normalize(smtp_from) == notifications_email
                and email_normalize(message['From']) != notifications_email):
            smtp_from = encapsulate_email(message['From'],
                                          notifications_email)

        self._alter_message__(message, smtp_from, smtp_to_list)

        if self._match_from_filter(bounce_address, from_filter):
            smtp_from = bounce_address

        smtp_from_rfc2822 = extract_rfc2822_addresses(smtp_from)
        if not smtp_from_rfc2822:
            raise AssertionError(
                self.NO_VALID_FROM,
                f"Malformed 'Return-Path' or 'From' address: {smtp_from} - "
                "It should contain one valid plain ASCII email"
            )
        smtp_from = smtp_from_rfc2822[-1]

        return smtp_from, smtp_to_list, message

    def _alter_message__(self, message, smtp_from, smtp_to_list):
        """≙ ``_alter_message__`` (``odoo19c: :735-762``).

        ``X-Forge-To`` sustituye el ``To``; ``X-Msg-To-Add`` le añade
        destinatarios que no cambian el envío SMTP. El ``From`` pasa a ser
        el del sobre, y salen ``Bcc`` y las cabeceras de control.
        """
        if x_forge_to := message['X-Forge-To']:
            message.replace_header('To', x_forge_to)
        elif x_msg_add_to := message['X-Msg-To-Add']:
            to = message['To'] or ''
            to_normalized = email_normalize_all(to)
            message.replace_header(
                'To', ', '.join([
                    to,
                    ', '.join(
                        address
                        for address in email_split_and_format(x_msg_add_to)
                        if email_normalize(address, strict=False)
                        not in to_normalized
                    ),
                ]))

        if message['From'] != smtp_from:
            message.replace_header('From', smtp_from)

        del message['Bcc']
        del message['X-Forge-To']
        del message['X-Msg-To-Add']
        del message['X-Msg-To-Consolidate']

    def _prepare_smtp_to_list(self, message, smtp_session):
        """≙ ``_prepare_smtp_to_list`` (``odoo19c: :764-797``).

        To, Cc y Bcc, sin repetir dentro de cada cabecera. El contexto puede
        restringir la lista (``send_validated_to``) o excluir direcciones
        (``send_smtp_skip_to``).
        """
        email_to = message['To']
        email_cc = message['Cc']
        email_bcc = message['Bcc']
        validated_to = self.env.context.get('send_validated_to') or []
        skip_to_lst = self.env.context.get('send_smtp_skip_to') or []
        return [
            address
            for base in [email_to, email_cc, email_bcc]
            for address in unique(extract_rfc2822_addresses(base))
            if (
                address and (not validated_to or address in validated_to)
                and email_normalize(address, strict=False) not in skip_to_lst
            )
        ]
