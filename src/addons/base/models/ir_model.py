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

Consecuencia: **el inverso del mapa no existe**. ``_reflect_fields`` deriva el
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
``one2many``          es el reverso de un FK; ``_reflect_fields`` lo salta
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
- **``_process_ondelete``** de ``IrModelFieldsSelection`` — **PORTADO**
  (tarea #205). Estuvo declarado BLOQUEADO *"por ``fields.Selection``, que no
  acepta ese parámetro"*, y esa premisa nombraba el receptor equivocado: la
  fuente declara ``ondelete=`` **junto a** ``selection_add=`` en la misma
  redeclaración del campo, y el ``selection_add`` de este árbol no es un
  parámetro de campo sino ``extend_model(selection_add=…)``
  (``orm/model_classes.py``). Ahí se construyó el receptor —el hermano que ya
  existía—, con las cinco políticas de la fuente y su validación.
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
                                         de ``_reflect_fields``, que lo tenía
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
import random
import re
from collections import defaultdict

import api
import fields
import models
from django.apps import apps
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db.models.fields import NOT_PROVIDED

from addons.base.models.ir_module import IrModule
from addons.base.models.ir_ui_view import IrUiView
from addons.base.models.res_groups import ResGroups
from addons.base.models.timestamped_mixin import TimeStampedModel
from django.db import DEFAULT_DB_ALIAS, connections, transaction
from exceptions import AccessError, UserError
from orm import registry
from orm.environments import get_current_user, is_su, is_system
from orm.fields import __all__ as _FIELD_NAMES
from orm.models import MAGIC_COLUMNS
from orm.utils import check_object_name, check_pg_name
from tools.safe_eval import safe_eval
from tools.cache import ormcache
from tools.misc import OrderedSet, split_every

#: Tope de elementos por sentencia, ≙ ``cr.IN_MAX`` de la fuente. Acota
#: el número de marcadores de un ``INSERT`` en lote: PostgreSQL admite
#: 65535 parámetros por sentencia y cada fila gasta cinco.
_IN_MAX = 1000

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

#: ≙ ``RE_ORDER_FIELDS`` (``odoo19c: ir_model.py:37``), verbatim. Saca el
#: nombre de cada campo de una cláusula de orden ya validada, para comprobar
#: uno por uno que existan y estén almacenados.
RE_ORDER_FIELDS = re.compile(r'"?(\w+)"?\s*(?:asc|desc)?', flags=re.I)

def _model_class(model_label):
    """≙ ``self.env[model]`` — la clase de ese nombre, o ``None``.

    La fuente indexa el entorno, que conoce todos los modelos por su ``_name``.
    Aquí se consulta el registro por nombre de la referencia (``orm.registry``)
    con respaldo en el de Django, porque un modelo propio del L0 no declara
    ``_name`` y sólo se alcanza por su etiqueta ``app.Modelo``. Devuelve
    ``None`` en vez de levantar: los sitios que lo consumen difieren en qué
    hacer con un modelo desaparecido —uno sigue, otro registra, otro
    devuelve— y esa decisión es de cada uno.

    Símbolo **nuestro**: la fuente no lo necesita porque su entorno ya es el
    índice. Vive a nivel de módulo y no colgado de una clase porque lo
    consumen cuatro de ellas —``ir.model.fields``, su selección,
    ``ir.model.data`` y ``ir.model``—; colgarlo de una obligaría a las otras
    tres a nombrarla para llegar a él.
    """
    model_cls = registry.MODELS_BY_NAME.get(model_label)
    if model_cls is not None:
        return model_cls
    try:
        return apps.get_model(model_label)
    except (LookupError, ValueError):
        return None


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

    _name = 'base'
    _description = 'Base'

    class Meta:
        abstract = True


class Unknown(models.Model):
    """``_unknown`` — sustituto de un campo relacional sin comodelo conocido."""

    _name = '_unknown'
    _description = 'Unknown'

    class Meta:
        abstract = True


class IrModel(models.OriginMixin, TimeStampedModel):
    """``ir.model`` — una fila por modelo declarado.

    ``models.OriginMixin`` entra por :meth:`save`: la guarda de los cuatro
    campos inmodificables compara el valor entrante contra el guardado, y
    ``_origin`` es el mecanismo que da ese valor (tarea #112).
    """

    #: Los cinco atributos de ORM que la fuente declara
    #: (``odoo19c: ir_model.py:56-61``), verbatim. El sexto que declara ahí,
    #: ``_obj_name_uniq``, es un **objeto de tabla**: vive en
    #: ``Meta.constraints`` conservando su nombre, que es el hogar que
    #: ``atributos-de-clase-de-modelo.md`` le fija.
    _name = 'ir.model'
    _description = 'Models'
    _order = 'model'
    _rec_names_search = ['name', 'model']
    _allow_sudo_commands = False

    name = fields.Char(
        max_length=255, verbose_name='Descripción del modelo',
        help_text='Odoo name (traducible allá).',
    )
    model = fields.Char(
        max_length=255, default='x_', db_index=True,
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
        constraints = [
            # ``_obj_name_uniq``: cada modelo tiene un nombre único.
            models.UniqueConstraint(
                fields=['model'], name='ir_model_obj_name_uniq'),
        ]

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

    def _inherited_models(self):
        """Los modelos que este extiende — ``_inherited_models``.

        ≙ ``odoo19c: ir_model.py:240-246``. En la referencia son los
        ``_inherits`` (herencia por delegación). Aquí los padres del MRO, que
        es la misma relación: el modelo hereda de ellos sin ser ellos.

        Nombre de la fuente para el cómputo; su superficie de lectura es la
        propiedad :attr:`inherited_model_ids`, que es donde el campo vive.
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
    def inherited_model_ids(self):
        """Superficie de lectura del campo; el cómputo es el de la fuente."""
        return self._inherited_models()

    @property
    def view_ids(self):
        """``_view_ids`` — las vistas declaradas sobre este modelo.

        ``compute`` sin ``store`` en la referencia → propiedad aquí. Cerrado
        con el porte de ``ir_ui_view.py``; era el hueco que este archivo dejó
        anotado.
        """
        return IrUiView.objects.filter(model=self.model)

    def _in_modules(self):
        """Las apps en que el modelo está definido — ``_in_modules``.

        ≙ ``odoo19c: ir_model.py:249-255``. La referencia cruza los XML IDs
        contra los módulos instalados. Aquí el dueño es el ``app_label`` de
        Django, que es dato de primera mano y no necesita el cruce.

        Nombre de la fuente para el cómputo; su superficie de lectura es la
        propiedad :attr:`modules`.
        """
        model = self.django_model
        return model._meta.app_label if model is not None else ''

    @property
    def modules(self):
        """Superficie de lectura del campo; el cómputo es el de la fuente."""
        return self._in_modules()

    @classmethod
    def _is_manual_name(cls, name):
        """¿Es el nombre de un objeto personalizado? — ``_is_manual_name``.

        ≙ ``odoo19c: ir_model.py:495-497``. La fuente lo declara **dos
        veces** —aquí y en ``IrModelFields`` (``:1357``)—, así que las dos
        clases lo llevan. El prefijo ``x_`` es la marca: separa lo que declara
        un módulo de lo que declara un usuario, y de esa distinción cuelgan
        :meth:`_check_manual_name` y :meth:`_unlink_if_manual`.
        """
        return name.startswith('x_')

    @classmethod
    def _check_manual_name(cls, name):
        """Rechaza un nombre personalizado sin el prefijo — ``_check_manual_name``.

        ≙ ``odoo19c: ir_model.py:499-501``, con su mensaje: *"The model name
        must start with 'x_'."*
        """
        if not cls._is_manual_name(name):
            raise ValidationError(
                "El nombre del modelo debe empezar con 'x_'.")

    def _check_model_name(self):
        """El nombre del modelo — ``_check_model_name`` (``odoo19c: :270-275``).

        Dos comprobaciones, las de la fuente y en su orden: si la fila es
        personalizada, el prefijo; y siempre, que el nombre esté en el
        alfabeto que ``check_object_name`` admite.
        """
        if self.state == STATE_MANUAL:
            type(self)._check_manual_name(self.model)
        if not check_object_name(self.model):
            raise ValidationError(
                'El nombre del modelo sólo puede llevar minúsculas, dígitos, '
                'guiones bajos y puntos.')

    def _check_order(self):
        """La cláusula de orden — ``_check_order`` (``odoo19c: :277-302``).

        Dos mitades, las dos de la fuente:

        1. **Que sea una cláusula válida** — lo mide :meth:`_check_qorder`, que
           la fuente cuelga de ``BaseModel`` y aquí llega por ``OrderMixin``.
           Su ``UserError`` se reenvasa en ``ValidationError``, igual que allá.
        2. **Que cada campo nombrado exista y esté almacenado** — la fuente
           compone el conjunto con los campos de la fila más
           ``MAGIC_COLUMNS``; aquí el conjunto sale del modelo de Django, que
           es donde viven los campos, más las mismas columnas mágicas.

        DIVERGENCIA DE ORIGEN, declarada: allá los campos candidatos salen de
        ``field_id``, la ``One2many`` a ``ir.model.fields``, porque un modelo
        personalizado se define en filas. Aquí un modelo se define en Python,
        así que el conjunto autoritativo es ``_meta.get_fields()``. Cuando el
        modelo aún no está en el registro —una fila que nombra algo no
        cargado— se cae a las columnas mágicas, que es lo que la fuente hace
        con su comentario *"in case 'model' has not been initialized yet"*.
        """
        try:
            self._check_qorder(self.order)
        except UserError as error:
            raise ValidationError(str(error))

        stored_fields = set(MAGIC_COLUMNS)
        model_cls = self.django_model
        if model_cls is not None:
            stored_fields.update(
                field.name for field in model_cls._meta.get_fields()
                if getattr(field, 'concrete', False))
            stored_fields.update(
                field.attname for field in model_cls._meta.concrete_fields)

        for field_name in RE_ORDER_FIELDS.findall(self.order):
            if field_name not in stored_fields:
                raise ValidationError(
                    'No se puede ordenar por %s: los campos usados para '
                    'ordenar deben existir en el modelo y estar almacenados.'
                    % field_name)

    def _check_fold_name(self):
        """El campo de plegado — ``_check_fold_name`` (``odoo19c: :304-308``).

        Nombra un campo del modelo o no vale. Mismo origen que
        :meth:`_check_order`: los campos salen del modelo de Django.
        """
        if not self.fold_name:
            return
        model_cls = self.django_model
        if model_cls is None:
            return
        names = {field.name for field in model_cls._meta.get_fields()}
        if self.fold_name not in names:
            raise ValidationError(
                "El valor de 'Campo de plegado' debe ser el nombre de un "
                'campo del modelo.')

    def clean(self):
        """Enganche de Django — corre las tres restricciones de la fuente.

        La fuente las declara con ``@api.constrains``, que su ORM dispara al
        escribir; aquí el disparador equivalente es ``clean()``, y por eso
        delega en vez de llevar el cuerpo. Los nombres son los de la fuente
        —``_check_model_name``, ``_check_order``, ``_check_fold_name``— para
        que cada uno se pueda llamar y probar por separado, como allá.
        """
        super().clean()
        self._check_model_name()
        self._check_order()
        self._check_fold_name()

    def _unlink_if_manual(self):
        """Un modelo de módulo no se borra a mano — ``_unlink_if_manual``.

        ≙ ``odoo19c: ir_model.py:346-351``, con su comentario verbatim:
        *"Prevent manual deletion of module tables"*. La fuente lo engancha con
        ``@api.ondelete(at_uninstall=False)``: corre al borrar desde la
        interfaz y **no** al desinstalar un módulo, que es cuando sí toca.
        Aquí lo llama :meth:`delete`, con la misma excepción.
        """
        if self.state != STATE_MANUAL:
            raise UserError(
                'El modelo "%s" contiene datos de módulo y no se puede '
                'eliminar.' % self.name)

    @classmethod
    def name_create(cls, name):
        """Crea la fila infiriendo el modelo de la etiqueta — ``name_create``.

        Docstring de la fuente, verbatim: *"Infer the model from the name.
        E.g.: 'My New Model' should become 'x_my_new_model'"*
        (``odoo19c: ir_model.py:415-422``).

        Sobreescribe el ``name_create`` universal de ``DisplayNameMixin``, que
        sólo escribe el ``_rec_name``: aquí hace falta además componer el
        nombre técnico, porque ``model`` no admite vacío.
        """
        record = cls.objects.create(
            name=name, model='x_' + '_'.join(name.lower().split(' ')))
        return record.pk, record.display_name

    def save(self, *args, **kwargs):
        """Enganche de Django — ≙ ``create`` (``:400-413``) y ``write`` (``:483-497``).

        De ``write`` se porta la guarda que importa: **cuatro campos no se
        modifican** una vez escrita la fila —``model``, ``state``, ``abstract``
        y ``transient``—, porque cambiarlos convertiría la fila en la
        descripción de otro modelo sin tocar el modelo. La fuente compara
        contra el valor guardado de cada registro; aquí ese valor lo da
        ``_origin`` (``orm/models.py``, tarea #112), que es el mecanismo
        equivalente y ya existe.

        DIVERGENCIA DE MECANISMO, la de la cabecera del módulo y ya declarada:
        las dos mitades de la fuente que **recargan el registro y actualizan el
        esquema** —``_setup_models__`` e ``init_models``— no tienen receptor.
        Django construye su registro al importar y lo congela, y el esquema lo
        gobiernan las migraciones. Lo que queda de esas dos mitades es la
        invalidación de ``_get_id``, que sí es nuestra y sí hay que hacer: sin
        ella una fila nueva no se resuelve por nombre hasta reiniciar.

        El filtro de la operación 4 sobre ``field_id`` tampoco tiene receptor:
        es un arreglo para el cliente web de la fuente, que envía
        ``(4, id, False)`` incluso para lo que no cambió.
        """
        if not self._state.adding:
            previous = self._origin
            if previous is not None:
                for field_name in ('model', 'state', 'abstract', 'transient'):
                    if getattr(self, field_name) != getattr(previous, field_name):
                        raise UserError(
                            'El campo %s no se puede modificar en un modelo.'
                            % field_name)
        result = super().save(*args, **kwargs)
        registry.clear_cache('stable')
        return result

    def delete(self, *args, at_uninstall=False, **kwargs):
        """Enganche de Django — ≙ ``unlink`` (``odoo19c: :353-381``).

        La fuente arrastra cuatro cosas antes de borrar la fila, y las cuatro
        se portan: los campos cuyo modelo relacionado desaparece, los crons que
        lo apuntan, los identificadores externos que lo nombran, y la guarda
        :meth:`_unlink_if_manual`.

        DIVERGENCIA DE MECANISMO, declarada en la cabecera del módulo: el
        ``_drop_table`` de la fuente no se porta —el esquema lo gobiernan las
        migraciones— ni la recarga del registro, que aquí no existe. La
        invalidación de ``_get_id`` sí, por la misma razón que en
        :meth:`save`.

        ``_prepare_update`` de la fuente, que preserva los campos que dependen
        de éstos, cae dentro de la maquinaria de campos manuales y no tiene
        receptor: aquí un campo se declara en Python.

        ``at_uninstall`` es el receptor de ``@api.ondelete(at_uninstall=False)``
        (``odoo19c: :346``), igual que en ``ir.model.fields.selection``: la
        guarda protege el borrado a mano y **no** corre al desinstalar, que es
        cuando el modelo de un módulo sí debe irse.

        :param at_uninstall: ``True`` cuando el borrado es parte de desinstalar
            un módulo. Salta la guarda.
        """
        if not at_uninstall:
            self._unlink_if_manual()
        model_name = self.model
        IrModelFields.objects.filter(relation=model_name).delete()
        # El cron llega por ``apps.get_model`` y no por ``import``: ``ir_cron``
        # importa ``ir_actions``, que importa este archivo. Es la vía de Django
        # para un ciclo entre modelos, y una llamada —no un ``import`` dentro
        # de una función—, así que el gate de imports perezosos la admite.
        #
        # Y apunta por ``model_name``, no por ``model_id``: aquí el cron nombra
        # su modelo con la etiqueta en un ``Char`` que delega en
        # ``ir.actions.server``, no con la FK a ``ir.model`` que la fuente usa.
        # Convertir ese ``Char`` en FK es la tarea **#139**; hasta entonces el
        # filtro es por etiqueta.
        apps.get_model('base', 'IrCron').objects.filter(
            ir_actions_server__model_name=model_name).delete()
        IrModelData.objects.filter(model=model_name).delete()
        result = super().delete(*args, **kwargs)
        registry.clear_cache('stable')
        return result

    @classmethod
    def _get(cls, name):
        """La fila de ``ir.model`` con ese nombre técnico, o ``None``.

        ≙ ``_get`` (``odoo19c: ir_model.py:312-317``). Su docstring verbatim:
        *"Return the (sudoed) `ir.model` record with the given name. The result
        may be an empty recordset if the model is not found."*

        La fuente devuelve un conjunto vacío cuando no encuentra; aquí el
        equivalente de "conjunto vacío" para una sola fila es ``None``, que es
        lo que ``objects.filter(...).first()`` produce. El ``sudo()`` de allá
        no tiene destinatario: este acceso no pasa por reglas de fila.
        """
        model_id = cls._get_id(name) if name else None
        return cls.objects.filter(pk=model_id).first() if model_id else None

    @classmethod
    @ormcache('name', cache='stable')
    def _get_id(cls, name):
        """El ``id`` de la fila con ese nombre, memorizado.

        ≙ ``_get_id`` (``odoo19c: ir_model.py:319-323``), con su mismo
        ``@ormcache('name', cache='stable')``. La fuente va a SQL crudo para
        saltarse el ORM en un camino caliente; aquí el ``values_list`` del ORM
        emite el mismo ``SELECT id FROM ir_model WHERE model=%s`` y no hay
        motivo para escribirlo a mano.

        El caché es ``stable`` porque el registro de modelos sólo cambia al
        instalar o desinstalar un módulo, no en el curso de una petición.
        """
        return cls.objects.filter(model=name).values_list('pk', flat=True).first()

    @classmethod
    def _reflect_model_params(cls, model):
        """Los valores que una fila guarda del modelo — ≙ ``:425-436``.

        **Las ocho claves de la fuente**, y cada una desde donde la fuente la
        toma: el **atributo de clase**, no el ``Meta`` de Django. La distinción
        no es cosmética — ``atributos-de-clase-de-modelo.md`` obliga a portar
        todos los que la fuente declare, y esos atributos son precisamente los
        que aquí se leen::

            'name': model._description        # ``:429``
            'order': model._order             # ``:430``
            'info': …__doc__ de la mro        # ``:431``
            'fold_name': model._fold_name     # ``:435``

        Un modelo que **no** declara el atributo cae a su equivalente de
        ``Meta``: ``verbose_name`` por ``_description`` y ``ordering`` por
        ``_order``. Ese respaldo no es una divergencia sino la otra mitad de la
        misma regla — *"si no declara ninguno, no se inventa ninguno"* —, y
        cubre a los modelos propios del L0 que no adaptan nada de la fuente.

        ``info`` recorre la ``mro`` buscando el primer ``__doc__`` no vacío,
        igual que ``:431``: una subclase sin docstring hereda la descripción de
        su base en vez de guardar la vacía.

        ``state`` es ``STATE_BASE`` y no el ``'manual' if model._custom`` de la
        fuente: ``_custom`` marca los modelos que su cliente crea en caliente
        por formulario, superficie que aquí no existe. Las filas manuales que
        sí existen las escribe quien las crea, no este reflejo.
        """
        info = next(
            (klass.__doc__ for klass in model.__mro__ if klass.__doc__), '')
        return {
            'name': str(getattr(model, '_description', None)
                        or model._meta.verbose_name),
            'order': (getattr(model, '_order', None)
                      or ', '.join(model._meta.ordering) or 'id'),
            'info': info.strip(),
            'state': STATE_BASE,
            'abstract': model._meta.abstract,
            'transient': not model._meta.managed,
            'fold_name': getattr(model, '_fold_name', '') or '',
        }

    @classmethod
    def _reflect_models(cls, app_labels=None):
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
            _row, was_created = cls.objects.update_or_create(
                model=label, defaults=cls._reflect_model_params(model))
            created += was_created
            updated += not was_created
        return created, updated


class IrModelFields(models.OriginMixin, TimeStampedModel):
    """``ir.model.fields`` — una fila por campo."""

    #: Los cinco atributos de ORM de ``odoo19c: ir_model.py:509-513``,
    #: verbatim. Los tres objetos de tabla que la fuente declara junto a
    #: ellos —``_name_unique``, ``_size_gt_zero``, ``_name_manual_field``—
    #: viven en ``Meta.constraints`` conservando su nombre, que es el hogar
    #: que ``atributos-de-clase-de-modelo.md`` les fija.
    _name = 'ir.model.fields'
    _description = 'Fields'
    _order = 'name, id'
    _rec_name = 'field_description'
    _allow_sudo_commands = False

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
        max_length=32, choices=FIELD_TYPES, required=True,
        verbose_name='Tipo de campo')
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

    def _compute_display_name(self, hide_model=False):
        """La etiqueta del campo — ``_compute_display_name``.

        ≙ ``odoo19c: ir_model.py:1155-1162``: la descripción del campo seguida
        del nombre del modelo entre paréntesis, o la descripción sola cuando el
        llamador pide ocultar el modelo.

        La fuente lee ese «ocultar» de una clave de contexto (``hide_model``);
        aquí llega por parámetro, que es la divergencia de contexto que este
        árbol ya declara en todas partes — no hay un contexto ambiente que
        consultar.
        """
        if hide_model:
            return self.field_description
        model_row = IrModel._get(self.model)
        model_string = model_row.name if model_row is not None else self.model
        return f'{self.field_description} ({model_string})'

    def __str__(self):
        """Enganche de Django — el nombre técnico, que es lo que identifica.

        NO delega en :meth:`_compute_display_name`: son dos etiquetas
        distintas y las dos se usan. La de la fuente —«Descripción (Modelo)»—
        es para la interfaz; ``modelo.campo`` es la que este árbol imprime en
        errores y trazas, donde hace falta el identificador exacto.
        """
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
                field_id=self, value=value, name=label,
                sequence=(index + 1) * 10)
            for index, (value, label) in enumerate(pairs)
        ])

    @property
    def modules(self):
        """``_in_modules`` — la app que declara el campo."""
        return self.model.split('.', 1)[0] if '.' in self.model else ''

    # -- restricciones -------------------------------------------------------
    #
    # La fuente las declara con ``@api.constrains``, que su ORM dispara al
    # escribir; aquí el disparador equivalente es :meth:`clean`, y por eso
    # delega en vez de llevar el cuerpo. Los nombres son los de la fuente para
    # que cada una se pueda llamar y probar por separado, como allá.

    def _check_name(self):
        """El identificador cabe en el motor — ``_check_name``.

        ≙ ``odoo19c: ir_model.py:641-647``. La fuente delega en
        ``models.check_pg_name`` y reenvasa su ``ValidationError`` con un
        mensaje propio; aquí ``check_pg_name`` es el mismo de ``orm.utils``.
        """
        try:
            check_pg_name(self.name or '')
        except ValidationError:
            raise ValidationError(
                'Los nombres de campo sólo pueden contener letras, dígitos y '
                'guiones bajos (hasta 63 caracteres).')

    def _check_domain(self):
        """El dominio evalúa — ``_check_domain`` (``odoo19c: :631-638``).

        La fuente lo pasa por ``safe_eval``, que es el mismo evaluador acotado
        que este árbol ya tiene portado (``tools.safe_eval``, tarea #140).
        """
        try:
            safe_eval(self.domain or '[]')
        except ValueError as error:
            raise ValidationError(
                'Ocurrió un error al evaluar el dominio:\n%s' % error)

    def _check_relation(self):
        """El modelo relacionado existe — ``_check_relation`` (``odoo19c: :728-731``).

        Sólo sobre un campo personalizado: uno declarado en Python ya tiene su
        relación resuelta por el propio ORM.
        """
        if (self.state == STATE_MANUAL and self.relation
                and not IrModel._get_id(self.relation)):
            raise ValidationError(
                "Nombre de modelo desconocido '%s' en Modelo relacionado"
                % self.relation)

    def _check_relation_table(self):
        """La tabla intermedia es un identificador válido — ``_check_relation_table``.

        ≙ ``odoo19c: :769-772``.
        """
        if self.relation_table:
            check_pg_name(self.relation_table)

    def _check_on_delete_required_m2o(self):
        """≙ ``_check_on_delete_required_m2o`` (``odoo19c: :835-841``).

        Un Many2one requerido no puede declarar ``set null``: la política se
        contradice con la obligatoriedad. Mensaje de la fuente, verbatim:
        *"Only 'restrict' and 'cascade' make sense"*.
        """
        if (self.ttype == 'many2one' and self.required
                and self.on_delete == 'set null'):
            raise ValidationError(
                'El campo m2o %s es requerido pero declara su política de '
                "borrado como 'set null'. Sólo 'restrict' y 'cascade' tienen "
                'sentido.' % self.name)

    def _check_currency_field(self):
        """El campo de moneda de un monetario — ``_check_currency_field``.

        ≙ ``odoo19c: :775-790``, con sus cuatro rechazos y su respaldo: sin
        ``currency_field`` declarado busca ``currency_id`` y luego
        ``x_currency_id`` en el mismo modelo, y si no hay ninguno rechaza.
        """
        if self.state != STATE_MANUAL or self.ttype != 'monetary':
            return
        cls = type(self)
        if not self.currency_field:
            currency_field = (cls._get(self.model, 'currency_id')
                              or cls._get(self.model, 'x_currency_id'))
            if currency_field is None:
                raise ValidationError(
                    'El campo de moneda está vacío y el modelo no tiene un '
                    'campo de respaldo')
        else:
            currency_field = cls._get(self.model, self.currency_field)
            if currency_field is None:
                raise ValidationError(
                    'Campo desconocido "%s" en currency_field'
                    % self.currency_field)
        if currency_field.ttype != 'many2one':
            raise ValidationError('El campo de moneda no es de tipo many2one')
        if currency_field.relation != 'res.currency':
            raise ValidationError(
                'El campo de moneda debe relacionar con res.currency')

    def _check_related(self):
        """El campo relacionado coincide en tipo y comodelo — ``_check_related``.

        ≙ ``odoo19c: :692-707``. Resuelve la ruta con :meth:`_related_field` y
        compara las dos cosas que la fuente compara: el tipo y el modelo
        relacionado.
        """
        if self.state != STATE_MANUAL or not self.related:
            return
        field = self._related_field()
        if field.ttype != self.ttype:
            raise ValidationError(
                'El campo relacionado "%s" no es de tipo "%s"'
                % (self.related, self.ttype))
        if field.relation != self.relation:
            raise ValidationError(
                'El campo relacionado "%s" no tiene el comodelo "%s"'
                % (self.related, self.relation))

    def _check_depends(self):
        """Las dependencias de un cómputo son válidas — ``_check_depends``.

        Docstring de la fuente, verbatim: *"Check whether all fields in
        dependencies are valid"* (``odoo19c: :734-761``). Sus cuatro rechazos
        se conservan: dependencia vacía, ``id``, campo desconocido, y un campo
        no relacional en medio de una ruta.

        La fuente recorre ``model._fields``; aquí el registro de campos es el
        de Django, y el paso de un tramo al siguiente es la clase relacionada
        del ``ForeignKey``.
        """
        if not self.depends:
            return
        for sequence in self.depends.split(','):
            if not sequence.strip():
                raise UserError('Dependencia vacía en "%s"' % self.depends)
            model_cls = _model_class(self.model)
            if model_cls is None:
                continue
            names = sequence.strip().split('.')
            last = len(names) - 1
            for index, name in enumerate(names):
                if name == 'id':
                    raise UserError(
                        "El método de cómputo no puede depender del campo 'id'")
                try:
                    field = model_cls._meta.get_field(name)
                except FieldDoesNotExist:
                    raise UserError(
                        'Campo desconocido "%s" en la dependencia "%s"'
                        % (name, sequence.strip()))
                related_model = getattr(field, 'related_model', None)
                if index < last and related_model is None:
                    raise UserError(
                        'Campo no relacional "%s" en la dependencia "%s"'
                        % (name, sequence.strip()))
                model_cls = related_model

    def clean(self):
        """Enganche de Django — corre las siete restricciones de la fuente."""
        super().clean()
        self._check_name()
        self._check_domain()
        self._check_relation()
        self._check_relation_table()
        self._check_on_delete_required_m2o()
        self._check_currency_field()
        self._check_related()
        self._check_depends()

    # -- resolución y consulta ----------------------------------------------

    @classmethod
    def _is_manual_name(cls, name):
        """¿Es el nombre de un campo personalizado? — ``_is_manual_name``.

        ≙ ``odoo19c: ir_model.py:1357-1358``. La fuente lo declara aquí **y**
        en ``IrModel`` (``:495``); las dos clases lo llevan.
        """
        return name.startswith('x_')

    @classmethod
    def _get(cls, model_name, name):
        """La fila de un campo, o ``None`` — ``_get``.

        Docstring de la fuente, verbatim: *"Return the (sudoed) `ir.model.fields`
        record with the given model and name. The result may be an empty
        recordset if the model is not found"* (``odoo19c: :843-848``).

        El conjunto vacío de allá es aquí ``None``, igual que en
        ``IrModel._get``.
        """
        field_id = cls._get_ids(model_name).get(name)
        return cls.objects.filter(pk=field_id).first() if field_id else None

    @classmethod
    @ormcache('model_name', cache='stable')
    def _get_ids(cls, model_name):
        """``{nombre: id}`` de los campos de un modelo — ``_get_ids``.

        ≙ ``odoo19c: :851-854``, memorizado como allá. Lo vacía
        :meth:`save`/:meth:`delete`, por la misma razón que la ACL vacía la
        suya: una fila nueva no se resolvería por nombre hasta reiniciar.
        """
        return dict(cls.objects.filter(model=model_name)
                    .values_list('name', 'id'))

    @classmethod
    def _get_fields_cached(cls, model_name):
        """Los campos de un modelo, por nombre — ``_get_fields_cached``.

        ≙ ``odoo19c: :1399-1419``. La fuente memoriza la **fila entera** para
        que ``get_field_string``, ``get_field_help`` y ``get_field_selection``
        no consulten una vez por campo. Aquí devuelve el diccionario
        ``{nombre: fila}``, que es lo que esos tres consumen.
        """
        return {row.name: row for row in cls.objects.filter(model=model_name)}

    @classmethod
    def get_field_string(cls, model_name):
        """``{nombre: etiqueta}`` de los campos de un modelo — ``get_field_string``.

        Docstring de la fuente, verbatim: *"Return the translation of fields
        strings in the context's language"* (``odoo19c: :1361-1371``). Aquí no
        hay eje de traducción todavía (tarea **#184**), así que devuelve la
        etiqueta guardada.
        """
        return {name: row.field_description
                for name, row in cls._get_fields_cached(model_name).items()}

    @classmethod
    def get_field_help(cls, model_name):
        """``{nombre: ayuda}`` — ``get_field_help`` (``odoo19c: :1374-1384``)."""
        return {name: row.help
                for name, row in cls._get_fields_cached(model_name).items()}

    @classmethod
    def get_field_selection(cls, model_name, field_name):
        """Los pares de un campo Selection — ``get_field_selection``.

        ≙ ``odoo19c: :1387-1395``. Delega en
        :meth:`IrModelFieldsSelection._get_selection`, que es donde vive la
        consulta ordenada.
        """
        row = cls._get(model_name, field_name)
        if row is None:
            return []
        return IrModelFieldsSelection._get_selection(row.pk)

    def _related_field(self):
        """La fila del campo al que apunta ``related`` — ``_related_field``.

        Docstring de la fuente, verbatim: *"Return the ``ir.model.fields``
        record corresponding to ``self.related``"* (``odoo19c: :656-689``).

        Sus tres rechazos se conservan y son lo que hace útil al método:
        nombre desconocido, tramo intermedio no relacional, y tramo intermedio
        no consultable. El tercero la fuente lo condiciona a que su registro
        esté listo; aquí el registro de Django siempre lo está, y la condición
        equivalente es que el campo esté almacenado.
        """
        names = self.related.split('.')
        last = len(names) - 1
        model_name = self.model or (self.model_id and self.model_id.model)
        field = None
        for index, name in enumerate(names):
            field = type(self)._get(model_name, name)
            if field is None:
                raise UserError(
                    'Nombre de campo desconocido "%s" en el campo relacionado '
                    '"%s"' % (name, self.related))
            if index < last and not field.relation:
                raise UserError(
                    'Campo no relacional "%s" en el campo relacionado "%s"'
                    % (name, self.related))
            if index < last and not field.store:
                raise UserError(
                    'El campo "%s" de la ruta relacionada "%s" no es '
                    'consultable. Un campo no consultable no se puede usar en '
                    'un campo relacionado.' % (name, self.related))
            model_name = field.relation
        return field

    @classmethod
    def _custom_many2many_names(cls, model_name, comodel_name):
        """Nombres por defecto de la tabla y columnas de un M2M personalizado.

        Docstring de la fuente, verbatim: *"Return default names for the table
        and columns of a custom many2many field"* (``odoo19c: :793-801``). Su
        forma se conserva entera, incluido el caso reflexivo: cuando las dos
        tablas coinciden las columnas son ``id1``/``id2``.
        """
        first = _model_class(model_name)
        second = _model_class(comodel_name)
        if first is None or second is None:
            raise ValueError(
                'No se pueden componer los nombres del M2M: %s o %s no está '
                'en el registro' % (model_name, comodel_name))
        rel1, rel2 = first._meta.db_table, second._meta.db_table
        table = 'x_%s_%s_rel' % tuple(sorted([rel1, rel2]))
        if rel1 == rel2:
            return table, 'id1', 'id2'
        return table, '%s_id' % rel1, '%s_id' % rel2

    # -- computes ------------------------------------------------------------

    def _compute_copied(self):
        """``copied`` — ≙ ``_compute_copied`` (``odoo19c: :617-619``).

        Un One2many no se copia, ni un campo derivado (relacionado o
        calculado): su valor lo produce otra cosa.
        """
        return (self.ttype != 'one2many'
                and not (self.related or self.compute))

    def _compute_relation_field_id(self):
        """``relation_field_id`` — ≙ ``odoo19c: :588-593``."""
        if self.state == STATE_MANUAL and self.relation_field:
            return type(self)._get(self.relation, self.relation_field)
        return None

    def _compute_related_field_id(self):
        """``related_field_id`` — ≙ ``odoo19c: :596-601``."""
        if self.state == STATE_MANUAL and self.related:
            return self._related_field()
        return None

    def _in_modules(self):
        """``modules`` — ≙ ``_in_modules`` (``odoo19c: :622-628``).

        Nombre de la fuente para el cómputo cuya superficie de lectura es la
        propiedad :attr:`modules`.
        """
        return self.model_id.django_model._meta.app_label \
            if self.model_id and self.model_id.django_model else ''

    # -- onchange ------------------------------------------------------------
    #
    # La fuente los dispara desde su cliente web al editar el formulario; aquí
    # no hay tal cliente, así que son métodos corrientes que el llamador
    # invoca. Se portan por su nombre y su conducta: rellenan campos derivados
    # a partir del que cambió, y devuelven el aviso cuando algo no cuadra.

    def _onchange_related(self):
        """≙ ``_onchange_related`` (``odoo19c: :710-718``).

        Copia tipo y comodelo desde el campo apuntado, y marca sólo lectura.
        Devuelve el aviso de la fuente en vez de propagar el error.
        """
        if not self.related:
            return None
        try:
            field = self._related_field()
        except UserError as error:
            return {'warning': {'title': 'Advertencia', 'message': str(error)}}
        self.ttype = field.ttype
        self.relation = field.relation
        self.readonly = True
        return None

    def _onchange_relation(self):
        """≙ ``_onchange_relation`` (``odoo19c: :721-725``)."""
        try:
            self._check_relation()
        except ValidationError as error:
            return {'warning': {
                'title': 'El modelo %s no existe' % self.relation,
                'message': str(error)}}
        return None

    def _onchange_compute(self):
        """≙ ``_onchange_compute`` (``odoo19c: :764-766``)."""
        if self.compute:
            self.readonly = True
        return None

    def _onchange_ttype(self):
        """≙ ``_onchange_ttype`` (``odoo19c: :804-813``).

        Rellena los tres nombres del M2M al elegir el tipo, y los limpia
        cuando el tipo deja de serlo.
        """
        if self.ttype == 'many2many' and self.model_id and self.relation:
            if _model_class(self.relation) is None:
                return None
            names = type(self)._custom_many2many_names(
                self.model_id.model, self.relation)
            self.relation_table, self.column1, self.column2 = names
        else:
            self.relation_table = ''
            self.column1 = ''
            self.column2 = ''
        return None

    def _onchange_relation_table(self):
        """≙ ``_onchange_relation_table`` (``odoo19c: :816-832``).

        Comentario de la fuente, verbatim: *"check whether other fields use the
        same table"*. Si el otro campo es el inverso, las columnas se cruzan;
        si no lo es, avisa — dos M2M sobre la misma tabla con columnas
        distintas se pisan.
        """
        if not self.relation_table:
            return None
        others = type(self).objects.filter(
            ttype='many2many', relation_table=self.relation_table,
        ).exclude(pk=self.pk)
        if not others.exists():
            return None
        for other in others:
            if (other.model, other.relation) == (self.relation, self.model):
                self.column1 = other.column2
                self.column2 = other.column1
                return None
        return {'warning': {
            'title': 'Advertencia',
            'message': 'La tabla "%s" la usa otro campo, posiblemente '
                       'incompatible.' % self.relation_table}}

    def _prepare_update(self):
        """¿Se puede modificar o quitar este campo? — ``_prepare_update``.

        Docstring de la fuente, verbatim: *"Check whether the fields in ``self``
        may be modified or removed. This method prevents the
        modification/deletion of many2one fields that have an inverse
        one2many, for instance"* (``odoo19c: ir_model.py:891-978``).

        Se portan sus **dos guardas**, que son lo que el método decide:

        1. **Una columna de módulo no se quita.** Mensaje de la fuente,
           verbatim: *"This column contains module data and cannot be
           removed!"*.
        2. **Un campo del que otro depende no se quita.** La fuente lo resuelve
           con su grafo de dependencias (``get_dependent_fields``,
           ``field_inverses``); aquí el grafo equivalente es
           ``_meta.related_objects`` de Django, que es quien sabe qué relación
           inversa apunta a este campo.

        DIVERGENCIA DE MECANISMO, la de la cabecera del módulo: el resto del
        cuerpo de la fuente —sacar el campo del registro con ``pop_field``,
        revisar que las vistas no queden rotas, y recargar el registro— es
        maquinaria de campos manuales. Django construye su registro al importar
        y lo congela; no hay campo que sacar ni registro que recargar.
        """
        if self.state != STATE_MANUAL:
            raise UserError(
                'Esta columna contiene datos de módulo y no se puede quitar.')
        model_cls = _model_class(self.model)
        if model_cls is None:
            return self
        try:
            field = model_cls._meta.get_field(self.name)
        except FieldDoesNotExist:
            return self
        for relation in model_cls._meta.related_objects:
            if relation.field is not field and relation.remote_field is field:
                raise UserError(
                    "El campo '%s' no se puede quitar porque el campo '%s' "
                    'depende de él.'
                    % (self.name, relation.get_accessor_name()))
        return self

    def save(self, *args, **kwargs):
        """Enganche de Django — ≙ ``create`` (``:1020-1061``) y ``write`` (``:1063-1152``).

        De los dos caminos se portan las guardas, que son su mitad sustantiva:

        - al **crear**, el modelo relacionado de un campo personalizado tiene
          que existir (*"Model %s does not exist!"*), y un One2many almacenado
          exige el Many2one inverso que lo sostiene;
        - al **escribir**, un campo base no se altera por esta vía, su modelo
          no se cambia, y su tipo tampoco — *"Changing the type of a field is
          not yet supported. Please drop it and create it again!"*.

        Y la invalidación que la fuente hace explícita con su comentario *"for
        self._get_ids() in _update_selection()"*: sin ella, un campo nuevo no
        se resuelve por nombre hasta reiniciar.

        DIVERGENCIA DE MECANISMO, declarada: las recargas del registro y la
        actualización del esquema (``_setup_models__``, ``init_models``) no
        tienen receptor, y el renombre de columna que la fuente emite recae
        sobre el esquema vivo, que aquí gobiernan las migraciones.
        """
        creating = self._state.adding
        if creating:
            if self.model_id_id and not self.model:
                self.model = self.model_id.model
            if self.state == STATE_MANUAL:
                if self.relation and not IrModel._get_id(self.relation):
                    raise UserError(
                        '¡El modelo %s no existe!' % self.relation)
                if (self.ttype == 'one2many' and self.store
                        and not self.related
                        and not type(self).objects.filter(
                            ttype='many2one', model=self.relation,
                            name=self.relation_field).exists()):
                    raise UserError(
                        '¡El Many2one %s del modelo %s no existe!'
                        % (self.relation_field, self.relation))
        else:
            previous = self._origin
            if previous is not None:
                if previous.state != STATE_MANUAL:
                    raise UserError(
                        'Las propiedades de un campo base no se alteran por '
                        'esta vía. Modifícalas en código Python, '
                        'preferentemente en un addon propio.')
                if self.model_id_id != previous.model_id_id:
                    raise UserError(
                        '¡Cambiar el modelo de un campo está prohibido!')
                if self.ttype != previous.ttype:
                    raise UserError(
                        'Cambiar el tipo de un campo no está soportado. '
                        'Bórralo y créalo de nuevo.')
        result = super().save(*args, **kwargs)
        registry.clear_cache('stable')
        return result

    def delete(self, *args, **kwargs):
        """Enganche de Django — ≙ ``unlink`` (``:980-1017``).

        La fuente antepone :meth:`_prepare_update`, y aquí igual: es la guarda
        que impide quitar una columna de módulo o un campo del que otro
        depende. El ``_drop_column`` que sigue es la divergencia de DDL ya
        declarada — el esquema lo gobiernan las migraciones.
        """
        self._prepare_update()
        result = super().delete(*args, **kwargs)
        registry.clear_cache('stable')
        return result

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
        que un addon añade columnas sin reescribir ``_reflect_fields``.
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
    def _reflect_fields(cls, model_row):
        """Refleja los campos de un modelo — inverso de ``_reflect_fields``.

        Devuelve ``(creados, actualizados)``. Salta los reversos de relación
        (``auto_created`` sin columna propia): en la referencia esos tampoco
        son filas de ``ir_model_fields``, son el One2many del otro lado.

        La fila de cada campo la arma ``_reflect_field_params``, que es el
        enganche; este método sólo recorre y escribe.

        **Escribe sin pasar por :meth:`save`**, y esa es la equivalencia
        exacta: la fuente refleja con ``upsert_en`` —SQL crudo— precisamente
        para no pasar por la guarda de ``write``, que es del camino
        interactivo. El reflejo escribe filas de campos **base**, y por esa vía
        la guarda lo prohibiría. Aquí ``bulk_create`` y ``update`` son los dos
        escritores de Django que no llaman al enganche.
        """
        model = model_row.django_model
        if model is None:
            return 0, 0
        created = updated = 0
        existing = dict(cls.objects.filter(model=model_row.model)
                        .values_list('name', 'id'))
        nuevas = []
        for field in model._meta.get_fields():
            if field.auto_created and not field.concrete:
                continue
            values = dict(cls._reflect_field_params(field, model_row))
            # ``_reflect_field_params`` puede traer ya ``model`` y ``name`` —el
            # enganche es libre de fijarlos—, así que se imponen aquí en vez de
            # pasarlos aparte: de lo contrario el constructor recibe el mismo
            # argumento dos veces.
            values['model'] = model_row.model
            values['name'] = field.name
            row_id = existing.get(field.name)
            if row_id is None:
                nuevas.append(cls(**values))
                created += 1
            else:
                cls.objects.filter(pk=row_id).update(**values)
                updated += 1
        if nuevas:
            cls.objects.bulk_create(nuevas)
        registry.clear_cache('stable')
        return created, updated


class IrModelInherit(models.Model):
    """``ir.model.inherit`` — el árbol de herencia entre modelos.

    Sin marcas de tiempo: la fuente declara ``_log_access = False``, así que
    aquí **no** se hereda ``TimeStampedModel``. Es una tabla derivada del
    código; su historia la lleva el commit que cambió la clase.
    """

    _name = 'ir.model.inherit'
    _description = 'Model Inheritance Tree'
    _log_access = False

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
    def _reflect_inherits(cls, model_row):
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


class IrModelFieldsSelection(models.OriginMixin, TimeStampedModel):
    """``ir.model.fields.selection`` — un valor de un campo Selection.

    ``models.OriginMixin`` entra por :meth:`save`: el aviso de renombre compara
    el valor entrante contra el guardado, y ``_origin`` es quien lo da.
    """

    _name = 'ir.model.fields.selection'
    _order = 'sequence, id'
    _description = 'Fields Selection'
    _allow_sudo_commands = False

    field_id = fields.Many2one(
        IrModelFields, on_delete=models.CASCADE, db_index=True,
        related_name='selection_ids', verbose_name='Campo',
        db_column='field_id')
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
                fields=['field_id', 'value'],
                name='ir_model_fields_selection_field_uniq'),
        ]

    def __str__(self):
        return f'{self.value} — {self.name}'

    @classmethod
    def _get_selection(cls, field_id, using=DEFAULT_DB_ALIAS):
        """Los pares ``(valor, etiqueta)`` de un campo — ``_get_selection``.

        Docstring de la fuente, verbatim: *"Return the given field's selection
        as a list of pairs (value, string)"* (``odoo19c: ir_model.py:1527-1530``).

        El ``flush_model`` de la fuente vacía su caché de escrituras pendientes
        antes de leer; aquí Django escribe al hacer ``save``, así que no hay
        nada que vaciar.
        """
        return cls._get_selection_data(field_id, using=using)

    @classmethod
    def _get_selection_data(cls, field_id, using=DEFAULT_DB_ALIAS):
        """≙ ``_get_selection_data`` (``odoo19c: :1532-1541``).

        Comentario de la fuente, verbatim: *"return selection as expected on
        registry (no translations)"*. El orden es el suyo —``sequence, id``— y
        de él depende el orden en que la interfaz ofrece los valores.
        """
        return list(cls.objects.using(using).filter(
            field_id=field_id).order_by('sequence', 'id')
            .values_list('value', 'name'))

    @classmethod
    def _existing_selection_data(cls, model_name, field_name,
                                 using=DEFAULT_DB_ALIAS):
        """≙ ``_existing_selection_data`` (``odoo19c: :1652-1663``).

        Docstring de la fuente, verbatim: *"Return the selection data of the
        given model, by field and value, as a dict {field_name: {value:
        row_values}}"*. Su propio cuerpo devuelve ``{value: row}`` para **un**
        campo, no el diccionario de dos niveles que el docstring anuncia; se
        porta el cuerpo, que es lo que sus llamadores consumen.
        """
        rows = cls.objects.using(using).filter(
            field_id__model=model_name, field_id__name=field_name,
        ).values('id', 'value', 'name', 'sequence')
        return {row['value']: row for row in rows}

    @classmethod
    def _update_selection(cls, model_name, field_name, selection,
                          using=DEFAULT_DB_ALIAS):
        """Fija la lista de valores de un campo — ``_update_selection``.

        Docstring de la fuente, verbatim: *"Set the selection of a field to the
        given list, and return the row values of the given selection
        records"* (``odoo19c: :1602-1650``).

        Las tres decisiones de la fuente se conservan: el índice en la lista
        **es** la secuencia, una fila que ya dice lo mismo no se toca, y quitar
        un valor que la lista nueva no trae **avisa** antes de borrarlo —su
        comentario lo dice: *"removing a selection in the new list, at your own
        risks"*, porque las filas que guardaban ese valor quedan apuntando a
        nada.

        La fuente envuelve ``name`` en ``Json({'en_US': ...})`` porque su campo
        es traducible; aquí es un ``Char`` y guarda el texto. El eje de
        traducción del ORM es la tarea **#184**.
        """
        field_row = IrModelFields.objects.using(using).filter(
            model=model_name, name=field_name).first()
        if field_row is None:
            raise ValueError(
                'No se puede fijar la selección de %s.%s: el campo no está en '
                'ir_model_fields' % (model_name, field_name))

        current = cls._existing_selection_data(model_name, field_name,
                                               using=using)
        expected = {
            value: {'value': value, 'name': label, 'sequence': index}
            for index, (value, label) in enumerate(selection)
        }

        to_remove = []
        for value in expected.keys() | current.keys():
            new_row, cur_row = expected.get(value), current.get(value)
            if new_row is None:
                _logger.warning(
                    'Se retira el valor de selección %s en %s.%s',
                    cur_row['value'], model_name, field_name)
                to_remove.append(cur_row['id'])
            elif cur_row is None:
                # ``bulk_create`` no llama a :meth:`save`, y esa es la
                # equivalencia exacta: la fuente inserta aquí con
                # ``query_insert`` —SQL crudo— precisamente para no pasar por
                # la guarda de ``create``, que es del camino interactivo. El
                # reflejo escribe la selección de un campo **base**, y por esa
                # vía la guarda lo prohibiría.
                [created] = cls.objects.using(using).bulk_create([
                    cls(field_id=field_row, **new_row)])
                current[value] = dict(new_row, id=created.pk)
            elif any(new_row[key] != cur_row[key] for key in new_row):
                cls.objects.using(using).filter(pk=cur_row['id']).update(**new_row)
                current[value] = dict(new_row, id=cur_row['id'])

        if to_remove:
            cls.objects.using(using).filter(pk__in=to_remove).delete()
            for value in list(current):
                if value not in expected:
                    del current[value]
        return current

    @classmethod
    def _reflect_selections(cls, model_classes, using=DEFAULT_DB_ALIAS):
        """Refleja las selecciones de los campos dados — ``_reflect_selections``.

        Docstring de la fuente, verbatim: *"Reflect the selections of the
        fields of the given models"* (``odoo19c: :1543-1600``).

        Su validación se porta entera, y es la que importa: un par
        ``(valor, etiqueta)`` con algo que no sea texto se rechaza **nombrando
        los campos culpables**, en vez de dejar que reviente al escribir.

        La fuente recorre ``model._fields`` buscando ``selection`` y
        ``reference``; aquí el equivalente es un campo de Django con
        ``choices``, que es la misma información en el mismo sitio.
        """
        offenders = OrderedSet()
        pending = []
        for model_cls in model_classes:
            for field in model_cls._meta.get_fields():
                choices = getattr(field, 'choices', None)
                if not choices:
                    continue
                for value, label in choices:
                    if not isinstance(value, str) or not isinstance(label, str):
                        offenders.add(
                            '%s.%s' % (model_cls._meta.label, field.name))
                pending.append((model_cls._meta.label, field.name, choices))
        if offenders:
            raise ValidationError(
                'Los campos %s tienen un valor o etiqueta que no es texto en '
                'su selección' % ', '.join(offenders))
        for model_name, field_name, choices in pending:
            if IrModelFields.objects.using(using).filter(
                    model=model_name, name=field_name).exists():
                cls._update_selection(model_name, field_name, list(choices),
                                      using=using)

    def _process_ondelete(self, using=DEFAULT_DB_ALIAS):
        """Aplica la politica de borrado de este valor — ``_process_ondelete``.

        Docstring de la fuente, verbatim: *"Process the 'ondelete' of the given
        selection values"* (``odoo19c: ir_model.py:1749-1822``).

        Un valor de seleccion que desaparece deja huerfanas las filas que lo
        guardaban. La politica dice que hacer con ellas, y la declara quien
        amplio el vocabulario, junto a su ``selection_add``:

        ==================  =================================================
        Politica            Efecto sobre las filas con este valor
        ==================  =================================================
        ``'set null'``      el campo queda vacio — es el defecto
        ``'set default'``   el campo toma el ``default`` de su declaracion
        ``'set VALOR'``     el campo toma ``VALOR``
        ``'cascade'``       la fila se borra con el valor
        invocable           se le entrega el conjunto de filas y decide el
        ==================  =================================================

        DIVERGENCIA DE MECANISMO, en tres ejes medidos:

        1. **La politica se lee del campo, no de un atributo del ``Field`` de
           la fuente.** Alla vive en ``field.ondelete`` porque el campo es suyo;
           aqui el campo es de Django y el atributo se lo cuelga
           :func:`~orm.model_classes.extend_selection_choices`, con el **mismo
           nombre**. Es el receptor que la tarea **#205** construyo: el bloqueo
           declarado decia que faltaba en ``fields.Selection``, y el sitio real
           es el hermano de ``selection_add``, que ya existia.
        2. **El respaldo del ``safe_write``.** La fuente envuelve la escritura
           en un ``savepoint`` y, si el ORM levanta, la repite por SQL crudo.
           Aqui el savepoint es ``transaction.atomic(savepoint=True)`` y el
           respaldo es ``QuerySet.update()``, que salta ``save()`` y sus
           senales — el mismo rodeo, con el constructor del stack.
        3. **El bucle por empresa no aplica.** Alla recorre ``env.companies``
           para un campo ``company_dependent``, porque su valor se guarda como
           ``{empresa: valor}`` en un ``jsonb`` y hay que tocar una entrada por
           empresa. Aqui ese eje ya esta construido (tarea #129) y su escritura
           pasa por el descriptor, que resuelve la empresa activa: la
           bifurcacion la hace el campo, no este metodo. Es la misma razon por
           la que :meth:`_get_records` tampoco bifurca.

        No levanta si el modelo o el campo desaparecieron del registro: la
        fuente tambien los salta, con su comentario sobre el script de
        migracion (``:1776-1786``).
        """
        model_cls = _model_class(self.field_id.model)
        if model_cls is None:
            return
        try:
            field = model_cls._meta.get_field(self.field_id.name)
        except FieldDoesNotExist:
            return
        if not getattr(field, 'choices', None):
            # El campo cambio de tipo; la fuente lo salta igual (``:1788-1790``).
            return

        policy = (getattr(field, 'ondelete', None) or {}).get(self.value)
        if policy is None:
            # No viene de una ampliacion de vocabulario: no hay nada que hacer.
            return

        records = self._get_records(using=using)
        if records is None:
            return

        if callable(policy):
            policy(records)
        elif policy == 'cascade':
            records.delete()
        elif policy == 'set default':
            value = None if field.default is NOT_PROVIDED else field.default
            self._safe_write(records, field.name, value, using=using)
        elif policy == 'set null':
            self._safe_write(records, field.name, None, using=using)
        elif policy.startswith('set '):
            self._safe_write(records, field.name, policy[4:], using=using)
        else:
            # Comprobacion de sanidad; la validacion vive en
            # ``check_ondelete_policies``, al declarar la politica.
            raise ValueError(
                f'La politica de borrado {policy!r} no es valida para el '
                f'campo {self.field_id.name!r}')

    @staticmethod
    def _safe_write(records, field_name, value, using=DEFAULT_DB_ALIAS):
        """Escribe por el ORM y, si levanta, por debajo — ``safe_write``.

        ≙ la clausura ``safe_write`` (``odoo19c: ir_model.py:1751-1773``), con
        su comentario verbatim: *"going through the ORM failed, probably
        because of an exception in an override or possibly a constraint"*.

        Se saca a metodo propio porque el test la interroga aparte; alla es una
        clausura y no se puede llamar sola. El respaldo es ``update()``, que no
        dispara ``save()`` ni sus senales — el equivalente del SQL crudo de la
        fuente, y por la misma razon: si un override o una restriccion impide
        limpiar el valor huerfano, dejarlo apuntando al vacio es peor.
        """
        if not records.exists():
            return
        try:
            with transaction.atomic(using=using, savepoint=True):
                for record in records:
                    setattr(record, field_name, value)
                    record.save(using=using)
        except Exception:
            _logger.warning(
                'No se pudo aplicar la politica de borrado sobre %s.%s; se '
                'intenta por debajo del ORM.',
                records.model._meta.label, field_name)
            records.update(**{field_name: value})

    def _get_records(self, using=DEFAULT_DB_ALIAS):
        """Los registros que tienen este valor — ``_get_records``.

        Docstring de la fuente, verbatim: *"Return the records having 'self' as
        a value"* (``odoo19c: :1823-1846``).

        La fuente lo escribe en SQL crudo y bifurca por ``company_dependent``,
        que allá se guarda como ``jsonb`` por empresa. Aquí el eje
        ``company_dependent`` ya está construido (tarea #129) y su lectura pasa
        por el descriptor, así que el filtro es el del ORM y la bifurcación no
        hace falta.
        """
        model_cls = _model_class(self.field_id.model)
        if model_cls is None:
            return None
        return model_cls.objects.using(using).filter(
            **{self.field_id.name: self.value})

    def _unlink_if_manual(self):
        """Un valor de un campo de módulo no se borra a mano — ``_unlink_if_manual``.

        ≙ ``odoo19c: :1723-1731``, con su comentario verbatim: *"Prevent manual
        deletion of module columns"*, y su mensaje. La fuente lo engancha con
        ``@api.ondelete(at_uninstall=False)``; aquí lo llama :meth:`delete`,
        con la misma excepción al desinstalar.
        """
        if self.field_id.state != STATE_MANUAL:
            raise UserError(
                'Las propiedades de un campo base no se alteran por esta vía. '
                'Modifícalas en código Python, preferentemente en un addon '
                'propio.')

    def save(self, *args, **kwargs):
        """Enganche de Django — ≙ ``create`` (``:1665-1687``) y ``write`` (``:1689-1721``).

        De los dos caminos se porta la guarda común, que es su mitad
        sustantiva: **la selección de un campo base no se toca por esta vía**.
        La fuente la escribe dos veces con el mismo mensaje, en ``create``
        sobre el campo destino y en ``write`` sobre cada fila.

        DIVERGENCIA DE MECANISMO, la de la cabecera del módulo: las recargas
        del registro (``_setup_models__``) no tienen receptor —Django congela
        el suyo al importar— y el ``UPDATE`` que la fuente emite al renombrar
        un valor recae sobre el esquema vivo, que aquí gobiernan las
        migraciones. Lo que sí queda es el aviso: renombrar un valor deja las
        filas que lo guardaban apuntando al viejo.
        """
        creating = self._state.adding
        # La fuente reparte la guarda de forma asimétrica, y se conserva: en
        # ``create`` rechaza **siempre** (``:1669-1673``); en ``write`` sólo si
        # quien escribe no es administrador (``:1693-1698``).
        if self.field_id.state != STATE_MANUAL and (creating or not is_system()):
            raise UserError(
                'Las propiedades de un campo base no se alteran por esta vía. '
                'Modifícalas en código Python, preferentemente en un addon '
                'propio.')
        if not creating:
            previous = self._origin
            if previous is not None and previous.value != self.value:
                _logger.warning(
                    'El valor de selección %s.%s pasa de %s a %s; las filas '
                    'que guardaban el viejo no se migran desde aquí.',
                    self.field_id.model, self.field_id.name,
                    previous.value, self.value)
        return super().save(*args, **kwargs)

    def delete(self, *args, at_uninstall=False, **kwargs):
        """Enganche de Django — ≙ ``unlink`` (``odoo19c: :1734-1746``).

        El orden es el de la fuente: primero la guarda, luego la politica de
        borrado sobre las filas que guardaban el valor, y sólo entonces el
        borrado del valor. Invertirlo dejaría a :meth:`_get_records` sin nada
        que encontrar.

        ``at_uninstall`` — el receptor de ``@api.ondelete(at_uninstall=False)``
        ---------------------------------------------------------------------

        La fuente **no** llama a :meth:`_unlink_if_manual` desde ``unlink``: la
        registra con ``@api.ondelete(at_uninstall=False)`` (``:1723``), y ese
        argumento significa *"no corras esta guarda al desinstalar"*. Aquí no
        hay decorador que registre enganches de borrado, así que la llamada es
        explícita y la bandera viaja como palabra clave del método.

        Sin ella el porte queda **incoherente**: la guarda rehúsa borrar el
        valor de un campo base, y ``_process_ondelete`` sólo tiene sentido
        justo ahí — al desinstalar el addon que sumó el valor. Un campo base
        es lo que declara cualquier módulo, así que la política de borrado
        quedaba inalcanzable para el caso que la motiva. El docstring de
        :meth:`_unlink_if_manual` ya prometía *"la misma excepción al
        desinstalar"*; esto es esa excepción.

        DIVERGENCIA DE MECANISMO: la fuente además condiciona la guarda a
        ``self.pool.ready`` — no dispara mientras el registro se carga. Aquí
        Django congela el suyo al importar y no hay fase equivalente que
        consultar, así que esa mitad no tiene receptor.

        :param at_uninstall: ``True`` cuando el borrado es parte de desinstalar
            un módulo. Salta la guarda y deja correr la política.
        """
        if not at_uninstall:
            self._unlink_if_manual()
        self._process_ondelete()
        return super().delete(*args, **kwargs)


class IrModelConstraint(models.CopyMixin, TimeStampedModel):
    """``ir.model.constraint`` — restricción o índice SQL rastreado.

    Registro, no ejecutor: ver el docstring del módulo sobre por qué no se
    porta el ``DROP CONSTRAINT`` de la desinstalación.

    ``models.CopyMixin`` entra por :meth:`copy_data`, que la fuente declara
    aquí para dar a la copia un nombre distinto.
    """

    _name = 'ir.model.constraint'
    _description = 'Model Constraint'
    _allow_sudo_commands = False

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

    def copy_data(self, default=None, seen=None):
        """≙ ``copy_data`` (``odoo19c: ir_model.py:1925-1927``).

        El nombre es único por ``(name, module)``, así que una copia no puede
        llevar el mismo: la fuente le añade el sufijo ``_copy`` y aquí se hace
        igual.
        """
        values = super().copy_data(default, seen=seen)
        if values is None:
            return None
        values['name'] = self.name + '_copy'
        return values

    @classmethod
    def _reflect_constraint(cls, model_cls, conname, constraint_type,
                            definition, module, message=None,
                            using=DEFAULT_DB_ALIAS):
        """Registra una restricción — ``_reflect_constraint``.

        Docstring de la fuente, verbatim: *"Reflect the given constraint, and
        return its corresponding record if a record is created or modified;
        returns ``None`` otherwise. The reflection makes it possible to remove
        a constraint when its corresponding module is uninstalled. ``type`` is
        either 'f', 'i', or 'u' depending on the constraint being a foreign key
        or not"* (``odoo19c: ir_model.py:1929-1985``).

        Las tres decisiones de la fuente se conservan: sin módulo no se
        registra nada —*"no need to save constraints for custom models as
        they're not part of any module"*—; el tipo se acota a los tres valores;
        y una fila que ya dice lo mismo **no se toca**, que es lo que hace
        distinguible «cambió» de «ya estaba».

        La fuente lo escribe en SQL crudo con ``INSERT``/``UPDATE``; aquí es el
        ORM. El ``message`` de allá es un ``jsonb`` por idioma porque su campo
        es traducible; aquí es un ``Char`` y guarda el texto — el eje de
        traducción del ORM es la tarea **#184**.
        """
        if not module:
            return None
        assert constraint_type in ('f', 'u', 'i')
        module_row = IrModule.objects.using(using).filter(name=module).first()
        if module_row is None:
            raise ValueError(
                'No se puede registrar la restricción %s: el módulo %s no '
                'está en ir_module_module' % (conname, module))
        label = model_cls._meta.label
        model_row = IrModel.objects.using(using).filter(model=label).first()
        if model_row is None:
            raise ValueError(
                'No se puede registrar la restricción %s: el modelo %s no '
                'está en ir_model' % (conname, label))

        row = cls.objects.using(using).filter(
            name=conname, module=module_row).first()
        if row is None:
            return cls.objects.using(using).create(
                name=conname, module=module_row, model=model_row,
                type=constraint_type, definition=definition or '',
                message=message or '')
        if (row.type, row.definition, row.message) == (
                constraint_type, definition or '', message or ''):
            return None
        row.type = constraint_type
        row.definition = definition or ''
        row.message = message or ''
        row.save(using=using)
        return row

    @classmethod
    def _reflect_constraints(cls, model_classes, using=DEFAULT_DB_ALIAS):
        """≙ ``_reflect_constraints`` (``odoo19c: :1987-1990``).

        Docstring de la fuente, verbatim: *"Reflect the table objects of the
        given models"*. Recibe las clases directamente porque aquí no hay un
        registro que resuelva un nombre punteado a un modelo vivo.
        """
        for model_cls in model_classes:
            cls._reflect_model(model_cls, using=using)

    @classmethod
    def _reflect_model(cls, model_cls, using=DEFAULT_DB_ALIAS):
        """Refleja los objetos de tabla de un modelo — ``_reflect_model``.

        Docstring de la fuente, verbatim: *"Reflect the _table_objects of the
        given model"* (``odoo19c: :1992-2003``).

        **Dónde viven los objetos de tabla es la única divergencia**, y ya está
        declarada por ``atributos-de-clase-de-modelo.md``: la fuente los guarda
        en ``model._table_objects``, un diccionario que su metaclase llena con
        los atributos de clase ``models.Constraint`` y ``models.Index``; aquí
        su hogar es ``Meta.constraints`` y ``Meta.indexes``, con el nombre
        conservado. De ahí sale todo lo que la fuente lee: el nombre, el tipo
        —``i`` para un índice, ``u`` para el resto, su misma regla— y la
        definición, que Django emite con ``constraint_sql``/``create_sql``
        sobre un editor de esquema que **no ejecuta nada** (``collect_sql``).

        El módulo es el ``app_label`` del modelo, que es lo que aquí cumple el
        papel del ``cons._module`` de allá.
        """
        module = model_cls._meta.app_label
        registered = []
        with connections[using].schema_editor(collect_sql=True) as editor:
            objects = [
                (obj.name, 'u', obj.constraint_sql(model_cls, editor))
                for obj in model_cls._meta.constraints
            ] + [
                (obj.name, 'i', str(obj.create_sql(model_cls, editor)))
                for obj in model_cls._meta.indexes
            ]
        for conname, constraint_type, definition in objects:
            if not conname:
                _logger.warning(
                    'Objeto de tabla sin nombre en %s', model_cls._meta.label)
                continue
            row = cls._reflect_constraint(
                model_cls, conname, constraint_type, definition, module,
                using=using)
            if row is not None:
                registered.append(row)
        return registered

    @classmethod
    def _module_data_uninstall(cls, modules_to_remove, using=DEFAULT_DB_ALIAS):
        """≙ ``unlink`` (``odoo19c: :1873-1923``), su mitad de datos.

        La guarda de propiedad es la de la fuente, con su comentario verbatim:
        *"double-check we are really going to delete all the owners of this
        schema element"* — una restricción que **otro** módulo también declara
        no se toca.

        DIVERGENCIA DE MECANISMO, la de la cabecera del módulo y la misma que
        ``IrModelRelation`` declara: la fuente cierra emitiendo ``ALTER TABLE
        ... DROP CONSTRAINT`` y ``DROP INDEX`` sobre el esquema vivo, tras
        consultar ``pg_constraint`` para no soltar lo que no existe. Aquí el
        esquema lo gobiernan las migraciones de Django. Se porta el borrado de
        las filas de registro y se devuelven los nombres que la fuente habría
        soltado, para que quien desinstale sepa qué migración le falta.

        El nombre es ``_module_data_uninstall`` y no ``unlink`` porque **no es
        el borrado de un registro**: es el paso de desinstalación de un módulo,
        el mismo que ``IrModelData`` e ``IrModelRelation`` nombran así. La
        fuente lo cuelga de ``unlink`` porque allá la desinstalación borra el
        conjunto; aquí ``delete`` es el enganche de Django sobre una fila y
        colgarle este cuerpo le daría a un borrado corriente el efecto de una
        desinstalación.
        """
        if not is_system():
            raise AccessError(
                'Administrator access is required to uninstall a module')

        rows = list(cls.objects.using(using).filter(
            module__in=list(modules_to_remove)).order_by('-id'))
        own_ids = {row.pk for row in rows}
        to_drop = OrderedSet()
        deletable_ids = []
        for row in rows:
            owners = set(cls.objects.using(using).filter(
                name=row.name).values_list('pk', flat=True))
            if owners - own_ids:
                continue
            to_drop.add(row.name)
            deletable_ids.append(row.pk)

        if deletable_ids:
            cls.objects.using(using).filter(pk__in=deletable_ids).delete()
        for name in to_drop:
            _logger.info(
                'La restricción %s queda huérfana al desinstalar el módulo; '
                'su borrado es una migración, no DDL desde el modelo.', name)
        return list(to_drop)


class IrModelRelation(TimeStampedModel):
    """``ir.model.relation`` — tabla intermedia de un Many2many.

    La fuente declara ``write_date``/``create_date`` explícitos; aquí los
    aporta ``TimeStampedModel`` (``created_at``/``updated_at``), que es el
    equivalente del log-access en este árbol.
    """

    _name = 'ir.model.relation'
    _description = 'Relation Model'
    _allow_sudo_commands = False

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

    @classmethod
    def _reflect_relation(cls, model_cls, table, module,
                          using=DEFAULT_DB_ALIAS):
        """Registra la tabla de un Many2many — ``_reflect_relation``.

        Docstring de la fuente, verbatim: *"Reflect the table of a many2many
        field for the given model, to make it possible to delete it later when
        the module is uninstalled"* (``odoo19c: ir_model.py:2051-2069``).

        Sin este registro la fila no existe, y sin la fila
        :meth:`_module_data_uninstall` no sabe qué tablas intermedias dejó un
        módulo: la trazabilidad del Many2many empieza aquí.

        La fuente lo escribe en SQL crudo con un ``SELECT`` de existencia y un
        ``INSERT`` condicionado; aquí es ``get_or_create``, que es la misma
        conducta —idempotente por ``(name, module)``— en el ORM. Y no hace
        falta el ``invalidate_all`` de la primera línea de la fuente: ese vacía
        su caché de registros, que aquí no existe.

        El módulo o el modelo que no estén en sus tablas **no se inventan**: la
        fuente los resuelve con dos subconsultas que dan ``NULL`` si faltan, y
        su ``INSERT`` fallaría por ``NOT NULL``. Aquí se levanta ``ValueError``
        con el nombre que faltó, que es el mismo rechazo con el motivo escrito.
        """
        module_row = IrModule.objects.using(using).filter(name=module).first()
        if module_row is None:
            raise ValueError(
                'No se puede registrar la relación %s: el módulo %s no está '
                'en ir_module_module' % (table, module))
        label = model_cls._meta.label
        model_row = IrModel.objects.using(using).filter(model=label).first()
        if model_row is None:
            raise ValueError(
                'No se puede registrar la relación %s: el modelo %s no está '
                'en ir_model' % (table, label))
        row, _created = cls.objects.using(using).get_or_create(
            name=table, module=module_row, defaults={'model': model_row})
        return row

    @classmethod
    def _module_data_uninstall(cls, modules_to_remove, using=DEFAULT_DB_ALIAS):
        """≙ ``_module_data_uninstall`` (``odoo19c: :2022-2049``), su mitad de datos.

        Docstring de la fuente, verbatim: *"Delete PostgreSQL many2many
        relations tracked by this model"*.

        La guarda de propiedad es el corazón del método y se porta entera: una
        tabla intermedia que **otro** módulo también declara no se toca. La
        fuente lo dice en su propio comentario —*"as installed modules have
        defined this element we must not delete it!"*— y lo resuelve
        comprobando que **todos** los dueños de ese nombre estén dentro del
        lote que se desinstala.

        DIVERGENCIA DE MECANISMO, la misma que declara
        ``IrModelData._module_data_uninstall`` y que el registro
        ``scripts/divergencias_declaradas.txt`` lleva anotada: la fuente cierra
        emitiendo ``DROP TABLE ... CASCADE`` sobre cada tabla superviviente, y
        aquí el esquema lo gobiernan las migraciones de Django. Lo que se porta
        es el borrado de las **filas de registro**, que es lo que da la
        trazabilidad; el DDL no.

        Devuelve los nombres de tabla que la fuente habría soltado, para que
        quien desinstale sepa qué migración le falta escribir.
        """
        if not is_system():
            raise AccessError(
                'Administrator access is required to uninstall a module')

        rows = list(cls.objects.using(using).filter(
            module__in=list(modules_to_remove)).order_by('-id'))
        own_ids = {row.pk for row in rows}
        to_drop = OrderedSet()
        deletable_ids = []
        for row in rows:
            owners = set(cls.objects.using(using).filter(
                name=row.name).values_list('pk', flat=True))
            if not owners.issubset(own_ids):
                continue
            to_drop.add(row.name)
            deletable_ids.append(row.pk)

        if deletable_ids:
            cls.objects.using(using).filter(pk__in=deletable_ids).delete()
        for table in to_drop:
            _logger.info(
                'La tabla %s queda huérfana al desinstalar el módulo; su '
                'borrado es una migración, no DDL desde el modelo.', table)
        return list(to_drop)


class IrModelAccess(TimeStampedModel):
    """``ir.model.access`` — permiso CRUD por modelo y grupo.

    Dato, no gate: la autorización efectiva de este árbol es por capacidad
    (``HasCapability``, DEC-11). Ver el docstring del módulo.
    """

    _name = 'ir.model.access'
    _description = 'Model Access'
    _order = 'model_id,group_id,name,id'
    _allow_sudo_commands = False

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
        ``(uid, mode)``. Aquí **también se memoriza, desde la tarea #172**: el
        invalidador que faltaba —``call_cache_clearing_methods``— ya está
        portado abajo y lo llaman :meth:`save` y :meth:`delete`, igual que la
        fuente lo llama desde ``create``/``write``/``unlink``. Sin él,
        memorizar habría sido el defecto que la tarea #58 midió en
        ``_get_group_ids``: una ACL revocada seguiría concediendo hasta
        reiniciar el proceso.

        **La clave es la del conjunto de grupos, no la del usuario.** La fuente
        puede usar ``self.env.uid`` porque su ``env`` lo lleva; aquí el usuario
        entra por parámetro y puede llegar sin resolver (``user=None`` significa
        *el de la petición*), así que una clave sobre ``user`` mezclaría a dos
        usuarios distintos bajo el mismo ``None``. Se resuelve primero y se
        memoriza sobre ``(grupos, modo)``, que es de lo que el resultado
        depende de verdad: dos usuarios con los mismos grupos ven el mismo
        conjunto, y la fuente les daría dos entradas iguales.
        """
        cls._check_mode(access_mode)
        if user is None:
            user = get_current_user()
        group_ids = (frozenset(user._get_group_ids())
                     if user is not None else frozenset())
        return cls._allowed_models_for_groups(group_ids, access_mode)

    @classmethod
    @ormcache('group_ids', 'access_mode', cache='stable')
    def _allowed_models_for_groups(cls, group_ids, access_mode):
        """La mitad memorizable de :meth:`_get_allowed_models`.

        Símbolo **nuestro**: la fuente no lo tiene porque no lo necesita —su
        ``ormcache`` se cuelga directamente de ``_get_allowed_models`` con la
        clave ``self.env.uid``. Aquí el usuario llega por parámetro y hay que
        resolverlo **antes** de calcular la clave; ese corte es lo único que
        este método añade. La consulta es la de la fuente, sin cambios.
        """
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

    @classmethod
    @api.model
    @ormcache('model_name', 'access_mode', cache='stable')
    def _get_access_groups(cls, model_name, access_mode='read'):
        """La expresión de grupos que puede ``access_mode`` sobre ``model_name``.

        ≙ ``_get_access_groups`` (``odoo19c: ir_model.py:2109-2126``), con sus
        tres desenlaces verbatim y en el mismo orden:

        1. sin ninguna ACL que conceda el modo → ``group_definitions.empty``;
        2. con **alguna** ACL sin grupo → ``group_definitions.universe``, porque
           una ACL global abre el modo a todos;
        3. si no → ``from_ids`` de los grupos de las ACL que lo conceden.

        Estuvo bloqueado por ``tools/set_expression.py``, que no existía en
        este árbol — tarea **#204**, que lo portó entero. **No era una
        divergencia**: el álgebra es pura, sin base de datos, y el stack no la
        traía sólo porque nadie la había construido.

        Sus dos mitades consultables —:meth:`group_names_with_access` y
        :meth:`has_global_access`— **se conservan**: no son un sustituto que
        ahora sobre, sino los dos consumidores concretos que ya tenían llamador
        (el mensaje de ``_make_access_error`` y el panel). Lo que aporta este
        método es lo que ninguna de las dos puede: **componer**, para expresar
        "puede quien esté en A y no en B".

        Divergencia de ENLACE, la misma que el resto del archivo declara: la
        fuente lo marca ``@api.model`` sobre un método de instancia; aquí es un
        ``classmethod``. ``@api.model`` se conserva encima y ``ormcache`` lee
        ``_name`` del ``cls``.

        La memoria va a ``stable``, la familia que la fuente nombra, y la
        invalida :meth:`call_cache_clearing_methods` — el mismo invalidador que
        ya cubre :meth:`_allowed_models_for_groups`, porque lo que cambia el
        resultado de los dos es exactamente lo mismo: una fila de esta tabla.
        """
        cls._check_mode(access_mode)
        label = cls._model_label(model_name)
        accesses = list(cls.objects.filter(
            model_id__model=label, active=True,
            **{f'perm_{access_mode}': True},
        ).values_list('group_id', flat=True))

        group_definitions = ResGroups._get_group_definitions()
        if not accesses:
            return group_definitions.empty
        if any(group_id is None for group_id in accesses):
            # Hay acceso global: una ACL sin grupo concede el modo a todos.
            return group_definitions.universe
        return group_definitions.from_ids(accesses)

    @classmethod
    def call_cache_clearing_methods(cls):
        """Vacía lo que una ACL modificada invalida — ``call_cache_clearing_methods``.

        ≙ ``odoo19c: odoo/addons/base/models/ir_model.py:2196-2199``. La fuente
        vacía dos cosas: el caché de registros del entorno
        (``env.invalidate_all()``) y la familia ``stable`` del registry, con el
        comentario *"mainly _get_allowed_models"*.

        Aquí sólo hay la segunda: el caché de registros de la fuente es su
        ``env``, y este árbol no lo tiene —Django relee la fila—. La familia
        ``stable`` sí existe (``orm.registry.clear_cache``) y es la que guarda
        :meth:`_allowed_models_for_groups`, que es a lo que apunta el
        comentario de la fuente.
        """
        registry.clear_cache('stable')

    def save(self, *args, **kwargs):
        """Enganche de Django — ≙ ``create`` (``:2205-2214``) y ``write`` (``:2216-2218``).

        Los dos caminos de la fuente colapsan en ``save``, y los dos empiezan
        por lo mismo: :meth:`call_cache_clearing_methods`. La fuente lo llama
        **antes** de escribir, no después, y aquí se conserva el orden — una
        entrada memorizada durante la escritura se recalcularía con la fila ya
        cambiada, que es lo que la invalidación busca.

        El aviso de la regla sin grupo es de ``create`` y sólo de ahí: una ACL
        que concede algún permiso **sin** nombrar grupo lo concede a todos, y
        la fuente lo marca como *deprecated feature*. Se emite al crear, que es
        cuando la fila nace con esa forma.
        """
        creating = self._state.adding
        type(self).call_cache_clearing_methods()
        if creating and self.group_id_id is None and any(
                (self.perm_read, self.perm_write,
                 self.perm_create, self.perm_unlink)):
            _logger.warning(
                'La regla %s no tiene grupo; es una capacidad obsoleta. Toda '
                'regla que conceda acceso debería nombrar su grupo.', self.name)
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Enganche de Django — ≙ ``unlink`` (``:2220-2222``)."""
        type(self).call_cache_clearing_methods()
        return super().delete(*args, **kwargs)


class IrModelData(models.CopyMixin, TimeStampedModel):
    """``ir.model.data`` — identificador externo de un registro.

    Sirve para dos cosas, según la fuente: integrar datos con sistemas de
    terceros identificando registros de forma estable, y rastrear el origen de
    lo que instaló un módulo para poder actualizarlo después.

    Los veinte símbolos de la fuente
    ================================

    **17 portados con su nombre.** Los tres restantes son la divergencia de
    stack que este árbol ya tiene declarada en todas partes: ``create`` y
    ``write`` colapsan en :meth:`save` —Django unifica los dos caminos y
    ``_state.adding`` los distingue— y ``unlink`` es :meth:`delete`. Las dos
    invalidaciones de caché que la fuente reparte entre los tres van con ellos.

    **El bloque escritor es nuevo desde la tarea #115.** Hasta entonces esta
    clase tenía el resolutor (leer un identificador) y un ``set_xmlid``
    nuestro, pero no el cargador: ``_update_xmlids`` con su ``INSERT ... ON
    CONFLICT``, ``_lookup_xmlids``, ``_load_xmlid`` y ``_process_end``. Sin
    ellos la tabla se poblaba fila a fila y nadie retiraba lo que un módulo
    dejaba de declarar.

    **De ``_module_data_uninstall`` se porta la mitad de datos, no la de DDL**
    — ver la divergencia declarada en la cabecera del módulo: aquí el esquema
    lo gobiernan las migraciones de Django.

    ``res_id`` es un ``Many2oneReference`` allá: el par (``model`` Char,
    ``res_id`` entero). Nuestro alias ``fields.Many2oneReference`` es
    ``GenericForeignKey`` (``orm/fields_reference.py:12``), que exige un FK
    ``content_type`` en lugar del Char y **cambia la forma de la tabla**. Se
    porta el par tal como está en la fuente — mismo criterio que
    ``ir_attachment.res_id`` ya usa en este árbol.
    """

    _name = 'ir.model.data'
    _description = 'Model Data'
    _order = 'module, model, name'
    _allow_sudo_commands = False

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

    def _compute_complete_name(self):
        """≙ ``_compute_complete_name`` (``odoo19c: ir_model.py:2248-2251``).

        ``modulo.nombre``, sin punto colgante cuando el módulo está vacío.
        """
        return '.'.join(part for part in (self.module, self.name) if part)

    def _compute_reference(self):
        """≙ ``_compute_reference`` (``odoo19c: :2253-2256``) — ``"modelo,id"``."""
        return f'{self.model},{self.res_id}'

    def _compute_display_name(self):
        """≙ ``_compute_display_name`` (``odoo19c: :2258-2267``).

        El nombre del registro apuntado si se puede leer; el completo si el
        modelo no está en el registro, el ``res_id`` es vacío, o leerlo levanta
        — la fuente traga la excepción por la misma razón: un identificador
        externo puede sobrevivir al registro que nombraba.
        """
        complete_name = self._compute_complete_name()
        if not self.res_id or not self.model:
            return complete_name
        model_cls = _model_class(self.model)
        if model_cls is None:
            return complete_name
        try:
            target = model_cls.objects.filter(pk=self.res_id).first()
            return (target and str(target)) or complete_name
        except Exception:                    # noqa: BLE001 — verbatim de la fuente
            return complete_name

    def __str__(self):
        """Enganche de Django — delega en ``_compute_display_name``."""
        return self._compute_display_name()

    @property
    def complete_name(self):
        """Superficie de lectura del campo; el cómputo es el de la fuente."""
        return self._compute_complete_name()

    @property
    def reference(self):
        """Superficie de lectura del campo; el cómputo es el de la fuente."""
        return self._compute_reference()

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
    @ormcache('xmlid', 'using', cache='default')
    def _xmlid_lookup(cls, xmlid, using=DEFAULT_DB_ALIAS):
        """``_xmlid_lookup`` — ``(model, res_id)`` o ``ValueError``.

        Memorizado como en la fuente (``odoo19c: :2270-2280``, ``@ormcache
        ('xmlid')``). Lo vacían :meth:`write` y :meth:`delete`, y
        :meth:`_update_xmlids` **siembra** el valor correcto en vez de vaciar
        — durante una instalación se crean cientos de identificadores y vaciar
        en cada uno tira el resto de la caché, que es lo que su comentario
        dice: *"small optimisation … set the correct value in the cache to
        avoid a bunch of query"*.

        DIVERGENCIA DE CLAVE, la misma que ``ir_config_parameter.py`` y
        ``properties_base_definition.py`` declaran: ``using`` entra en la clave
        porque aquí el registry es el módulo y no hay uno por base.

        El identificador es ``modulo.nombre``; el ``split`` es por el **primer**
        punto porque el nombre puede llevar más (``l10n_mx.tax12`` frente a
        ``account.1_tax_group_16``).
        """
        module, _, name = xmlid.partition('.')
        if not name:
            raise ValueError(
                'Identificador externo mal formado (falta el módulo): %s' % xmlid)
        row = cls.objects.using(using).filter(module=module, name=name).first()
        if row is None or not row.res_id:
            raise ValueError('Identificador externo no encontrado: %s' % xmlid)
        return row.model, row.res_id

    @classmethod
    def _xmlid_to_res_model_res_id(cls, xmlid, raise_if_not_found=False,
                                   using=DEFAULT_DB_ALIAS):
        """``_xmlid_to_res_model_res_id`` — la pareja, o ``(None, None)``.

        La referencia devuelve ``(False, False)`` porque en su ORM el falso es
        el vacío de cualquier tipo; aquí el vacío es ``None``.
        """
        try:
            return cls._xmlid_lookup(xmlid, using=using)
        except ValueError:
            if raise_if_not_found:
                raise
            return None, None

    @classmethod
    def _xmlid_to_res_id(cls, xmlid, raise_if_not_found=False,
                         using=DEFAULT_DB_ALIAS):
        """``_xmlid_to_res_id`` — sólo el id."""
        return cls._xmlid_to_res_model_res_id(
            xmlid, raise_if_not_found, using=using)[1]

    @classmethod
    def ref(cls, xmlid, raise_if_not_found=True, using=DEFAULT_DB_ALIAS):
        """El registro que designa el identificador — ≙ ``env.ref``.

        Vive aquí y no en un ``env`` porque este proyecto no tiene ese objeto:
        la referencia lo pone en ``odoo/orm/environments.py:158`` sólo para dar
        el atajo, y su cuerpo no hace otra cosa que llamar a
        ``_xmlid_to_res_model_res_id`` y traer el registro.

        Devuelve ``None`` si la fila apunta a algo ya borrado — la referencia
        hace lo mismo con su ``record.exists()``: un identificador externo
        puede sobrevivir al registro que nombraba.
        """
        model_label, res_id = cls._xmlid_to_res_model_res_id(
            xmlid, raise_if_not_found=raise_if_not_found, using=using)
        if not model_label or not res_id:
            return None
        record = (apps.get_model(model_label).objects.using(using)
                  .filter(pk=res_id).first())
        if record is None and raise_if_not_found:
            raise ValueError(
                'El identificador externo %s apunta a un registro que ya no '
                'existe (%s,%s)' % (xmlid, model_label, res_id))
        return record

    @classmethod
    def check_object_reference(cls, module, xml_id, raise_on_access_error=False,
                               using=DEFAULT_DB_ALIAS):
        """≙ ``check_object_reference`` (``odoo19c: ir_model.py:2296-2305``).

        Docstring de la fuente, verbatim: *"Returns (model, res_id)
        corresponding to a given module and xml_id (cached), if and only if the
        user has the necessary access rights to see that object, otherwise
        raise a ValueError if raise_on_access_error is True or returns a tuple
        (model found, False)"*.

        La comprobación de lectura la hace el manager: ``AccessManager`` acota
        por fila, así que un ``filter(pk=res_id)`` vacío **es** el rechazo de
        acceso — el mismo mecanismo que la fuente usa con su ``search``.
        """
        model_label, res_id = cls._xmlid_lookup(f'{module}.{xml_id}', using=using)
        model_cls = _model_class(model_label)
        if model_cls is None:
            raise ValueError(f'Model {model_label!r} is not loaded')
        if model_cls.objects.using(using).filter(pk=res_id).exists():
            return model_label, res_id
        if raise_on_access_error:
            raise AccessError(
                'Not enough access rights on the external ID '
                f'"{module}.{xml_id}"')
        return model_label, False

    def copy_data(self, default=None, seen=None):
        """≙ ``copy_data`` (``odoo19c: ir_model.py:2313-2318``).

        El identificador externo es único por ``(module, name)``, así que una
        copia no puede llevar el mismo: la fuente le añade cuatro dígitos
        hexadecimales aleatorios y aquí se hace igual.

        > **Actualizado (tarea #114).** El cuerpo copiaba a mano cuatro campos
        > —``module``, ``model``, ``res_id``, ``noupdate``— porque **no había
        > base a la que llamar**: el ``copy_data`` del ORM no estaba portado.
        > La fuente sólo llama a ``super()`` y parchea ``name``, y eso es lo
        > que hace ahora. La lista escrita a mano además envejecía sola: un
        > campo nuevo en el modelo no entraba en la copia y nada lo delataba.
        """
        values = super().copy_data(default, seen=seen)
        if values is None:
            return None
        values['name'] = '%s_%04x' % (self.name, random.getrandbits(16))
        return values

    def save(self, *args, **kwargs):
        """Enganche de Django — ≙ ``create`` (``:2314-2319``) y ``write`` (``:2321-2326``).

        Los dos caminos de la fuente colapsan en ``save``, y sus dos
        invalidaciones se conservan: la familia ``default`` porque
        :meth:`_xmlid_lookup` vive ahí, y ``groups`` cuando la fila apunta a un
        grupo — su pertenencia se memoriza aparte.

        La fuente sólo vacía en ``write`` (en ``create`` no hace falta: la
        entrada no existía). Aquí ``save`` no distingue por sí solo, así que lo
        decide ``_state.adding``, igual que el resto del árbol.
        """
        creating = self._state.adding
        result = super().save(*args, **kwargs)
        if not creating:
            registry.clear_cache('default')
        if self.model == 'base.ResGroups':
            registry.clear_cache('groups')
        return result

    def delete(self, *args, **kwargs):
        """Enganche de Django — ≙ ``unlink`` (``odoo19c: :2328-2334``).

        Docstring de la fuente, verbatim: *"Regular unlink method, but make
        sure to clear the caches."*
        """
        was_group = self.model == 'base.ResGroups'
        registry.clear_cache('default')
        if was_group:
            registry.clear_cache('groups')
        return super().delete(*args, **kwargs)

    @classmethod
    def _lookup_xmlids(cls, xml_ids, model, using=DEFAULT_DB_ALIAS):
        """≙ ``_lookup_xmlids`` (``odoo19c: :2336-2360``).

        Docstring de la fuente, verbatim: *"Look up the given XML ids of the
        given model."*

        Devuelve, por cada identificador que exista, la fila de
        ``ir_model_data`` **más** el id del registro apuntado si sigue vivo —
        el ``LEFT JOIN`` es lo que distingue "no hay identificador" de "hay
        identificador y su registro se borró", y el cargador necesita las dos
        respuestas por separado.

        Agrupa por módulo porque la clave única es ``(module, name)``: una
        consulta por prefijo con ``name = ANY(...)`` toca el índice; una por
        identificador haría N viajes.

        **NO filtra por ``d.model``, y es deliberado.** La fuente tampoco
        (``:2355-2358``: sólo ``d.module`` y ``d.name``), y esa ausencia es lo
        que hace alcanzable la guarda de ``_load_records``: una fila de OTRO
        modelo vuelve, y el cargador la rechaza nombrando los dos modelos. Con
        el filtro puesto la fila no volvería, el identificador se leería como
        libre, y se crearía un registro nuevo bajo un ``xml_id`` que ya apunta
        a otra tabla — el conflicto se descubriría al chocar con la clave
        única, sin decir cuál era el otro modelo.

        Fue un defecto real de este porte: el filtro estaba, y con él la guarda
        no podía disparar nunca (el sub-patrón D de
        ``metrica-decide-la-conclusion.md``). Lo destapó su propio test.

        La columna ``d.model`` **sí** se devuelve — es la que el cargador
        compara.
        """
        if not xml_ids:
            return []

        by_module = defaultdict(set)
        for xml_id in xml_ids:
            prefix, _, suffix = xml_id.partition('.')
            by_module[prefix].add(suffix)

        table = model._meta.db_table
        result = []
        with connections[using].cursor() as cursor:
            for prefix, suffixes in by_module.items():
                query = (
                    'SELECT d.id, d.module, d.name, d.model, d.res_id, '
                    'd.noupdate, r.id '
                    f'FROM ir_model_data d LEFT JOIN "{table}" r ON d.res_id = r.id '
                    'WHERE d.module = %s AND d.name = ANY(%s)'
                )
                for piece in split_every(_IN_MAX, suffixes, piece_maker=list):
                    cursor.execute(query, [prefix, piece])
                    result.extend(cursor.fetchall())
        return result

    @classmethod
    def _update_xmlids(cls, data_list, update=False, using=DEFAULT_DB_ALIAS):
        """≙ ``_update_xmlids`` (``odoo19c: :2362-2412``).

        Docstring de la fuente, verbatim: *"Create or update the given XML
        ids."* — ``data_list`` son diccionarios con ``xml_id`` (el que se
        asigna), ``noupdate`` (su bandera) y ``record`` (el registro destino);
        ``update`` va a ``True`` al actualizar un módulo.

        Es el **lado escritor** del cargador, y su forma importa: un solo
        ``INSERT ... ON CONFLICT DO UPDATE`` por lote, no una fila a la vez.
        La cláusula ``WHERE`` sólo reescribe si el destino cambió — así una
        recarga que no mueve nada no toca ``write_date``, y el ``RETURNING``
        distingue lo que cambió de lo que no.

        ``AND NOT ir_model_data.noupdate`` sólo se añade cuando ``update``:
        durante una actualización, una fila marcada como no actualizable
        **protege** al registro que el usuario tocó a mano.
        """
        if not data_list:
            return

        rows = OrderedSet()
        for data in data_list:
            prefix, _, suffix = data['xml_id'].partition('.')
            record = data['record']
            rows.add((prefix, suffix, type(record)._meta.label, record.pk,
                      bool(data.get('noupdate'))))

        for sub_rows in split_every(_IN_MAX, rows, piece_maker=list):
            query = cls._build_update_xmlids_query(sub_rows, update)
            params = [arg for row in sub_rows for arg in row]
            try:
                with connections[using].cursor() as cursor:
                    cursor.execute(query, params)
                    returned = cursor.fetchall()
            except Exception:
                _logger.error('Failed to insert ir_model_data\n%s',
                              '\n'.join(str(row) for row in sub_rows))
                raise
            for module, name, model, res_id, created, written in returned:
                # Sembrar en vez de vaciar — ver :meth:`_xmlid_lookup`.
                cls._xmlid_lookup.__func__.__cache__.add_value(
                    cls, f'{module}.{name}', using,
                    cache_value=(model, res_id))
                if created != written:
                    registry.cache_invalidated.add('default')

        registry.loaded_xmlids.update(f'{row[0]}.{row[1]}' for row in rows)

        if any(row[2] == 'base.ResGroups' for row in rows):
            registry.clear_cache('groups')

    @classmethod
    def _build_insert_xmlids_values(cls):
        """≙ ``_build_insert_xmlids_values`` (``odoo19c: :2414-2424``).

        Comentario de la fuente sobre por qué es un método y no una constante,
        verbatim: *"this method is overriden in web_studio; if you need to make
        another override, make sure it is compatible with the one that is
        there."* — es el punto de extensión de las columnas del ``INSERT``.
        """
        return {
            'module': '%s',
            'name': '%s',
            'model': '%s',
            'res_id': '%s',
            'noupdate': '%s',
            # Las dos columnas de auditoría, y por qué van AQUÍ: el ``INSERT``
            # en bruto esquiva a Django, que es quien las rellena con
            # ``auto_now_add``/``auto_now``. Allá las pone su propio ORM por
            # ``_log_access``, así que la fuente no las nombra. Son literales,
            # no marcadores: no consumen parámetro y el conteo por fila sigue
            # siendo cinco.
            'created_at': "now() at time zone 'UTC'",
            'updated_at': "now() at time zone 'UTC'",
        }

    @classmethod
    def _build_update_xmlids_query(cls, sub_rows, update):
        """≙ ``_build_update_xmlids_query`` (``odoo19c: :2426-2442``)."""
        rows = cls._build_insert_xmlids_values()
        row_names = f"({','.join(rows.keys())})"
        row_placeholders = f"({','.join(rows.values())})"
        row_placeholders = ', '.join([row_placeholders] * len(sub_rows))
        and_where = 'AND NOT ir_model_data.noupdate' if update else ''
        return f"""
            INSERT INTO ir_model_data {row_names}
            VALUES {row_placeholders}
            ON CONFLICT (module, name)
            DO UPDATE SET (model, res_id, updated_at) =
                (EXCLUDED.model, EXCLUDED.res_id, now() at time zone 'UTC')
                WHERE (ir_model_data.res_id != EXCLUDED.res_id
                       OR ir_model_data.model != EXCLUDED.model) {and_where}
            RETURNING module, name, model, res_id, created_at, updated_at
        """

    @classmethod
    def _load_xmlid(cls, xml_id, using=DEFAULT_DB_ALIAS):
        """≙ ``_load_xmlid`` (``odoo19c: :2444-2452``).

        Docstring de la fuente, verbatim: *"Simply mark the given XML id as
        being loaded, and return the corresponding record."*

        Marcarlo es lo que evita que :meth:`_process_end` lo borre: un
        identificador que el módulo sigue declarando tiene que estar en el
        conjunto de esta carga.
        """
        record = cls.ref(xml_id, raise_if_not_found=False, using=using)
        if record is not None:
            registry.loaded_xmlids.add(xml_id)
        return record

    @classmethod
    def toggle_noupdate(cls, model, res_id, using=DEFAULT_DB_ALIAS):
        """≙ ``toggle_noupdate`` (``odoo19c: ir_model.py:2713-2717``).

        Invierte la bandera del identificador externo de un registro concreto.
        Es lo que el usuario acciona para **proteger** un dato que tocó a mano:
        con ``noupdate``, la siguiente actualización del módulo no lo pisa.

        La guarda es la de la fuente —``self.env[model].browse(res_id)
        .check_access('write')``—: quien puede **escribir** el registro puede
        proteger su identificador. No es una guarda de administrador; leerla
        así restringiría la acción a un actor que la fuente no exige.

        El recordset se construye con ``AccessQuerySet`` **explícitamente**, no
        a través del manager del modelo apuntado, y es deliberado: allá las
        cuatro formas cuelgan de ``BaseModel``, así que **todo** modelo las
        tiene; aquí cuelgan de ese queryset y hoy ningún ``objects`` lo adopta
        (la adopción modelo a modelo es la tarea #96). Leerlas del manager
        dejaría la guarda inerte en todos los modelos — un control que no puede
        fallar, que es el sub-patrón D de ``metrica-decide-la-conclusion.md``.
        Nombrando la clase, la comprobación corre siempre, como en la fuente.

        Invierte **todas** las filas que nombren el registro, como la fuente:
        un mismo registro puede llevar identificador de más de un módulo.
        """
        target = _model_class(model)
        if target is not None:
            models.AccessQuerySet(model=target, using=using).filter(
                pk=res_id).check_access('write')
        for xid in cls.objects.using(using).filter(model=model, res_id=res_id):
            xid.noupdate = not xid.noupdate
            xid.save(using=using)

    @classmethod
    def _process_end_unlink_record(cls, record):
        """≙ ``_process_end_unlink_record`` (``odoo19c: ir_model.py:2455-2457``).

        Una línea en la fuente, y aun así un método: es el **punto de
        extensión** que un addon sobreescribe para no borrar de verdad —
        ``mail`` lo usa para archivar en vez de eliminar. Portarlo como llamada
        en línea cerraría esa puerta.
        """
        record.delete()

    @classmethod
    def _process_end(cls, modules, using=DEFAULT_DB_ALIAS):
        """≙ ``_process_end`` (``odoo19c: :2459-2527``).

        Docstring de la fuente, verbatim: *"Clear records removed from updated
        module data. This method is called at the end of the module loading
        process. It is meant to removed records that are no longer present in
        the updated data. Such records are recognised as the one with an xml id
        and a module in ir_model_data and noupdate set to false, but not
        present in self.pool.loaded_xmlids."*

        Es la mitad que hace que actualizar un módulo **retire** lo que dejó de
        declarar. Sin ella, quitar un registro del archivo de data no lo quita
        de la base: queda huérfano, sin nadie que lo declare y sin nadie que lo
        borre.

        El orden descendente por ``id`` no es cosmético — la fuente lo pide
        explícitamente (``ORDER BY id DESC``): los registros creados después
        suelen depender de los creados antes, así que borrarlos al revés evita
        que una FK con ``PROTECT`` detenga el barrido a medias.
        """
        if not modules:
            return True

        stale_ids = []
        query = (
            "SELECT id, module || '.' || name, model, res_id FROM ir_model_data "
            'WHERE module = ANY(%s) AND res_id IS NOT NULL '
            'AND COALESCE(noupdate, false) != %s ORDER BY id DESC'
        )
        with connections[using].cursor() as cursor:
            cursor.execute(query, [list(modules), True])
            rows = cursor.fetchall()

        for row_id, xmlid, model_label, res_id in rows:
            if xmlid in registry.loaded_xmlids:
                continue
            model_cls = _model_class(model_label)
            if model_cls is None:
                continue
            record = model_cls.objects.using(using).filter(pk=res_id).first()
            if record is None:
                # El registro ya no está; la fila que lo nombraba sobra.
                stale_ids.append(row_id)
                continue
            _logger.info('Deleting %s@%s (%s)', res_id, model_label, xmlid)
            cls._process_end_unlink_record(record)
            stale_ids.append(row_id)

        if stale_ids:
            cls.objects.using(using).filter(pk__in=stale_ids).delete()
            registry.clear_cache('default')
        return True

    @classmethod
    def _module_data_uninstall(cls, modules_to_remove, using=DEFAULT_DB_ALIAS):
        """≙ ``_module_data_uninstall`` (``odoo19c: :2454-2528``), su mitad de datos.

        Docstring de la fuente, verbatim: *"Deletes all the records referenced
        by the ir.model.data entries ``ids`` along with their corresponding
        database backed … as long as there is no other ir.model.data entry
        holding a reference to them (which indicates that they are still owned
        by another module)."*

        Esa condición es el corazón del método y se porta entera: un registro
        que **otro** módulo también declara no se borra al desinstalar éste.

        DIVERGENCIA DE MECANISMO, ya declarada en la cabecera de este módulo y
        no ampliada aquí: la fuente además emite ``DROP TABLE`` y ``ALTER TABLE
        ... DROP CONSTRAINT`` sobre el esquema vivo, y aquí el esquema lo
        gobiernan las migraciones de Django — DDL fuera de ellas deja
        ``django_migrations`` mintiendo. La mitad de DDL no se porta; la de
        datos, que es la que da la trazabilidad, sí.

        La bisección de la fuente al fallar un borrado también se porta: si el
        lote entero no se puede eliminar, se parte en dos y se reintenta, y
        sólo cuando queda un registro suelto se le declara indelegable.
        """
        if not is_system():
            raise AccessError(
                'Administrator access is required to uninstall a module')

        module_data = list(cls.objects.using(using).filter(
            module__in=list(modules_to_remove)).order_by('-id'))
        if not module_data:
            return []

        ids_by_model = defaultdict(list)
        for data in module_data:
            ids_by_model[data.model].append(data.res_id)

        own_data_ids = {data.pk for data in module_data}
        undeletable_ids = []

        def delete(model_cls, ids):
            """≙ la clausura ``delete`` de la fuente (``:2521-2571``)."""
            if not ids:
                return
            # *"do not delete records that have other external ids (and thus do
            # not belong to the modules being installed)"*
            foreign = set(cls.objects.using(using).filter(
                model=model_cls._meta.label, res_id__in=ids,
            ).exclude(pk__in=own_data_ids).values_list('res_id', flat=True))
            ids = [i for i in ids if i not in foreign]
            if not ids:
                return
            try:
                with transaction.atomic(using=using):
                    model_cls.objects.using(using).filter(pk__in=ids).delete()
            except Exception:                # noqa: BLE001 — verbatim de la fuente
                if len(ids) <= 1:
                    undeletable_ids.extend(ids)
                else:
                    half = len(ids) // 2
                    delete(model_cls, ids[:half])
                    delete(model_cls, ids[half:])

        for model_label, ids in ids_by_model.items():
            model_cls = _model_class(model_label)
            if model_cls is None:
                _logger.info(
                    "Orphan ir.model.data records %s refer to unavailable "
                    "model '%s'", ids, model_label)
                continue
            delete(model_cls, ids)

        if undeletable_ids:
            _logger.info(
                'ir.model.data could not be deleted (%s)', undeletable_ids)

        spent_ids = [d.pk for d in module_data
                     if d.res_id not in undeletable_ids]
        cls.objects.using(using).filter(pk__in=spent_ids).delete()
        registry.clear_cache('default')
        return undeletable_ids

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
        # Delega en el escritor de la fuente: un solo camino de escritura, con
        # su INSERT ... ON CONFLICT, su siembra de caché y su registro en
        # ``loaded_xmlids``. Antes duplicaba esa lógica con un
        # ``update_or_create``, que no hacía ni lo segundo ni lo tercero.
        cls._update_xmlids([{
            'xml_id': xmlid, 'record': record, 'noupdate': noupdate,
        }])
        return cls.objects.get(module=module, name=name)
