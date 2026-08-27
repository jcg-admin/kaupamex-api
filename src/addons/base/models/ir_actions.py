"""``ir.actions.*`` — la familia de acciones que el cliente puede disparar.

Adaptación de ``odoo/addons/base/models/ir_actions.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 1463 líneas). La referencia declara
**nueve** modelos en este archivo; aquí se portan los siete que tienen forma de
dato, y los dos restantes se declaran con su medición al final.

Una acción es "qué pasa cuando el usuario pulsa esto": abrir una ventana, ir a
una URL, ejecutar código en el servidor, cerrar el diálogo. La familia importa
más allá de su propio uso: **cinco archivos ya portados la esperan** —
``ir_cron`` (que allá delega su "qué ejecutar" en ``ir.actions.server``),
``ir_filters.action_id``, ``report_paperformat.report_ids``,
``res_company.external_report_layout_id`` e ``ir_embedded_actions`` entero
(H-API-142).

Cómo se traduce el ``_inherit`` de la referencia
================================================

Odoo usa aquí **herencia por prototipo**: ``ir.actions.act_window`` declara
``_inherit = ['ir.actions.actions']`` pero ``_table = 'ir_act_window'`` — copia
los campos del padre a una tabla propia. El equivalente exacto en Django es un
**modelo abstracto**, así que los campos comunes viven en ``IrActionsBase`` y
cada subtipo concreto los hereda con su propia tabla:

===========================  ======================  =====================
Modelo de la referencia      Tabla                   Aquí
===========================  ======================  =====================
``ir.actions.actions``       ``ir_actions``          ``IrActionsActions``
``ir.actions.act_window``    ``ir_act_window``       ``IrActionsActWindow``
``ir.actions.act_url``       ``ir_act_url``          ``IrActionsActUrl``
``ir.actions.client``        ``ir_act_client``       ``IrActionsClient``
``ir.actions.server``        ``ir_act_server``       ``IrActionsServer``
``ir.actions.act_window.view`` ``ir_act_window_view`` ``IrActionsActWindowView``
``ir.actions.todo``          ``ir_actions_todo``     ``IrActionsTodo``
``ir.actions.act_window_close`` ``ir_actions``       **proxy** de ``IrActionsActions``
===========================  ======================  =====================

La última fila es el caso interesante: ``act_window_close`` **comparte tabla**
con el padre (``_table = 'ir_actions'``) y sólo fija ``type``. En Django eso es
literalmente un ``proxy = True``: misma tabla, otra clase, otro default. Darle
tabla propia habría inventado una tabla que la referencia no tiene.

Detalles conservados que un port ingenuo pierde
===============================================

- **``path`` tiene tres reglas, no una.** Además del patrón
  ``[a-z][a-z0-9_-]*``, la referencia **reserva dos prefijos**: ``m-`` y
  ``action-``. Sin ellos, una acción puede reclamar una URL que el cliente ya
  usa para otra cosa. Se portan los tres chequeos con sus mensajes.
- **``_compute_views`` resuelve una precedencia de tres fuentes** —
  ``view_ids`` (explícito), ``view_mode`` (lista separada por comas) y
  ``view_id`` (vista de referencia). El orden importa: los modos declarados en
  ``view_ids`` van primero; de los que faltan, **si ``view_id`` es de uno de
  ellos, ése se adelanta**; el resto va con vista vacía. Ese adelanto es la
  línea que se pierde al portar "más o menos".
- **``mobile_view_mode``** cae a ``kanban``, y si ese modo no está disponible
  se usa el mismo que en pantalla ancha. Es un default con respaldo, no un
  valor fijo.
- **``limit = 80``** — el tamaño de página por defecto de la vista de lista.
- **``target`` no tiene los mismos valores en todos los subtipos**:
  ``act_window`` y ``client`` usan ``current``/``new``/``fullscreen``/``main``;
  ``act_url`` usa ``new``/``self``/``download``. Son vocabularios distintos y
  se declaran por separado.

Qué NO se porta, con su medición
================================

- **El motor de ejecución de ``ir.actions.server``** — sus seis modos
  (``object_write``, ``object_create``, ``object_copy``, ``code``,
  ``webhook``, ``multi``) se portan como **vocabulario**, porque son el dato
  que clasifica la acción. Lo que no se porta es el ``_run_action_*`` de cada
  uno: el modo ``code`` evalúa Python almacenado con ``safe_eval``. Es la
  misma decisión que ``ir_rule.domain_force`` (``api@020e965``) y por la misma
  razón: montar un evaluador sobre entrada almacenada es superficie de
  ejecución de código y exige decidir explícitamente el evaluador y su
  contexto. ``run()`` deja el punto de extensión declarado y levanta.
- **``model_id`` como FK a ``ir.model``.** **Actualizado** (porte de
  ``ir_model.py``): ``grep -rn "^class IrModel\b" src/`` → **1** clase.
  [PROVEN] La medición que justificaba el ``Char`` —**0** clases— dejó de ser
  cierta; se corrige aquí en vez de dejarla envejecer. El campo **sigue**
  siendo ``model_name`` (``Char``) en este pase: convertirlo a FK migra esta
  tabla, y eso va en su propio pase, igual que se decidió con
  ``ir_filters.action_id``. Mismo estado en ``ir_rule``, ``ir_filters`` e
  ``ir_attachment``.

  El **ancla de columna 0** no es cosmética: sin ella el grep cuenta también
  los docstrings que *citan* el comando —el de ``ir_rule.py`` ya lo hacía— y
  el auto-conteo de H-API-141 reaparece de forma transitiva, ahora entre
  archivos distintos. Una definición de clase empieza en la columna 0; una
  cita dentro de un docstring va indentada. El patrón anclado distingue las
  dos sin depender de excluir archivos a mano.
- **``ServerActionHistoryWizard`` e ``IrActionsServerHistory``** — registran
  qué acción servidor corrió y con qué resultado. Sin motor de ejecución no
  hay historial que registrar; entran con el motor, no antes.
- **``LoggerProxy``** — envuelve el logger para exponerlo al código evaluado
  del modo ``code``. Pertenece al evaluador que no se porta.
- **``params``/``params_store`` de ``ir.actions.client``** — un ``Binary``
  computado con inverse que serializa argumentos arbitrarios. Se porta
  ``params_store`` como ``Json``, que es lo que de verdad guarda, en vez de un
  binario opaco: aquí no hay que preservar el formato de pickle de nadie.
"""
import logging
import re

import fields
import models
from django.core.exceptions import ValidationError

from addons.base.models.res_groups import ResGroups
from addons.base.models.timestamped_mixin import TimeStampedModel

_logger = logging.getLogger(__name__)

#: ``VIEW_TYPES`` verbatim de ``ir_actions.py:401-408``.
VIEW_TYPES = [
    ('list', 'Lista'),
    ('form', 'Formulario'),
    ('graph', 'Gráfica'),
    ('pivot', 'Tabla dinámica'),
    ('calendar', 'Calendario'),
    ('kanban', 'Kanban'),
]

#: Patrón admitido para ``path`` — verbatim de la fuente.
PATH_PATTERN = re.compile(r'[a-z][a-z0-9_-]*')

#: Prefijos que la referencia reserva para el cliente.
RESERVED_PATH_PREFIXES = ('m-', 'action-')

BINDING_TYPE_CHOICES = [
    ('action', 'Acción'),
    ('report', 'Reporte'),
]


class IrActionsBase(TimeStampedModel):
    """Campos comunes de toda acción — el ``_inherit`` de la referencia.

    Abstracto porque allá la herencia es **por prototipo**: cada subtipo copia
    estos campos a su propia tabla en vez de compartirla.
    """

    name = fields.Char(max_length=255, verbose_name='Nombre de la acción')
    type = fields.Char(max_length=64, verbose_name='Tipo de acción')
    path = fields.Char(
        max_length=64, blank=True, default=None, unique=True, null=True,
        verbose_name='Ruta en la URL',
        help_text='Debe ser única (Odoo _path_unique). default=None, no '
                  "'': la referencia declara el campo sin default "
                  '(``path = fields.Char(...)``, odoo19c: ir_actions.py:70) '
                  'y un Char sin valor se escribe NULL en Odoo, no cadena '
                  'vacía — con NULL el UNIQUE admite múltiples acciones sin '
                  'ruta (H-API-332: default=\'\' colisionaba en la segunda '
                  'ir.actions.server creada sin path explícito).',
    )
    help = fields.Html(
        blank=True, default='', verbose_name='Descripción de la acción',
        help_text='Texto de ayuda opcional que describe la vista destino.',
    )
    binding_model_name = fields.Char(
        max_length=120, blank=True, default='', db_index=True,
        verbose_name='Modelo de anclaje',
        help_text='Odoo binding_model_id. Con valor, la acción aparece en la '
                  'barra lateral de ese modelo.',
    )
    binding_type = fields.Selection(
        max_length=16, choices=BINDING_TYPE_CHOICES, default='action',
        verbose_name='Tipo de anclaje')
    binding_view_types = fields.Char(
        max_length=64, default='list,form', verbose_name='Vistas de anclaje')

    class Meta:
        abstract = True

    def __str__(self):
        return self.name

    def clean(self):
        """``_check_path`` — patrón **y** los dos prefijos reservados."""
        super().clean()
        if not self.path:
            return
        if not PATH_PATTERN.fullmatch(self.path):
            raise ValidationError(
                'La ruta sólo admite minúsculas alfanuméricas, guion bajo y '
                'guion, y debe empezar por letra.'
            )
        for prefix in RESERVED_PATH_PREFIXES:
            if self.path.startswith(prefix):
                raise ValidationError("'%s' es un prefijo reservado." % prefix)


class IrActionsActions(IrActionsBase):
    """La acción genérica (``ir.actions.actions``, tabla ``ir_actions``)."""

    class Meta:
        db_table = 'ir_actions'
        ordering = ['name', 'id']
        verbose_name = 'Acción'
        verbose_name_plural = 'Acciones'


class IrActionsActWindowClose(IrActionsActions):
    """Cierra el diálogo actual (``ir.actions.act_window_close``).

    **Proxy**: la referencia le da ``_table = 'ir_actions'``, la misma tabla
    que el padre, y sólo fija el ``type``. Darle tabla propia habría inventado
    una que la fuente no tiene.
    """

    TYPE = 'ir.actions.act_window_close'

    class Meta:
        proxy = True
        verbose_name = 'Acción de cierre de ventana'
        verbose_name_plural = 'Acciones de cierre de ventana'

    def save(self, *args, **kwargs):
        if not self.type:
            self.type = self.TYPE
        return super().save(*args, **kwargs)


class IrActionsActWindow(IrActionsBase):
    """Abre una ventana sobre un modelo (``ir.actions.act_window``)."""

    TARGET_CHOICES = [
        ('current', 'Ventana actual'),
        ('new', 'Ventana nueva'),
        ('fullscreen', 'Pantalla completa'),
        ('main', 'Acción principal de la ventana actual'),
    ]

    domain = fields.Char(
        max_length=1024, blank=True, default='', verbose_name='Dominio',
        help_text='Filtrado opcional del destino, como expresión Python. '
                  'Este archivo NO lo evalúa — ver el docstring del módulo.',
    )
    context = fields.Json(
        default=dict, verbose_name='Contexto',
        help_text='Odoo context. Allá es texto de una expresión Python; aquí '
                  'es JSON, que es lo que de verdad se guarda.',
    )
    res_id = fields.Integer(
        null=True, blank=True, verbose_name='ID del registro',
        help_text="Sólo cuando view_mode es 'form'.",
    )
    res_model = fields.Char(
        max_length=120, db_index=True, verbose_name='Modelo destino')
    target = fields.Selection(
        max_length=16, choices=TARGET_CHOICES, default='current',
        verbose_name='Ventana destino')
    view_mode = fields.Char(
        max_length=120, default='list,form', verbose_name='Modos de vista',
        help_text="Lista separada por comas: 'form', 'list', 'calendar'…",
    )
    mobile_view_mode = fields.Char(
        max_length=32, default='kanban', verbose_name='Modo de vista móvil',
        help_text='Primer modo en pantallas pequeñas. Si no está entre los '
                  'disponibles, se usa el mismo que en pantalla ancha.',
    )
    usage = fields.Char(
        max_length=64, blank=True, default='', verbose_name='Uso')
    limit = fields.Integer(
        default=80, verbose_name='Límite',
        help_text='Tamaño de página por defecto de la vista de lista.',
    )
    groups = fields.Many2many(
        ResGroups, blank=True, related_name='act_window_ids',
        db_table='ir_act_window_group_rel', verbose_name='Grupos')
    filter = fields.Boolean(default=False, verbose_name='Filtro')
    cache = fields.Boolean(
        default=True, verbose_name='Caché de datos',
        help_text='Cachea los datos de lista, kanban y formulario para '
                  'acelerar la carga.',
    )

    class Meta:
        db_table = 'ir_act_window'
        ordering = ['name', 'id']
        verbose_name = 'Acción de ventana'
        verbose_name_plural = 'Acciones de ventana'

    @property
    def views(self):
        """Lista ordenada de ``(view_id, modo)`` — ``_compute_views``.

        Resuelve la precedencia de tres fuentes, y el orden es el de la
        fuente: primero los modos que ``view_ids`` declara explícitamente;
        después los de ``view_mode`` que falten, **adelantando el de
        ``view_id``** si está entre ellos; el resto, con vista vacía.
        """
        declared = [(v.view_id, v.view_mode) for v in self.view_ids.all()]
        got_modes = [mode for _vid, mode in declared]
        all_modes = [m for m in (self.view_mode or '').split(',') if m]
        missing = [m for m in all_modes if m not in got_modes]

        result = list(declared)
        reference = getattr(self, 'view_id', None)
        reference_type = getattr(reference, 'type', None)
        if missing and reference_type in missing:
            # El adelanto de view_id: la línea que se pierde al portar
            # "más o menos".
            missing.remove(reference_type)
            result.append((reference.pk, reference_type))
        result.extend((None, mode) for mode in missing)
        return result

    def resolve_mobile_view_mode(self):
        """``mobile_view_mode`` con su respaldo al modo de pantalla ancha."""
        available = [m for m in (self.view_mode or '').split(',') if m]
        if self.mobile_view_mode in available:
            return self.mobile_view_mode
        return available[0] if available else self.mobile_view_mode


class IrActionsActWindowView(TimeStampedModel):
    """Una vista concreta de una acción de ventana (``ir.actions.act_window.view``)."""

    sequence = fields.Integer(null=True, blank=True, verbose_name='Secuencia')
    view_id = fields.Integer(
        null=True, blank=True, verbose_name='Vista',
        help_text='Odoo view_id (Many2one a ir.ui.view). Entero mientras '
                  'ir_ui_view.py no esté portado.',
    )
    view_mode = fields.Selection(
        max_length=16, choices=VIEW_TYPES, verbose_name='Tipo de vista')
    act_window = fields.Many2one(
        IrActionsActWindow, on_delete=models.CASCADE, db_index=True,
        related_name='view_ids', verbose_name='Acción')
    multi = fields.Boolean(
        default=False, verbose_name='En varios documentos',
        help_text='Si está activo, la acción no aparece en la barra derecha '
                  'de un formulario.',
    )

    class Meta:
        db_table = 'ir_act_window_view'
        ordering = ['sequence', 'id']
        verbose_name = 'Vista de acción de ventana'
        verbose_name_plural = 'Vistas de acción de ventana'
        constraints = [
            # ``_unique_mode_per_action`` de la fuente.
            models.UniqueConstraint(
                fields=['act_window', 'view_mode'],
                name='ir_act_window_view_unique_mode_per_action'),
        ]

    def __str__(self):
        return f'{self.act_window_id}: {self.view_mode}'


class IrActionsActUrl(IrActionsBase):
    """Navega a una URL (``ir.actions.act_url``)."""

    TYPE = 'ir.actions.act_url'

    #: Vocabulario **distinto** al de ``act_window``: aquí no hay
    #: ``current``/``fullscreen``/``main``, y sí ``self`` y ``download``.
    TARGET_CHOICES = [
        ('new', 'Ventana nueva'),
        ('self', 'Esta ventana'),
        ('download', 'Descargar'),
    ]

    url = fields.Text(verbose_name='URL de la acción')
    target = fields.Selection(
        max_length=16, choices=TARGET_CHOICES, default='new',
        verbose_name='Destino de la acción')

    class Meta:
        db_table = 'ir_act_url'
        ordering = ['name', 'id']
        verbose_name = 'Acción de URL'
        verbose_name_plural = 'Acciones de URL'


class IrActionsClient(IrActionsBase):
    """Acción resuelta por el cliente (``ir.actions.client``)."""

    TYPE = 'ir.actions.client'

    TARGET_CHOICES = IrActionsActWindow.TARGET_CHOICES

    tag = fields.Char(
        max_length=120, verbose_name='Etiqueta de la acción de cliente',
        help_text='Identificador que el cliente resuelve a un componente.',
    )
    target = fields.Selection(
        max_length=16, choices=TARGET_CHOICES, default='current',
        verbose_name='Ventana destino')
    res_model = fields.Char(
        max_length=120, blank=True, default='', verbose_name='Modelo destino')
    context = fields.Json(default=dict, verbose_name='Contexto')
    params_store = fields.Json(
        default=dict, blank=True, verbose_name='Parámetros',
        help_text='Odoo params_store. Allá es Binary con un compute/inverse '
                  'que lo serializa; aquí es Json, que es lo que guarda.',
    )

    class Meta:
        db_table = 'ir_act_client'
        ordering = ['name', 'id']
        verbose_name = 'Acción de cliente'
        verbose_name_plural = 'Acciones de cliente'


class IrActionsServer(IrActionsBase):
    """Acción ejecutada en el servidor (``ir.actions.server``).

    Los seis modos se portan como **vocabulario** —clasifican la acción— pero
    el motor que los ejecuta no; ver el docstring del módulo.
    """

    TYPE = 'ir.actions.server'

    STATE_CHOICES = [
        ('object_write', 'Actualizar registro'),
        ('object_create', 'Crear registro'),
        ('object_copy', 'Duplicar registro'),
        ('code', 'Ejecutar código'),
        ('webhook', 'Enviar notificación webhook'),
        ('multi', 'Varias acciones'),
    ]

    #: ≙ ``usage`` (``odoo19c: ir_actions.py:608-611``) — lo que distingue una
    #: accion suelta de la que respalda a un ``ir.cron``. Lo escribe
    #: ``IrCron.save()`` al crear, igual que la fuente lo fija en ``create``
    #: (``ir_cron.py:137``). Sin este campo la accion de un cron era
    #: indistinguible de cualquier otra, y el filtro de la fuente —*"Used to
    #: filter menu and home actions from the user form"*— no tenia por donde.
    USAGE_CHOICES = [
        ('ir_actions_server', 'Acción de servidor'),
        ('ir_cron', 'Acción programada'),
    ]

    state = fields.Selection(
        max_length=16, choices=STATE_CHOICES, verbose_name='Tipo')
    usage = fields.Selection(
        max_length=20, choices=USAGE_CHOICES, default='ir_actions_server',
        verbose_name='Uso',
        help_text='Odoo usage. ir_cron cuando la accion respalda a una tarea '
                  'programada.',
    )
    sequence = fields.Integer(
        default=5, verbose_name='Secuencia',
        help_text='Orden de ejecución en una acción de tipo "varias".',
    )
    model_name = fields.Char(
        max_length=120, db_index=True, verbose_name='Modelo',
        help_text='Odoo model_id. Label del modelo; 0 clases IrModel en este '
                  'árbol.',
    )
    code = fields.Text(
        blank=True, default='', verbose_name='Código',
        help_text='Bloque Python del modo "code". Este archivo NO lo evalúa.',
    )
    # Adaptación de proyecto (sin análogo en la referencia): sustituye la
    # EVALUACIÓN de ``code`` por una llamada a método resuelta en runtime
    # (``getattr(apps.get_model(model_name), method_name)``). Vive aquí, y no
    # en ``ir.cron``, porque este es el modelo donde la referencia pone el
    # "qué ejecutar" — ``ir.cron`` sólo aporta la periodicidad y lo delega.
    method_name = fields.Char(
        max_length=128, blank=True, default='', verbose_name='Método',
        help_text='Método a invocar sobre model_name. Alternativa segura al '
                  'code Python del modo "code"; este archivo tampoco lo invoca.',
    )
    #: ≙ ``parent_id`` (``odoo19c: ir_actions.py:648``) — el enlace del modo
    #: ``multi``: una acción compuesta encadena a sus hijas. La fuente declara
    #: ``ondelete='cascade'`` e ``index=True``; los dos se conservan.
    #:
    #: El inverso ``child_ids`` (``:649-650``) es aquí ``related_name``: en
    #: Django la relación se declara una vez y el reverso lo da el ORM. Su
    #: ``domain`` y su ``copy=True`` NO se portan — el primero es filtro de
    #: vista y el segundo es semántica de ``copy()``, que este árbol resuelve
    #: en el serializer. Divergencia declarada, no omisión.
    parent = fields.Many2one(
        'self', on_delete=models.CASCADE, db_index=True,
        null=True, blank=True, related_name='child_ids',
        verbose_name='Acción padre',
        help_text='Odoo parent_id. Acción compuesta que encadena a ésta.',
    )

    class Meta:
        db_table = 'ir_act_server'
        ordering = ['sequence', 'name', 'id']
        verbose_name = 'Acción de servidor'
        verbose_name_plural = 'Acciones de servidor'

    # ---- Las dos acciones de apertura de la referencia -------------------

    def action_open_parent_action(self):
        """≙ ``action_open_parent_action`` (``odoo19c: ir_actions.py:1328-1335``).

        Devuelve el descriptor ``ir.actions.act_window`` que abre la accion
        padre. ``ir.cron`` delega aqui (``ir_cron.py:889-891``), que es por
        que el metodo vive en este modelo y no alli.

        Sin ``parent`` declarado —el estado hasta este pase— no habia a que
        apuntar y el metodo era una firma vacia.
        """
        return {
            'type': 'ir.actions.act_window',
            'target': 'current',
            'views': [[False, 'form']],
            'res_model': self.TYPE,
            'res_id': self.parent_id,
        }

    def action_open_scheduled_action(self):
        """≙ ``action_open_scheduled_action`` (``odoo19c: :1337-1344``).

        Abre el ``ir.cron`` que esta accion respalda. La fuente lo resuelve
        con ``self.ir_cron_ids.ids[0]``; aqui el inverso de la FK de
        ``IrCron`` se llama ``crons``, y **incluye los inactivos** sin hacer
        nada: el manager por defecto de Django no filtra, que es exactamente
        lo que la fuente pide con ``context={'active_test': False}``
        (``:641``).

        Devuelve ``None`` cuando la accion no respalda ningun cron — la
        fuente indexaria ``[0]`` y reventaria con ``IndexError``. Divergencia
        declarada: un descriptor que apunta a nada no es mas util que
        ninguno, y aqui el llamador es una vista React que sabe leer el
        ``None``.
        """
        cron = self.crons.first()
        if cron is None:
            return None
        return {
            'type': 'ir.actions.act_window',
            'target': 'current',
            'views': [[False, 'form']],
            'res_model': 'ir.cron',
            'res_id': cron.pk,
        }

    def run(self):
        """Punto de extensión del motor de ejecución.

        Levanta a propósito: el modo ``code`` evalúa Python almacenado, y
        quien conecte el motor decide con qué evaluador y con qué contexto
        (misma decisión que ``ir_rule.build_domain``).
        """
        raise NotImplementedError(
            'El motor de ir.actions.server no está portado; ver el docstring '
            'del módulo.'
        )


class IrActionsTodo(TimeStampedModel):
    """Paso pendiente de configuración (``ir.actions.todo``)."""

    STATE_OPEN = 'open'
    STATE_DONE = 'done'
    STATE_CHOICES = [
        (STATE_OPEN, 'Por hacer'),
        (STATE_DONE, 'Hecho'),
    ]

    action = fields.Many2one(
        IrActionsActions, on_delete=models.CASCADE, db_index=True,
        related_name='todos', verbose_name='Acción')
    sequence = fields.Integer(default=10, verbose_name='Secuencia')
    state = fields.Selection(
        max_length=8, choices=STATE_CHOICES, default=STATE_OPEN,
        verbose_name='Estado')
    name = fields.Char(
        max_length=255, blank=True, default='', verbose_name='Nombre')

    class Meta:
        db_table = 'ir_actions_todo'
        ordering = ['sequence', 'id']
        verbose_name = 'Tarea de configuración'
        verbose_name_plural = 'Tareas de configuración'

    def __str__(self):
        return self.name or f'todo #{self.pk}'
