"""``res.device.log`` + ``res.device`` — dispositivos desde los que se abre sesión.

Portación fiel de ``odoo19c: odoo/addons/base/models/res_device.py`` (LGPL-3,
``odoo-tools@622ddc2a``) — atribución y aviso de licencia preservados
(DEC-KX-03).

La referencia declara **dos** modelos y sólo uno es una tabla::

    res_device.py:17   _name = 'res.device.log'
    res_device.py:175  _name = 'res.device'
                       _inherit = ["res.device.log"]
                       _auto = False          ← vista SQL, no tabla

Ambos están portados aquí. ``res.device`` es la **última fila viva por
(usuario, sesión, plataforma, navegador)**: no es un modelo nuevo, es una
proyección del log. En Django el análogo de ``_auto = False`` es
``Meta.managed = False`` sobre una vista creada por migración — que es
exactamente lo que hace la referencia en ``init()`` con ``CREATE or REPLACE
VIEW`` (``res_device.py:250-256``).

El ``_inherit`` de la referencia (herencia por prototipo: "reusa los campos")
se adapta con una **base abstracta**, la forma Django de compartir campos entre
dos modelos concretos con tablas distintas. La FK a usuario se declara en cada
concreto para conservar su propio ``related_name`` (``device_logs`` / ``devices``),
que una base abstracta obligaría a nombrar con ``%(class)s``.

**De dónde viene.** Reemplaza al ``UserSession`` que murió con el addon
``users`` (H-API-119). El modelo de la referencia es más rico que aquél
—``platform``, ``browser``, ``country``, ``city``, ``device_type``,
``revoked``— así que el port no es una mudanza: es lo que ``UserSession``
quería ser.
"""
import logging
from datetime import datetime, timezone

import fields
import models

from addons.base.models.timestamped_mixin import TimeStampedModel
from tools._vendor.useragents import parse_user_agent

_logger = logging.getLogger(__name__)

# ``odoo19c: odoo/http.py:331`` — la referencia guarda sólo el prefijo del sid,
# no el sid completo: un log filtrado no entrega sesiones secuestrables. El
# ``session_key`` de Django mide 32 caracteres, así que el corte es hoy un
# no-op; se conserva porque la garantía es del diseño, no del largo actual.
STORED_SESSION_BYTES = 42

# ``odoo19c: odoo/http.py:1323`` — una fila nueva por dispositivo cada hora, no
# por petición. Sin este umbral el log crecería con el tráfico, no con el uso.
TRACE_MAX_IDLE_SECONDS = 3600

# Clave de la lista de trazas dentro de la sesión (``session['_trace']`` en la
# referencia, ``odoo19c: odoo/http.py:1320``).
TRACE_SESSION_KEY = '_trace'
TRACE_DISABLE_KEY = '_trace_disable'


class _ResDeviceFields(TimeStampedModel):
    """Campos compartidos por ``res.device.log`` y su vista ``res.device``.

    Adaptación del ``_inherit = ["res.device.log"]`` de la referencia
    (``res_device.py:176``). Abstracta: no crea tabla.
    """

    DEVICE_COMPUTER = 'computer'
    DEVICE_MOBILE   = 'mobile'
    DEVICE_TYPES = [
        (DEVICE_COMPUTER, 'Computadora'),
        (DEVICE_MOBILE,   'Móvil'),
    ]

    session_identifier = fields.Char(
        max_length=128, db_index=True,
        help_text='Identificador de la sesión (Odoo session_identifier).',
    )
    platform    = fields.Char(max_length=64,  blank=True, default='')
    browser     = fields.Char(max_length=64,  blank=True, default='')
    ip_address  = fields.Char(max_length=45,  blank=True, default='',
                              help_text='IPv4 o IPv6 (Odoo ip_address).')
    country     = fields.Char(max_length=64,  blank=True, default='')
    city        = fields.Char(max_length=120, blank=True, default='')
    device_type = fields.Selection(
        max_length=16, choices=DEVICE_TYPES, null=True, blank=True,
        help_text='Tipo de dispositivo (Odoo device_type).',
    )
    first_activity = fields.Datetime(null=True, blank=True)
    last_activity  = fields.Datetime(null=True, blank=True, db_index=True)
    revoked        = fields.Boolean(
        default=False,
        help_text='Sesión revocada desde el panel de dispositivos (Odoo revoked).',
    )

    class Meta:
        abstract = True

    # ------------------------------------------------------------------
    # Odoo ``_is_mobile`` (``res_device.py:70-75``)
    # ------------------------------------------------------------------
    MOBILE_PLATFORMS = ('android', 'iphone', 'ipad', 'ipod',
                        'blackberry', 'windows phone', 'webos')

    @classmethod
    def _is_mobile(cls, platform):
        if not platform:
            return False
        return platform.lower() in cls.MOBILE_PLATFORMS

    def __str__(self) -> str:
        return f'{self.browser or "?"} / {self.platform or "?"} ({self.user_id})'


class ResDeviceLog(_ResDeviceFields):
    """``res.device.log`` — una fila por actividad de sesión en un dispositivo.

    Fiel a ``odoo19c: odoo/addons/base/models/res_device.py:17-35``.
    """

    user = fields.Many2one(
        'base.ResUsers', on_delete=models.CASCADE, db_index=True,
        related_name='device_logs',
        help_text='Usuario de la sesión (Odoo user_id).',
    )

    class Meta:
        db_table            = 'res_device_log'
        ordering            = ['-last_activity']
        verbose_name        = 'Registro de dispositivo'
        verbose_name_plural = 'Registros de dispositivo'

    # ------------------------------------------------------------------
    # Productor — Odoo ``_update_device`` (``res_device.py:76-114``)
    # ------------------------------------------------------------------
    @classmethod
    def _update_device(cls, request):
        """Registra la actividad del dispositivo de esta petición.

        Fiel a ``odoo19c: res_device.py:77-114``. La referencia lo invoca desde
        ``check_session`` (``odoo19c: odoo/service/security.py:23,31``), es
        decir **una vez por petición autenticada**; aquí ese punto es
        :class:`DeviceLogMiddleware`, porque nuestro ``service/security.py`` es
        un stub declarado (Django/DRF revalidan la sesión por petición).

        Devuelve la fila creada, o ``None`` si la traza no cambió — mismo
        contrato de "no hagas nada" que el ``if not trace: return`` de la
        fuente.

        **Divergencias declaradas:**

        - La fuente hace ``INSERT`` en SQL crudo para poder abrir un cursor de
          escritura cuando el de la petición es de sólo-lectura
          (``res_device.py:92-97``). Aquí no hay split lectura/escritura
          cableado, así que se usa el ORM.
        - ``country``/``city`` salen de ``GeoIP(ip)`` en la fuente
          (``res_device.py:88``). No hay proveedor GeoIP en esta pila: los
          campos quedan vacíos, no inventados. El día que haya proveedor, es el
          único punto a tocar.
        """
        trace = update_trace(request)
        if not trace:
            return None
        session_key = getattr(request.session, 'session_key', None) or ''
        fila = cls.objects.create(
            session_identifier=session_key[:STORED_SESSION_BYTES],
            platform=trace['platform'] or '',
            browser=trace['browser'] or '',
            ip_address=trace['ip_address'] or '',
            country='',
            city='',
            device_type=(cls.DEVICE_MOBILE if cls._is_mobile(trace['platform'])
                         else cls.DEVICE_COMPUTER),
            user_id=request.user.pk,
            first_activity=_as_datetime(trace['first_activity']),
            last_activity=_as_datetime(trace['last_activity']),
            revoked=False,
        )
        _logger.info('Usuario %s inserta log de dispositivo (%s)',
                     request.user.pk, fila.session_identifier)
        return fila


class ResDevice(_ResDeviceFields):
    """``res.device`` — la última actividad viva por dispositivo (vista SQL).

    Fiel a ``odoo19c: res_device.py:175-256``: ``_auto = False`` + ``init()``
    con ``CREATE or REPLACE VIEW``. Aquí ``Meta.managed = False`` y la vista la
    crea la migración ``base.0004``, que porta el ``_select``/``_from``/
    ``_where`` de la fuente.

    Es de **sólo lectura**: escribir revoca desde ``res.device.log``, que es
    donde vive el dato (la fuente hace lo mismo — su ``_revoke`` escribe sobre
    ``ResDeviceLog``, ``res_device.py:185-190``).
    """

    user = fields.Many2one(
        'base.ResUsers', on_delete=models.DO_NOTHING, db_index=True,
        related_name='devices',
        help_text='Usuario de la sesión (Odoo user_id).',
    )

    class Meta:
        managed             = False
        db_table            = 'res_device'
        ordering            = ['-last_activity']
        verbose_name        = 'Dispositivo'
        verbose_name_plural = 'Dispositivos'

    def is_current(self, request):
        """``is_current`` de la fuente (``res_device.py:59-61``), como método.

        La fuente lo declara ``compute=`` porque su ORM resuelve ``request``
        desde un global; aquí la petición se pasa explícita, que es la forma
        Django de la misma pregunta.
        """
        session_key = getattr(getattr(request, 'session', None), 'session_key', None)
        if not session_key or not self.session_identifier:
            return False
        return session_key.startswith(self.session_identifier)


def _as_datetime(epoch_seconds):
    """Epoch entero (como lo guarda la traza) → ``datetime`` con zona."""
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc)


def update_trace(request):
    """Traza de dispositivo de esta sesión: ``dict`` a insertar, o ``None``.

    Fiel a ``odoo19c: odoo/http.py:1301-1337``. La fuente lo declara como
    método de **su** clase ``Session``; aquí la sesión es la de
    ``django.contrib.sessions`` y no se subclasea, así que la función vive
    junto a su único consumidor — divergencia de ubicación, no de contrato.

    Reglas portadas verbatim:

    - ``_trace_disable`` en la sesión ⇒ no se traza (la fuente lo reserva para
      sesiones técnicas automatizadas; ningún usuario sin privilegio puede
      ponerlo).
    - Una traza existente se reconoce por la terna
      (``platform``, ``browser``, ``ip_address``).
    - Si existe y lleva **menos** de una hora inactiva ⇒ ``None`` (no se
      inserta nada). Si lleva una hora o más ⇒ se refresca ``last_activity`` y
      se devuelve.
    - Si no existe ⇒ se añade con ``first_activity == last_activity``.
    """
    session = getattr(request, 'session', None)
    if session is None or session.get(TRACE_DISABLE_KEY):
        return None

    platform, browser, _version, _language = parse_user_agent(
        request.META.get('HTTP_USER_AGENT', ''))
    ip_address = _client_ip(request)
    ahora = int(datetime.now(tz=timezone.utc).timestamp())

    trazas = session.get(TRACE_SESSION_KEY) or []
    for traza in trazas:
        if (traza.get('platform') == platform
                and traza.get('browser') == browser
                and traza.get('ip_address') == ip_address):
            if ahora - traza['last_activity'] >= TRACE_MAX_IDLE_SECONDS:
                traza['last_activity'] = ahora
                session[TRACE_SESSION_KEY] = trazas
                session.modified = True
                return traza
            return None

    nueva = {
        'platform': platform,
        'browser': browser,
        'ip_address': ip_address,
        'first_activity': ahora,
        'last_activity': ahora,
    }
    trazas.append(nueva)
    session[TRACE_SESSION_KEY] = trazas
    session.modified = True
    return nueva


def _client_ip(request):
    """IP del cliente, honrando el proxy inverso.

    La fuente lee ``request.httprequest.remote_addr``
    (``odoo19c: odoo/http.py:1318``), que werkzeug ya resuelve tras su
    ``ProxyFix``. Aquí el equivalente es leer ``X-Forwarded-For`` primero, el
    mismo criterio que usaba ``observability.middleware`` para ``RequestLog``
    (retirado por DEC-AF-11; el criterio sobrevive aquí y en
    ``observability.audit.extract_ip``).
    """
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[0].strip()[:45]
    return request.META.get('REMOTE_ADDR') or ''


class DeviceLogMiddleware:
    """Invoca ``_update_device`` una vez por petición autenticada.

    Es el análogo de la llamada que la fuente hace desde ``check_session``
    (``odoo19c: odoo/service/security.py:23,31``), no una capa nueva: allí el
    guardián de sesión corre por petición y, tras validarla, registra el
    dispositivo. Nuestro ``service/security.py`` documenta que esa
    revalidación la hacen Django y DRF, así que el registro cuelga de un
    middleware.

    Ubicar DESPUÉS de ``AuthenticationMiddleware`` (necesita ``request.user``)
    y de ``SessionMiddleware`` (necesita ``session_key``). Nunca rompe la
    petición: un fallo al trazar no puede tumbar la respuesta que el usuario
    pidió.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user is not None and getattr(user, 'is_authenticated', False):
            try:
                ResDeviceLog._update_device(request)
            except Exception:  # pragma: no cover - defensa, no contrato
                _logger.exception('No se pudo registrar el dispositivo')
        return self.get_response(request)
