"""``ir.profile`` — resultados de perfilado guardados.

Adaptación fiel de ``odoo/addons/base/models/ir_profile.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 251 líneas). La referencia declara
**dos** modelos en este archivo, y aquí también: ``ir.profile`` (una ejecución
de perfilado con sus trazas) y ``base.enable.profiling.wizard`` (el asistente
que habilita el perfilado por un rato acotado).

El modelo entero, campo por campo
=================================

Todas las columnas de la referencia se portan con su nombre y su tipo:
``session`` (indexada), ``name``, ``duration`` y ``cpu_duration`` (ambas
``digits=(9, 3)`` → ``max_digits=9, decimal_places=3``), ``init_stack_trace``,
``sql``, ``sql_count``, ``traces_async``, ``traces_sync``, ``others``,
``qweb`` y ``entry_count``. Y los **tres campos computados** del visor —
``speedscope``, ``speedscope_url`` y ``config_url``— con el mecanismo sin
columna que este árbol construyó para el ``store=False`` de la fuente.

El ``prefetch=False`` que la referencia pone en los cinco campos de traza es
una directiva de su ORM: "no traigas esta columna al leer el registro, pesa
demasiado". El equivalente de Django es ``.defer()`` en el queryset, que es
propiedad del consumidor y no del campo — por eso el manager por defecto
difiere los cinco: leer una lista de perfiles no debe arrastrar megabytes de
JSON. ``objects_full`` los trae cuando sí se necesitan, y es el manager que
debe usar quien vaya a generar un speedscope: con ``objects`` cada traza se
carga en una consulta aparte al tocarla.

``_log_access = False`` de la referencia (con el comentario *"avoid useless
foreign key on res_user"*) se respeta: el modelo hereda de ``TimeStampedModel``
por las marcas de tiempo, y **no** lleva FK a usuario.

El ``self`` de la fuente es un CONJUNTO, y aquí son dos objetos
===============================================================

Siete símbolos de la referencia operan sobre un **recordset**, no sobre una
fila: ``_has_memory_traces`` recorre ``for profile in self``,
``_generate_speedscope`` lee ``self[0].init_stack_trace`` y compara ``len(self)
> 1``, ``action_view_speedscope`` une los ids con coma. Su llamador real lo
confirma — ``odoo19c: addons/web/controllers/profiling.py:33-48`` invoca
``profiles._default_profile_params()``, ``profiles._parse_params(params)`` y
``profiles._generate_speedscope(parsed)`` sobre el conjunto que acaba de
buscar.

En Django ese conjunto es un ``QuerySet`` y la fila es una instancia: son dos
tipos distintos, y la fuente los llama a los dos con la misma sintaxis
(``_compute_speedscope`` hace ``execution._generate_speedscope(params)`` sobre
un singleton, ``:100``). Por eso los siete cuerpos viven **una sola vez** en
:class:`ProfileSetMixin`, que ambos adoptan: ``IrProfileQuerySet`` se resuelve
a sí mismo como conjunto y ``IrProfile`` se resuelve a ``[self]``. Los dos
sitios de llamada quedan idénticos a los de la fuente, sin consultas extra y
sin duplicar ningún cuerpo. Es la misma lectura que
:class:`~addons.base.models.res_device.ResDeviceQuerySet` ya tomó para
``_revoke``, con el eslabón añadido de que aquí la fuente llama también desde
la fila.

Divergencias declaradas
=======================

- **``set_profiling`` recibe ``request`` explícito.** La fuente lo lee del
  global ``odoo.http.request`` (``:12``); aquí no hay tal global —``src/http``
  no existe, medido con ``ls src/``— y la petición se pasa como argumento,
  igual que en ``res_device.py:316``. El contenido es el mismo: la sesión de
  Django es un ``dict`` con la misma superficie (``__setitem__``/``get``) que
  la de la fuente.
- **Los tres ``_compute_*`` devuelven el valor en vez de asignarlo.** La
  fuente asigna dentro de un bucle (``profile.config_url = …``) porque su ORM
  computa sobre el recordset entero. El mecanismo sin columna de este árbol
  —``orm.fields_nonstored.NonStored``— resuelve **por fila** al leerla, así
  que el cuerpo devuelve. Es la forma que ``ir_actions.py:1291`` ya fijó para
  ``warning``.
- **El ``@api.autovacuum`` de ``_gc_profile``** y el resto del comportamiento
  se portan verbatim.

Lo que este archivo NO trae, y por qué
======================================

- **Las rutas ``/web/speedscope/<id>`` y ``/web/profile_config/<ids>``** que
  ``speedscope_url``, ``config_url`` y ``action_view_speedscope`` publican.
  Viven en ``odoo19c: addons/web/controllers/profiling.py``, que es otro
  archivo y otro addon; medido: ``find src -path '*web/controllers*'`` → 0.
  Los tres campos son el **contrato** —la URL que el cliente pide— y se portan
  completos; el manejador que la atiende es el porte de ese controlador,
  registrado como tarea **#361**.

.. note::

   Hasta ``api@d9a05f6f`` este archivo declaraba bloqueados los tres campos
   computados y su motor *"porque dependen de ``odoo.tools.speedscope`` y
   ``odoo.tools.profiler``; medido: 0 archivos cada uno"*. Los dos módulos
   entraron en ``api@9bb9b3e1`` y ``api@d9a05f6f``, y ``ir.actions.act_window``
   / ``act_url`` existen desde el porte de ``ir_actions.py``: las dos causas
   dejaron de existir y el bloqueo quedó caduco. Ver :ref:`h-api-1081`.
"""
import base64
import datetime
import json
import logging

from dateutil.relativedelta import relativedelta
from django.utils import timezone

import api
import fields
import models

from addons.base.models.ir_config_parameter import SystemParameter
from addons.base.models.timestamped_mixin import TimeStampedModel
from exceptions import UserError
from orm.environments import get_context
from orm.models_transient import TransientModel
from tools.constants import GC_UNLINK_LIMIT
from tools.misc import str2bool
from tools.profiler import make_session
from tools.speedscope import Speedscope
from tools.translate import _

_logger = logging.getLogger(__name__)

#: Clave del parámetro que habilita el perfilado — nombre verbatim de la
#: referencia, para que el valor sea intercambiable con el suyo.
PROFILING_ENABLED_UNTIL = 'base.profiling_enabled_until'

#: Días que se conserva un perfil antes de que el recolector lo borre.
GC_RETENTION_DAYS = 30

#: Campos de traza: pesados y rara vez necesarios al listar. La referencia los
#: marca ``prefetch=False``; aquí el manager por defecto los difiere.
_TRACE_FIELDS = (
    'init_stack_trace', 'sql', 'traces_async', 'traces_sync', 'others', 'qweb',
)


class ProfileSetMixin:
    """Los siete símbolos cuyo ``self`` en la fuente es un **conjunto**.

    La referencia los declara en el modelo y su ORM los sirve tanto sobre un
    singleton como sobre un recordset de N. Aquí esas dos formas son dos tipos
    de Python distintos, así que el cuerpo vive una vez y cada tipo declara
    cómo se ve a sí mismo como conjunto en :meth:`_profiles`.
    """

    def _profiles(self):
        """El conjunto sobre el que operan los métodos de esta clase.

        NO existe en la referencia: allá ``self`` **ya es** el conjunto. Es el
        único símbolo inventado del archivo, y lo pide la diferencia de tipos
        entre ``QuerySet`` e instancia.
        """
        raise NotImplementedError

    def _has_memory_traces(self):
        """≙ ``_has_memory_traces`` (``odoo19c: ir_profile.py:60-68``).

        ``True`` cuando **todos** los perfiles traen medición de RSS en
        ``traces_async``. Basta con mirar la primera entrada: el colector de
        memoria escribe la clave en todas o en ninguna.
        """
        for profile in self._profiles():
            if not profile.traces_async:
                return False
            entries = json.loads(profile.traces_async)
            if not entries or entries[0].get('memory') is None:
                return False
        return True

    def _get_memory_data(self):
        """≙ ``_get_memory_data`` (``:70-88``).

        Los puntos de RSS con la línea base restada, para la gráfica. La base
        es el **primer** valor visto en todo el conjunto, no el primero de cada
        perfil: así dos perfiles consecutivos se leen en la misma escala.
        """
        points = []
        baseline = None
        for profile in self._profiles():
            if not profile.traces_async:
                continue
            for entry in json.loads(profile.traces_async):
                mem = entry.get('memory')
                if mem is None:
                    continue
                if baseline is None:
                    baseline = mem
                points.append({
                    'timestamp': entry['start'],
                    'memory': mem - baseline,
                    'abs_memory': mem,
                })
        return {'points': points}

    def _default_profile_params(self):
        """≙ ``_default_profile_params`` (``:102-112``).

        Qué salidas ofrecer cuando nadie las pidió, derivado de lo que el
        conjunto **tiene**: con SQL y marcos, la combinada; sólo con SQL, la de
        SQL sin huecos; sólo con marcos, la de marcos. La de densidad nunca es
        default — es una lectura de detalle que se pide a mano.
        """
        profiles = list(self._profiles())
        has_sql = any(profile.sql for profile in profiles)
        has_traces = any(profile.traces_async for profile in profiles)
        has_memory = self._has_memory_traces()
        return {
            'combined_profile': has_sql and has_traces,
            'sql_no_gap_profile': has_sql and not has_traces,
            'sql_density_profile': False,
            'frames_profile': has_traces and not has_sql,
            'memory_profile': has_memory,
        }

    def _parse_params(self, params):
        """≙ ``_parse_params`` (``:114-125``).

        Normaliza lo que llega de fuera. El comentario de la fuente lo dice
        entero (``:96-97``): *"la variable params existe para controlar la
        entrada del usuario; al ampliarla, elegir de un enum para que sólo
        entren los valores correctos"*. Aquí eso se conserva: nueve claves
        fijas, ocho pasadas por ``str2bool`` y el modo de agregación con su
        default; nada más del diccionario de entrada sobrevive.
        """
        return {
            'constant_time': str2bool(params.get('constant_time', False)),
            'aggregate_sql': str2bool(params.get('aggregate_sql', False)),
            'use_context': str2bool(params.get('use_execution_context', True)),
            'combined_profile': str2bool(params.get('combined_profile', False)),
            'sql_no_gap_profile': str2bool(params.get('sql_no_gap_profile', False)),
            'sql_density_profile': str2bool(params.get('sql_density_profile', False)),
            'frames_profile': str2bool(params.get('frames_profile', False)),
            'memory_profile': str2bool(params.get('memory_profile', False)),
            'profile_aggregation_mode': params.get('profile_aggregation_mode', 'tabs'),
        }

    def _generate_speedscope(self, params):
        """≙ ``_generate_speedscope`` (``:127-145``).

        El documento speedscope de este conjunto, ya serializado a ``bytes``.

        Exige que **todos** compartan la traza de pila inicial: es la tabla de
        marcos común, y sin ella los índices de un perfil no significan lo
        mismo en otro. La fuente lo comprueba con la misma guarda y el mismo
        mensaje.
        """
        profiles = list(self._profiles())
        init_stack_trace = profiles[0].init_stack_trace
        for record in profiles:
            if record.init_stack_trace != init_stack_trace:
                raise UserError(_(
                    'All profiles must have the same initial stack trace to be '
                    'displayed together.'))
        sp = Speedscope(init_stack_trace=json.loads(init_stack_trace))
        for profile in profiles:
            if (params['sql_no_gap_profile'] or params['sql_density_profile']
                    or params['combined_profile']) and profile.sql:
                sp.add(f'sql {profile.id}', json.loads(profile.sql))
            if (params['frames_profile'] or params['combined_profile']
                    or params['memory_profile']) and profile.traces_async:
                sp.add(f'frames {profile.id}', json.loads(profile.traces_async))
            if params['profile_aggregation_mode'] == 'tabs':
                profile._add_outputs(
                    sp,
                    f'{profile.id} {profile.name}' if len(profiles) > 1 else '',
                    params,
                )

        if params['profile_aggregation_mode'] == 'temporal':
            self._add_outputs(sp, 'all', params)

        result = json.dumps(sp.make(**params))
        return result.encode('utf-8')

    def _add_outputs(self, sp, suffix, params):
        """≙ ``_add_outputs`` (``:147-159``).

        Añade al documento las vistas que ``params`` pidió, cada una sobre los
        perfiles de este conjunto. Los nombres (``sql <id>`` / ``frames <id>``)
        son las claves con que :meth:`_generate_speedscope` los registró.
        """
        profiles = list(self._profiles())
        sql = [f'sql {profile.id}' for profile in profiles]
        frames = [f'frames {profile.id}' for profile in profiles]
        if params['combined_profile']:
            sp.add_output(sql + frames, display_name=f'Combined {suffix}', **params)
        if params['sql_no_gap_profile']:
            sp.add_output(sql, hide_gaps=True,
                          display_name=f'Sql (no gap) {suffix}', **params)
        if params['sql_density_profile']:
            sp.add_output(sql, continuous=False, complete=False,
                          display_name=f'Sql (density) {suffix}', **params)
        if params['frames_profile']:
            sp.add_output(frames, display_name=f'Frames {suffix}', **params)
        if params['memory_profile']:
            sp.add_memory_output(frames, display_name=f'Memory {suffix}', **params)

    def action_view_speedscope(self):
        """≙ ``action_view_speedscope`` (``:223-229``).

        La acción que abre el visor con **todos** los perfiles del conjunto en
        una sola pestaña: los ids van unidos por coma en la URL.

        La ruta la sirve el controlador de ``web`` (tarea **#361**); esta
        acción es el contrato del lado del modelo y se porta completa.
        """
        ids = ",".join(str(profile.id) for profile in self._profiles())
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/profile_config/{ids}',
            'target': 'new',
        }


class IrProfileQuerySet(ProfileSetMixin, models.AccessQuerySet):
    """El **recordset** de ``ir.profile`` — el ``self`` de la fuente."""

    def _profiles(self):
        return self


class IrProfileManager(models.Manager.from_queryset(IrProfileQuerySet)):
    """Manager por defecto: difiere las trazas pesadas (``prefetch=False``)."""

    def get_queryset(self):
        return super().get_queryset().defer(*_TRACE_FIELDS)


class IrProfile(ProfileSetMixin, TimeStampedModel):
    """Una ejecución de perfilado con sus trazas (``ir.profile``)."""

    _name = 'ir.profile'
    _description = 'Profiling results'
    _log_access = False  # avoid useless foreign key on res_user
    _order = 'session desc, id desc'
    _allow_sudo_commands = False

    session = fields.Char(
        max_length=120, blank=True, default='', db_index=True,
        verbose_name='Sesión',
    )
    name = fields.Char(
        max_length=255, blank=True, default='', verbose_name='Descripción',
    )
    # La referencia declara ``fields.Float(digits=(9, 3))``, que su ORM guarda
    # como ``numeric(9,3)``. En este vocabulario ``fields.Float`` es
    # ``FloatField`` y **no** acepta ``digits``; el tipo que preserva esa
    # precisión exacta es ``DecimalField``. ``fields.Monetary`` también lo es,
    # pero nombra dinero y esto son segundos — así que se usa el primitivo de
    # Django directamente en vez de forzar un alias que miente.
    duration = models.DecimalField(
        max_digits=9, decimal_places=3, null=True, blank=True,
        verbose_name='Duración', help_text='Tiempo real transcurrido.',
    )
    cpu_duration = models.DecimalField(
        max_digits=9, decimal_places=3, null=True, blank=True,
        verbose_name='Duración de CPU',
        help_text='Reloj de CPU (sin otros procesos ni SQL).',
    )

    init_stack_trace = fields.Text(
        blank=True, default='', verbose_name='Traza de pila inicial')
    sql = fields.Text(blank=True, default='', verbose_name='Sql')
    sql_count = fields.Integer(
        null=True, blank=True, verbose_name='Conteo de consultas')
    traces_async = fields.Text(
        blank=True, default='', verbose_name='Trazas asíncronas')
    traces_sync = fields.Text(
        blank=True, default='', verbose_name='Trazas síncronas')
    others = fields.Text(blank=True, default='', verbose_name='Otros')
    qweb = fields.Text(blank=True, default='', verbose_name='Qweb')
    entry_count = fields.Integer(
        null=True, blank=True, verbose_name='Conteo de entradas')

    #: ≙ ``speedscope`` (``odoo19c: ir_profile.py:47``):
    #: ``fields.Binary('Speedscope', compute='_compute_speedscope')``.
    #: Sin columna, como allá: el documento se genera al leerlo.
    speedscope = fields.NonStored(
        'Speedscope',
        default=lambda profile: profile._compute_speedscope(),
        compute='_compute_speedscope',
    )
    #: ≙ ``speedscope_url`` (``:48``): ``fields.Text('Open', compute=…)``.
    speedscope_url = fields.NonStored(
        'Open',
        default=lambda profile: profile._compute_speedscope_url(),
        compute='_compute_speedscope_url',
    )
    #: ≙ ``config_url`` (``:50``):
    #: ``fields.Text('Open profiles config', compute=…)``.
    config_url = fields.NonStored(
        'Open profiles config',
        default=lambda profile: profile._compute_config_url(),
        compute='_compute_config_url',
    )

    #: Difiere las trazas, como el ``prefetch=False`` de la referencia.
    objects = IrProfileManager()
    #: Trae todo, para cuando las trazas sí se necesitan.
    objects_full = IrProfileQuerySet.as_manager()

    class Meta:
        db_table = 'ir_profile'
        # La referencia ordena por ``session desc, id desc``.
        ordering = ['-session', '-id']
        verbose_name = 'Resultado de perfilado'
        verbose_name_plural = 'Resultados de perfilado'

    def __str__(self):
        return self.name or f'perfil #{self.pk}'

    def _profiles(self):
        """Una fila se ve a sí misma como el conjunto de un elemento.

        Es el singleton con el que la fuente llama desde ``_compute_speedscope``
        (``:100``): ``execution._generate_speedscope(params)``.
        """
        return [self]

    @classmethod
    @api.autovacuum
    def _gc_profile(cls):
        """Borra los perfiles de más de 30 días, por lotes.

        Devuelve ``(hechos, restantes)`` igual que la referencia: si el lote
        se llenó, quedan más y ``ir_autovacuum`` lo reencola.
        """
        cutoff = timezone.now() - datetime.timedelta(days=GC_RETENTION_DAYS)
        ids = list(
            cls.objects.filter(created_at__lt=cutoff)
            .values_list('pk', flat=True)[:GC_UNLINK_LIMIT]
        )
        if ids:
            cls.objects.filter(pk__in=ids).delete()
        return len(ids), len(ids) == GC_UNLINK_LIMIT

    def _compute_config_url(self):
        """≙ ``_compute_config_url`` (``odoo19c: ir_profile.py:90-92``)."""
        return f'/web/profile_config/{self.id}'

    @api.depends('init_stack_trace')
    def _compute_speedscope(self):
        """≙ ``_compute_speedscope`` (``:94-100``).

        Los parámetros salen del contexto, que es por donde el cliente pasa los
        interruptores de la vista; ``_parse_params`` es quien los acota.
        """
        params = self._parse_params(get_context())
        return base64.b64encode(self._generate_speedscope(params))

    @api.depends('speedscope')
    def _compute_speedscope_url(self):
        """≙ ``_compute_speedscope_url`` (``:161-164``)."""
        return f'/web/speedscope/{self.id}'

    @classmethod
    def _enabled_until(cls):
        """Hasta cuándo está habilitado el perfilado, o ``None`` si no lo está.

        Fiel a la referencia (``:166-172``): lee el parámetro y lo devuelve
        **sólo** si la hora actual aún no lo alcanzó.
        """
        limit = SystemParameter.get_param(PROFILING_ENABLED_UNTIL, default='')
        if not limit:
            return None
        return limit if str(timezone.now()) < str(limit) else None

    @classmethod
    def set_profiling(cls, request, profile=None, collectors=None, params=None):
        """≙ ``set_profiling`` (``:174-221``) — habilita o apaga el perfilado.

        :param request: la petición en curso. La fuente lo lee del global
            ``odoo.http.request``; aquí se pasa explícito (divergencia
            declarada en la cabecera del archivo).
        :param profile: ``True`` para habilitar, ``False`` para apagar.
        :param collectors: lista opcional de colectores a usar.
        :param params: parámetros opcionales para el objeto ``Profiler``.

        El comentario de la fuente se conserva porque es la razón de la guarda:
        los parámetros llegan de una llamada RPC o de un parámetro de ruta
        —usuario público incluido—, así que las variables de sesión las define
        el cliente. Eso permite activar cualquier perfilador y hace peligroso
        manipular ``profile_collectors``/``profile_params`` sin acotarlos.
        """
        if profile:
            limit = cls._enabled_until()
            _logger.info("User %s started profiling", request.user.name)
            if not limit:
                request.session['profile_session'] = None
                if request.user._is_system():
                    return {
                        'type': 'ir.actions.act_window',
                        'view_mode': 'form',
                        'res_model': 'base.enable.profiling.wizard',
                        'target': 'new',
                        'views': [[False, 'form']],
                    }
                raise UserError(_(
                    'Profiling is not enabled on this database. Please contact '
                    'an administrator.'))
            if not request.session.get('profile_session'):
                request.session['profile_session'] = make_session(request.user.name)
                request.session['profile_expiration'] = limit
                if request.session.get('profile_collectors') is None:
                    request.session['profile_collectors'] = []
                if request.session.get('profile_params') is None:
                    request.session['profile_params'] = {}
        elif profile is not None:
            request.session['profile_session'] = None

        if collectors is not None:
            request.session['profile_collectors'] = collectors

        if params is not None:
            request.session['profile_params'] = params

        return {
            'session': request.session.get('profile_session'),
            'collectors': request.session.get('profile_collectors'),
            'params': request.session.get('profile_params'),
        }


class BaseEnableProfilingWizard(TransientModel):
    """El asistente que habilita el perfilado por un rato acotado.

    ≙ ``BaseEnableProfilingWizard`` (``odoo19c: ir_profile.py:230-251``).
    Su trabajo entero cabe en dos campos y dos metodos: se elige una duracion,
    de ella sale una fecha limite, y ``submit`` la escribe en el parametro que
    :meth:`IrProfile._enabled_until` lee.

    **Tiene tabla, como todo transitorio de la fuente.** ``TransientModel``
    declara ``_auto = True`` (``odoo19c: odoo/orm/models_transient.py:18``), y
    ``expiration`` es ``store=True`` alla: sin columna no hay donde guardar lo
    que ``submit`` va a leer. Hasta este pase la clase era ``abstract = True``
    con dos ``classmethod``, sin ninguno de los dos campos — un porte parcial
    silencioso que ``porte-completo-no-parcial.md`` prohibe. Cierra la parte de
    la tarea **#201** que corresponde a este transitorio; los otros dos
    (``IrDemo`` y ``ResConfig``) siguen con su ``managed = False`` y su razon
    sin medir.
    """

    _name = 'base.enable.profiling.wizard'
    _description = "Enable profiling for some time"

    #: ≙ el ``Selection`` de ``:234-239``. El valor es ``<unidad>_<cantidad>``
    #: y de ahi lo parte el computo, igual que la fuente.
    DURATION_CHOICES = [
        ('minutes_5', "5 Minutes"),
        ('hours_1', "1 Hour"),
        ('days_1', "1 Day"),
        ('months_1', "1 Month"),
    ]

    duration = fields.Selection(
        max_length=16, choices=DURATION_CHOICES, null=True, blank=True,
        verbose_name="Enable profiling for",
        help_text='Cuanto dura el permiso de perfilado (Odoo ``duration``, '
                  '``odoo19c: ir_profile.py:234``).',
    )
    expiration = fields.Datetime(
        null=True, blank=True,
        compute='_compute_expiration', store=True,
        verbose_name="Enable profiling until",
        help_text='Instante en que caduca el permiso (Odoo ``expiration``, '
                  '``odoo19c: ir_profile.py:240``). La fuente lo declara '
                  '``readonly=False``: el computo propone y quien llena el '
                  'formulario puede sobrescribir, que aqui es el '
                  '``blank=True`` del campo.',
    )

    class Meta:
        # Con tabla real, como el resto de los transitorios de la fuente. El
        # ``abstract = True`` que habia aqui dejaba al asistente sin columnas
        # y sin los dos campos que la fuente declara.
        db_table = 'base_enable_profiling_wizard'
        verbose_name = 'Asistente de habilitacion de perfilado'
        verbose_name_plural = 'Asistentes de habilitacion de perfilado'

    @api.depends('duration')
    def _compute_expiration(self):
        """≙ ``_compute_expiration`` (``odoo19c: ir_profile.py:242-246``).

        La fuente parte el valor en unidad y cantidad —``'days_1'`` da
        ``relativedelta(days=1)``— y cae a ``'days_0'`` cuando la duracion
        viene vacia, que es *ahora mismo*. El cuerpo se copia tal cual: el
        ``relativedelta`` de ``dateutil`` es dependencia declarada del proyecto
        (``pyproject.toml:58``), asi que el mes calendario no se aproxima a
        treinta dias como hacia la version anterior de este archivo.

        La fuente itera ``for record in self`` porque su ``self`` es un
        conjunto; aqui el computo recibe la fila, que es la forma que
        ``save()`` invoca en este arbol (precedente:
        ``res_partner._compute_commercial_company_name``).
        """
        unit, quantity = (self.duration or 'days_0').split('_')
        self.expiration = timezone.now() + relativedelta(**{unit: int(quantity)})

    def submit(self):
        """≙ ``submit`` (``:248-250``) — escribe el parametro y no abre vista.

        La fuente devuelve ``False``, que en su cliente significa *cierra el
        dialogo y no navegues a ningun lado*. Se conserva el valor: es el
        contrato de la accion, no un detalle de su interfaz.
        """
        SystemParameter.set_param(PROFILING_ENABLED_UNTIL, str(self.expiration))
        _logger.info('Perfilado habilitado hasta %s', self.expiration)
        return False
