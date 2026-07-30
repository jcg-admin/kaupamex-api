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

Adaptación clave — se DROPEA la delegación a ``ir.actions.server``
=====================================================================

Odoo modela ``ir.cron`` con ``_inherits = {'ir.actions.server':
'ir_actions_server_id'}`` (18 línea 68-70; 19 línea 104-108): el "qué
ejecutar" vive delegado en un modelo ``ir.actions.server`` aparte (código
Python arbitrario, llamada a método, etc.), y ``ir.cron`` solo añade la
periodicidad. Este monolito **no tiene** ningún modelo ``ir.actions.*``
(grep verificado: cero clases ``IrActions`` en ``src/addons`` — mismo
patrón de ausencia documentado en ``ir_filters.py`` para su ``action_id``).

Sin el modelo destino no hay FK fiel que portar. La adaptación fiel es
almacenar el objetivo directamente como **``model_name`` (Char) +
``method_name`` (Char)** — el runner (diferido, ver abajo) llamará
``getattr(apps.get_model(model_name), method_name)`` sobre el modelo
resuelto. Esto espeja cómo ``ir.filters.model_id`` y
``ir.attachment.res_model`` ya son ``Char`` plano en vez de una FK real
(mismo criterio: el "modelo técnico" no es una relación de Django, es un
string resuelto en runtime por la capa de negocio).

El campo Odoo ``cron_name`` (``Char``, ``compute='_compute_cron_name'``,
delegado del ``name`` de la acción servidor — 18/19 línea 109/71) se porta
como campo **local** ``name`` (no computado, directamente editable) —
adaptación forzada por el drop de la delegación: sin ``ir.actions.server``
no hay de dónde computar el nombre.

El runner del cron — DIFERIDO (Clausula 4, fuera de este slice)
=====================================================================

Esta portación modela **solo el registro de horario como dato** (qué
existe, cuándo debe correr próximamente). El *runner* real — el proceso
que hace polling de ``ir_cron`` con ``active=True AND nextcall <= now()``,
adquiere el job, lo ejecuta y reprograma ``nextcall`` — es un **nodo
consumidor separado** (worker/scheduler, análogo a
``IrCron._process_jobs``/``_acquire_one_job``/``_run_job`` de Odoo) que
**no se construye en este slice**. Se documenta explícitamente aquí y en
el docstring de clase para que quede trazable como alcance diferido, no
como omisión silenciosa.

Deliberadamente NO se porta (fuera de alcance de un registro de horario)
=====================================================================

- **``failure_count`` / ``first_failure_date`` + auto-desactivación tras
  fallos consecutivos** (18/19): pertenecen al ciclo de vida de EJECUCIÓN
  del job (qué hace el runner cuando el callback lanza una excepción), no
  al registro de horario. Candidato H-BASE cuando se construya el runner.
- **``ir.cron.trigger`` / ``ir.cron.progress``** (modelos satélite 18/19
  para triggers ad-hoc y progreso batch — ``_trigger``/``_commit_progress``):
  mecanismo de ejecución/observabilidad del runner, no de programación.
- **``_process_jobs``/``_acquire_one_job``/``_run_job``/``_callback`` y
  todo el locking ``FOR NO KEY UPDATE SKIP LOCKED``**: es el runner mismo
  (ver sección anterior) — explícitamente diferido.
- **``_notifydb`` (LISTEN/NOTIFY de PostgreSQL vía ``pg_notify``)**:
  mecanismo de wake-up específico de Postgres; MariaDB no tiene un
  equivalente directo y el runner (diferido) decidirá su propio esquema
  de polling/wake-up cuando se construya.

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
``calendar``/``datetime`` de la stdlib. El runner futuro es quien invoca
este método tras cada ejecución — este método NO hace loop "hasta superar
now()" (eso es ``_reschedule_later`` de Odoo, responsabilidad del runner
diferido, no del registro de horario).

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
``ir_sequence``/``ir_attachment``: el dueño es opcional a nivel de dato;
el runner (diferido) decide qué usuario de ejecución usar cuando esté
ausente (p. ej. un usuario de sistema).

Cross-app: ``user`` → ``settings.AUTH_USER_MODEL`` (Odoo ``user_id``).
"""
import calendar
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

import fields
import models

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
    """``ir.cron`` — registro de horario de una tarea programada.

    Modela SOLO el dato de programación (qué ejecutar + cada cuánto +
    próxima corrida). El runner que hace polling y ejecuta las tareas
    ``active=True`` con ``nextcall`` vencido es un componente separado,
    diferido fuera de este slice (ver docstring del módulo)."""

    name = fields.Char(
        max_length=256,
        help_text=(
            'Nombre de la tarea (Odoo cron_name — ahí computado desde el '
            'name de la ir.actions.server delegada; aquí campo local '
            'directo porque no se porta esa delegación, ver docstring '
            'del módulo).'
        ),
    )
    model_name = fields.Char(
        max_length=128,
        help_text=(
            'Modelo técnico objetivo, p. ej. "sale.SaleOrder" (adaptación '
            'del model_id delegado en ir.actions.server de Odoo — aquí '
            'Char plano, mismo criterio que ir_filters.model_id / '
            'ir_attachment.res_model: no es FK real, el runner diferido '
            'la resuelve con apps.get_model()).'
        ),
    )
    method_name = fields.Char(
        max_length=128,
        help_text=(
            'Nombre del método a invocar sobre model_name (adaptación: '
            'sustituye el code Python arbitrario de ir.actions.server de '
            'Odoo por una llamada directa a método, resuelta por el '
            'runner diferido).'
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
            'request implícito al registrar la tarea, ver docstring del '
            'módulo).'
        ),
    )

    class Meta:
        db_table = 'ir_cron'
        ordering = ['name', 'id']
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
