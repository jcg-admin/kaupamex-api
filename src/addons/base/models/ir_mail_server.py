"""``ir.mail_server`` — el registro declarativo de servidores SMTP salientes.

Adaptación de ``odoo/addons/base/models/ir_mail_server.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 991 líneas). Un registro por servidor
SMTP, con su prioridad y —lo que de verdad importa— su ``from_filter``: la
lista de direcciones o dominios para los que ese servidor puede enviar.

Qué añade sobre la configuración global
=======================================

Todo el correo saliente pasa por ``send_email`` de este modelo: la cola de
``mail.mail``, ``dispatch_email`` de ``addons/mail/models/email_executor.py``
y la confirmación de la newsletter. La configuración global ``EMAIL_*`` la
leen los lectores de ``tools.config`` cuando no hay servidor declarado.

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

- **La superficie del modelo que aún diverge** —``smtp_authentication_info``,
  ``_check_smtp_ssl_files`` y ``_onchange_encryption``—: es el paso 3e de
  ``designs/base-ir-mail-server-complete.md``. El transporte está portado
  entero (pasos 3a a 3d) y es el único camino de salida, como en la fuente.
- **Las ramas de versión antigua de los imports** (``:36-56``): la carga de
  PEM con ``OpenSSL.crypto`` para pyOpenSSL < 24.3.0 y
  ``urllib3.packages.ssl_match_hostname`` para urllib3 <= 1.25. Con los
  pisos que ``pyproject.toml`` declara (pyOpenSSL >= 26.2.0, urllib3 >=
  2.7.0) ninguna de las dos se puede ejecutar, así que los imports van sin
  condición: la rama vigente de la fuente, sin el código muerto.
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

import base64
import datetime
import email.policy
import functools
import logging
import re
import smtplib
import ssl
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import make_msgid
from socket import gaierror, timeout

import fields
import idna
import models
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.x509 import load_pem_x509_certificate
from django.core.exceptions import ValidationError
from exceptions import UserError
from OpenSSL.crypto import Error as SSLCryptoError
from OpenSSL.SSL import VERIFY_FAIL_IF_NO_PEER_CERT, VERIFY_PEER
from OpenSSL.SSL import Error as SSLError
from urllib3.contrib.pyopenssl import PyOpenSSLContext, get_subj_alt_name
from urllib3.util.ssl_match_hostname import CertificateError, match_hostname

from addons.base.models.ir_config_parameter import SystemParameter
from addons.base.models.timestamped_mixin import TimeStampedModel
from orm.domains import Domain
from orm.environments import env
from tools.mail import (
    email_domain_extract,
    email_domain_normalize,
    email_normalize,
    email_normalize_all,
    email_split_and_format,
    encapsulate_email,
    formataddr,
    generate_tracking_message_id,
    html2plaintext,
)
from tools import config
from tools.misc import human_size, unique
from tools.translate import _

_logger = logging.getLogger(__name__)
_test_logger = logging.getLogger('odoo.tests')

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


def _print_debug(self, *args):
    """≙ ``_print_debug`` (``odoo19c: :68-71``): la depuración de ``smtplib``
    va al log en DEBUG, no a ``stderr``."""
    _logger.debug(' '.join(str(a) for a in args))


smtplib.SMTP._print_debug = _print_debug

# ≙ ``odoo19c: :73-92`` — rodeo de bpo-35805: no plegar las cabeceras de
# identificación (un MTA reescribe un ``Message-ID`` plegado y el hilo se
# pierde) y plegar las de usuario a 998 columnas en vez de 78.
RFC5322_IDENTIFICATION_HEADERS = {
    'message-id', 'in-reply-to', 'references', 'resent-msg-id'}
USER_DEFINED_HEADERS = {'bcc', 'cc', 'from', 'reply-to', 'subject', 'to'}
_noFoldPolicy = email.policy.SMTP.clone(max_line_length=None)
# rfc5322#section-2.1.1
_maxFoldPolicy = email.policy.SMTP.clone(max_line_length=998)


class IdentificationFieldsNoFoldPolicy(email.policy.EmailPolicy):
    """La política SMTP de la fuente, que la instala para todo el proceso."""

    def _fold(self, name, value, *args, **kwargs):
        if name.lower() in RFC5322_IDENTIFICATION_HEADERS:
            return _noFoldPolicy._fold(name, value, *args, **kwargs)
        if name.lower() in USER_DEFINED_HEADERS:
            return _maxFoldPolicy._fold(name, value, *args, **kwargs)
        return super()._fold(name, value, *args, **kwargs)


# Parche global de la fuente, conservando su ``linesep``.
email.policy.SMTP = IdentificationFieldsNoFoldPolicy(
    linesep=email.policy.SMTP.linesep)


class WriteToLogger:
    """≙ ``WriteToLogger`` (``odoo19c: :94-98``): el ``stderr`` de
    ``smtplib`` escribe en el log."""

    def write(self, s):
        _logger.debug(s)


smtplib.stderr = WriteToLogger()


def is_ascii(text):
    """``is_ascii`` — verbatim de la fuente."""
    return all(ord(cp) < 128 for cp in text)


def extract_rfc2822_addresses(text):
    """≙ ``extract_rfc2822_addresses`` (``odoo19c: :105-119``).

    Docstring de la fuente: *"Returns a list of valid RFC2822 addresses that
    can be found in ``source``, ignoring malformed ones and non-ASCII
    ones."* Un dominio internacional se conserva codificado con ``idna`` por
    el ``formataddr`` de ``tools``; el que ``idna`` no puede codificar se
    descarta.
    """
    if not text:
        return []
    candidates = _ADDRESS_PATTERN.findall(text)
    valid_addresses = []
    for c in candidates:
        try:
            valid_addresses.append(formataddr(('', c), charset='ascii'))
        except idna.IDNAError:
            # silent OK because la fuente descarta la dirección malformada
            pass
    return valid_addresses


def _verify_check_hostname_callback(cnx, x509, err_no, err_depth,
                                    return_code, *, hostname):
    """≙ ``_verify_check_hostname_callback`` (``odoo19c: :122-137``).

    pyOpenSSL sólo mira ``err_no``; además se exige que el ``hostname`` del
    servidor SMTP case el CN o el SAN del certificado hoja.
    """
    if err_no:
        return False

    if err_depth == 0:  # certificado hoja
        peercert = {
            "subject": ((("commonName", x509.get_subject().CN),),),
            "subjectAltName": get_subj_alt_name(x509),
        }
        match_hostname(peercert, hostname)  # lanza si no casa

    return True


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

    def _get_test_email_from(self):
        """≙ ``_get_test_email_from`` (``odoo19c: :280-295``).

        El primer correo completo del ``from_filter``; si el filtro sólo trae
        dominios, ``noreply@<primer dominio>``; sin filtro, el correo del
        usuario actual.
        """
        email_from = False
        if from_filter_parts := self._parse_from_filter(self.from_filter):
            # el primer correo completo de las partes del filtro
            email_from = next(
                (email for email in from_filter_parts if "@" in email), False)
            # sin correo completo -> noreply
            if not email_from:
                email_from = f"noreply@{from_filter_parts[0]}"
        if not email_from:
            # Sin filtro: el correo del usuario actual
            email_from = self.env.user.email
        if not email_from or "@" not in email_from:
            raise UserError(_(
                'Please configure an email on the current user to simulate '
                'sending an email message via this outgoing server'))
        return email_from

    def _get_test_email_to(self):
        """≙ ``_get_test_email_to`` (``odoo19c: :297-298``), verbatim."""
        return "noreply@odoo.com"

    def test_smtp_connection(self, autodetect_max_email_size=False):
        """≙ ``test_smtp_connection`` (``odoo19c: :300-382``).

        Simula un envío sin enviarlo: ``MAIL FROM``, ``RCPT TO`` y el inicio
        de ``DATA``. Con ``autodetect_max_email_size`` guarda además el tamaño
        máximo que anuncia el servidor; la fuente lo asigna al campo, que en
        su ORM escribe, y aquí se escribe con ``write``.
        """
        for server in self:
            smtp = False
            try:
                # simular un envío desde el correo del usuario, sin enviarlo
                email_from = server._get_test_email_from()
                email_to = server._get_test_email_to()
                smtp = self._connect__(
                    mail_server_id=server.id, allow_archived=True,
                    smtp_from=email_from)
                # MAIL FROM detecta problemas del filtro de remitente
                (code, repl) = smtp.mail(email_from)
                if code != 250:
                    raise UserError(_(
                        'The server refused the sender address '
                        '(%(email_from)s) with error %(repl)s',
                        email_from=email_from, repl=repl))
                # RCPT TO detecta la mayoría de los problemas de relevo
                (code, repl) = smtp.rcpt(email_to)
                if code not in (250, 251):
                    raise UserError(_(
                        'The server refused the test recipient '
                        '(%(email_to)s) with error %(repl)s',
                        email_to=email_to, repl=repl))
                # Iniciar DATA detecta algunos rechazos diferidos; data()
                # enviaría el correo de verdad
                smtp.putcmd("data")
                (code, repl) = smtp.getreply()
                if code != 354:
                    raise UserError(_(
                        'The server refused the test connection with error '
                        '%(repl)s', repl=repl))
                if autodetect_max_email_size:
                    max_size = smtp.esmtp_features.get('size')
                    if not max_size:
                        raise UserError(_(
                            'The server "%(server_name)s" doesn\'t return '
                            'the maximum email size.',
                            server_name=server.name))
                    server.write(
                        {'max_email_size': float(max_size) / (1024 ** 2)})
            except (UnicodeError, idna.core.InvalidCodepoint) as e:
                raise UserError(_("Invalid server name!\n %s", e)) from e
            except (gaierror, timeout) as e:
                raise UserError(_(
                    "No response received. Check server address and port "
                    "number.\n %s", e)) from e
            except smtplib.SMTPServerDisconnected as e:
                raise UserError(_(
                    "The server has closed the connection unexpectedly. "
                    "Check configuration served on this port number.\n %s",
                    e)) from e
            except smtplib.SMTPResponseException as e:
                raise UserError(_(
                    "Server replied with following exception:\n %s",
                    e)) from e
            except smtplib.SMTPNotSupportedError as e:
                raise UserError(_(
                    "An option is not supported by the server:\n %s",
                    e)) from e
            except smtplib.SMTPException as e:
                raise UserError(_(
                    "An SMTP exception occurred. Check port number and "
                    "connection security type.\n %s", e)) from e
            except CertificateError as e:
                raise UserError(_(
                    "An SSL exception occurred. Check connection security "
                    "type.\n CertificateError: %s", e)) from e
            except (ssl.SSLError, SSLError) as e:
                raise UserError(_(
                    "An SSL exception occurred. Check connection security "
                    "type.\n %s", e)) from e
            except UserError:
                raise
            except Exception as e:
                _logger.warning(
                    "Connection test on %s failed with a generic error.",
                    server, exc_info=True)
                raise UserError(_(
                    "Connection Test Failed! Here is what we got instead:"
                    "\n %s", e)) from e
            finally:
                try:
                    if smtp:
                        smtp.close()
                except Exception:
                    # silent OK because es consecuencia de la excepción
                    # anterior, que es la que se informa
                    pass

        if autodetect_max_email_size:
            message = _(
                'Email maximum size updated (%(details)s).',
                details=', '.join(
                    f'{server.name}: '
                    f'{human_size(server.max_email_size * 1024 ** 2)}'
                    for server in self))
        else:
            message = _('Connection Test Successful!')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': message,
                'type': 'success',
                'sticky': False,
                # fuerza recargar el formulario
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def action_retrieve_max_email_size(self):
        """≙ ``action_retrieve_max_email_size`` (``odoo19c: :384-386``)."""
        self.ensure_one()
        return self.test_smtp_connection(autodetect_max_email_size=True)

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

    @classmethod
    def _disable_send(cls):
        """≙ ``_disable_send`` (``odoo19c: :388-392``): sin envío bajo
        pruebas ni mientras el registro se inicializa.

        ``modules.module.current_test`` es ``tools.config.test_enable()``
        aquí, y ``pool._init`` es ``Registry._init`` de la base del entorno.
        """
        return config.test_enable() or env().registry._init

    def _connect__(self, host=None, port=None, user=None, password=None,
                   encryption=None, smtp_from=None, ssl_certificate=None,
                   ssl_private_key=None, smtp_debug=False,
                   mail_server_id=None, allow_archived=False):
        """≙ ``_connect__`` (``odoo19c: :394-534``): una conexión SMTP nueva.

        Bajo pruebas no conecta y devuelve ``None``. Con ``mail_server_id``
        usa ese servidor; sin ``host`` busca el servidor por remitente; y sin
        servidor —o con autenticación ``cli``— toma los parámetros dados o los
        de ``tools.config``.
        """
        # No conectar en modo de prueba
        if self._disable_send():
            return None
        mail_server = smtp_encryption = None
        if mail_server_id:
            mail_server = self.sudo().browse(mail_server_id)
            self._check_forced_mail_server(
                mail_server, allow_archived, smtp_from)

        elif not host:
            mail_server, smtp_from = self.sudo()._find_mail_server(smtp_from)

        if not mail_server:
            mail_server = self.env['ir.mail_server']
        ssl_context = None

        if mail_server and mail_server.smtp_authentication != "cli":
            smtp_server = mail_server.smtp_host
            smtp_port = mail_server.smtp_port
            if mail_server.smtp_authentication == "certificate":
                smtp_user = None
                smtp_password = None
            else:
                smtp_user = mail_server.smtp_user
                smtp_password = mail_server.smtp_pass
            smtp_encryption = mail_server.smtp_encryption
            smtp_debug = smtp_debug or mail_server.smtp_debug
            from_filter = mail_server.from_filter

            if mail_server.smtp_authentication == "certificate":
                try:
                    ssl_context = PyOpenSSLContext(ssl.PROTOCOL_TLS)
                    if mail_server.smtp_encryption in (
                            'ssl_strict', 'starttls_strict'):
                        ssl_context.set_default_verify_paths()
                        ssl_context._ctx.set_verify(
                            VERIFY_PEER | VERIFY_FAIL_IF_NO_PEER_CERT,
                            functools.partial(
                                _verify_check_hostname_callback,
                                hostname=smtp_server)
                        )
                    else:  # ssl, starttls
                        ssl_context.verify_mode = ssl.CERT_NONE
                    ssl_context._ctx.use_certificate(
                        load_pem_x509_certificate(
                            base64.b64decode(
                                mail_server.smtp_ssl_certificate)))
                    ssl_context._ctx.use_privatekey(load_pem_private_key(
                        base64.b64decode(mail_server.smtp_ssl_private_key),
                        password=None))
                    # La llave privada tiene que casar el certificado
                    ssl_context._ctx.check_privatekey()
                except SSLCryptoError as e:
                    raise UserError(_(
                        'The private key or the certificate is not a valid'
                        ' file. \n%s', str(e)))
                except SSLError as e:
                    raise UserError(_(
                        'Could not load your certificate / private key.'
                        ' \n%s', str(e)))
            elif mail_server.smtp_encryption != 'none':
                if mail_server.smtp_encryption in (
                        'ssl_strict', 'starttls_strict'):
                    ssl_context = ssl.create_default_context()
                    ssl_context.check_hostname = True
                    ssl_context.verify_mode = ssl.CERT_REQUIRED
                else:  # ssl, starttls
                    ssl_context = ssl.create_default_context()
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE

        else:
            # Parámetros sueltos, o ninguno y sin servidor por defecto
            smtp_server = host or config.smtp_server()
            smtp_port = config.smtp_port() if port is None else port
            smtp_user = user or config.smtp_user()
            smtp_password = password or config.smtp_password()
            if mail_server:
                from_filter = mail_server.from_filter
            else:
                from_filter = self.env[
                    'ir.mail_server']._get_default_from_filter()

            smtp_encryption = encryption
            if smtp_encryption is None and config.smtp_ssl():
                smtp_encryption = 'starttls'  # smtp_ssl => STARTTLS desde v7
            smtp_ssl_certificate_filename = (
                ssl_certificate or config.smtp_ssl_certificate_filename())
            smtp_ssl_private_key_filename = (
                ssl_private_key or config.smtp_ssl_private_key_filename())

            if (smtp_ssl_certificate_filename
                    and smtp_ssl_private_key_filename):
                try:
                    ssl_context = PyOpenSSLContext(ssl.PROTOCOL_TLS)
                    ssl_context.verify_mode = ssl.CERT_NONE
                    ssl_context.load_cert_chain(
                        smtp_ssl_certificate_filename,
                        keyfile=smtp_ssl_private_key_filename)
                    # La llave privada tiene que casar el certificado
                    ssl_context._ctx.check_privatekey()
                except SSLCryptoError as e:
                    raise UserError(_(
                        'The private key or the certificate is not a valid'
                        ' file. \n%s', str(e)))
                except SSLError as e:
                    raise UserError(_(
                        'Could not load your certificate / private key.'
                        ' \n%s', str(e)))

        if not smtp_server:
            raise UserError(_(
                "Missing SMTP Server\n"
                "Please define at least one SMTP server, "
                "or provide the SMTP parameters explicitly.",
            ))

        if smtp_encryption in ('ssl', 'ssl_strict'):
            connection = smtplib.SMTP_SSL(
                smtp_server, smtp_port, timeout=SMTP_TIMEOUT,
                context=ssl_context)
        else:
            connection = smtplib.SMTP(
                smtp_server, smtp_port, timeout=SMTP_TIMEOUT)
        connection.set_debuglevel(smtp_debug)
        if smtp_encryption in ('starttls', 'starttls_strict'):
            # starttls() hace ehlo() si hace falta y descarta la lista de
            # servicios previa (RFC 3207): una capacidad AUTH que sólo
            # aparece sobre el canal cifrado se detecta en el paso siguiente.
            connection.starttls(context=ssl_context)

        if smtp_user:
            # Autenticar; lanza si el servidor no ofrece AUTH
            local, at, domain = smtp_user.rpartition('@')
            if at:
                smtp_user = local + at + idna.encode(domain).decode('ascii')
            mail_server._smtp_login__(
                connection, smtp_user, smtp_password or '')

        # Algunos métodos de SMTP no comprueban si EHLO/HELO se envió; como
        # login() pudo enviarlo, el resto lo da por enviado.
        connection.ehlo_or_helo_if_needed()

        # El ``from_filter`` del servidor o de la config, para decidir al
        # preparar el mensaje si hay que cambiar el FROM.
        connection.from_filter = from_filter
        connection.smtp_from = smtp_from

        return connection

    def _check_forced_mail_server(self, mail_server, allow_archived,
                                  smtp_from):
        """≙ ``_check_forced_mail_server`` (``odoo19c: :546-548``).

        Un servidor archivado no se fuerza, salvo que se admita.
        """
        if not allow_archived and not mail_server.active:
            raise UserError(_(
                'The server "%s" cannot be used because it is archived.',
                mail_server.display_name))

    def _smtp_login__(self, connection, smtp_user, smtp_password):
        """≙ ``_smtp_login__`` (``odoo19c: :541-551``): autentica la
        conexión. Otros módulos lo sobreescriben con otro método de
        autenticación; se llama sobre el modelo o sobre un registro."""
        connection.login(smtp_user, smtp_password)

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

    def send_email(self, message, mail_server_id=None, smtp_server=None,
                   smtp_port=None, smtp_user=None, smtp_password=None,
                   smtp_encryption=None, smtp_ssl_certificate=None,
                   smtp_ssl_private_key=None, smtp_debug=False,
                   smtp_session=None):
        """≙ ``send_email`` (``odoo19c: :798-868``): envía sin cola.

        Sin reintentos: quien llama atiende ``MailDeliveryException`` para
        que el correo no se pierda. ``smtp_session``, si se da, sustituye a
        ``mail_server_id`` y a los ``smtp_*``, y quien llama la cierra.
        Devuelve el ``Message-Id`` del mensaje enviado.
        """
        smtp = smtp_session
        if not smtp:
            smtp = self._connect__(
                smtp_server, smtp_port, smtp_user, smtp_password,
                smtp_encryption, smtp_from=message['From'],
                ssl_certificate=smtp_ssl_certificate,
                ssl_private_key=smtp_ssl_private_key,
                smtp_debug=smtp_debug, mail_server_id=mail_server_id,)

        smtp_from, smtp_to_list, message = self._prepare_email_message__(
            message, smtp)

        # ¡No enviar en modo de prueba!
        if self._disable_send():
            _test_logger.debug("skip sending email in test mode")
            return message['Message-Id']

        try:
            message_id = message['Message-Id']

            smtp.send_message(message, smtp_from, smtp_to_list)

            # una smtp_session ya abierta no se cierra aquí
            if not smtp_session:
                smtp.quit()
        except smtplib.SMTPServerDisconnected:
            raise
        except Exception as e:
            msg = _(
                "Mail delivery failed via SMTP server '%(server)s'.\n"
                "%(exception_name)s: %(message)s",
                server=smtp_server,
                exception_name=e.__class__.__name__,
                message=e,
            )
            _logger.info(msg)
            raise MailDeliveryException(_("Mail Delivery Failed"), msg)
        return message_id
