"""``ir.ui.view`` — el registro de vistas y su árbol de herencia.

Adaptación de ``odoo/addons/base/models/ir_ui_view.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 3623 líneas — el archivo más grande de
``base``). Una vista es un XML que describe una pantalla; las vistas se
**heredan** entre sí, y el motor las combina aplicando parches ``<xpath/>``
sobre el árbol del padre.

Se porta el **registro y las reglas de herencia**; no el combinador de XML.

Qué desbloquea
==============

Cuatro archivos ya portados dejaron anotado que esperaban a éste:

- ``res_groups.py`` — ``view_access``, reverso del M2M de grupos;
- ``res_company.py`` — el diseño de documento externo;
- ``ir_actions.py`` — ``IrActionsActWindowView.view_id``;
- ``ir_model.py`` — ``IrModel.view_ids``;
- ``ir_actions_report.py`` — ``associated_view``.

De esos, **sólo el de ``res_groups`` se cierra solo**: llega por el
``related_name`` del M2M de aquí. Los otros cuatro llevan una columna ``Char``
o una propiedad ausente y su conversión migra su propia tabla, así que va en
su pase — mismo criterio que ``ir_filters.action_id``. Sus mediciones sí se
corrigen en este commit (regla de H-API-149).

Las tres reglas de herencia que el registro codifica
====================================================

Sin el combinador, lo que queda es lo que decide **qué vistas se combinan y en
qué orden** — y eso es dato, no XML:

1. **``mode``**: ``extension`` (por defecto) o ``primary``. La diferencia la
   explica la fuente y se conserva verbatim en el ``help_text``: en
   ``extension`` se busca la vista primaria más cercana por ``inherit_id`` y
   se le aplican **todas** las vistas que hereden de ella *con el mismo
   modelo*; en ``primary`` se resuelve la primaria entera —aunque use otro
   modelo— y luego se aplican los parches de ésta.
2. **El orden es ``priority`` y después ``id``**
   (``_get_inheriting_views``). No es cosmético: dos parches sobre el mismo
   nodo se aplican en ese orden y el segundo ve el resultado del primero.
   Cambiarlo produce pantallas distintas sin ningún error.
3. **``active`` filtra antes de combinar**: una vista hija desactivada no
   extiende a su padre, pero sigue existiendo y puede reactivarse. Por eso es
   un booleano y no un borrado.

Y una invariante SQL que **no** es redundante con lo anterior:
``CHECK (mode != 'extension' OR inherit_id IS NOT NULL)``. Una vista en modo
extensión que no extiende a nadie es un parche sin destino — se acepta hoy y
revienta al combinar, lejos de donde se creó.

Qué NO se porta, con su medición
================================

- **El combinador de XML**: ``_apply_inheritance_specs``, ``_apply_view_
  inheritance``, ``_combine_arch``, la resolución de ``<xpath expr=… position=
  …>``, ``NameManager`` y ``_check_xml``. Son ~700 líneas de cirugía ``lxml``
  sobre XML almacenado. Medido en este árbol: ``find src -name '*.xml'`` →
  **0** archivos [PROVEN]; las pantallas las declara React en ``ui``. Misma
  razón que ``ir_qweb.py`` (H-API-165), y aquí se suma que el resultado del
  combinador sólo lo consume el cliente web de Odoo.
- **``arch`` / ``arch_base`` como campos calculados sobre ``arch_db`` /
  ``arch_fs``**: leen del disco en modo desarrollo y aplican traducción de
  términos XML. Se portan las **columnas** (``arch_db``, ``arch_fs``,
  ``arch_prev``, ``arch_updated``) — que son el dato— y no los cómputos, que
  dependen del lector de archivos y del mecanismo de traducción de Odoo.
- **``get_view_arch_from_file``** y ``_hasclass``: lectura de la vista desde
  su archivo fuente y una extensión XPath. Ambos son del combinador.
- **``xml_id`` / ``model_data_id``**: dependen de ``ir.model.data``, tabla que
  existe desde ``api@b618a6b`` pero que nadie puebla. ``key`` **sí** se porta:
  es el identificador estable de una vista QWeb y no pasa por esa tabla.
- **``warning_info`` / ``invalid_locators``**: diagnósticos que el editor de
  vistas de Odoo muestra al validar el XML; sin combinador no hay qué validar.
- **``ResetViewArchWizard._compute_arch_diff``**: compone un diff HTML entre
  dos versiones del XML. El asistente **sí** se porta —los tres modos de
  reinicio son la decisión, y ésa es dato— sin el generador del diff.
"""
import logging

import fields
import models
from django.core.exceptions import ValidationError

from addons.base.models.res_groups import ResGroups
from addons.base.models.res_users import ResUsers
from addons.base.models.timestamped_mixin import TimeStampedModel

_logger = logging.getLogger(__name__)

#: Atributos de marcado que el editor en línea mueve con el nodo — verbatim.
MOVABLE_BRANDING = [
    'data-oe-model', 'data-oe-id', 'data-oe-field', 'data-oe-xpath',
    'data-oe-source-id',
]

#: Los cuatro modificadores que una vista puede declarar sobre un campo.
VIEW_MODIFIERS = ('column_invisible', 'invisible', 'readonly', 'required')

#: Los ocho tipos de vista, verbatim de la fuente.
VIEW_TYPE_CHOICES = [
    ('list', 'Lista'),
    ('form', 'Formulario'),
    ('graph', 'Gráfica'),
    ('pivot', 'Tabla dinámica'),
    ('calendar', 'Calendario'),
    ('kanban', 'Kanban'),
    ('search', 'Búsqueda'),
    ('qweb', 'QWeb'),
]

MODE_PRIMARY = 'primary'
MODE_EXTENSION = 'extension'
#: ``mode`` — ver el docstring del módulo sobre la diferencia entre los dos.
MODE_CHOICES = [
    (MODE_PRIMARY, 'Vista base'),
    (MODE_EXTENSION, 'Vista de extensión'),
]

RESET_SOFT = 'soft'
RESET_HARD = 'hard'
RESET_OTHER_VIEW = 'other_view'
#: Los tres modos de reinicio del asistente, verbatim.
RESET_MODE_CHOICES = [
    (RESET_SOFT, 'Restaurar la versión anterior (reinicio suave).'),
    (RESET_HARD, 'Reiniciar a la versión del archivo (reinicio duro).'),
    (RESET_OTHER_VIEW, 'Reiniciar a partir de otra vista.'),
]


class IrUiView(TimeStampedModel):
    """``ir.ui.view`` — una vista y su lugar en el árbol de herencia."""

    name = fields.Char(max_length=255, verbose_name='Nombre de la vista')
    model = fields.Char(
        max_length=255, blank=True, default='', db_index=True,
        verbose_name='Modelo',
        help_text='Modelo técnico que la vista muestra. Char plano, mismo '
                  'criterio que ir_rule.model_name.',
    )
    key = fields.Char(
        max_length=255, blank=True, default='', db_index=True,
        verbose_name='Clave',
        help_text='Identificador estable de una vista QWeb. NO pasa por '
                  'ir.model.data, por eso sí se porta.',
    )
    priority = fields.Integer(
        default=16, verbose_name='Secuencia',
        help_text='Orden de aplicación entre vistas hermanas. Menor = antes. '
                  'Ver el docstring del módulo: el orden cambia el resultado.',
    )
    type = fields.Selection(
        max_length=16, choices=VIEW_TYPE_CHOICES, blank=True, default='',
        verbose_name='Tipo de vista')
    arch_db = fields.Text(
        blank=True, default='', verbose_name='Arquitectura',
        help_text='El XML de la vista. Este archivo NO lo interpreta.')
    arch_fs = fields.Char(
        max_length=512, blank=True, default='',
        verbose_name='Archivo de origen',
        help_text='Archivo del que procede la vista; sirve para el reinicio '
                  'duro.',
    )
    arch_updated = fields.Boolean(
        default=False, verbose_name='Arquitectura modificada',
        help_text='Marcado, la vista se editó tras cargarse del archivo.')
    arch_prev = fields.Text(
        blank=True, default='', verbose_name='Arquitectura anterior',
        help_text='Copia del arch_db antes de la última escritura; sirve para '
                  'el reinicio suave.',
    )
    inherit_id = fields.Many2one(
        'self', on_delete=models.PROTECT, null=True, blank=True, db_index=True,
        related_name='inherit_children_ids', verbose_name='Vista heredada',
        help_text='ondelete restrict de la fuente: no se borra una vista de '
                  'la que otras heredan.',
        db_column='inherit_id',
    )
    groups = fields.Many2many(
        ResGroups, blank=True, db_table='ir_ui_view_group_rel',
        related_name='view_access', verbose_name='Grupos',
        help_text='Vacío = la vista aplica a todos. Con valor, sólo a los '
                  'usuarios de esos grupos. Este related_name es el '
                  'view_access que res_groups.py dejó anotado como pendiente.',
    )
    mode = fields.Selection(
        max_length=16, choices=MODE_CHOICES, default=MODE_PRIMARY,
        verbose_name='Modo de herencia',
        help_text='Sólo aplica si la vista hereda de otra. En extensión se '
                  'busca la primaria más cercana y se le aplican todas las '
                  'vistas que hereden de ella con el mismo modelo; en '
                  'primaria se resuelve la primaria entera —aunque use otro '
                  'modelo— y luego se aplican los parches de ésta.',
    )
    active = fields.Boolean(
        default=True, verbose_name='Activa',
        help_text='Si la vista es heredada: activa extiende siempre a su '
                  'padre; inactiva no lo extiende hoy pero puede reactivarse.',
    )

    class Meta:
        db_table = 'ir_ui_view'
        ordering = ['priority', 'name', 'id']
        verbose_name = 'Vista'
        verbose_name_plural = 'Vistas'
        constraints = [
            # ``_inheritance_mode``: una vista en modo extensión tiene que
            # extender a alguien, o es un parche sin destino.
            models.CheckConstraint(
                condition=(
                    ~models.Q(mode=MODE_EXTENSION)
                    | models.Q(inherit_id__isnull=False)
                ),
                name='ir_ui_view_inheritance_mode',
            ),
            # ``_qweb_required_key``: una vista QWeb necesita su clave.
            models.CheckConstraint(
                condition=~models.Q(type='qweb') | ~models.Q(key=''),
                name='ir_ui_view_qweb_required_key',
            ),
        ]
        indexes = [
            # ``_model_type_inherit_id``.
            models.Index(fields=['model', 'inherit_id'],
                         name='ir_ui_view_model_inherit'),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        """``_check_000_inheritance`` — no se admiten herencias recursivas.

        La fuente comenta que este chequeo va **antes** que los demás para no
        entrar en bucle infinito al combinar; aquí el orden lo da que sea lo
        primero de ``clean``.
        """
        super().clean()
        seen = set()
        node = self.inherit_id
        while node is not None:
            if node.pk == self.pk or node.pk in seen:
                raise ValidationError(
                    'No se pueden crear vistas heredadas recursivas.')
            seen.add(node.pk)
            node = node.inherit_id

    @property
    def root_view(self):
        """La vista primaria más cercana subiendo por ``inherit_id``.

        Es el punto de partida de la combinación en modo ``extension``.
        Devuelve ``self`` si ya es primaria.
        """
        node = self
        while node.mode == MODE_EXTENSION and node.inherit_id is not None:
            node = node.inherit_id
        return node

    def inheriting_views(self, include_inactive=False):
        """``_get_inheriting_views`` — las vistas que extienden a ésta.

        Recorrido transitivo, **ordenado por ``priority`` y luego ``id``** —
        ver el docstring del módulo: ese orden decide el resultado de la
        combinación, no sólo su presentación.

        Las condiciones de la fuente que se conservan: sólo hereda quien
        declara ``mode='extension'``, y sólo si su ``model`` **coincide** con
        el del padre (``coalesce(model,'') = coalesce(parent.model,'')``); una
        extensión sobre otro modelo no entra en esta rama.
        """
        collected = []
        seen = {self.pk}
        frontier = [self]
        manager = type(self).objects
        while frontier:
            parent_ids = [view.pk for view in frontier]
            children = manager.filter(
                inherit_id__in=parent_ids, mode=MODE_EXTENSION,
            ).order_by('priority', 'id')
            if not include_inactive:
                children = children.filter(active=True)
            frontier = []
            for child in children:
                if child.pk in seen:
                    continue
                # ``coalesce(model,'') = coalesce(parent.model,'')`` — un
                # ``model`` vacío casa con otro vacío, no con cualquiera.
                if (child.model or '') != (child.inherit_id.model or ''):
                    continue
                seen.add(child.pk)
                collected.append(child)
                frontier.append(child)
        return collected


class IrUiViewCustom(TimeStampedModel):
    """``ir.ui.view.custom`` — la personalización de una vista por un usuario.

    ``_order = 'create_date desc, id desc'`` en la fuente, con el comentario
    que explica por qué: *"search(limit=1) should return the last
    customization"*. Se conserva el orden descendente por creación, porque un
    orden ascendente devolvería la personalización **más vieja** al pedir una
    sola — un fallo silencioso en el que la vista guardada nunca se ve.
    """

    ref_id = fields.Many2one(
        IrUiView, on_delete=models.CASCADE, db_index=True,
        related_name='custom_ids', verbose_name='Vista original',
        db_column='ref_id',
    )
    user = fields.Many2one(
        ResUsers, on_delete=models.CASCADE, db_index=True,
        related_name='custom_views', verbose_name='Usuario')
    arch = fields.Text(verbose_name='Arquitectura de la vista')

    class Meta:
        db_table = 'ir_ui_view_custom'
        ordering = ['-created_at', '-id']
        verbose_name = 'Vista personalizada'
        verbose_name_plural = 'Vistas personalizadas'
        indexes = [
            # ``_user_id_ref_id``.
            models.Index(fields=['user', 'ref_id'],
                         name='ir_ui_view_custom_user_ref'),
        ]

    def __str__(self):
        return f'{self.ref_id_id} / {self.user_id}'


class ResetViewArchWizard(models.Model):
    """``reset.view.arch.wizard`` — comparar y reiniciar la vista.

    Transitorio en la fuente; abstracto aquí, como el resto de asistentes que
    este árbol porta. Lo que aporta es la **decisión de los tres modos**, que
    es dato; el diff HTML entre versiones no se porta (ver el docstring del
    módulo).
    """

    class Meta:
        abstract = True

    @staticmethod
    def source_arch_for(view, reset_mode, compare_view=None):
        """De dónde sale el XML con el que se reinicia, según el modo.

        - ``soft``: de ``arch_prev``, la copia previa a la última escritura;
        - ``hard``: del archivo de origen (``arch_fs``) — **no** se lee aquí,
          se devuelve la ruta para que lo haga quien tenga el disco;
        - ``other_view``: del ``arch_db`` de la vista con la que se compara.

        Devuelve ``(origen, valor)`` para que el llamador sepa **qué** recibió
        y no tenga que adivinarlo por el contenido.
        """
        if reset_mode == RESET_SOFT:
            return ('arch_prev', view.arch_prev)
        if reset_mode == RESET_HARD:
            return ('arch_fs', view.arch_fs)
        if reset_mode == RESET_OTHER_VIEW:
            if compare_view is None:
                raise ValidationError(
                    'El modo "otra vista" requiere una vista de comparación.')
            return ('arch_db', compare_view.arch_db)
        raise ValidationError(f'Modo de reinicio desconocido: {reset_mode!r}.')

    @staticmethod
    def check_comparable(views):
        """``default_get`` — no se comparan más de dos vistas."""
        if len(views) > 2:
            raise ValidationError('No se pueden comparar más de dos vistas.')
        return True
