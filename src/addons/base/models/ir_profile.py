"""``ir.profile`` — resultados de perfilado guardados.

Adaptación fiel de ``odoo/addons/base/models/ir_profile.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 251 líneas). La referencia declara
**dos** modelos en este archivo, y aquí también: ``ir.profile`` (una corrida de
perfilado con sus trazas) y ``base.enable.profiling.wizard`` (el asistente que
habilita el perfilado por un rato acotado).

El modelo entero, campo por campo
=================================

Todas las columnas de la referencia se portan con su nombre y su tipo:
``session`` (indexada), ``name``, ``duration`` y ``cpu_duration`` (ambas
``digits=(9, 3)`` → ``max_digits=9, decimal_places=3``), ``init_stack_trace``,
``sql``, ``sql_count``, ``traces_async``, ``traces_sync``, ``others``,
``qweb`` y ``entry_count``.

El ``prefetch=False`` que la referencia pone en los cinco campos de traza es
una directiva de su ORM: "no traigas esta columna al leer el registro, pesa
demasiado". El equivalente de Django es ``.defer()`` en el queryset, que es
propiedad del consumidor y no del campo — por eso el manager por defecto
difiere los cinco: leer una lista de perfiles no debe arrastrar megabytes de
JSON. ``objects_full`` los trae cuando sí se necesitan.

``_log_access = False`` de la referencia (con el comentario *"avoid useless
foreign key on res_user"*) se respeta: el modelo hereda de ``TimeStampedModel``
por las marcas de tiempo, y **no** lleva FK a usuario.

Qué NO se porta, y la medición que lo sustenta
==============================================

- **Los tres campos computados de speedscope** (``speedscope``,
  ``speedscope_url``, ``config_url``) y todo su motor de generación
  (``_generate_speedscope``, ``_add_outputs``, ``_parse_params``,
  ``_default_profile_params``). Dependen de ``odoo.tools.speedscope.Speedscope``
  y ``odoo.tools.profiler``. Medido: ``find src -name 'speedscope*'`` y
  ``find src -name 'profiler*'`` → **0** archivos cada uno. Son un visor de
  llamaradas, no el modelo; entran si algún día se porta el visor.
- **``set_profiling``** — su cuerpo entero manipula ``request.session`` del
  framework web de Odoo (``profile_session``, ``profile_collectors``,
  ``profile_params``) y devuelve una ``ir.actions.act_window``. No hay
  ``ir.actions.*`` en este árbol (misma ausencia que ``ir_cron.py`` y
  ``ir_filters.py`` ya declaran). Lo que **sí** se porta de ese bloque es
  ``_enabled_until``, que es la política real y no depende de la sesión.
- **``action_view_speedscope``** — devuelve una ``ir.actions.act_url`` al
  visor ausente.

Lo que sí se conserva del comportamiento
========================================

- ``_enabled_until`` — lee ``base.profiling_enabled_until`` de
  ``ir.config_parameter`` (aquí ``SystemParameter``) y devuelve el límite sólo
  si aún no venció. Es el interruptor que decide si el perfilado corre.
- ``_gc_profile`` — el ``@api.autovacuum`` que borra perfiles de más de 30
  días por lotes, devolviendo ``(hechos, restantes)`` para que
  ``ir_autovacuum`` lo reencole. Se porta completo, incluido el patrón de
  lote: es exactamente el caso de uso que justifica el reencolado.
- ``base.enable.profiling.wizard`` con sus cuatro duraciones y su ``submit()``
  que escribe el parámetro.
"""
import datetime
import logging

from django.utils import timezone

import api
import fields
import models

from addons.base.models.ir_config_parameter import SystemParameter
from addons.base.models.timestamped_mixin import TimeStampedModel
from orm.models_transient import TransientModel

_logger = logging.getLogger(__name__)

#: Clave del parámetro que habilita el perfilado — nombre verbatim de la
#: referencia, para que el valor sea intercambiable con el suyo.
PROFILING_ENABLED_UNTIL = 'base.profiling_enabled_until'

#: Tope de filas por lote del recolector. La referencia usa
#: ``GC_UNLINK_LIMIT`` de ``odoo.tools.constants``; aquí es local porque ese
#: módulo de constantes no está portado.
GC_UNLINK_LIMIT = 100_000

#: Días que se conserva un perfil antes de que el recolector lo borre.
GC_RETENTION_DAYS = 30

#: Campos de traza: pesados y rara vez necesarios al listar. La referencia los
#: marca ``prefetch=False``; aquí el manager por defecto los difiere.
_TRACE_FIELDS = (
    'init_stack_trace', 'sql', 'traces_async', 'traces_sync', 'others', 'qweb',
)


class IrProfileManager(models.AccessManager):
    """Manager por defecto: difiere las trazas pesadas (``prefetch=False``)."""

    def get_queryset(self):
        return super().get_queryset().defer(*_TRACE_FIELDS)


class IrProfile(TimeStampedModel):
    """Una corrida de perfilado con sus trazas (``ir.profile``)."""

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

    #: Difiere las trazas, como el ``prefetch=False`` de la referencia.
    objects = IrProfileManager()
    #: Trae todo, para cuando las trazas sí se necesitan.
    objects_full = models.Manager()

    class Meta:
        db_table = 'ir_profile'
        # La referencia ordena por ``session desc, id desc``.
        ordering = ['-session', '-id']
        verbose_name = 'Resultado de perfilado'
        verbose_name_plural = 'Resultados de perfilado'

    def __str__(self):
        return self.name or f'perfil #{self.pk}'

    @classmethod
    @api.autovacuum
    def _gc_profile(cls):
        """Borra los perfiles de más de 30 días, por lotes.

        Devuelve ``(hechos, restantes)`` igual que la referencia: si el lote
        se llenó, quedan más y ``ir_autovacuum`` reencola el método.
        """
        corte = timezone.now() - datetime.timedelta(days=GC_RETENTION_DAYS)
        ids = list(
            cls.objects.filter(created_at__lt=corte)
            .values_list('pk', flat=True)[:GC_UNLINK_LIMIT]
        )
        if ids:
            cls.objects.filter(pk__in=ids).delete()
        return len(ids), len(ids) == GC_UNLINK_LIMIT

    @classmethod
    def _enabled_until(cls):
        """Hasta cuándo está habilitado el perfilado, o ``None`` si no lo está.

        Fiel a la referencia: lee el parámetro y lo devuelve **sólo** si la
        hora actual aún no lo alcanzó.
        """
        limite = SystemParameter.get_param(PROFILING_ENABLED_UNTIL, default='')
        if not limite:
            return None
        return limite if str(timezone.now()) < str(limite) else None


class BaseEnableProfilingWizard(TransientModel):
    """Habilita el perfilado por un rato acotado (``base.enable.profiling.wizard``).

    ``TransientModel`` sin tabla (``managed = False``), como el asistente de la
    referencia: su estado vive lo que dura la interacción.
    """

    DURATION_CHOICES = [
        ('minutes_5', '5 minutos'),
        ('hours_1', '1 hora'),
        ('days_1', '1 día'),
        ('months_1', '1 mes'),
    ]

    #: Cuántos días vale cada opción; la referencia usa ``relativedelta`` con
    #: la unidad literal del valor (``minutes``/``hours``/``days``/``months``).
    _DURATION_DELTAS = {
        'minutes_5': datetime.timedelta(minutes=5),
        'hours_1': datetime.timedelta(hours=1),
        'days_1': datetime.timedelta(days=1),
        'months_1': datetime.timedelta(days=30),
    }

    class Meta:
        abstract = True
        managed = False

    @classmethod
    def compute_expiration(cls, duration):
        """Instante de expiración para una duración — ``_compute_expiration``.

        La referencia parte ``'days_1'`` en unidad y cantidad, y cae a
        ``'days_0'`` (ahora mismo) cuando la duración viene vacía.
        """
        delta = cls._DURATION_DELTAS.get(duration, datetime.timedelta(0))
        return timezone.now() + delta

    @classmethod
    def submit(cls, duration):
        """Escribe el parámetro que habilita el perfilado y devuelve el límite."""
        expiration = cls.compute_expiration(duration)
        SystemParameter.set_param(PROFILING_ENABLED_UNTIL, str(expiration))
        _logger.info('Perfilado habilitado hasta %s', expiration)
        return expiration
