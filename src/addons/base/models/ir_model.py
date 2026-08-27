"""``ir.model`` y su familia — el registro reflejado de modelos y campos.

Adaptación de ``odoo/addons/base/models/ir_model.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 2717 líneas). Es el archivo que
**refleja el código en filas**: por cada modelo declarado en Python hay una
fila en ``ir_model``, por cada campo una en ``ir_model_fields``, y sobre esas
filas cuelgan los permisos (``ir.model.access``), las reglas de fila
(``ir.rule``), las restricciones SQL y los identificadores externos.

Diez clases, en el orden de la fuente
=====================================

============================== ===== ==========================================
Clase                          Línea Qué es
============================== ===== ==========================================
``Base``                         192 abstracto raíz; todo modelo lo hereda
``Unknown``                      198 sustituto de un comodelo desconocido
``IrModel``                      207 una fila por modelo
``IrModelFields``                508 una fila por campo
``IrModelInherit``              1422 el árbol de herencia entre modelos
``IrModelFieldsSelection``      1507 los valores de un campo Selection
``IrModelConstraint``           1850 restricciones e índices SQL rastreados
``IrModelRelation``             2006 tablas intermedias de los Many2many
``IrModelAccess``               2072 permisos CRUD por modelo y grupo
``IrModelData``                 2218 identificadores externos (XML IDs)
============================== ===== ==========================================

``Base`` es degenerado en Django —``models.Model`` ya cumple el papel de raíz
implícita— pero se porta igual: existe para que un ``_inherit = 'base'`` de la
referencia tenga a qué apuntar, y borrarlo dejaría el mapa incompleto sin
ganar nada.

Qué desbloquea este archivo
===========================

Cuatro archivos ya portados llevan el modelo objetivo como ``Char`` plano
esperando precisamente a esta clase: ``ir_rule.model_name``,
``ir_actions.IrActionsActWindow.res_model``, ``ir_filters.model_id`` y
``ir_embedded_actions.parent_res_model``. Su medición —
``grep -rn "^class IrModel\\b" src/`` → **0**— deja de ser cierta con este
commit y se corrige en los mismos archivos, no después (regla operativa de
H-API-149). **La conversión de esas columnas a FK real no entra aquí**: cada
una migra su propia tabla, y eso va en su pase, igual que se decidió con
``ir_filters.action_id``.

``FIELD_TYPES`` se **deriva**, no se declara
============================================

La referencia escribe ``FIELD_TYPES = [(key, key) for key in
sorted(fields.Field._by_type__)]`` (línea 505): la lista sale del **registro
de campos del ORM**, no de un literal. Aquí se hace lo mismo contra el
registro que este árbol sí tiene —``orm.fields.__all__``— convirtiendo el
nombre de clase a la clave snake_case de Odoo (``Many2oneReference`` →
``many2one_reference``, ``PropertiesDefinition`` → ``properties_definition``).

Delta medido y declarado: la referencia declara **19** claves de tipo
distintas (``grep -rh "^    type = " odoo/orm/fields*.py | sort -u``), y esta
derivación produce **20**. La diferencia es exactamente ``image``: allá
``Image`` hereda de ``Binary`` y **reusa** la clave ``binary``, mientras que
aquí ``fields.Image`` es ``ImageField`` y ``fields.Binary`` es
``BinaryField`` — dos columnas distintas de verdad. La clave extra describe el
sustrato real; no es un descuido de la derivación.

El mapa de alias es muchos-a-uno: la reflexión no puede invertirlo
=================================================================

``_reflect_fields`` de la referencia lee ``model._fields[name].type`` y guarda
esa clave. Aquí no existe ese atributo: un campo Django sólo sabe su tipo
Django. Y el mapa de alias **colapsa** tipos distintos de Odoo sobre la misma
clase — medido en ``orm/fields_textual.py:11-12`` (``Text`` y ``Html`` son
ambos ``TextField``) y ``orm/fields_selection.py:9`` (``Selection`` es
``CharField``, como ``Char``).

Consecuencia: **el inverso del mapa no existe**. ``reflect_fields`` deriva el
``ttype`` del tipo interno de Django (``get_internal_type()``) con un mapa
declarado, y recupera ``selection`` sólo porque ``field.choices`` lo delata.
Un ``html`` reflejado saldrá como ``text``: la distinción se pierde en el
sustrato y no se inventa aquí.

Medido sobre el mapa declarado: de las **20** claves de ``FIELD_TYPES``, la
reflexión puede producir **14**. Las **6** inalcanzables, con su motivo:

===================== ==========================================================
Clave                 Por qué la reflexión nunca la emite
===================== ==========================================================
``html``              colapsa en ``text`` (mismo ``TextField``)
``one2many``          es el reverso de un FK; ``reflect_fields`` lo salta
``reference``         ``GenericForeignKey``: no es campo concreto
``many2one_reference`` ídem
``properties``        es ``JSONField``; sale como ``json``
``properties_definition`` ídem
===================== ==========================================================

Que una clave sea inalcanzable **no** la saca del vocabulario: una fila
escrita a mano (o por un cargador futuro) sí puede declararla, y quitarla de
``FIELD_TYPES`` haría que ese valor legítimo fuera inválido. El límite es de
la reflexión, no del campo.

``view_ids`` — cerrado, ya no es un pendiente
=============================================

Este archivo dejó ``view_ids`` en la lista de omisiones con su medición
(``^class IrUiView\\b`` → **0** clases). Tras portar ``ir_ui_view.py`` esa
medición da **1** [PROVEN] y la propiedad se implementó abajo — **no** bastaba
con corregir la cifra: el hueco tenía un cuerpo de cinco líneas esperando, y
dejarlo pendiente por inercia habría sido deuda gratuita.

Qué NO se porta, con su medición
================================

- **La maquinaria de campos manuales** (``_add_manual_models``,
  ``_instanciate``, ``make_compute``, ``_reflect_model``… con su
  ``safe_eval``): crea **clases de modelo en caliente** a partir de filas de
  ``ir_model``. Django construye su registro al importar y lo congela
  (``apps.populate``); no hay equivalente, y montarlo significaría un
  metaregistro paralelo al de Django. La reflexión que sí cabe es la
  **inversa** —del registro de Django a filas—, que es la que se porta.
- **``_module_data_uninstall`` / ``unlink`` de ``IrModelConstraint`` y
  ``IrModelRelation``**: emiten ``DROP TABLE`` / ``ALTER TABLE ... DROP
  CONSTRAINT`` sobre el esquema vivo al desinstalar un módulo. En este árbol
  el esquema lo gobiernan las migraciones de Django; DDL fuera de ellas deja
  la tabla ``django_migrations`` mintiendo. Las dos clases se portan como
  **registro** —que es lo que aporta trazabilidad— sin el ejecutor de DDL.
- **``_get_access_groups``** de ``IrModelAccess``: devuelve un objeto de
  expresión de grupos de ``res.groups._get_group_definitions()``. Ese
  constructor no está portado —``grep -rn "_get_group_definitions" src/`` →
  **0**—; ``res_groups.py`` porta la implicación transitiva (``_closure``) y
  los disjuntos, no el álgebra de expresiones. ``group_names_with_access`` sí
  se porta, que es la parte consultable.
- **La autorización efectiva sigue siendo por capacidad (DEC-11).**
  ``ir.model.access`` se porta como **dato** —el permiso CRUD declarado por
  modelo y grupo—, no como el gate que corre en cada request: ese es
  ``HasCapability``, fail-closed. Portar la tabla no cambia quién decide.

Los enganches que Enterprise usa sobre esta familia
===================================================

Medido sobre ``19.x/odoo19-enterprise-main``, clases con ``_inherit`` a uno de
estos modelos, cruzado con lo que ``odoo19c: ir_model.py`` declara: seis
enganches que aquí no existían por su nombre. Uno se abrió; los otros cinco
caen dentro de divergencias ya declaradas arriba, y se nombran para que no
haya que volver a medirlo.

======================================== ====================================
Enganche                                 Desenlace
======================================== ====================================
``IrModelFields._reflect_field_params``  **portado** — se extrajo del cuerpo
                                         de ``reflect_fields``, que lo tenía
                                         en línea. Es el único que era un
                                         hueco de verdad.
``IrModelFields._check_name``            **divergencia de mecanismo** — el
                                         enganche de validación de Django es
                                         ``clean()``, y ahí está portado con
                                         su cita. Un addon lo extiende por
                                         ``clean()``, no por ese nombre.
``IrModelFields._compute_display_name``  **divergencia de mecanismo** — aquí
                                         es ``__str__``. Y de **contenido**:
                                         la fuente devuelve
                                         ``"<descripción> (<modelo>)"``;
                                         aquí, ``"<modelo>.<campo>"``, que es
                                         el identificador y no la etiqueta.
``IrModelFields._instanciate_attrs``     **divergencia declarada** — es la
                                         maquinaria de campos manuales
                                         (``_instanciate``), primera viñeta
                                         de la sección de arriba.
``IrModel.name_create``                  **divergencia declarada** — crea una
                                         fila ``x_...`` para que
                                         ``_add_manual_models`` la instancie.
                                         Sin esa maquinaria la fila no la
                                         lee nadie.
``IrModelData._build_insert_xmlids_values`` **divergencia de mecanismo** — es
                                         la lista de columnas del ``INSERT
                                         ... ON CONFLICT`` en crudo del
                                         cargador. Aquí ``set_xmlid`` escribe
                                         con ``update_or_create``: el
                                         diccionario existe, pero es el
                                         ``defaults`` del ORM y no
                                         marcadores de posición de SQL.
                                         Darle ese nombre a algo con otra
                                         forma de retorno engañaría a quien
                                         lo herede.
======================================== ====================================

*Métrica:* nombres declarados en el cuerpo de las clases de Enterprise que
heredan de estos modelos, intersectados con los que ``odoo19c: ir_model.py``
declara y este archivo no.
*Ciega a:* un enganche que Enterprise consuma sin declararlo (por
``super()`` de un tercero), y a la distinción entre *"aquí se llama distinto"*
y *"aquí no existe"* — ésa la resolvió la lectura, no el conteo.
"""
import logging
import re

import fields
import models
from django.apps import apps
from django.core.exceptions import ValidationError

from addons.base.models.ir_module import IrModule
from addons.base.models.ir_ui_view import IrUiView
from addons.base.models.res_groups import ResGroups
from addons.base.models.timestamped_mixin import TimeStampedModel
from exceptions import AccessError
from orm import registry
from orm.environments import get_current_user, is_su
from orm.fields import __all__ as _FIELD_NAMES

_logger = logging.getLogger(__name__)

#: Separa el ``CamelCase`` del nombre exportado para reconstruir la clave
#: snake_case de Odoo: ``Many2oneReference`` → ``many2one_reference``.
_CAMEL_BOUNDARY = re.compile(r'(?<=[a-z0-9])(?=[A-Z])')


def _type_key(exported_name):
    """Nombre de clase exportado → clave de tipo al estilo Odoo."""
    return _CAMEL_BOUNDARY.sub('_', exported_name).lower()


#: Derivado del registro de campos, igual que ``fields.Field._by_type__`` en la
#: referencia. Ver el docstring del módulo para el delta medido (``image``).
FIELD_TYPES = sorted((_type_key(name), _type_key(name)) for name in _FIELD_NAMES)

#: Tipo interno de Django → clave de tipo Odoo, para la reflexión inversa.
#: Declarado, no derivado: el mapa de alias es muchos-a-uno y no se puede
#: invertir (ver el docstring del módulo).
DJANGO_TYPE_TO_TTYPE = {
    'AutoField': 'integer',
    'BigAutoField': 'integer',
    'BigIntegerField': 'integer',
    'BinaryField': 'binary',
    'BooleanField': 'boolean',
    'CharField': 'char',
    'DateField': 'date',
    'DateTimeField': 'datetime',
    'DecimalField': 'monetary',
    'EmailField': 'char',
    'FileField': 'binary',
    'FloatField': 'float',
    'ForeignKey': 'many2one',
    'ImageField': 'image',
    'IntegerField': 'integer',
    'JSONField': 'json',
    'ManyToManyField': 'many2many',
    'OneToOneField': 'many2one',
    'PositiveIntegerField': 'integer',
    'PositiveSmallIntegerField': 'integer',
    'SlugField': 'char',
    'SmallIntegerField': 'integer',
    'TextField': 'text',
    'URLField': 'char',
    'UUIDField': 'char',
}

STATE_MANUAL = 'manual'
STATE_BASE = 'base'
#: ``[('manual', 'Custom Object'), ('base', 'Base Object')]`` de la fuente.
STATE_CHOICES = [
    (STATE_MANUAL, 'Objeto personalizado'),
    (STATE_BASE, 'Objeto base'),
]

#: Modos de acceso de ``ir.model.access``, en el orden de la fuente.
ACCESS_MODES = ('read', 'write', 'create', 'unlink')

#: Las cuatro cabeceras del error de acceso — ``ACCESS_ERROR_HEADER``
#: (``odoo19c: odoo/addons/base/models/ir_model.py:25-31``), traducidas al
#: idioma de la prosa de este árbol. La fuente las declara *in extenso* «so
#: they are properly exported in translation terms»; aquí se conserva esa
#: forma —una por operación, no una plantilla con el verbo interpolado— por la
#: misma razón: un traductor necesita la frase entera.
ACCESS_ERROR_HEADER = {
    'read': 'No tiene permiso para consultar registros de «%(document_kind)s» '
            '(%(document_model)s).',
    'write': 'No tiene permiso para modificar registros de «%(document_kind)s» '
             '(%(document_model)s).',
    'create': 'No tiene permiso para crear registros de «%(document_kind)s» '
              '(%(document_model)s).',
    'unlink': 'No tiene permiso para borrar registros de «%(document_kind)s» '
              '(%(document_model)s).',
}
ACCESS_ERROR_GROUPS = ('Esta operación está permitida para los siguientes '
                       'grupos:\n%(groups_list)s')
ACCESS_ERROR_NOGROUP = 'Ningún grupo permite actualmente esta operación.'
ACCESS_ERROR_RESOLUTION = ('Contacte a su administrador para solicitar el '
                           'acceso si lo necesita.')


class Base(models.Model):
    """``base`` — la raíz implícita de todo modelo.

    Degenerado en Django (``models.Model`` ya lo es). Se porta para que las
    citas ``_inherit = 'base'`` de la referencia tengan destino.
    """

    class Meta:
        abstract = True


class Unknown(models.Model):
    """``_unknown`` — sustituto de un campo relacional sin comodelo conocido."""

    class Meta:
        abstract = True


class IrModel(TimeStampedModel):
    """``ir.model`` — una fila por modelo declarado."""

    name = fields.Char(
        max_length=255, verbose_name='Descripción del modelo',
        help_text='Odoo name (traducible allá).',
    )
    model = fields.Char(
        max_length=255, default='x_', unique=True, db_index=True,
        verbose_name='Modelo',
        help_text='Nombre técnico, p. ej. "base.IrModel".',
    )
    order = fields.Char(
        max_length=255, default='id', verbose_name='Orden',
        help_text='Expresión de ordenamiento; p. ej. "x_sequence asc, id desc".',
    )
    info = fields.Text(blank=True, default='', verbose_name='Información')
    state = fields.Selection(
        max_length=16, choices=STATE_CHOICES, default=STATE_MANUAL,
        verbose_name='Tipo',
    )
    abstract = fields.Boolean(default=False, verbose_name='Modelo abstracto')
    transient = fields.Boolean(default=False, verbose_name='Modelo transitorio')
    fold_name = fields.Char(
        max_length=120, blank=True, default='', verbose_name='Campo de plegado',
        help_text='En una vista Kanban por columnas de este modelo, el campo '
                  'booleano que decide qué columna se pliega por defecto.',
    )

    class Meta:
        db_table = 'ir_model'
        ordering = ['model']
        verbose_name = 'Modelo'
        verbose_name_plural = 'Modelos'

    def __str__(self):
        return self.model

    @property
    def django_model(self):
        """La clase Django que esta fila refleja, o ``None`` si ya no existe.

        Una fila puede sobrevivir al modelo que reflejaba (módulo desinstalado,
        clase renombrada); devolver ``None`` en vez de reventar es lo que
        permite que ``count`` y ``inherited_model_ids`` sigan siendo
        consultables sobre un registro obsoleto.
        """
        try:
            app_label, model_name = self.model.split('.', 1)
        except ValueError:
            return None
        try:
            return apps.get_model(app_label, model_name)
        except LookupError:
            return None

    @property
    def count(self):
        """``_compute_count`` — total de filas, archivadas incluidas.

        La fuente salta los abstractos y los que no tienen tabla propia
        (``not records._auto``); aquí eso es ``Meta.abstract`` y
        ``Meta.managed``.
        """
        model = self.django_model
        if model is None or model._meta.abstract or not model._meta.managed:
            return 0
        return model._base_manager.count()

    @property
    def inherited_model_ids(self):
        """``_inherited_models`` — los modelos que este extiende.

        En la referencia son los ``_inherits`` (herencia por delegación). Aquí
        los padres abstractos del MRO, que es la misma relación: el modelo
        hereda de ellos sin ser ellos.
        """
        model = self.django_model
        if model is None:
            return type(self).objects.none()
        parent_labels = [
            f'{base._meta.app_label}.{base._meta.object_name}'
            for base in model.__mro__[1:]
            if isinstance(base, type)
            and issubclass(base, models.Model)
            and base is not models.Model
            and getattr(base, '_meta', None) is not None
        ]
        return type(self).objects.filter(model__in=parent_labels)

    @property
    def view_ids(self):
        """``_view_ids`` — las vistas declaradas sobre este modelo.

        ``compute`` sin ``store`` en la referencia → propiedad aquí. Cerrado
        con el porte de ``ir_ui_view.py``; era el hueco que este archivo dejó
        anotado.
        """
        return IrUiView.objects.filter(model=self.model)

    @property
    def modules(self):
        """``_in_modules`` — apps en que el modelo está definido.

        La referencia cruza los XML IDs contra los módulos instalados. Aquí el
        dueño es el ``app_label`` de Django, que es dato de primera mano y no
        necesita el cruce.
        """
        model = self.django_model
        return model._meta.app_label if model is not None else ''

    def clean(self):
        """``_check_model_name`` — un modelo personalizado se nombra ``x_``."""
        super().clean()
        if self.state == STATE_MANUAL and not self.model.startswith('x_'):
            raise ValidationError(
                'Los modelos personalizados deben tener un nombre que empiece '
                'por "x_".'
            )

    @classmethod
    def reflect_models(cls, app_labels=None):
        """Refleja el registro de Django en filas — inverso de ``_reflect_model``.

        La referencia refleja desde su propio registro; aquí la fuente es
        ``apps.get_models()``. Devuelve ``(creadas, actualizadas)``.

        No borra filas huérfanas: una fila cuyo modelo desapareció es
        justamente la que ``django_model`` devuelve ``None``, y perderla borra
        con ella sus permisos y reglas. La limpieza es una decisión de
        desinstalación, no de reflexión.
        """
        created = updated = 0
        for model in apps.get_models(include_auto_created=True):
            if app_labels and model._meta.app_label not in app_labels:
                continue
            label = f'{model._meta.app_label}.{model._meta.object_name}'
            values = {
                'name': str(model._meta.verbose_name),
                'state': STATE_BASE,
                'abstract': model._meta.abstract,
                'transient': not model._meta.managed,
                'order': ', '.join(model._meta.ordering) or 'id',
            }
            _row, was_created = cls.objects.update_or_create(
                model=label, defaults=values)
            created += was_created
            updated += not was_created
        return created, updated


class IrModelFields(TimeStampedModel):
    """``ir.model.fields`` — una fila por campo."""

    name = fields.Char(
        max_length=63, default='x_', db_index=True,
        verbose_name='Nombre del campo',
        help_text='63 caracteres es el límite del identificador en el motor.',
    )
    model = fields.Char(
        max_length=255, db_index=True, verbose_name='Nombre del modelo',
        help_text='Nombre técnico del modelo dueño del campo.',
    )
    model_id = fields.Many2one(
        IrModel, on_delete=models.CASCADE, db_index=True,
        related_name='field_id', verbose_name='Modelo',
        help_text='Odoo lo llama field_id (One2many en singular, contra su '
                  'propia convención _ids); se conserva ese nombre en el '
                  'reverso.',
        db_column='model_id',
    )
    relation = fields.Char(
        max_length=255, blank=True, default='', verbose_name='Modelo relacionado',
        help_text='En un campo relacional, el nombre técnico del destino.',
    )
    relation_field = fields.Char(
        max_length=63, blank=True, default='',
        verbose_name='Campo de la relación inversa',
        help_text='En un One2many, el campo del destino que implementa el '
                  'Many2one opuesto.',
    )
    relation_field_id = fields.Many2one(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='inverse_of', verbose_name='Campo de relación',
        help_text='Odoo lo computa con store=True; aquí es columna real igual, '
                  'poblada por la reflexión.',
        db_column='relation_field_id',
    )
    field_description = fields.Char(
        max_length=255, blank=True, default='', verbose_name='Etiqueta del campo')
    help = fields.Text(blank=True, default='', verbose_name='Ayuda del campo')
    ttype = fields.Selection(
        max_length=32, choices=FIELD_TYPES, verbose_name='Tipo de campo')
    # ``selection_ids`` es el One2many de la fuente: llega como reverso desde
    # ``IrModelFieldsSelection.field`` (``related_name='selection_ids'``).
    copied = fields.Boolean(
        default=True, verbose_name='Copiado',
        help_text='Si el valor se copia al duplicar el registro.',
    )
    related = fields.Char(
        max_length=255, blank=True, default='',
        verbose_name='Definición del campo relacionado',
        help_text='Lista de nombres separados por punto.',
    )
    related_field_id = fields.Many2one(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='related_from', verbose_name='Campo relacionado',
        db_column='related_field_id',
    )
    required = fields.Boolean(default=False, verbose_name='Requerido')
    readonly = fields.Boolean(default=False, verbose_name='Sólo lectura')
    index = fields.Boolean(default=False, verbose_name='Indexado')
    translate = fields.Selection(
        max_length=16, blank=True, default='',
        choices=[
            ('standard', 'Traducir como un todo'),
            ('html_translate', 'Traducir términos HTML'),
            ('xml_translate', 'Traducir términos XML'),
        ],
        verbose_name='Traducible',
    )
    company_dependent = fields.Boolean(
        default=False, verbose_name='Depende de la company',
        help_text='Terminología L0/L1: company, nunca tenant.',
    )
    size = fields.Integer(null=True, blank=True, verbose_name='Tamaño')
    state = fields.Selection(
        max_length=16,
        choices=[(STATE_MANUAL, 'Campo personalizado'), (STATE_BASE, 'Campo base')],
        default=STATE_MANUAL, db_index=True, verbose_name='Tipo',
    )
    on_delete = fields.Selection(
        max_length=16,
        choices=[
            ('cascade', 'En cascada'),
            ('set null', 'Poner a NULL'),
            ('restrict', 'Restringir'),
        ],
        default='set null', verbose_name='Al eliminar',
        help_text='Comportamiento al borrar el destino de un Many2one.',
    )
    domain = fields.Char(
        max_length=1024, blank=True, default='[]', verbose_name='Dominio',
        help_text='Dominio opcional que acota los valores posibles. Este '
                  'archivo NO lo evalúa — mismo criterio que ir_rule.',
    )
    groups = fields.Many2many(
        ResGroups, blank=True, db_table='ir_model_fields_group_rel',
        related_name='field_ids', verbose_name='Grupos',
        help_text='La referencia lo marca "CLEANME unimplemented field (empty '
                  'table)"; se porta con esa nota, no como funcionalidad viva.',
    )
    group_expand = fields.Boolean(
        default=False, verbose_name='Expandir grupos',
        help_text='Incluye todos los registros del modelo destino en un '
                  'resultado agrupado. Caro si el destino tiene muchas filas.',
    )
    selectable = fields.Boolean(default=True, verbose_name='Seleccionable')
    relation_table = fields.Char(
        max_length=255, blank=True, default='', verbose_name='Tabla de relación')
    column1 = fields.Char(max_length=63, blank=True, default='', verbose_name='Columna 1')
    column2 = fields.Char(max_length=63, blank=True, default='', verbose_name='Columna 2')
    compute = fields.Text(
        blank=True, default='', verbose_name='Cómputo',
        help_text='Código que calcula el valor. Dato, no ejecutable aquí.',
    )
    depends = fields.Char(
        max_length=1024, blank=True, default='', verbose_name='Dependencias')
    store = fields.Boolean(default=True, verbose_name='Almacenado')
    currency_field = fields.Char(
        max_length=63, blank=True, default='', verbose_name='Campo de moneda')
    # Reflexión del saneo de HTML — inútil en cualquier otro tipo de campo.
    sanitize = fields.Boolean(default=True, verbose_name='Sanear HTML')
    sanitize_overridable = fields.Boolean(
        default=False, verbose_name='Saneo de HTML sobreescribible')
    sanitize_tags = fields.Boolean(default=True, verbose_name='Sanear etiquetas HTML')
    sanitize_attributes = fields.Boolean(
        default=True, verbose_name='Sanear atributos HTML')
    sanitize_style = fields.Boolean(default=False, verbose_name='Sanear estilo HTML')
    sanitize_form = fields.Boolean(default=True, verbose_name='Sanear formularios HTML')
    strip_style = fields.Boolean(default=False, verbose_name='Quitar atributo style')
    strip_classes = fields.Boolean(default=False, verbose_name='Quitar atributo class')

    class Meta:
        db_table = 'ir_model_fields'
        ordering = ['name', 'id']
        verbose_name = 'Campo'
        verbose_name_plural = 'Campos'
        constraints = [
            # ``_name_unique`` de la fuente.
            models.UniqueConstraint(
                fields=['model', 'name'], name='ir_model_fields_name_unique'),
            # ``_size_gt_zero``: el tamaño no puede ser negativo.
            models.CheckConstraint(
                condition=models.Q(size__isnull=True) | models.Q(size__gte=0),
                name='ir_model_fields_size_gt_zero',
            ),
            # ``_name_manual_field``: un campo personalizado se llama ``x_``.
            models.CheckConstraint(
                condition=(
                    ~models.Q(state=STATE_MANUAL) | models.Q(name__startswith='x_')
                ),
                name='ir_model_fields_name_manual_field',
            ),
        ]

    def __str__(self):
        return f'{self.model}.{self.name}'

    @property
    def selection(self):
        """``_compute_selection`` — los pares (valor, etiqueta) del Selection.

        La fuente marca el campo "Deprecated" y lo mantiene por
        compatibilidad: el dato vivo son las filas de
        ``ir.model.fields.selection``. Aquí es propiedad derivada, no columna,
        que es lo que un ``compute`` sin ``store`` significa.
        """
        if self.ttype not in ('selection', 'reference'):
            return []
        return list(
            self.selection_ids.order_by('sequence', 'id')
            .values_list('value', 'name')
        )

    @selection.setter
    def selection(self, pairs):
        """``_inverse_selection`` — reescribe las filas desde los pares."""
        self.selection_ids.all().delete()
        IrModelFieldsSelection.objects.bulk_create([
            IrModelFieldsSelection(
                field=self, value=value, name=label, sequence=(index + 1) * 10)
            for index, (value, label) in enumerate(pairs)
        ])

    @property
    def modules(self):
        """``_in_modules`` — la app que declara el campo."""
        return self.model.split('.', 1)[0] if '.' in self.model else ''

    def clean(self):
        """``_check_name`` — el identificador cabe en el motor."""
        super().clean()
        if not re.fullmatch(r'\w{1,63}', self.name or ''):
            raise ValidationError(
                'Los nombres de campo sólo pueden contener letras, dígitos y '
                'guiones bajos (hasta 63 caracteres).'
            )

    @staticmethod
    def ttype_for(field):
        """Tipo Django → clave de tipo Odoo.

        ``selection`` se recupera porque ``choices`` lo delata; ``html`` no se
        recupera nunca (colapsa en ``text``). Ver el docstring del módulo.
        """
        internal = field.get_internal_type()
        if internal == 'CharField' and getattr(field, 'choices', None):
            return 'selection'
        return DJANGO_TYPE_TO_TTYPE.get(internal, 'char')

    @classmethod
    def _reflect_field_params(cls, field, model_row):
        """``_reflect_field_params`` — la fila que le toca a un campo.

        Está aparte del recorrido por la misma razón que en la referencia
        (``odoo19c: ir_model.py:1164``): es el **punto de extensión** por el
        que un addon añade columnas sin reescribir ``reflect_fields``.
        Enterprise 19 lo hereda en dos clases con
        ``_inherit = 'ir.model.fields'``; aquí el diccionario vivía en línea
        y no había dónde engancharse.

        La firma diverge de la fuente en su segundo argumento —``model_row``,
        la fila, en vez de ``model_id``, el entero— porque aquí la columna es
        una FK y el ORM quiere el objeto. El primero (``field``) también es
        otra cosa: allá un ``odoo.fields.Field``, aquí un campo de Django. Son
        las dos caras del mismo hecho: este recorrido es el **inverso** del de
        la referencia (ver el docstring del módulo).
        """
        remote = getattr(field, 'related_model', None)
        return {
            'model': model_row.model,
            'model_id': model_row,
            'ttype': cls.ttype_for(field),
            'field_description': str(
                getattr(field, 'verbose_name', '') or field.name),
            'help': str(getattr(field, 'help_text', '') or ''),
            'required': not getattr(field, 'null', True),
            'index': bool(getattr(field, 'db_index', False)),
            'store': bool(getattr(field, 'concrete', True)),
            'state': STATE_BASE,
            'relation': (
                f'{remote._meta.app_label}.{remote._meta.object_name}'
                if remote is not None else ''
            ),
            'size': getattr(field, 'max_length', None),
        }

    @classmethod
    def reflect_fields(cls, model_row):
        """Refleja los campos de un modelo — inverso de ``_reflect_fields``.

        Devuelve ``(creados, actualizados)``. Salta los reversos de relación
        (``auto_created`` sin columna propia): en la referencia esos tampoco
        son filas de ``ir_model_fields``, son el One2many del otro lado.

        La fila de cada campo la arma ``_reflect_field_params``, que es el
        enganche; este método sólo recorre y escribe.
        """
        model = model_row.django_model
        if model is None:
            return 0, 0
        created = updated = 0
        for field in model._meta.get_fields():
            if field.auto_created and not field.concrete:
                continue
            values = cls._reflect_field_params(field, model_row)
            _row, was_created = cls.objects.update_or_create(
                model=model_row.model, name=field.name, defaults=values)
            created += was_created
            updated += not was_created
        return created, updated


class IrModelInherit(models.Model):
    """``ir.model.inherit`` — el árbol de herencia entre modelos.

    Sin marcas de tiempo: la fuente declara ``_log_access = False``, así que
    aquí **no** se hereda ``TimeStampedModel``. Es una tabla derivada del
    código; su historia la lleva el commit que cambió la clase.
    """

    model_id = fields.Many2one(
        IrModel, on_delete=models.CASCADE, related_name='inherit_ids',
        verbose_name='Modelo',
        db_column='model_id',
    )
    parent_id = fields.Many2one(
        IrModel, on_delete=models.CASCADE, related_name='inherit_child_ids',
        verbose_name='Modelo padre',
        db_column='parent_id',
    )
    parent_field_id = fields.Many2one(
        IrModelFields, on_delete=models.CASCADE, null=True, blank=True,
        related_name='inherit_ids', verbose_name='Campo de delegación',
        help_text='Sólo en herencia por delegación (Odoo _inherits).',
        db_column='parent_field_id',
    )

    class Meta:
        db_table = 'ir_model_inherit'
        verbose_name = 'Herencia de modelo'
        verbose_name_plural = 'Herencias de modelo'
        constraints = [
            # ``_uniq``: un modelo hereda de otro una sola vez.
            models.UniqueConstraint(
                fields=['model_id', 'parent_id'], name='ir_model_inherit_uniq'),
        ]

    def __str__(self):
        return f'{self.model_id_id} ← {self.parent_id_id}'

    @classmethod
    def reflect_inherits(cls, model_row):
        """Refleja los padres del MRO — inverso de ``_reflect_inherits``.

        La fuente recorre ``type(model).mro()`` buscando definiciones de
        modelo; aquí es el mismo recorrido sobre el MRO de Django. Devuelve el
        número de aristas registradas.
        """
        model = model_row.django_model
        if model is None:
            return 0
        registered = 0
        for base in model.__mro__[1:]:
            meta = getattr(base, '_meta', None)
            if meta is None or base is models.Model:
                continue
            label = f'{meta.app_label}.{meta.object_name}'
            parent = IrModel.objects.filter(model=label).first()
            if parent is None:
                continue
            _edge, was_created = cls.objects.get_or_create(
                model_id=model_row, parent_id=parent)
            registered += was_created
        return registered


class IrModelFieldsSelection(TimeStampedModel):
    """``ir.model.fields.selection`` — un valor de un campo Selection."""

    field = fields.Many2one(
        IrModelFields, on_delete=models.CASCADE, db_index=True,
        related_name='selection_ids', verbose_name='Campo')
    value = fields.Char(max_length=255, verbose_name='Valor')
    name = fields.Char(max_length=255, verbose_name='Etiqueta')
    sequence = fields.Integer(default=1000, verbose_name='Secuencia')

    class Meta:
        db_table = 'ir_model_fields_selection'
        ordering = ['sequence', 'id']
        verbose_name = 'Valor de selección'
        verbose_name_plural = 'Valores de selección'
        constraints = [
            # ``_selection_field_uniq``.
            models.UniqueConstraint(
                fields=['field', 'value'],
                name='ir_model_fields_selection_field_uniq'),
        ]

    def __str__(self):
        return f'{self.value} — {self.name}'


class IrModelConstraint(TimeStampedModel):
    """``ir.model.constraint`` — restricción o índice SQL rastreado.

    Registro, no ejecutor: ver el docstring del módulo sobre por qué no se
    porta el ``DROP CONSTRAINT`` de la desinstalación.
    """

    name = fields.Char(
        max_length=255, db_index=True, verbose_name='Restricción',
        help_text='Nombre de la restricción o clave foránea en el motor.')
    definition = fields.Char(
        max_length=1024, blank=True, default='', verbose_name='Definición')
    message = fields.Char(
        max_length=512, blank=True, default='', verbose_name='Mensaje',
        help_text='Error devuelto cuando se viola la restricción.')
    model = fields.Many2one(
        IrModel, on_delete=models.CASCADE, db_index=True,
        related_name='constraint_ids', verbose_name='Modelo')
    module = fields.Many2one(
        IrModule, on_delete=models.CASCADE, db_index=True,
        related_name='constraint_ids', verbose_name='Módulo')
    type = fields.Char(
        max_length=1, verbose_name='Tipo de restricción',
        help_text='"f" para clave foránea, "u" para el resto.')

    class Meta:
        db_table = 'ir_model_constraint'
        verbose_name = 'Restricción de modelo'
        verbose_name_plural = 'Restricciones de modelo'
        constraints = [
            # ``_module_name_uniq``.
            models.UniqueConstraint(
                fields=['name', 'module'],
                name='ir_model_constraint_module_name_uniq'),
        ]

    def __str__(self):
        return self.name


class IrModelRelation(TimeStampedModel):
    """``ir.model.relation`` — tabla intermedia de un Many2many.

    La fuente declara ``write_date``/``create_date`` explícitos; aquí los
    aporta ``TimeStampedModel`` (``created_at``/``updated_at``), que es el
    equivalente del log-access en este árbol.
    """

    name = fields.Char(
        max_length=255, db_index=True, verbose_name='Nombre de la relación',
        help_text='Nombre de la tabla que implementa el Many2many.')
    model = fields.Many2one(
        IrModel, on_delete=models.CASCADE, db_index=True,
        related_name='relation_ids', verbose_name='Modelo')
    module = fields.Many2one(
        IrModule, on_delete=models.CASCADE, db_index=True,
        related_name='relation_ids', verbose_name='Módulo')

    class Meta:
        db_table = 'ir_model_relation'
        verbose_name = 'Relación de modelo'
        verbose_name_plural = 'Relaciones de modelo'

    def __str__(self):
        return self.name


class IrModelAccess(TimeStampedModel):
    """``ir.model.access`` — permiso CRUD por modelo y grupo.

    Dato, no gate: la autorización efectiva de este árbol es por capacidad
    (``HasCapability``, DEC-11). Ver el docstring del módulo.
    """

    name = fields.Char(max_length=255, db_index=True, verbose_name='Nombre')
    active = fields.Boolean(
        default=True, verbose_name='Activo',
        help_text='Desmarcar desactiva la ACL sin borrarla; una ACL nativa '
                  'borrada se recrea al recargar el módulo.',
    )
    model_id = fields.Many2one(
        IrModel, on_delete=models.CASCADE, db_index=True,
        related_name='access_ids', verbose_name='Modelo',
        db_column='model_id',
    )
    group_id = fields.Many2one(
        ResGroups, on_delete=models.PROTECT, null=True, blank=True,
        db_index=True, related_name='model_access', verbose_name='Grupo',
        help_text='Vacío = acceso global. ondelete restrict de la fuente: no '
                  'se borra un grupo que aún concede permisos.',
        db_column='group_id',
    )
    perm_read = fields.Boolean(default=False, verbose_name='Acceso de lectura')
    perm_write = fields.Boolean(default=False, verbose_name='Acceso de escritura')
    perm_create = fields.Boolean(default=False, verbose_name='Acceso de creación')
    perm_unlink = fields.Boolean(default=False, verbose_name='Acceso de borrado')

    class Meta:
        db_table = 'ir_model_access'
        ordering = ['model_id', 'group_id', 'name', 'id']
        verbose_name = 'Permiso de modelo'
        verbose_name_plural = 'Permisos de modelo'

    def __str__(self):
        return self.name

    @classmethod
    def _check_mode(cls, access_mode):
        """``assert access_mode in (...)`` de la fuente, como excepción real."""
        if access_mode not in ACCESS_MODES:
            raise ValueError(
                f'Modo de acceso inválido: {access_mode!r}. '
                f'Válidos: {", ".join(ACCESS_MODES)}.'
            )

    @classmethod
    def group_names_with_access(cls, model_name, access_mode):
        """Nombres de los grupos con ``access_mode`` sobre ``model_name``.

        La fuente arma ``"privilegio/grupo"`` cuando el grupo pertenece a un
        privilegio, y sólo el nombre del grupo cuando no. ``ResGroups`` ya
        expone eso como ``full_name``, así que aquí se reusa en vez de
        rehacer el ``COALESCE`` a mano.
        """
        cls._check_mode(access_mode)
        rows = cls.objects.filter(
            model_id__model=cls._model_label(model_name), active=True,
            group_id__isnull=False, **{f'perm_{access_mode}': True},
        ).select_related('group_id', 'group_id__privilege')
        return [access.group_id.full_name for access in rows]

    @classmethod
    def _model_label(cls, model):
        """Normaliza el nombre del modelo a la clave que guarda ``ir_model``.

        Este árbol guarda el **label de Django** en ``ir_model.model`` — lo
        declara su ``help_text`` y de ello depende ``IrModel.django_model``,
        que hace ``model.split('.', 1)`` y llama a ``apps.get_model``. La
        fuente guarda el nombre punteado del modelo (``ir.ui.view``).

        Divergencia de forma, no de mecanismo: se normaliza **en la puerta**
        con ``orm.registry``, así que un llamador puede nombrar el modelo como
        lo nombra su fuente —``check('ir.ui.view', 'write')``— y leer igual que
        ella, sin que la tabla cambie de clave.

        Un nombre que el registro no conozca se devuelve tal cual: puede ser un
        label válido de un modelo que aún no declara ``_name``, y denegar por
        no resolverlo sería confundir *«no está permitido»* con *«no sé quién
        es»*.
        """
        model_class = registry.model_by_name(model)
        if model_class is not None:
            return model_class._meta.label
        return model

    @classmethod
    def _get_allowed_models(cls, access_mode='read', user=None):
        """Los modelos con ``access_mode`` para ese usuario — ``_get_allowed_models``.

        Fiel a ``odoo19c: odoo/addons/base/models/ir_model.py:2134``: fila
        **activa**, con ``perm_<mode>``, y con ``group_id`` **nulo** (global) o
        entre los grupos del usuario.

        De ahí se sigue el invariante que gobierna todo lo demás: **un modelo
        sin ninguna fila queda fuera del conjunto**, y por tanto denegado. El
        fail-closed no lo pone una guarda escrita aparte — lo pone la forma de
        la consulta.

        La fuente lo hace en SQL crudo y lo memoriza con ``ormcache`` sobre
        ``(uid, mode)``. Aquí es el ORM y **no se memoriza**: la caché de la
        fuente tiene su invalidador (``call_cache_clearing_methods``, llamado
        desde ``create``/``write``/``unlink`` de esta misma tabla) y aquí ese
        invalidador no existe todavía. Memorizar sin invalidador es la clase de
        defecto que la tarea #58 ya midió en ``_get_group_ids``: una ACL
        revocada seguiría concediendo hasta reiniciar el proceso.
        """
        cls._check_mode(access_mode)
        if user is None:
            user = get_current_user()
        group_ids = list(user._get_group_ids()) if user is not None else []
        rows = cls.objects.filter(
            active=True, **{f'perm_{access_mode}': True},
        ).filter(
            models.Q(group_id__isnull=True) | models.Q(group_id__in=group_ids)
        ).values_list('model_id__model', flat=True)
        return frozenset(rows)

    @classmethod
    def check(cls, model=None, access_mode='read', raise_exception=True,
              user=None, **django_checks):
        """¿Tiene el usuario ``access_mode`` sobre ``model``? — ``check``.

        **El nombre colisiona con Django, y la colisión se resuelve aquí.**
        ``django.db.models.Model.check(**kwargs)`` es el hook del framework de
        *system checks*: lo llama ``manage.py check`` con ``databases=…`` y
        espera una lista de mensajes. La fuente llama ``check`` a otra cosa
        entera —la resolución de permiso— y este modelo hereda las dos.

        Renombrar la nuestra sería promover el símbolo a otro nombre que la
        referencia no declara (``porte-completo-no-parcial.md``); tapar la de
        Django dejaría el árbol sin *system checks* sobre esta tabla. Así que
        **se despachan por la firma**, que es inequívoca: Django llama sin
        argumento posicional, la referencia siempre nombra un modelo.

        Los dos caminos tienen su control en
        ``tests/integration/base/test_ir_model_access_check.py``; el defecto
        que lo destapó está en :ref:`h-api-840`.

        Fiel a ``odoo19c: odoo/addons/base/models/ir_model.py:2153``: bajo
        elevación devuelve ``True`` **sin consultar la tabla** (*"User root
        have all accesses"*), y con ``raise_exception`` levanta el error
        compuesto en vez de devolver ``False``.

        Esta es la **primera mitad** de la resolución de permiso; la segunda
        son las reglas de registro (``ir.rule``), que acotan qué filas. Las
        compone ``orm.models.AccessQuerySet._check_access``, igual que
        ``_check_access`` las compone en la fuente.
        """
        if model is None:
            return super().check(**django_checks)
        cls._check_mode(access_mode)
        if is_su():
            return True
        label = cls._model_label(model)
        has_access = label in cls._get_allowed_models(access_mode, user=user)
        if not has_access and raise_exception:
            raise cls._make_access_error(label, access_mode)
        return has_access

    @classmethod
    def _make_access_error(cls, model, access_mode):
        """El error que explica el rechazo — ``_make_access_error``.

        Tres partes, como la fuente: qué operación se negó sobre qué modelo,
        qué grupos la permitirían (o que ninguno lo hace), y a quién pedirla.
        La segunda es la que convierte un 403 opaco en algo accionable, y sale
        de ``group_names_with_access``, que ya estaba portado.
        """
        _logger.info(
            'Acceso denegado por la ACL — operación: %s, modelo: %s',
            access_mode, model)
        described = IrModel.objects.filter(model=model).values_list(
            'name', flat=True).first() or model
        operation_error = ACCESS_ERROR_HEADER[access_mode] % {
            'document_kind': described,
            'document_model': model,
        }
        groups = '\n'.join(
            f'\t- {name}'
            for name in cls.group_names_with_access(model, access_mode))
        if groups:
            group_info = ACCESS_ERROR_GROUPS % {'groups_list': groups}
        else:
            group_info = ACCESS_ERROR_NOGROUP
        return AccessError(
            operation_error + '\n\n' + group_info + '\n\n'
            + ACCESS_ERROR_RESOLUTION)

    @classmethod
    def has_global_access(cls, model_name, access_mode):
        """¿Hay alguna ACL **sin grupo** que conceda el modo?

        Es la mitad portable de ``_get_access_groups``: la fuente devuelve
        ``group_definitions.universe`` exactamente en este caso —una ACL sin
        grupo abre el modo a todos—. La otra mitad (el álgebra de expresiones
        de grupos) no está portada; ver el docstring del módulo.
        """
        cls._check_mode(access_mode)
        return cls.objects.filter(
            model_id__model=cls._model_label(model_name), active=True,
            group_id__isnull=True,
            **{f'perm_{access_mode}': True},
        ).exists()


class IrModelData(TimeStampedModel):
    """``ir.model.data`` — identificador externo de un registro.

    Sirve para dos cosas, según la fuente: integrar datos con sistemas de
    terceros identificando registros de forma estable, y rastrear el origen de
    lo que instaló un módulo para poder actualizarlo después.

    ``res_id`` es un ``Many2oneReference`` allá: el par (``model`` Char,
    ``res_id`` entero). Nuestro alias ``fields.Many2oneReference`` es
    ``GenericForeignKey`` (``orm/fields_reference.py:12``), que exige un FK
    ``content_type`` en lugar del Char y **cambia la forma de la tabla**. Se
    porta el par tal como está en la fuente — mismo criterio que
    ``ir_attachment.res_id`` ya usa en este árbol.
    """

    name = fields.Char(
        max_length=255, verbose_name='Identificador externo',
        help_text='Clave estable para integrar con sistemas de terceros.')
    model = fields.Char(max_length=255, verbose_name='Nombre del modelo')
    module = fields.Char(
        max_length=255, blank=True, default='', verbose_name='Módulo')
    res_id = fields.Integer(
        null=True, blank=True, verbose_name='ID del registro',
        help_text='ID del registro destino. Ver el docstring de la clase '
                  'sobre por qué no es un GenericForeignKey.')
    noupdate = fields.Boolean(
        default=False, verbose_name='No actualizable',
        help_text='Marcado, la actualización del módulo no lo sobreescribe.')

    class Meta:
        db_table = 'ir_model_data'
        ordering = ['module', 'model', 'name']
        verbose_name = 'Dato de modelo'
        verbose_name_plural = 'Datos de modelo'
        constraints = [
            # ``_name_nospaces``: un ID externo no lleva espacios.
            models.CheckConstraint(
                condition=~models.Q(name__contains=' '),
                name='ir_model_data_name_nospaces',
            ),
            # ``_module_name_uniq_index``.
            models.UniqueConstraint(
                fields=['module', 'name'], name='ir_model_data_module_name_uniq'),
        ]
        indexes = [
            # ``_model_res_id_index``.
            models.Index(fields=['model', 'res_id'], name='ir_model_data_model_res'),
        ]

    def __str__(self):
        return self.complete_name

    @property
    def complete_name(self):
        """``_compute_complete_name`` — ``modulo.nombre``, sin punto colgante."""
        return '.'.join(part for part in (self.module, self.name) if part)

    @property
    def reference(self):
        """``_compute_reference`` — ``"modelo,id"``."""
        return f'{self.model},{self.res_id}'

    # -- resolución de identificadores externos -----------------------------
    #
    # La tabla sin resolutor es un archivador sin índice: se pueden guardar
    # filas y no se puede recuperar nada por su nombre. Estos cinco métodos son
    # el mecanismo que la referencia reparte entre ``ir.model.data`` (la
    # búsqueda) y ``env.ref`` (el atajo que devuelve el registro).
    #
    # **Qué va en ``model``.** La referencia guarda su nombre punteado
    # (``account.tax``); nuestros modelos no tienen ``_name``, así que la clave
    # equivalente es la etiqueta de Django (``account.AccountTax``,
    # ``Model._meta.label``). No es una elección nueva: el único lector previo
    # de esta tabla ya consultaba así (``uom_uom.py:209``,
    # ``model=cls._meta.label``), y ``apps.get_model`` acepta exactamente ese
    # formato — de modo que la ida y la vuelta usan la misma llave.

    @classmethod
    def xmlid_lookup(cls, xmlid):
        """``_xmlid_lookup`` — ``(model, res_id)`` o ``ValueError``.

        El identificador es ``modulo.nombre``; el ``split`` es por el **primer**
        punto porque el nombre puede llevar más (``l10n_mx.tax12`` frente a
        ``account.1_tax_group_16``).
        """
        module, _, name = xmlid.partition('.')
        if not name:
            raise ValueError(
                'Identificador externo mal formado (falta el módulo): %s' % xmlid)
        fila = cls.objects.filter(module=module, name=name).first()
        if fila is None or not fila.res_id:
            raise ValueError('Identificador externo no encontrado: %s' % xmlid)
        return fila.model, fila.res_id

    @classmethod
    def xmlid_to_res_model_res_id(cls, xmlid, raise_if_not_found=False):
        """``_xmlid_to_res_model_res_id`` — la pareja, o ``(None, None)``.

        La referencia devuelve ``(False, False)`` porque en su ORM el falso es
        el vacío de cualquier tipo; aquí el vacío es ``None``.
        """
        try:
            return cls.xmlid_lookup(xmlid)
        except ValueError:
            if raise_if_not_found:
                raise
            return None, None

    @classmethod
    def xmlid_to_res_id(cls, xmlid, raise_if_not_found=False):
        """``_xmlid_to_res_id`` — sólo el id."""
        return cls.xmlid_to_res_model_res_id(xmlid, raise_if_not_found)[1]

    @classmethod
    def ref(cls, xmlid, raise_if_not_found=True):
        """El registro que designa el identificador — ≙ ``env.ref``.

        Vive aquí y no en un ``env`` porque este proyecto no tiene ese objeto:
        la referencia lo pone en ``odoo/orm/environments.py:158`` sólo para dar
        el atajo, y su cuerpo no hace otra cosa que llamar a
        ``_xmlid_to_res_model_res_id`` y traer el registro.

        Devuelve ``None`` si la fila apunta a algo ya borrado — la referencia
        hace lo mismo con su ``record.exists()``: un identificador externo
        puede sobrevivir al registro que nombraba.
        """
        model_label, res_id = cls.xmlid_to_res_model_res_id(
            xmlid, raise_if_not_found=raise_if_not_found)
        if not model_label or not res_id:
            return None
        record = apps.get_model(model_label).objects.filter(pk=res_id).first()
        if record is None and raise_if_not_found:
            raise ValueError(
                'El identificador externo %s apunta a un registro que ya no '
                'existe (%s,%s)' % (xmlid, model_label, res_id))
        return record

    @classmethod
    def set_xmlid(cls, record, xmlid, noupdate=False):
        """Registra (o repunta) el identificador externo de ``record``.

        Es el lado **escritor**, que en la referencia no es un método sino el
        cargador de archivos de datos. Sin él la tabla no se puebla y el
        resolutor de arriba no tendría nada que resolver — el defecto que
        :ref:`h-api-346` documenta como "símbolo sin consumidor".

        Idempotente por ``(module, name)``, que es la clave única de la tabla:
        volver a sembrar repunta la fila en vez de duplicarla.
        """
        module, _, name = xmlid.partition('.')
        if not name:
            raise ValueError(
                'Identificador externo mal formado (falta el módulo): %s' % xmlid)
        fila, _creada = cls.objects.update_or_create(
            module=module, name=name,
            defaults={
                'model': type(record)._meta.label,
                'res_id': record.pk,
                'noupdate': noupdate,
            },
        )
        return fila
