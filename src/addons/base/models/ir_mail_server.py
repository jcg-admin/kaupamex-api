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
import logging
import re
from email.utils import formataddr

import fields
import models
from django.conf import settings
from django.core.exceptions import ValidationError

from addons.base.models.ir_config_parameter import SystemParameter
from addons.base.models.timestamped_mixin import TimeStampedModel
from tools.mail import (
    email_domain_extract,
    email_domain_normalize,
    email_normalize,
)

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
            valid_addresses.append(formataddr(('', candidate), charset='ascii'))
        except (UnicodeEncodeError, UnicodeError):
            continue
    return valid_addresses


class IrMailServer(TimeStampedModel):
    """``ir.mail_server`` — un servidor SMTP saliente declarado."""

    #: Mensajes de la fuente, en extenso para que se exporten como términos.
    NO_VALID_RECIPIENT = (
        'Debe especificarse al menos un destinatario válido para el correo '
        'saliente (Para/CC/CCO).'
    )
    NO_FOUND_FROM = (
        'Debe indicar un remitente explícito o configurar el remitente por '
        'defecto de la plataforma.'
    )
    NO_FOUND_SMTP_FROM = (
        'La cabecera Return-Path o From es obligatoria en todo correo saliente.'
    )
    NO_VALID_FROM = (
        'Dirección Return-Path o From malformada: debe contener un correo '
        'ASCII válido.'
    )

    name = fields.Char(max_length=255, db_index=True, verbose_name='Nombre')
    from_filter = fields.Char(
        max_length=512, blank=True, default='', verbose_name='Filtro de remitente',
        help_text='Lista separada por comas de direcciones o dominios para los '
                  'que este servidor puede usarse; p. ej. '
                  '"notificaciones@kaupamex.com" o "kaupamex.com". Vacío = '
                  'sirve para cualquiera.',
    )
    smtp_host = fields.Char(
        max_length=255, blank=True, default='', verbose_name='Servidor SMTP',
        help_text='Nombre de host o IP del servidor SMTP.')
    smtp_port = fields.Integer(
        default=25, verbose_name='Puerto SMTP',
        help_text='Normalmente 465 para SSL, y 25 o 587 en el resto de casos.')
    smtp_authentication = fields.Selection(
        max_length=16, choices=AUTHENTICATION_CHOICES, default=AUTH_LOGIN,
        verbose_name='Autenticar con')
    smtp_user = fields.Char(
        max_length=255, blank=True, default='', verbose_name='Usuario',
        help_text='SECRETO. La referencia lo restringe a nivel de campo con '
                  'groups="base.group_system"; aquí NO se expone en el '
                  'Meta.fields de ningún serializer.',
    )
    smtp_pass = fields.Char(
        max_length=255, blank=True, default='', verbose_name='Contraseña',
        help_text='SECRETO. Mismo criterio que smtp_user: nunca en un '
                  'serializer.',
    )
    smtp_encryption = fields.Selection(
        max_length=32, choices=ENCRYPTION_CHOICES, default=ENCRYPTION_NONE,
        verbose_name='Cifrado de la conexión',
        help_text='Las variantes "y validación" además autentican al servidor '
                  'con su certificado; las de "sólo cifrado" no.',
    )
    smtp_ssl_certificate = fields.Binary(
        null=True, blank=True, verbose_name='Certificado SSL',
        help_text='SECRETO. Certificado usado para autenticar. Nunca en un '
                  'serializer.',
    )
    smtp_ssl_private_key = fields.Binary(
        null=True, blank=True, verbose_name='Llave privada SSL',
        help_text='SECRETO. Llave privada usada para autenticar. Nunca en un '
                  'serializer.',
    )
    smtp_debug = fields.Boolean(
        default=False, verbose_name='Depuración',
        help_text='Vuelca la sesión SMTP completa al log en nivel DEBUG. Muy '
                  'verboso y puede incluir información confidencial.',
    )
    max_email_size = fields.Float(
        null=True, blank=True, verbose_name='Tamaño máximo del correo (MB)')
    sequence = fields.Integer(
        default=10, verbose_name='Prioridad',
        help_text='Cuando un correo no pide un servidor concreto se usa el de '
                  'mayor prioridad. Número menor = prioridad mayor.',
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
                f'Falta la llave privada SSL de {self.name}.')
        if not self.smtp_ssl_certificate:
            raise ValidationError(
                f'Falta el certificado SSL de {self.name}.')

    def suggested_port(self):
        """``_onchange_encryption`` — puerto convencional según el cifrado.

        La fuente lo aplica como onchange del formulario; aquí es consulta,
        no efecto: quien edite decide si lo toma.
        """
        return SSL_PORT if self.smtp_encryption == 'ssl' else self.smtp_port

    # --- Guardián de archivado ------------------------------------------

    def active_usages(self):
        """``_active_usages_compute`` — qué usa este servidor.

        Devuelve ``{}``. **Es el contrato de la fuente**, no un hueco: los
        módulos que envíen por un servidor dedicado sobreescriben este método
        y devuelven ``{id: [descripción, ...]}``. Sin sobreescribirlo, nadie
        declara uso y el archivado no se bloquea.
        """
        return {}

    def check_can_archive(self):
        """``write`` de la fuente — no se archiva un servidor en uso.

        La fuente distingue el mensaje de **uno** y el de **varios**; se
        conserva la distinción porque el plural nombra los servidores y el
        singular no, y perderla deja al operador sin saber cuál desarchivar.
        """
        usages = self.active_usages()
        detail = usages.get(self.pk)
        if not detail:
            return
        lines = '\n'.join(f'- {item}' for item in detail)
        raise ValidationError(
            f'No se puede archivar el servidor de correo saliente '
            f'({self.name}) porque sigue en uso en:\n{lines}'
        )

    @classmethod
    def check_can_archive_many(cls, servers):
        """Variante en plural de ``check_can_archive``.

        Ordena por nombre antes de componer el mensaje, igual que la fuente
        (``sorted(..., key=lambda r: r.display_name)``): sin ese orden el
        mismo conjunto produce mensajes distintos en cada llamada.
        """
        blocked = {}
        for server in servers:
            detail = server.active_usages().get(server.pk)
            if detail:
                blocked[server] = detail
        if not blocked:
            return
        ordered = sorted(blocked, key=lambda server: server.name)
        if len(ordered) == 1:
            ordered[0].check_can_archive()
            return
        names = ', '.join(server.name for server in ordered)
        lines = '\n'.join(
            line
            for server in ordered
            for line in [f'{server.name} (servidor dedicado):']
            + [f'- {item}' for item in blocked[server]]
        )
        raise ValidationError(
            f'No se pueden archivar estos servidores de correo saliente '
            f'({names}) porque siguen en uso en:\n{lines}'
        )

    # --- Tamaño y remitentes por defecto --------------------------------

    def get_max_email_size(self):
        """``_get_max_email_size`` — el del servidor, o el parámetro global."""
        if self.max_email_size:
            return float(self.max_email_size)
        return float(SystemParameter.get_param(
            MAX_EMAIL_SIZE_PARAM, str(DEFAULT_MAX_EMAIL_SIZE)))

    @staticmethod
    def get_default_from_address():
        """``_get_default_from_address`` — remitente por defecto.

        La fuente lee el parámetro de arranque ``--email-from``; el
        equivalente de este árbol es ``settings.DEFAULT_FROM_EMAIL``
        (``config/settings/base.py:244``).
        """
        return getattr(settings, 'DEFAULT_FROM_EMAIL', '') or ''

    @classmethod
    def get_default_from_filter(cls):
        """``_get_default_from_filter`` — el de la config global.

        Primero el parámetro de sistema, luego el valor de arranque; mismo
        orden que la fuente.
        """
        return SystemParameter.get_param(DEFAULT_FROM_FILTER_PARAM, '') or ''

    def get_test_email_from(self, fallback_email=''):
        """``_get_test_email_from`` — remitente para la prueba de conexión.

        Toma el primer correo completo del ``from_filter``; si el filtro sólo
        trae dominios, compone ``noreply@<primer dominio>``. La fuente cae al
        correo del usuario actual cuando no hay filtro — aquí ese usuario lo
        aporta el llamador, porque este archivo no conoce el request.
        """
        parts = self.parse_from_filter(self.from_filter)
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
    def parse_from_filter(from_filter):
        """``_parse_from_filter`` — trocea el filtro y descarta lo vacío."""
        return [
            part.strip() for part in (from_filter or '').split(',')
            if part.strip()
        ]

    @classmethod
    def match_from_filter(cls, email_from, from_filter):
        """``_match_from_filter`` — ¿el remitente casa el filtro?

        Un filtro vacío casa **siempre** — es "sin restricción", no "no casa
        nada". Cada parte se compara como correo completo si trae ``@``, y
        como dominio si no.
        """
        if not from_filter:
            return True
        normalized_from = email_normalize(email_from)
        normalized_domain = email_domain_extract(normalized_from)
        for part in cls.parse_from_filter(from_filter):
            if '@' in part:
                if email_normalize(part) == normalized_from:
                    return True
            elif email_domain_normalize(part) == normalized_domain:
                return True
        return False

    @classmethod
    def filter_servers_fallback(cls, servers):
        """``_filter_mail_servers_fallback`` — candidatos de respaldo.

        Devuelve todos. Igual que ``active_usages``, es el contrato de la
        fuente para que otro módulo lo acote, no un hueco.
        """
        return servers

    @classmethod
    def find_mail_server(cls, email_from, servers=None, notifications_email=None):
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
            notifications_email = email_normalize(cls.get_default_from_address())
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
                if any(normalize(part) == target
                       for part in cls.parse_from_filter(server.from_filter)):
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

        servers = cls.filter_servers_fallback(servers)

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
                'Ningún servidor de correo casa el filtro de remitente; se usa '
                '%s como respaldo.', notifications_email or email_from)
            return servers[0], notifications_email or email_from

        # Sin filas: cae a la configuración global.
        from_filter = cls.get_default_from_filter()
        if cls.match_from_filter(email_from, from_filter):
            return None, email_from
        if notifications_email and cls.match_from_filter(
                notifications_email, from_filter):
            return None, notifications_email

        _logger.warning(
            'El filtro de remitente de la configuración global no casa el '
            'correo de notificaciones ni el del usuario; se usa %s como '
            'respaldo.', notifications_email or email_from)
        return None, notifications_email or email_from
