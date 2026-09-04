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

Cobertura del porte — 15 métodos de la referencia, los 15 con contraparte
=========================================================================

Este archivo se presentaba como *"portación fiel"* desde su primer pase y
**no lo era**: medido por AST contra la fuente, entregaba 4 de sus 15 métodos.
El conteo de líneas ya lo decía —237 allá contra 323 aquí, y las nuestras de
más son ``update_trace`` y el middleware, que allá viven en ``http.py``— y
nadie lo comparó. Es el defecto que ``porte-completo-no-parcial.md`` describe:
un porte parcial presentado como porte sale de la lista de pendientes.

La frase se corrige aquí porque el porte ya está cerrado: los 15 tienen
contraparte, y los que cambian de forma la declaran (tarea #71).

*Portados aquí — 8:* ``_is_mobile``, ``_update_device``,
``_compute_display_name`` (como ``__str__``, que es el ``display_name`` de
Django), ``_revoke`` (tarea #69), ``_compute_linked_ip_addresses``,
``_gc_device_log`` y ``__update_revoked`` (tarea #71 — los dos últimos con su
``@api.autovacuum``, que el colector ``ir.autovacuum`` ya recorre).

*Portados con su forma cambiada, declarada — 7:*

- ``revoke`` (``:182-184``) y ``action_revoke_all_devices``: el par
  público-con-``@check_identity`` / interno-sin-él colapsa en **un** cuerpo,
  porque aquí la identidad fresca la exige ``authz_reauth
  .assert_session_fresh`` desde la vista (DEC-12). Misma resolución que
  ``authz_totp.revoke_all_devices``.
- ``_compute_is_current`` → :meth:`ResDevice.is_current`, con la petición
  explícita en vez de leída de un global.
- ``_select``, ``_from``, ``_where``, ``_query`` e ``init`` (``:198-256``) →
  la migración ``base.0004_resdevice``, que es donde vive el ``CREATE OR
  REPLACE VIEW``. Divergencia de **ubicación**: en la referencia el modelo
  crea su propia vista al cargar; en Django el DDL es de la migración.
- ``_order_field_to_sql`` (``:65-68``) →
  :meth:`ResDeviceQuerySet.order_by_is_current`. La fuente engancha el ORM y
  con eso cualquier consulta que pida ``order='is_current'`` obtiene ese SQL;
  Django no tiene
  punto de extensión de campo-a-SQL en el orden, así que la misma capacidad se
  expone como método explícito del recordset.

*Trabajo pendiente — 0.*

Dos piezas que la referencia obtiene de su almacén de sesiones se construyen
aquí como funciones de módulo, porque ``django.contrib.sessions`` no se
subclasea: :func:`delete_sessions_from_identifiers` (la que borra) y
:func:`get_missing_session_identifiers` (la que pregunta cuáles faltan). Las
dos comparten la misma restricción declarada — el log guarda un **prefijo** de
la clave, así que sólo un almacén consultable por prefijo responde.
"""
import importlib
import logging
from datetime import datetime, timedelta, timezone

import api
import fields
import models

from addons.base.models.ir_http import get_current_request
from addons.base.models.timestamped_mixin import TimeStampedModel
from django.apps import apps
from django.conf import settings
from django.contrib.auth import logout as django_logout
from django.contrib.postgres.aggregates import ArrayAgg
from orm.environments import get_context
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
        """≙ ``_compute_display_name`` (``odoo19c: res_device.py:39-43``).

        La fuente lo declara ``compute`` sobre el campo ``display_name`` que su
        ORM da a todo modelo; en Django ese campo es ``__str__``. El cuerpo se
        porta verbatim, respaldo ``"Unknown"`` incluido — decía
        ``browser / platform (user)``, que ni es el formato de la fuente ni
        cae en su respaldo cuando el navegador es desconocido.
        """
        platform = self.platform or 'Unknown'
        browser = self.browser or 'Unknown'
        return f'{platform.capitalize()} {browser.capitalize()}'

    # ------------------------------------------------------------------
    # Odoo ``_compute_linked_ip_addresses`` (``res_device.py:50-63``)
    # ------------------------------------------------------------------
    @classmethod
    def _linked_ip_addresses_map(cls, devices):
        """Las IP de cada dispositivo, en **una** consulta agrupada.

        Es el ``_read_group`` de la fuente (``res_device.py:52-58``): agrupa
        el log por (sesión, plataforma, navegador) y agrega ``ip_address``
        con ``array_agg``. Aquí ese agregado es
        ``django.contrib.postgres.aggregates.ArrayAgg`` sobre un
        ``values(...).annotate(...)``, que emite el mismo ``GROUP BY``.

        Se declara aparte —y en plural— porque la fuente **no** consulta una
        vez por dispositivo: el ``compute`` recibe el recordset entero y hace
        una sola consulta. Un método de instancia que consultara por su cuenta
        sería N+1 con el mismo resultado.

        :returns: ``{(sesión, plataforma, navegador): [ip, ...]}``, con las IP
            en el orden en que el log las registró.
        """
        log = apps.get_model('base', 'ResDeviceLog')
        identifiers = [d.session_identifier for d in devices if d.session_identifier]
        if not identifiers:
            return {}
        rows = (log.objects
                 .filter(session_identifier__in=identifiers)
                 .values('session_identifier', 'platform', 'browser')
                 .annotate(ips=ArrayAgg('ip_address', order_by='id')))
        return {
            (f['session_identifier'], f['platform'], f['browser']): f['ips']
            for f in rows
        }

    def _compute_linked_ip_addresses(self, ip_map=None):
        """≙ ``_compute_linked_ip_addresses`` (``odoo19c: res_device.py:50-63``).

        Desde cuántas IP se usó **este** dispositivo, una por línea. El
        ``OrderedSet`` de la fuente (``:60``) es aquí ``dict.fromkeys``, que
        deduplica conservando el orden de aparición.

        :param ip_map: el mapa de :meth:`_linked_ip_addresses_map` cuando ya
            se calculó para un conjunto — es la vía sin N+1. Sin él se calcula
            para este dispositivo solo.
        """
        if ip_map is None:
            ip_map = self._linked_ip_addresses_map([self])
        key = (self.session_identifier, self.platform, self.browser)
        return '\n'.join(dict.fromkeys(ip_map.get(key, [])))


class ResDeviceLog(_ResDeviceFields):
    """``res.device.log`` — una fila por actividad de sesión en un dispositivo.

    Fiel a ``odoo19c: odoo/addons/base/models/res_device.py:17-35``.
    """

    # Atributos de clase de modelo — los tres de ORM que la referencia declara
    # (``odoo19c: res_device.py:17-19``), verbatim. Los otros dos que lleva su
    # cabecera —``_composite_idx`` y ``_revoked_idx``— NO son atributos de ORM
    # sino **objetos de tabla**; su hogar es ``Meta.indexes``, abajo, con el
    # nombre de la referencia conservado (tarea #70).
    _name = 'res.device.log'
    _description = 'Device Log'
    _rec_names_search = ['platform', 'browser']

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
        # ≙ los dos objetos de tabla de la cabecera de la referencia
        # (``odoo19c: res_device.py:37-38``). Son **parciales**: la condición
        # ``WHERE revoked IS NOT TRUE`` es lo que los hace baratos — el índice
        # sólo cubre las sesiones vivas, que es lo único que la vista
        # ``res.device`` consulta (ver ``migrations/0004_resdevice.py``).
        #
        # El nombre de la fuente se conserva, como manda
        # ``atributos-de-clase-de-modelo.md`` para un objeto de tabla portado.
        # PostgreSQL corta a 63 caracteres, así que los dos van sin prefijo.
        #
        # ``~Q(revoked=True)`` y no ``Q(revoked=False)``: en SQL de tres
        # valores no son lo mismo. La fuente escribe ``IS NOT TRUE``, que
        # incluye el NULL; ``revoked=False`` lo dejaría fuera y el índice
        # no cubriría una fila cuyo ``revoked`` quedara nulo por una
        # escritura que esquive el ``default``.
        indexes = [
            models.Index(
                fields=['user', 'session_identifier', 'platform', 'browser',
                        'last_activity', 'id'],
                condition=~models.Q(revoked=True),
                name='res_device_log_composite_idx',
            ),
            models.Index(
                fields=['revoked'],
                condition=~models.Q(revoked=True),
                name='res_device_log_revoked_idx',
            ),
        ]

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

    # ------------------------------------------------------------------
    # Barridos — Odoo ``@api.autovacuum`` (``res_device.py:116-169``)
    # ------------------------------------------------------------------
    @classmethod
    @api.autovacuum
    def _gc_device_log(cls):
        """≙ ``_gc_device_log`` (``odoo19c: res_device.py:116-135``).

        Conserva **la última fila por dispositivo** —la terna (sesión,
        plataforma, navegador) más la IP— y borra toda fila superada por otra
        más reciente. El comentario de la fuente lo dice entero: se guarda la
        última *aunque su sesión ya no exista en el almacén*, porque esa fila
        es lo que el panel muestra como dispositivo revocado.

        La fuente lo escribe como ``DELETE ... USING`` con la auto-unión
        (``:120-128``); aquí el mismo predicado se expresa con el ORM —un
        ``Exists`` correlacionado por los cuatro campos— y el conteo sale del
        propio ``delete()``, que es el ``cr.rowcount`` de la fuente.

        El ``lastcall`` del contexto (``:130-134``) se porta con su forma: si
        el cron lo puebla, sólo se consideran supersedings las filas activas
        desde entonces, que es lo que acota el barrido incremental.
        """
        superseding = cls.objects.filter(
            session_identifier=models.OuterRef('session_identifier'),
            platform=models.OuterRef('platform'),
            browser=models.OuterRef('browser'),
            ip_address=models.OuterRef('ip_address'),
            last_activity__gt=models.OuterRef('last_activity'),
        )
        if lastcall := get_context().get('lastcall'):
            superseding = superseding.filter(last_activity__gte=lastcall)
        deleted, _rest = cls.objects.filter(models.Exists(superseding)).delete()
        _logger.info('GC device logs delete %d entries', deleted)

    @classmethod
    @api.autovacuum
    def __update_revoked(cls):
        """≙ ``__update_revoked`` (``odoo19c: res_device.py:137-169``).

        Marca ``revoked`` en las filas cuya sesión ya no existe en el almacén.
        El log no se entera solo de que una sesión caducó: este barrido es lo
        que mantiene el panel diciendo la verdad.

        **El doble guion bajo se porta.** La fuente lo declara ``__``, no
        ``_``, y eso lo somete al mangling de Python: el colector lo encuentra
        como ``_ResDeviceLog__update_revoked``. Es el contrato de
        ``porte-completo-no-parcial.md`` — quitarle un guion lo promovería.

        **Por lotes, y el desplazamiento retrocede.** Como en la fuente
        (``:143-169``): se leen ``batch_size`` candidatas ordenadas por ``id``,
        se pregunta al almacén cuáles faltan, se marcan, y el desplazamiento
        **baja** por las que se marcaron —porque ya no volverán a salir en el
        filtro de ``revoked=False``, así que sin ese retroceso el siguiente
        lote se saltaría tantas filas como las marcadas.

        El ``self.env.cr.commit()`` de la fuente (``:168``) no se porta: aquí
        cada ``update()`` es su propia transacción bajo el autocommit de
        Django. Es divergencia de mecanismo, no de efecto.
        """
        batch_size = 100_000
        offset = 0
        threshold = datetime.now(tz=timezone.utc) - timedelta(
            seconds=get_session_max_inactivity())

        while True:
            candidates = list(cls.objects.filter(
                revoked=False, last_activity__lt=threshold,
            ).order_by('id')[offset:offset + batch_size])
            if not candidates:
                break
            offset += batch_size

            missing = get_missing_session_identifiers(
                {c.session_identifier for c in candidates if c.session_identifier})
            if not missing:
                continue

            to_revoke = [c.pk for c in candidates
                         if c.session_identifier in missing]
            cls.objects.filter(pk__in=to_revoke).update(revoked=True)
            offset -= len(to_revoke)


class ResDeviceQuerySet(models.AccessQuerySet):
    """El **recordset** de ``res.device``.

    ``_revoke`` actúa sobre un conjunto en la referencia —``for device in
    self``, ``self.filtered('is_current')``— y borra las sesiones de **todos**
    los identificadores de una sola llamada al almacén. Declararlo en la
    instancia obligaría a quien llama a iterar, y con eso se perdería
    justamente esa propiedad. Es la misma lectura que
    :class:`~addons.base.models.res_users.ResUsersQuerySet`.
    """

    def _revoke(self, request=None):
        """≙ ``_revoke`` (``odoo19c: res_device.py:185-196``).

        Cierra las sesiones de estos dispositivos: borra sus sesiones del
        almacén, marca ``revoked`` en el log —que es donde vive el dato, la
        vista es de sólo lectura— y, si entre ellos estaba el dispositivo
        **actual**, cierra la sesión en curso.

        **Un solo cuerpo donde la fuente tiene dos.** Allá ``revoke``
        (``:182-184``) es el público con ``@check_identity`` y ``_revoke`` el
        interno sin él; aquí la identidad fresca la exige
        ``authz_reauth.assert_session_fresh`` desde la vista (DEC-12), así que
        no hay dos cuerpos que separar — el gate lo pone quien lo exponga. Es
        la misma resolución que ``authz_totp.revoke_all_devices`` ya tomó para
        el par homónimo de ese addon.

        :param request: la petición en curso; por defecto la del contexto. La
            fuente la lee de un global (``odoo19c: odoo/http.py``), aquí se
            pasa explícita y se cae al contexto cuando no la hay.
        :returns: cuántas filas del log quedaron revocadas.
        """
        request = request if request is not None else get_current_request()

        # ``unique(...)`` de la fuente (``:187``) — mismo criterio: un
        # identificador aparece una vez aunque lo compartan dos filas.
        identifiers = list(dict.fromkeys(
            device.session_identifier for device in self
            if device.session_identifier))
        if not identifiers:
            return 0

        # La fuente marca ``is_current`` ANTES de borrar, porque después la
        # sesión ya no existe para comparar.
        must_logout = request is not None and any(
            device.is_current(request) for device in self)

        delete_sessions_from_identifiers(identifiers)

        log = apps.get_model('base', 'ResDeviceLog')
        revoked = log.objects.filter(
            session_identifier__in=identifiers).update(revoked=True)
        _logger.info('Se revocan dispositivos (%s): %s filas de log',
                     ', '.join(identifiers), revoked)

        if must_logout:
            django_logout(request)
        return revoked

    def order_by_is_current(self, request=None):
        """≙ ``_order_field_to_sql`` para ``is_current`` (``odoo19c:
        res_device.py:65-68``).

        Empuja arriba el dispositivo de la sesión en curso, comparando el
        **prefijo** que el log guarda con el de la sesión actual, y sólo
        después ordena por actividad. La fuente lo emite como
        ``session_identifier = %s DESC``; aquí es una anotación booleana en
        ``ORDER BY``, que es el mismo SQL.

        **Divergencia de mecanismo, declarada.** La fuente engancha el ORM:
        sobreescribe ``_order_field_to_sql`` y con eso cualquier consulta que
        pida ``order='is_current'`` obtiene ese SQL. Django no tiene punto de
        extensión de campo-a-SQL en el orden —``Meta.ordering`` fija el orden
        y no se consulta por nombre de campo calculado—, así que la misma
        capacidad se expone como método explícito del recordset. Lo que se
        pierde es la implicitud; lo que se gana es que la petición viaja como
        argumento en vez de leerse de un global.
        """
        request = request if request is not None else get_current_request()
        session_key = getattr(getattr(request, 'session', None),
                              'session_key', None)
        if not session_key:
            return self.order_by('-last_activity')
        prefix = session_key[:STORED_SESSION_BYTES]
        return self.annotate(
            _current=models.ExpressionWrapper(
                models.Q(session_identifier=prefix),
                output_field=models.BooleanField(),
            ),
        ).order_by('-_current', '-last_activity')


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

    # Atributos de clase de modelo — los cinco de ``odoo19c: res_device.py:
    # 175-180``, verbatim. ``_auto = False`` y ``_order`` conviven con su forma
    # Django (``Meta.managed`` y ``Meta.ordering``), que es lo que el motor lee.
    _name = 'res.device'
    _inherit = ['res.device.log']
    _description = "Devices"
    _auto = False
    _order = 'last_activity desc'

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

    objects = ResDeviceQuerySet.as_manager()

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


def delete_sessions_from_identifiers(identifiers):
    """≙ ``root.session_store.delete_from_identifiers`` (``odoo19c:
    res_device.py:188``) — borra del almacén las sesiones de esos prefijos.

    **Por qué hace falta construirlo.** El almacén guarda la sesión por su
    clave completa y aquí sólo se conserva un **prefijo** de ella
    (``STORED_SESSION_BYTES``, la garantía de que un log filtrado no entrega
    sesiones secuestrables). Ni ``SessionStore(clave).delete()`` ni
    ``request.session.flush()`` sirven para eso: el primero exige la clave
    entera, el segundo sólo alcanza a la sesión en curso. La referencia tiene
    el mismo problema y por eso su almacén expone este método; aquí se
    construye contra el motor configurado.

    **Alcance declarado.** Sólo el respaldo de base de datos
    (``django.contrib.sessions.backends.db``, que es el que
    ``config/settings/base.py:675`` declara) admite consultar por prefijo: su
    modelo tiene la clave como columna. Con ``cache``, ``file`` o
    ``signed_cookies`` no hay índice por prefijo que recorrer, así que la
    función lo dice y no borra nada — antes que borrar de menos en silencio.

    :returns: cuántas sesiones se borraron.
    """
    model = _session_model()
    if model is None:
        _logger.warning(
            'El motor de sesiones %s no expone su modelo: no se puede borrar '
            'por prefijo y las sesiones de %s quedan vivas.',
            settings.SESSION_ENGINE, ', '.join(identifiers))
        return 0

    query = models.Q()
    for identifier in identifiers:
        query |= models.Q(session_key__startswith=identifier)
    deleted, _rest = model().objects.filter(query).delete()
    return deleted


def _session_model():
    """El modelo del almacén de sesiones, o ``None`` si el motor no lo expone.

    Los dos consumidores —borrar por prefijo y preguntar cuáles faltan—
    necesitan lo mismo: una tabla con la clave de sesión como columna. Sólo el
    respaldo de base de datos la tiene.
    """
    engine = importlib.import_module(settings.SESSION_ENGINE)
    store = getattr(engine, 'SessionStore', None)
    return getattr(store, 'get_model_class', None)


def get_missing_session_identifiers(identifiers):
    """≙ ``root.session_store.get_missing_session_identifiers`` (``odoo19c:
    odoo/http.py:1099-1127``) — de esos prefijos, los que ya no existen.

    Es la mitad que **pregunta** donde
    :func:`delete_sessions_from_identifiers` es la que **borra**, y comparte
    su restricción: el log guarda un prefijo de la clave
    (``STORED_SESSION_BYTES``), no la clave entera, así que la pregunta sólo
    se puede resolver contra un almacén consultable por prefijo.

    La fuente recorre directorios del sistema de archivos y por eso se molesta
    en acotar cuáles (``:1107-1111``: en el peor caso 4096). Aquí el almacén
    es una tabla y la pregunta es un ``startswith`` por identificador — misma
    respuesta, otro sustrato.

    **Alcance declarado.** Con ``cache``, ``file`` o ``signed_cookies`` no hay
    índice por prefijo que recorrer. Ahí esta función devuelve el **conjunto
    vacío**: no sabe cuáles faltan, y decir «ninguna falta» revoca de menos,
    que es el lado seguro. Lo contrario —darlas todas por muertas— revocaría
    sesiones vivas.

    :returns: ``set`` con los identificadores sin sesión viva en el almacén.
    """
    identifiers = set(identifiers)
    if not identifiers:
        return set()

    model = _session_model()
    if model is None:
        _logger.warning(
            'El motor de sesiones %s no expone su modelo: no se puede '
            'preguntar por prefijo y ninguna sesión se da por muerta.',
            settings.SESSION_ENGINE)
        return set()

    query = models.Q()
    for identifier in identifiers:
        query |= models.Q(session_key__startswith=identifier)
    live_keys = model().objects.filter(query).values_list('session_key', flat=True)
    present = {
        identifier
        for identifier in identifiers
        for key in live_keys
        if key.startswith(identifier)
    }
    return identifiers - present


def get_session_max_inactivity():
    """≙ ``get_session_max_inactivity`` (``odoo19c: odoo/http.py:452-461``).

    Cuántos segundos de inactividad hacen caducar una sesión. La fuente lee el
    parámetro de configuración ``sessions.max_inactivity_seconds`` y cae a su
    ``SESSION_LIFETIME``; aquí el mismo parámetro se lee de
    ``ir.config_parameter`` —``SystemParameter``, que es el modelo portado— y
    el respaldo es
    ``settings.SESSION_COOKIE_AGE``, que es donde Django declara esa vida.

    Un valor no numérico se avisa y se ignora, como en la fuente (``:459``):
    un parámetro mal escrito no debe dejar el barrido sin umbral.
    """
    fallback = getattr(settings, 'SESSION_COOKIE_AGE', 60 * 60 * 24 * 7)
    parameter = apps.get_model('base', 'SystemParameter')
    raw = parameter.get_param('sessions.max_inactivity_seconds', fallback)
    try:
        return int(raw)
    except (TypeError, ValueError):
        _logger.warning(
            "Valor inválido en 'sessions.max_inactivity_seconds' (%r): se usa "
            'el respaldo %s.', raw, fallback)
        return fallback


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
