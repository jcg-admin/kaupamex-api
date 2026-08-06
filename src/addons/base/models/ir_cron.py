"""``ir.cron`` — registro de tareas programadas (Odoo ``base``).

Portación fiel de ``IrCron``
(``scratchpad/odoo18/extracted/odoo/addons/base/models/ir_cron.py:54-750``,
Odoo 18; ``scratchpad/odoo19x/odoo/addons/base/models/ir_cron.py:91-895``,
Odoo 19) — la **estructura de control** que persiste una tarea programada
(qué ejecutar, cada cuánto, próxima corrida) — **no** el runner que la
ejecuta. Parte de la iniciativa ``adaptar-familias-odoo-monolito-modular``
(SOL-096), backlog de control núcleo ``ir.*`` (H-BASE-01 C-2). Premisa
verificada por el orquestador: ``ir_cron`` AUSENTE de
``src/addons/base/models/`` antes de este commit (``grep -rl "class IrCron"
src/addons/base/models/`` → vacío).

Delegación a ``ir.actions.server`` — PORTADA
=====================================================================

Odoo modela ``ir.cron`` con ``_inherits = {'ir.actions.server':
'ir_actions_server_id'}`` (19 línea 104-108, enlace en :106-108 como
``Many2one(..., delegate=True, ondelete='restrict', required=True)``): el
"qué ejecutar" vive delegado en la acción servidor, y ``ir.cron`` **sólo
aporta la periodicidad**.

Se porta con el patrón establecido en este árbol para ``_inherits`` — **FK
real + delegación por propiedad**, NO herencia multi-tabla de Django (que
crea un ``OneToOneField(parent_link=True)``, una hija por padre, cuando el
``_inherits`` de Odoo es un ``Many2one``). Mismo criterio que
``product_product.py`` → ``product.template``, ``res_users.py`` →
``res.partner`` y ``mail_mail.py`` → ``mail.message``.

**Revierte la adaptación anterior**, que declaraba ``name``/``model_name``/
``method_name`` como columnas locales. Aquella se justificaba en que "sin el
modelo destino no hay FK fiel que portar"; ``IrActionsServer`` ya existe
(``ir_actions.py:402``), así que la premisa caducó. Prevalece el análisis
actual — principio rector, Clausula 1; directiva del ejecutor 2026-08-01
(*"queremos delegar las cosas, como lo tienes en odoo-tools"*). Ver
H-API-203.

Qué NO cambia con la delegación
---------------------------------

El **motor de ejecución sigue sin portarse**: ``IrActionsServer.run()``
levanta ``NotImplementedError`` a propósito, porque el modo ``code`` evalúa
Python almacenado y quién conecte el evaluador es una decisión aparte (ver
el docstring de ``ir_actions.py``). Delegar mueve el *dato* del "qué
ejecutar" a su hogar fiel; **no** habilita la evaluación de código.

``method_name`` — dónde vive ahora
-----------------------------------

Es una adaptación de proyecto **sin análogo** en la referencia: sustituye la
evaluación del ``code`` Python por una llamada a método
(``getattr(apps.get_model(model_name), method_name)``, que resolverá el
runner diferido). Vive en ``IrActionsServer`` junto a ``code`` y
``model_name`` —no en ``ir.cron``— porque ese es el modelo donde la
referencia pone el "qué ejecutar". Partirlo entre los dos modelos habría
dejado el objetivo a medias en cada uno.

``model_name`` sigue siendo ``Char`` plano en su nuevo hogar, igual que
``ir.filters.model_id`` y ``ir.attachment.res_model`` — la delegación no
cambia ese criterio, sólo dónde está el campo.

El runner del cron — PORTADO (parcial; Clausula 4 cerrada para lo esencial)
=====================================================================

Iteración posterior a la portación original de este módulo: el runner que
hace polling de ``ir_cron`` con ``active=True AND nextcall <= now()``,
adquiere el job, lo ejecuta y reprograma ``nextcall`` **ya está portado**
como los cuatro métodos homónimos de la referencia —
``_acquire_one_job``/``_run_job``/``_process_jobs``/``_callback`` (18/19
líneas 308-388/458-568/187-212/671-696)— más dos helpers propios
(``_ready_q``, ``_reschedule``) que no tienen nombre en la referencia
porque allá su lógica vive inline en ``_get_ready_sql_condition`` y
``_reschedule_later``.

Adquisición: ``FOR NO KEY UPDATE SKIP LOCKED`` vía
``QuerySet.select_for_update(skip_locked=True, no_key=True)`` — la misma
capacidad de PostgreSQL que la referencia usa (ADR-028 la desbloqueó;
MariaDB no la daba), **no** un lock de aplicación en Python. Cada job se
adquiere y ejecuta en su propia transacción (``transaction.atomic``),
igual que la referencia comitea por-job en ``_process_jobs_loop``.

Colapso deliberado frente a la referencia (por lo que SÍ se excluyó,
ver la sección siguiente): sin ``ir.cron.progress`` no hay estados
"parcialmente hecho" — un job es ``FULLY_DONE`` o ``FAILED`` en una sola
pasada de ``_callback``, y **ambos** resultados reprograman por el
intervalo normal (== la referencia: ``_reschedule_later`` corre para
``FULLY_DONE`` y para ``FAILED`` por igual, ir_cron.py:445-448) — un job
que falla no queda atascado en un reintento apretado ni bloquea a los
siguientes.

Deliberadamente NO se porta (fuera de alcance de este runner)
=====================================================================

- **``failure_count`` / ``first_failure_date`` + auto-desactivación tras
  fallos consecutivos** (18/19): sin ellos, un job que falla siempre
  sigue reprogramándose (nunca se auto-desactiva). Candidato H-BASE si el
  volumen de jobs con fallos crónicos lo justifica.
- **``ir.cron.trigger`` / ``ir.cron.progress``** (modelos satélite 18/19
  para triggers ad-hoc y progreso batch — ``_trigger``/``_commit_progress``):
  sin ``ir.cron.trigger`` no hay ``_reschedule_asap`` ni disparo fuera de
  horario; sin ``ir.cron.progress`` no hay ejecución multi-lote de un
  mismo job. Ninguno de los dos es requisito de un runner correcto de
  polling — son optimizaciones de UX/observabilidad de Odoo.
- **``_check_version``/``_check_modules_state`` (``BadVersion``/
  ``BadModuleState``)**: dependen de ``ir_module_module.latest_version`` y
  de filas con ``state LIKE 'to %'`` — semántica de "módulo instalando/
  actualizando" que no tiene equivalente portado en este monolito (los
  "módulos" aquí son apps Django versionadas por migraciones, no filas con
  estado propio). ``_process_jobs`` no las invoca.
- **``_notifydb`` (LISTEN/NOTIFY de PostgreSQL vía ``pg_notify``)**:
  mecanismo de wake-up específico de Postgres para reaccionar a triggers
  entre pasadas del worker; sin ``ir.cron.trigger`` no hay a qué
  reaccionar. El subcomando ``cron`` (``management/commands/cron.py``)
  hace polling por intervalo fijo en su lugar.

Comportamiento SÍ portado (adaptado a un método plano, no a los
decoradores ``@api``/loop de reintento de Odoo): ``_compute_next()`` —
calcula el próximo ``nextcall`` avanzando por
``interval_number``×``interval_type`` desde el ``nextcall`` actual,
replicando la tabla ``_intervalTypes`` de Odoo (18/19 líneas 39-45/52-58)
sin ``dateutil.relativedelta`` (no es dependencia del proyecto —
verificado: ausente de ``pyproject.toml`` y de la instalación ``uv``).
Para ``months`` se implementa suma calendario con *clamping* de día de mes
(mismo comportamiento observable que ``relativedelta`` para overflow de
día, p. ej. 31 de enero + 1 mes → 28/29 de febrero) usando solo
``calendar``/``datetime`` de la stdlib. ``_reschedule()`` es quien invoca
este cálculo repetidamente (loop "hasta superar now()", == referencia
``_reschedule_later``) — ``_compute_next()`` en sí sigue siendo una sola
pasada, sin loop propio.

Campos del brief NO presentes en Odoo 18 ni 19 — OMITIDOS, no inventados
=====================================================================

El brief de esta tarea especulaba dos campos adicionales que **no existen**
en ninguna de las dos fuentes citadas arriba (verificado con ``grep -En
"numbercall|doall" scratchpad/odoo{18,19x}/.../ir_cron.py`` → 0 matches en
ambos archivos):

- **``numbercall``** (contador de ejecuciones restantes, ``-1``=ilimitado):
  campo de versiones muy anteriores de Odoo (pre-10, antes del rediseño a
  ``ir.cron.trigger``); ausente de 18 y 19. NO se agrega — inventarlo sin
  respaldo en la fuente violaría el criterio "fiel a Odoo, no inventado".
- **``doall``** (ejecutar corridas perdidas): mismo caso — campo legado
  ausente de 18 y 19.

Ambos quedan como hallazgo H-BASE-NN candidato (ver reporte del commit)
por si una futura iteración del runner necesita semántica equivalente
("ejecutar N veces y desactivar" / "compensar corridas perdidas");
se implementaría entonces con nombre y semántica propios, sin resucitar
el nombre legado de Odoo si no se porta su comportamiento exacto.

``company_id`` tampoco existe en ``ir.cron`` en ninguna de las dos fuentes
(verificado leyendo el modelo completo en ambas versiones) — se omite por
ausencia real, no se especula (mismo criterio que ``ir_filters.py`` con su
propio ``company_id`` ausente).

``user`` — adaptación deliberada respecto a Odoo
=====================================================================

Odoo declara ``user_id`` ``required=True`` con
``default=lambda self: self.env.user`` (18/19 línea 72/110) — siempre hay
un usuario ejecutor porque Odoo lo resuelve del contexto de sesión al
crear el cron. Este monolito no tiene ese contexto de request implícito al
registrar una tarea programada (p. ej. seed de datos, management command),
así que ``user`` se porta **nullable** (``null=True, blank=True,
on_delete=SET_NULL``) — mismo patrón que ``company`` en
``ir_sequence``/``ir_attachment``: el dueño es opcional a nivel de dato.

Cross-app: ``user`` → ``settings.AUTH_USER_MODEL`` (Odoo ``user_id``).

``user`` SÍ se consume: el callback corre bajo ``user_scope``
--------------------------------------------------------------

La referencia ejecuta el callback **como el usuario del job**
(``env = api.Environment(job_cr, job['user_id'], {...})``,
ir_cron.py:481-483). Aquí el equivalente es ``orm.environments.user_scope``
—el ``with_user`` de ``odoo19c: odoo/orm/models.py:5981-5988``, implementado
con ``ContextVar`` para ser seguro bajo hilos y async—, que ``_callback``
envuelve alrededor de la invocación.

El camino HTTP ya poblaba ese mismo eje (``ir_http.py:257``,
``set_current_uid``); el cron era el único llamador que lo dejaba sin
poblar. Con el scope puesto, ``orm.environments.get_current_user()`` dentro
del método invocado devuelve el ``user`` del cron, que es lo que consumen
``bus/ir_attachment.py``, ``bus/bus_listener_mixin.py`` y
``digest/digest.py``.

**Lo que esto NO alcanza todavía:** ``IrRule.eval_context`` (``ir_rule.py:161``)
recibe ``user`` como parámetro explícito y **no** cae a ``get_current_user()``
cuando el llamador no lo pasa. Así que un cron con ``user`` puesto tiene el
usuario disponible en el contexto, pero las record rules evaluadas dentro no
lo ven salvo que el propio método lo pase. Cambiar ese default altera el
dominio evaluado para **todo** consumidor de record rules, no sólo el cron:
va por separado, con su barrido de llamadores (tarea #127, segunda mitad;
:ref:`h-api-333`).
"""
import calendar
import logging
from datetime import timedelta

from django.apps import apps
from django.conf import settings
from django.db import DEFAULT_DB_ALIAS, transaction
from django.utils import timezone

import fields
import models
from addons.base.models.ir_actions import IrActionsServer
from orm.environments import user_scope

_logger = logging.getLogger(__name__)

INTERVAL_CHOICES = [
    ('minutes', 'Minutes'),
    ('hours', 'Hours'),
    ('days', 'Days'),
    ('weeks', 'Weeks'),
    ('months', 'Months'),
]


def _add_months(dt, months):
    """Suma ``months`` meses calendario a ``dt``, con *clamping* de día de
    mes (equivalente observable a ``dateutil.relativedelta(months=months)``
    para el caso de overflow de día — p. ej. 31 de enero + 1 mes → último
    día de febrero). Implementado con stdlib porque ``dateutil`` no es
    dependencia del proyecto (ver docstring del módulo)."""
    month_index = dt.month - 1 + months
    year = dt.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(dt.day, last_day)
    return dt.replace(year=year, month=month, day=day)


def _add_interval(dt, number, interval_type):
    """Avanza ``dt`` por ``number`` unidades de ``interval_type`` — réplica
    de la tabla ``_intervalTypes`` de Odoo (``ir_cron.py:39-45`` en 18,
    ``ir_cron.py:52-58`` en 19)."""
    if interval_type == 'minutes':
        return dt + timedelta(minutes=number)
    if interval_type == 'hours':
        return dt + timedelta(hours=number)
    if interval_type == 'days':
        return dt + timedelta(days=number)
    if interval_type == 'weeks':
        return dt + timedelta(weeks=number)
    if interval_type == 'months':
        return _add_months(dt, number)
    raise ValueError(f'interval_type desconocido: {interval_type!r}')


class IrCron(models.Model):
    """``ir.cron`` — registro de horario de una tarea programada + runner.

    El registro de horario (qué ejecutar + cada cuánto + próxima corrida)
    y el runner que hace polling y ejecuta las tareas ``active=True`` con
    ``nextcall`` vencido (``_process_jobs``/``_acquire_one_job``/
    ``_run_job``/``_callback``) viven en la misma clase — igual que en la
    referencia. Ver docstring del módulo para el detalle de qué del runner
    de Odoo se portó y qué se excluyó deliberadamente."""

    # Enlace de _inherits (Odoo ir_actions_server_id, ir_cron.py:106-108):
    # Many2one required con ondelete='restrict' (≙ PROTECT). NO es herencia
    # multi-tabla — ver el docstring del módulo.
    ir_actions_server = fields.Many2one(
        IrActionsServer, on_delete=models.PROTECT, db_index=True,
        related_name='crons',
        help_text=(
            'Acción que este cron ejecuta (Odoo ir_actions_server_id, '
            '_inherits). El "qué ejecutar" —name, model_name, method_name— '
            'vive ahí y se delega; ir.cron sólo aporta la periodicidad.'
        ),
    )
    interval_number = fields.Integer(
        default=1,
        help_text='Repetir cada x (Odoo interval_number).',
    )
    interval_type = fields.Selection(
        max_length=8, choices=INTERVAL_CHOICES, default='months',
        help_text='Unidad del intervalo (Odoo interval_type).',
    )
    nextcall = fields.Datetime(
        default=timezone.now,
        help_text='Próxima fecha de ejecución planeada (Odoo nextcall).',
    )
    lastcall = fields.Datetime(
        null=True, blank=True,
        help_text='Última ejecución exitosa (Odoo lastcall).',
    )
    priority = fields.Integer(
        default=5,
        help_text=(
            'Prioridad: 0 = más alta, 10 = más baja (Odoo priority, '
            'consumida por el runner diferido para ordenar el polling).'
        ),
    )
    active = fields.Boolean(default=True, help_text='Odoo active.')
    user = fields.Many2one(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ir_crons',
        help_text=(
            'Usuario de ejecución (Odoo user_id — ahí required con '
            'default=env.user; aquí nullable porque no hay contexto de '
            'request implícito al registrar la tarea). El runner lo aplica '
            'con orm.environments.user_scope, así que get_current_user() '
            'dentro del método invocado lo devuelve. Caveat: IrRule.'
            'eval_context aún no cae a ese usuario — ver docstring del '
            'módulo.'
        ),
    )

    class Meta:
        db_table = 'ir_cron'
        ordering = ['ir_actions_server__name', 'id']
        verbose_name = 'Tarea programada'
        verbose_name_plural = 'Tareas programadas'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(interval_number__gt=0),
                name='ir_cron_interval_number_positivo',
            ),
        ]

    def __str__(self) -> str:
        return self.name

    # ---- Campos delegados (≙ _inherits de ir.actions.server) ----
    # Solo lectura, como el resto de delegaciones del árbol (product_product,
    # res_users, mail_mail). Para escribirlos se toca la acción servidor.

    @property
    def name(self):
        """El nombre de la acción (Odoo ``cron_name``, computado desde el
        ``name`` de la ``ir.actions.server`` delegada)."""
        return self.ir_actions_server.name

    @property
    def model_name(self):
        """El modelo técnico objetivo (delegado; Odoo ``model_id``)."""
        return self.ir_actions_server.model_name

    @property
    def method_name(self):
        """El método a invocar (delegado; ocupa el lugar del ``code`` de la
        referencia — ver el docstring de ``ir_actions.py``)."""
        return self.ir_actions_server.method_name

    def _compute_next(self):
        """Calcula el próximo ``nextcall`` avanzando por
        ``interval_number``×``interval_type`` desde el ``nextcall`` actual
        (réplica simplificada de ``_intervalTypes`` de Odoo — ver
        docstring del módulo). NO hace loop "hasta superar now()": esa
        política de recuperación de corridas perdidas es responsabilidad
        del runner diferido (``_reschedule_later`` en Odoo), no del
        registro de horario. Devuelve el valor calculado sin guardarlo —
        el runner decide cuándo persistirlo junto con ``lastcall``."""
        return _add_interval(self.nextcall, self.interval_number, self.interval_type)

    # ---- Runner: adquisición, ejecución y reprogramación de jobs --------
    # (== _acquire_one_job / _run_job / _process_jobs / _callback de Odoo,
    # ver docstring del módulo para el colapso deliberado frente a la
    # referencia.)

    @classmethod
    def _ready_q(cls):
        """Condición de "listo para correr" (== ``_get_ready_sql_condition``
        de Odoo, ir_cron.py:284-293, sin el ``OR`` de ``ir_cron_trigger`` —
        no portado, ver docstring del módulo): ``active`` y ``nextcall`` ya
        vencido."""
        return models.Q(active=True, nextcall__lte=timezone.now())

    @classmethod
    def _acquire_one_job(cls, job_id, using=DEFAULT_DB_ALIAS, *, include_not_ready=False):
        """Adquiere para actualización el job ``job_id`` sin bloquear si
        otro worker ya lo tiene (== ``_acquire_one_job`` de Odoo,
        ir_cron.py:308-388). ``FOR NO KEY UPDATE SKIP LOCKED`` vía
        ``select_for_update(skip_locked=True, no_key=True)`` — la misma
        capacidad de PostgreSQL que la referencia usa (ADR-028), no un lock
        de aplicación en Python. Debe llamarse dentro de una transacción
        (``transaction.atomic``) que el caller cierra tras ``_run_job()``;
        Django lo exige (``TransactionManagementError`` si no).

        ``include_not_ready=True`` (== Odoo ``method_direct_trigger``)
        adquiere el job aunque no esté listo todavía — no usado por el
        polling normal, disponible para un disparo manual futuro.

        Devuelve la instancia adquirida, o ``None`` si otro worker ya la
        tenía tomada o si dejó de estar lista entre el listado y la
        adquisición."""
        qs = (
            cls.objects.using(using)
            .select_for_update(skip_locked=True, no_key=True)
            .filter(pk=job_id)
        )
        if not include_not_ready:
            qs = qs.filter(cls._ready_q())
        return qs.first()

    def _reschedule(self, now):
        """Avanza ``nextcall`` hasta superar ``now`` y persiste junto con
        ``lastcall`` (== ``_reschedule_later`` de Odoo, ir_cron.py:634-654,
        sin el ajuste a la timezone de usuario — este monolito no tiene
        contexto de sesión por cron job, ver docstring del módulo sobre
        ``user``). ``lastcall`` se actualiza siempre, con éxito o con
        fallo — fiel a la referencia: ``_reschedule_later`` corre para
        ``FULLY_DONE`` y para ``FAILED`` por igual (ir_cron.py:445-448),
        aunque el ``help_text`` de Odoo en el campo diga "successfully"
        (ir_cron.py:119) — la implementación real no distingue.
        ``UPDATE ... WHERE pk=`` en vez de ``self.save()``: sólo toca las
        dos columnas que cambian, sin re-serializar el resto del row bajo
        el lock ya tomado por ``_acquire_one_job``."""
        nextcall = self.nextcall
        while nextcall <= now:
            nextcall = _add_interval(nextcall, self.interval_number, self.interval_type)
        type(self).objects.filter(pk=self.pk).update(nextcall=nextcall, lastcall=now)
        self.nextcall = nextcall
        self.lastcall = now

    def _callback(self):
        """Invoca el método delegado por la acción servidor (==
        ``_callback`` de Odoo, ir_cron.py:671-696). La referencia llama
        ``ir.actions.server.browse(id).run()``; en este árbol
        ``IrActionsServer.run()`` levanta ``NotImplementedError`` a
        propósito (el modo ``code`` no se evalúa, ver ``ir_actions.py``).
        La alternativa sancionada por este proyecto
        (``ir_actions.py:436-444``) es ``method_name``/``model_name``: el
        runner —este método— la invoca directamente, sin pasar por
        ``.run()``. Deja escapar la excepción del método invocado; quien la
        atrapa es ``_run_job()``.

        Corre bajo ``user_scope(self.user_id)`` — el equivalente del
        ``env = api.Environment(job_cr, job['user_id'], ...)`` de la
        referencia (ir_cron.py:481-483). ``user_id`` es el atributo de la FK
        de Django (el id crudo), no una consulta extra. Con ``user`` nulo el
        scope se fija a ``None``, que es el estado que ya tiene el proceso
        worker: poner el contextmanager de todos modos mantiene un solo
        camino y garantiza que el valor previo se **restaure** al salir, sin
        filtrar el usuario de un job al siguiente."""
        model = apps.get_model(self.model_name)
        method = getattr(model, self.method_name)
        with user_scope(self.user_id):
            method()

    def _run_job(self):
        """Ejecuta el callback de este cron ya adquirido (lock tomado) y
        reprograma su siguiente corrida — colapsa ``_process_job`` +
        ``_run_job`` de la referencia (ir_cron.py:396-568, ver docstring
        del módulo sobre la API de progreso no portada). Nunca deja escapar
        la excepción del callback — un fallo se loggea y de todos modos se
        reprograma (ver ``_reschedule``), para que un job que falla
        sistemáticamente no bloquee a los siguientes ni quede reintentando
        en bucle apretado."""
        now = timezone.now()
        try:
            self._callback()
        except Exception:  # noqa: BLE001 — un job no debe tumbar al runner
            _logger.exception('cron %r (id=%s) fallo', self.name, self.pk)
        self._reschedule(now)

    @classmethod
    def _process_jobs(cls, using=DEFAULT_DB_ALIAS):
        """Ejecuta todos los jobs listos en la base ``using`` (== combina
        ``_process_jobs`` + ``_process_jobs_loop`` de Odoo, ir_cron.py:
        187-230 — aquí en un único método porque no hay ``_check_version``/
        ``_check_modules_state`` que verificar antes del loop, ver
        docstring del módulo). Cada job se adquiere y corre en su propia
        transacción, igual que la referencia comitea por-job en
        ``_process_jobs_loop``. Devuelve el número de jobs procesados
        (adquiridos y ejecutados, con éxito o con fallo — un fallo cuenta
        como procesado; lo que no cuenta es un job que otro worker ya
        tenía tomado)."""
        ready_ids = list(
            cls.objects.using(using)
            .filter(cls._ready_q())
            .order_by('priority', 'id')
            .values_list('pk', flat=True)
        )
        processed = 0
        for job_id in ready_ids:
            with transaction.atomic(using=using):
                cron = cls._acquire_one_job(job_id, using=using)
                if cron is None:
                    _logger.debug('cron id=%s ya tomado por otro worker', job_id)
                    continue
                cron._run_job()
            processed += 1
        return processed
