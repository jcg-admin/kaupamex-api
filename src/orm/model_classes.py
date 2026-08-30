"""Construcción de clases de modelo — fiel a ``odoo/orm/model_classes.py`` (Odoo 19).

En Odoo este módulo es la maquinaria que, al cargar los addons, **fusiona** las
definiciones de un mismo ``_name`` (herencia por ``_inherit``) en una sola clase
registrada, resuelve los campos, y las inserta en el ``Registry``
(``add_to_registry``, ``setup_model_classes``, ``add_field``, ``pop_field``). Es
el corazón del sistema de herencia de Odoo.

Mapeo a Django — **Django ya tiene su propia maquinaria de construcción de
clases**: la metaclase ``ModelBase`` procesa cada ``class X(models.Model)`` al
importarla (resuelve campos, ``Meta``, herencia) y la registra en ``apps``. Por
eso este archivo es un stub delgado documentado:

=====================================  ==================================================
Odoo ``model_classes``                 Equivalente Django
=====================================  ==================================================
metaclase que arma la clase            ``django.db.models.base.ModelBase``
``add_to_registry(...)`` (``:152``)    registro automático de ``ModelBase`` en ``apps``
``setup_model_classes(env)`` (``:301``)  import de ``models/`` + ``apps.populate()``
``_inherit`` = *extensión* (fusiona    intra-app: herencia Python (abstract base /
definiciones del mismo ``_name``,      multi-table); cross-app: **FK RELATED**
o del padre, en una clase por MRO)     (DEC-SALE-01) — no hay fusión por ``_name``
``_inherits`` = *delegación* (Many2one  ``OneToOneField``/FK + delegación por
delegate required, ondelete cascade;   ``property`` (o multi-table inheritance) —
``_check_inherits`` ``:465``)          composición, no fusión de clase
``add_field`` / ``pop_field``          declaración de campos en la clase +
                                       ``contribute_to_class`` de ``ModelBase``
``is_model_class`` / ``is_model_def``  ``issubclass(x, models.Model)`` /
                                       ``not x._meta.abstract``
=====================================  ==================================================

Validación del bloque de comentarios de Odoo (``model_classes.py:32-138``,
PROVEN verbatim en la fuente 19) y su mapeo — los comentarios son **correctos** y
describen el mecanismo real (el código bajo ellos, ``:152+``, lo implementa). Tres
conceptos y por qué en Django divergen:

1. **"model definitions" vs "model classes".** En Odoo la *definición* es la
   clase estática del código del módulo; la *model class* del ``Registry`` se
   construye **dinámicamente al armar el registro**, heredando (en orden inverso,
   para respetar el override) de TODAS las definiciones del mismo ``_name`` — su
   MRO se calcula ahí. En Django **no existe esa dualidad**: ``ModelBase``
   construye la clase **una vez, al importar** (estática), y esa misma clase es la
   del registro (``apps``). No hay "definición" separada de "clase de registro".

2. **Fusión por ``_name`` (A1+A2+A3 → una clase ``a``).** Es la mayor divergencia:
   Django es *una clase = un modelo = una tabla*; no se declara el mismo modelo
   varias veces en módulos distintos para fusionarlo. Por DEC-SALE-01, la
   *extensión* (``_inherit``) se resuelve como herencia Python intra-app y como
   **FK RELATED** cross-app; la *delegación* (``_inherits``, que en Odoo exige un
   Many2one delegate) es composición nativa (``OneToOneField``/FK + delegación).

3. **Model classes por registro (por-DB) + "fields shared across registries".**
   En Odoo el registro es **por base de datos** y la optimización es compartir el
   objeto ``field`` entre registros cuando se puede (por eso los magic fields van
   en las clases-definición, ``:136-138``). En Django las clases son
   **process-global** (una sola vez por proceso), así que esa optimización es
   **irrelevante**: no hay reconstrucción de clase por conexión — el multi-DB es
   un asunto de *router* (``orm/routers.py``), no de rebuild de clases.

Por eso este archivo es un stub delgado documentado: ``ModelBase`` hace el
registro y las migraciones materializan el schema; no hay ``add_to_registry`` ni
MRO-fusion que replicar.


``extend_model`` — el ``_inherit`` por nombre
===============================================

La referencia extiende un modelo **nombrándolo**: ``add_to_registry``
(``odoo19c: odoo/orm/model_classes.py:152-231``) resuelve cada cadena de
``_inherit`` contra ``registry[parent_name]``, y ``add_field`` (``:596``) le
cuelga el campo. Las dos operaciones viven en **este** archivo allá, y por eso
viven aquí — un archivo propio sería la divergencia de forma de
:ref:`h-api-568`.

Django trae el acoplamiento tardío en ``Apps.lazy_model_operation``
(``django/apps/registry.py:388-426``). Lo que este bloque añade es el
adaptador que lo vuelve seguro; el porqué está medido en ``H-API-577`` y sus
pruebas en ``tests/unit/orm/test_extension_tardia_por_nombre.py``.
"""
import importlib
import inspect

from django.db.models import Model
from django.db.models.fields import NOT_PROVIDED
from django.db.models.base import ModelBase
from django.db.models.signals import class_prepared
from django.dispatch import receiver

from django.apps import apps

from orm.method_chain import chain_method, wrap_method
from orm.registry import resolve_model_key

__all__ = [
    'ModelBase', 'is_model_class', 'is_model_definition',
    'extend_model', 'extend_property', 'add_field_if_absent', 'model_key',
    'resolve_rec_name', 'ensure_rec_names',
    'adopt_access_manager', 'ensure_access_managers',
]


def is_model_class(cls) -> bool:
    """``True`` si ``cls`` es una clase de modelo (subclase de ``models.Model``).
    Equivale a ``odoo.orm.model_classes.is_model_class`` — sobre ``ModelBase``."""
    return isinstance(cls, ModelBase) and issubclass(cls, Model)


def is_model_definition(cls) -> bool:
    """``True`` si ``cls`` es una definición concreta (no abstracta). Equivale a
    ``odoo.orm.model_classes.is_model_definition`` — sobre ``Model._meta``."""
    return is_model_class(cls) and not cls._meta.abstract


def _is_computed_surface(model_cls, name) -> bool:
    """¿``name`` es un campo **calculado no almacenado** de este modelo?

    La fuente valida ``_rec_name`` contra ``_fields``, y ahí entran también los
    calculados sin columna: ``res.groups`` declara ``_rec_name = 'full_name'``
    y su ``full_name`` es ``Char(compute='_compute_full_name')`` sin ``store``
    (``odoo19c: base/models/res_groups.py:12,29``).

    Aquí un campo así no es un campo de Django —no tiene columna que declarar—
    sino un **descriptor** sobre la clase: una ``property`` o un
    :class:`orm.fields_nonstored.NonStored`. Sin este reconocimiento, portar el
    ``_rec_name`` de la fuente verbatim reventaba el arranque, y la única
    salida habría sido no declararlo — omitir un atributo que la fuente sí
    declara.

    Se mira con ``inspect.getattr_static``, no con ``getattr``: éste
    **ejecutaría** la ``property`` contra la clase y daría ``AttributeError``
    por falta de instancia. Aquél devuelve el descriptor sin invocarlo.

    Un nombre que no está en la clase sigue siendo inválido, que es lo que el
    control tiene que poder rechazar: ``_rec_name = 'no_existe'`` no encuentra
    ni campo ni descriptor y levanta igual que antes.
    """
    attr = inspect.getattr_static(model_cls, name, None)
    return attr is not None and hasattr(type(attr), '__get__')


def resolve_rec_name(model_cls):
    """Fija ``_rec_name`` cuando el modelo no lo declara y tiene ``name``.

    ≙ el paso 5 de ``_init_model_class_attributes``
    (``odoo19c: odoo/orm/model_classes.py:433-441``), verbatim en su lógica:
    si el modelo declara ``_rec_name`` se valida que sea un campo suyo; si no
    lo declara y tiene un campo ``name``, ``_rec_name`` pasa a ser ``'name'``.

    Por qué hace falta resolverlo y no basta con leerlo: la referencia declara
    ``_rec_name`` **sólo cuando difiere del default**, y por eso
    ``ResPartner`` no lo declara y aun así ``name_create`` escribe
    ``{self._rec_name: ...}`` (``odoo19c: res_partner.py:1088``). Sin este
    paso ese acceso revienta con ``AttributeError`` — y declararlo a mano en
    cada modelo sería inventar un atributo que la fuente no tiene, que es lo
    que ``atributos-de-clase-de-modelo.md`` prohíbe.

    La rama ``_custom`` con ``x_name`` de la fuente **no se porta**: los
    modelos a medida en tiempo de ejecución son su mecanismo de estudio, y
    aquí un modelo es una clase Python. Es divergencia de mecanismo, no un
    hueco: sin modelos a medida no hay campo ``x_name`` que resolver.

    :returns: el ``_rec_name`` resuelto, o ``None`` si el modelo no tiene
        campo que lo respalde.
    """
    declared = model_cls.__dict__.get('_rec_name')
    # ``fields`` y ``many_to_many``, NO ``get_fields()``: este ultimo trae las
    # inversas, y para eso recorre el grafo de relaciones, que exige el
    # registro de apps poblado. Esta funcion corre desde ``class_prepared``,
    # cuando aun no lo esta — medido: revienta con ``AppRegistryNotReady`` en
    # el primer modelo de ``contenttypes``. La fuente tampoco las mira:
    # ``_fields`` son los campos del modelo, no lo que apunta a el.
    campos = [*model_cls._meta.fields, *model_cls._meta.many_to_many]
    # El nombre Y el ``attname``. La fuente compara contra ``_fields``, donde
    # una Many2one se llama ``user_id``; aqui esa misma relacion se declara
    # ``user = fields.Many2one(...)`` y Django le pone ``attname='user_id'``.
    # Un ``_rec_name = 'user_id'`` portado verbatim —``ir.ui.view.custom`` lo
    # trae asi— nombra el mismo campo por su otra cara, y ``getattr`` responde
    # con las dos. Aceptar solo ``name`` convertiria el porte fiel en un error.
    field_names = {f.name for f in campos} | {f.attname for f in campos}
    if declared:
        if declared not in field_names and not _is_computed_surface(model_cls, declared):
            raise ValueError(
                f'Invalid _rec_name={declared!r} for model '
                f'{model_cls._meta.label}'
            )
        return declared
    if getattr(model_cls, '_rec_name', None):
        return model_cls._rec_name
    if 'name' in field_names:
        model_cls._rec_name = 'name'
        return 'name'
    # El default de la fuente, explicito: ``BaseModel`` los declara
    # ``_rec_name: str | None = None`` y ``_rec_names_search = None``
    # (``odoo19c: odoo/orm/models.py:431-433``), asi que **todo** modelo los
    # tiene y ``cls._rec_name`` nunca revienta. Aqui la base es la de Django y
    # no es nuestra, asi que el default se pone al resolver. Sin esto,
    # ``IrCron`` —que llama a su campo ``cron_name``— daba ``AttributeError``.
    if '_rec_name' not in model_cls.__dict__:
        model_cls._rec_name = None
    if not hasattr(model_cls, '_rec_names_search'):
        model_cls._rec_names_search = None
    return None


#: Los prefijos de módulo que NO son nuestros. El discriminador es el módulo y
#: no la etiqueta de app: ``auth``, ``sessions`` o ``token_blacklist`` son
#: nombres cortos que un addon nuestro podría reusar, mientras que el módulo
#: de origen no se puede confundir.
THIRD_PARTY_MODULE_PREFIXES = ('django.', 'rest_framework')


def adopt_access_manager(model_cls):
    """Le da al modelo las cuatro formas de permiso, si no las tiene ya.

    ≙ que ``check_access``, ``has_access``, ``_check_access`` y
    ``_filtered_access`` cuelguen de ``BaseModel``
    (``odoo19c: odoo/orm/models.py:4100-4135``): allá **todo** modelo las
    tiene, sin declarar nada.

    Aquí las lleva un ``Manager``, y la universalidad se recupera en el
    momento en que Django termina de construir la clase. El discriminador de
    *"no declaró manager propio"* es de Django, no nuestro:
    ``manager.auto_created`` lo marca el propio ``ModelBase._prepare`` cuando
    pone el ``objects`` por defecto (``django/db/models/base.py:434-441``).
    Un modelo que sí declara el suyo se respeta — los siete del árbol derivan
    de ``AccessManager``, que es lo que ``RuleScopedManager`` ya hacía desde la
    tarea #93.

    Por qué una señal y no 90 declaraciones a mano: la alternativa se olvida
    en la primera, y **el olvido no falla** — deja el modelo sin las cuatro
    formas y nada lo delata hasta que alguien las llama.

    :returns: ``True`` si se lo puso; ``False`` si ya lo tenía, es de terceros
        o es abstracto — para que el llamador pueda medir en vez de suponer.

    .. note:: ``orm.models`` se resuelve con ``importlib``, no con un ``import``
       al top, y es la **excepción #4** de ``no-lazy-imports.md`` aplicada a su
       causa hermana. Aquel módulo importa ``orm.environments``, que toca el
       registro de apps; importarlo desde aquí al cargar da
       ``AppRegistryNotReady``, medido. La resolución sancionada es una
       **llamada**, no un statement ``import``: el gate AST da exit 0 y el
       arranque se preserva.
    """
    # Las guardas van ANTES de resolver ``orm.models``, y el orden importa: la
    # señal dispara mientras ``contenttypes`` se está importando, y resolver
    # ``orm.models`` ahí lo arrastra de vuelta —``orm/fields_reference`` pide
    # ``ContentType``— con un ``ImportError`` de módulo parcialmente
    # inicializado. Medido. Descartar al ajeno primero cierra el ciclo.
    if model_cls._meta.abstract or model_cls._meta.proxy:
        return False
    if model_cls.__module__.startswith(THIRD_PARTY_MODULE_PREFIXES):
        return False
    manager = model_cls._meta.managers_map.get('objects')
    if manager is None or not getattr(manager, 'auto_created', False):
        return False

    orm_models = importlib.import_module('orm.models')
    AccessManager = orm_models.AccessManager
    AccessQuerySet = orm_models.AccessQuerySet
    if isinstance(manager.get_queryset(), AccessQuerySet):
        return False
    # Retirar el viejo ANTES de colgar el nuevo, y no es opcional:
    # ``Options.managers`` recorre ``local_managers`` en orden de inserción y
    # se queda con el **primero** de cada nombre (``seen_managers``). Sin esta
    # línea el ``objects`` auto-creado sigue ganando y ``add_to_class`` no
    # cambia nada — medido: 159 adopciones reportadas y 0 efectivas.
    model_cls._meta.local_managers = [
        m for m in model_cls._meta.local_managers if m.name != 'objects']
    model_cls._meta._expire_cache()
    nuevo = AccessManager()
    nuevo.auto_created = True
    model_cls.add_to_class('objects', nuevo)
    return True


@receiver(class_prepared, dispatch_uid='orm.model_classes.adopt_access_manager')
def _adopt_access_manager_on_prepared(sender, **kwargs):
    """Adopta el manager de permisos en cuanto la clase queda construida."""
    adopt_access_manager(sender)


def ensure_access_managers():
    """Barre el registro por si la señal llegó tarde.

    Dos vías por la misma razón de ``H-API-577``, igual que
    :func:`ensure_rec_names`: la señal cubre lo que llega después de importar
    este módulo; el barrido, lo que ya estaba.

    :returns: cuántos modelos lo adoptaron en el barrido.
    """
    return sum(1 for model in apps.get_models(include_auto_created=True)
               if adopt_access_manager(model))


#: Los cinco símbolos del bloque ``display_name`` de la fuente
#: (``odoo19c: odoo/orm/models.py:473,1425,1442,1493,1512``). Se enumeran aquí
#: y no se derivan del ``__dict__`` del mixin: un ayudante privado que se
#: añadiera allá entraría al barrido sin que nadie lo decidiera.
DISPLAY_NAME_SYMBOLS = (
    'display_name', '_compute_display_name', '_search_display_name',
    'name_create', 'name_search',
)


def adopt_display_name(model_cls):
    """Le da al modelo su etiqueta y su búsqueda por etiqueta, si no las tiene.

    ≙ que ``display_name``, ``_compute_display_name``,
    ``_search_display_name``, ``name_create`` y ``name_search`` cuelguen de
    ``BaseModel`` (``odoo19c: odoo/orm/models.py:473,1421-1543``): allá **todo**
    modelo los tiene sin declarar nada.

    Aquí los lleva :class:`orm.models.DisplayNameMixin`, que ``TimeStampedModel``
    adopta — **284 de los 374 modelos concretos nuestros** lo heredan (medido).
    Esta función cubre a los **90** que no: los que declaran su propia base,
    como toda la familia ``account``.

    Un símbolo que el modelo ya resuelve **no se toca**, y el discriminador es
    ``getattr`` sobre el MRO, no ``__dict__``: un modelo que hereda su
    ``_compute_display_name`` de una base propia lo tiene tan resuelto como el
    que lo declara. Los doce que declaran ``display_name`` como ``property``
    siguen ganando por MRO, que es lo que la fuente hace con un ``compute``
    sobreescrito.

    :returns: cuántos de los cinco símbolos se instalaron — 0 si ya los tenía,
        es de terceros o es abstracto, para que el llamador pueda medir en vez
        de suponer.

    .. note:: ``orm.models`` se resuelve con ``importlib`` por la misma causa
       que :func:`adopt_access_manager` documenta: importarlo al top arrastra
       ``orm.environments`` y da ``AppRegistryNotReady``.
    """
    if model_cls._meta.abstract or model_cls._meta.proxy:
        return 0
    if model_cls.__module__.startswith(THIRD_PARTY_MODULE_PREFIXES):
        return 0

    faltantes = [nombre for nombre in DISPLAY_NAME_SYMBOLS
                 if getattr(model_cls, nombre, None) is None]
    if not faltantes:
        return 0

    mixin = importlib.import_module('orm.models').DisplayNameMixin
    for nombre in faltantes:
        setattr(model_cls, nombre, mixin.__dict__[nombre])
    return len(faltantes)


def adopt_base_url(model_cls):
    """Le da al modelo la URL raíz desde la que se sirve, si no la tiene.

    ≙ que ``get_base_url`` cuelgue de ``BaseModel``
    (``odoo19c: odoo/orm/models.py:3985``): allá **todo** modelo la tiene sin
    declarar nada.

    Aquí la lleva :class:`orm.models.BaseUrlMixin`, que ``TimeStampedModel``
    adopta — **291 de los 389 modelos concretos** lo heredan (medido). Esta
    función cubre a los **98** que no: los que declaran su propia base, como
    ``IrAttachment``, más los de Django y los de terceros.

    Lo destapó un test del bloque B de ``ir.actions.report`` que pedía la URL
    a un modelo cualquiera, no al reporte: sin él, el porte habría sido del
    **método** y no del **mecanismo**, que es la distinción que
    :ref:`h-api-350` registró.

    Un modelo que ya lo resuelve **no se toca**, y el discriminador es
    ``getattr`` sobre el MRO, igual que en :func:`adopt_display_name`: un
    modelo que sobreescriba ``get_base_url`` en una base propia gana, que es
    lo que la fuente permite con cualquier método de ``BaseModel``.

    :returns: 1 si se instaló, 0 si ya lo tenía, es de terceros o es
        abstracto — para que el llamador pueda medir en vez de suponer.
    """
    if model_cls._meta.abstract or model_cls._meta.proxy:
        return 0
    if model_cls.__module__.startswith(THIRD_PARTY_MODULE_PREFIXES):
        return 0
    if getattr(model_cls, 'get_base_url', None) is not None:
        return 0

    mixin = importlib.import_module('orm.models').BaseUrlMixin
    model_cls.get_base_url = mixin.__dict__['get_base_url']
    return 1


@receiver(class_prepared, dispatch_uid='orm.model_classes.adopt_base_url')
def _adopt_base_url_on_prepared(sender, **kwargs):
    """Adopta la URL raíz en cuanto la clase queda construida."""
    adopt_base_url(sender)


def ensure_base_urls():
    """Barre el registro por si la señal llegó tarde.

    Dos vías por la razón de ``H-API-577``, igual que
    :func:`ensure_display_names`.

    :returns: cuántos modelos adoptaron el método en el barrido.
    """
    return sum(1 for model in apps.get_models(include_auto_created=True)
               if adopt_base_url(model))


@receiver(class_prepared, dispatch_uid='orm.model_classes.adopt_display_name')
def _adopt_display_name_on_prepared(sender, **kwargs):
    """Adopta el bloque de etiqueta en cuanto la clase queda construida."""
    adopt_display_name(sender)


def ensure_display_names():
    """Barre el registro por si la señal llegó tarde.

    Dos vías por la razón de ``H-API-577``, igual que :func:`ensure_rec_names`
    y :func:`ensure_access_managers`.

    :returns: cuántos modelos adoptaron al menos un símbolo en el barrido.
    """
    return sum(1 for model in apps.get_models(include_auto_created=True)
               if adopt_display_name(model))


@receiver(class_prepared, dispatch_uid='orm.model_classes.resolve_rec_name')
def _resolve_rec_name_on_prepared(sender, **kwargs):
    """Resuelve el ``_rec_name`` del modelo recién construido.

    ``class_prepared`` dispara al final de ``ModelBase.__new__``, así que
    ``_meta`` ya está poblado y los campos se pueden enumerar.
    """
    resolve_rec_name(sender)


def ensure_rec_names():
    """Barre el registro de Django por si la señal llegó tarde.

    **Dos vías y ninguna sobra**, por la misma razón que ``H-API-577`` dejó
    escrita para ``MODELS_BY_NAME``: la señal sólo cubre los modelos
    preparados **después** de importar este módulo. Si algo lo importa tras
    ``django.setup()``, los que ya estaban se quedan sin resolver y el
    ``_rec_name`` no existe, **sin error que lo delate** hasta que alguien lo
    lea.

    :returns: cuántos modelos quedaron con ``_rec_name`` resuelto — para que
        el llamador pueda medir en vez de suponer.
    """
    resueltos = 0
    for model in apps.get_models(include_auto_created=True):
        if resolve_rec_name(model):
            resueltos += 1
    return resueltos


def model_key(app_label, model_name):
    """La clave que ``do_pending_operations`` va a reconstruir.

    ``Model._meta.label`` da ``stock.StockLocation``; la cola se indexa por
    ``_meta.model_name``, que Django guarda en minúscula. Normalizar aquí es lo
    que impide el cuelgue silencioso descrito en el docstring del módulo.
    """
    return (app_label, model_name.lower())


def add_field_if_absent(model, name, field):
    """Cuelga el campo sólo si el modelo no lo tiene ya.

    Idéntico al ``_add_if_absent`` que ya repiten ``account``,
    ``account_fleet``, ``l10n_mx`` y ``product_expiry``: el idioma de extensión
    por ``add_to_class`` no tiene MRO, así que dos addons que cuelguen el mismo
    campo duplicarían la columna.

    Devuelve ``True`` si lo añadió — para que el llamador pueda medir en vez de
    suponer.
    """
    if any(f.name == name for f in model._meta.get_fields()):
        return False
    model.add_to_class(name, field)
    return True


def add_meta_index(model, index):
    """Cuelga un ``models.Index`` del ``Meta`` de un model ajeno.

    Es lo que ``extend_model(campos=…)`` no alcanza: ``add_to_class`` instala
    la columna y no toca ``_meta.indexes``. La referencia sí lo alcanza, porque
    allá el índice es un atributo del propio campo (``index='btree_not_null'``),
    y aquí es una entrada del ``Meta`` del model — que pertenece a otro addon.

    **Las DOS escrituras son necesarias, y la segunda no es opcional.**
    ``ModelState.from_model`` sólo lee ``model._meta.indexes`` si el nombre
    ``indexes`` figura en ``model._meta.original_attrs``
    (``django/db/migrations/state.py:839``), que es el registro de qué opciones
    declaró el ``class Meta`` del model. Un model cuyo ``Meta`` nunca declaró
    ``indexes`` no lo tiene, así que el autodetector leería una lista vacía y
    **propondría borrar el índice en cada `makemigrations`** — un rojo perpetuo
    que además no cuesta nada evitar. Declararlo en ``original_attrs`` es
    exactamente lo que habría hecho escribir ``indexes = [...]`` en el ``Meta``.

    Idempotente por nombre: ``ready()`` puede correr más de una vez en tests que
    recargan el registro de apps, y un índice repetido saldría dos veces en la
    migración propuesta.

    Devuelve ``True`` si lo añadió — para que el llamador pueda medir.
    """
    if any(i.name == index.name for i in model._meta.indexes):
        return False
    model._meta.indexes = list(model._meta.indexes) + [index]
    model._meta.original_attrs['indexes'] = model._meta.indexes
    return True


#: Las cinco politicas de borrado de un valor de seleccion, verbatim de la
#: fuente (``odoo19c: odoo/orm/fields_selection.py:45-57``). ``'set VALUE'``
#: no cabe en un conjunto —el valor es libre— y se reconoce por prefijo.
ONDELETE_POLICIES = ('set null', 'set default', 'cascade')

#: La politica que la fuente pone por defecto a todo valor nuevo que el
#: ``selection_add`` no nombre (``:131-133``).
ONDELETE_DEFAULT = 'set null'


def check_ondelete_policies(field, ondelete, new_values, values):
    """Valida el mapa ``{valor: politica}`` — ≙ el bloque de la fuente.

    ≙ ``odoo19c: odoo/orm/fields_selection.py:129-163``, con sus cuatro
    comprobaciones y sus cuatro mensajes. Se saca a funcion propia porque
    :func:`extend_selection_choices` la usa una vez y el test la interroga
    aparte; alla es un tramo del cuerpo de ``_setup_attrs__`` y no se puede
    llamar sola.

    :param field: el campo de Django cuyo vocabulario se amplia.
    :param ondelete: el mapa declarado, ya con los defectos rellenos.
    :param new_values: los valores que este ``selection_add`` **agrega** —
        son los unicos a los que la politica aplica.
    :param values: el vocabulario completo tras la ampliacion, para validar
        el destino de un ``'set VALUE'``.
    :raises ValueError: con el mensaje de la fuente, adaptado al espanol.
    """
    # La INTENCION declarada, no el defecto de Django. ``null`` y ``blank``
    # nacen en ``False``, asi que deducir de ellos daria "requerido" en los
    # 181 campos ``Selection`` del arbol que no declaran ninguno de los dos —
    # el instrumento mediria la forma del ORM anfitrion y la conclusion seria
    # sobre la intencion de la fuente. ``fields.Selection`` anota
    # ``field.required`` cuando la declaracion lo dice, y su ausencia vale
    # ``False``, que es el defecto de la fuente.
    required = bool(getattr(field, 'required', False))
    if required and new_values and ONDELETE_DEFAULT in ondelete.values():
        raise ValueError(
            f'{field.name!r}: un campo de seleccion requerido debe declarar '
            f'una politica de borrado que limpie sus registros al '
            f'desinstalar el modulo. Use una o mas de estas: '
            f"'set default' (si el campo declara uno), 'cascade', o un "
            f'invocable de un solo argumento, que recibe el conjunto de '
            f'registros con el valor.')

    for key, policy in ondelete.items():
        if callable(policy) or policy in ('set null', 'cascade'):
            continue
        if policy == 'set default':
            if field.default is NOT_PROVIDED:
                raise ValueError(
                    f"{field.name!r}: la politica 'set default' no vale para "
                    f'este campo porque no declara un valor por defecto. '
                    f'Declare uno en el campo base, o cambie la politica.')
        elif isinstance(policy, str) and policy.startswith('set '):
            if policy[4:] not in values:
                raise ValueError(
                    f"{field.name!r}: la politica 'set %' debe ser "
                    f"'set null', 'set default', o 'set VALOR' donde VALOR "
                    f'es un valor valido de la seleccion.')
        else:
            raise ValueError(
                f'{field.name!r}: la politica de borrado {policy!r} para el '
                f'valor {key!r} no es valida; elija una de '
                f"'set null', 'set default', 'set [valor]', 'cascade' o un "
                f'invocable.')


def extend_selection_choices(model, field_name, extra, ondelete=None):
    """Amplia en sitio los ``choices`` de un campo ya declarado — ≙ ``selection_add``.

    ``extra`` es la lista de pares ``(valor, etiqueta)`` que el addon suma al
    vocabulario que otro ya declaro. Es exactamente lo que la referencia
    expresa redeclarando el campo con ``selection_add=``: **amplia**, no
    sustituye, y por eso preserva los valores del declarante original.

    ``ondelete`` es el ``{valor: politica}`` que la fuente declara **junto** a
    ``selection_add``, y por la misma razon: la politica dice que hacer con
    las filas que guardaban un valor cuando ese valor desaparece. Se guarda en
    el atributo ``ondelete`` del propio campo —el mismo nombre que la fuente
    le da (``odoo19c: fields_selection.py:67``)— porque es ahi donde
    :meth:`~addons.base.models.ir_model.IrModelFieldsSelection._process_ondelete`
    lo lee. Todo valor nuevo que el mapa no nombre recibe
    :data:`ONDELETE_DEFAULT`, igual que alla (``:131-133``).

    No genera migracion. ``choices`` no es DDL: PostgreSQL guarda el valor en
    la misma columna de texto, y ``Field.validate()`` consulta la lista viva en
    cada llamada, asi que la ampliacion es efectiva desde el momento en que
    corre. Lo unico que puede necesitar migracion es el ``max_length`` del
    campo, si el valor nuevo no cupiera — quien amplie lo comprueba.

    Idempotente por pertenencia: ``ready()`` puede correr mas de una vez en
    tests que recargan el registro de apps, y un valor repetido en ``choices``
    sale duplicado en todo selector que lo lea. El mapa de politicas se
    **acumula** por la misma razon que alla (``self.ondelete.update``): dos
    addons pueden ampliar el mismo campo, y el segundo no borra al primero.

    Devuelve los valores realmente agregados, para que el llamador pueda medir
    en vez de suponer.
    """
    field = model._meta.get_field(field_name)
    present = {value for value, _label in field.choices}
    added = []
    for value, label in extra:
        if value in present:
            continue
        field.choices = list(field.choices) + [(value, label)]
        present.add(value)
        added.append(value)

    policies = dict(ondelete or {})
    for value in added:
        policies.setdefault(value, ONDELETE_DEFAULT)
    if policies:
        check_ondelete_policies(field, policies, added, present)
        combined = dict(getattr(field, 'ondelete', None) or {})
        combined.update(policies)
        field.ondelete = combined
    return added


def extend_model(*destino, campos=None, metodos=None, overrides=None,
                 propiedades=None, selection_add=None, ondelete=None,
                 indexes=None, luego=None):
    """Extiende un modelo cuando exista — ≙ ``_inherit``.

    El destino se nombra de una de las dos formas, y la primera es la de la
    referencia::

        extend_model('product.removal', campos={...})       # el _name portado
        extend_model('stock', 'ProductRemoval', campos={})  # el par de Django

    El nombre punteado exige que el modelo **ya esté cargado** (lo registra la
    señal ``class_prepared``); el par de Django no, y es por tanto el único que
    sirve para el caso genuinamente tardío. Ver
    :func:`orm.model_naming.resolve_model_key`.

    Ninguno de los cuatro bloques es obligatorio; se aplican en este orden
    sobre la clase destino:

    ``campos``
        ``{nombre: field}`` — vía :func:`add_field_if_absent`.
    ``metodos``
        ``{nombre: función}`` — vía ``chain_method``: el mecanismo decide
        cuándo invocar la previa (relevo por ``None``, o ``combine``), y la
        nueva corre primero.
    ``overrides``
        ``{nombre: función}`` — vía :func:`~orm.method_chain.wrap_method`: la
        previa llega **en la mano**, ligada al receptor, como segundo
        argumento de ``func``. Es la forma del override que necesita el
        resultado de ``super()`` como insumo, o que hace su trabajo **antes**
        de delegar. La referencia usa las dos en el mismo archivo
        (``odoo19c: sale/models/ir_config_parameter.py`` — ``create`` delega
        primero, ``unlink`` delega último), así que ningún mecanismo que fije
        el orden las cubre.

        Su nombre va en inglés porque es un identificador nuevo
        (``identificadores-en-ingles.md``). Los cinco hermanos están en
        español como deuda heredada congelada: renombrarlos toca 135 sitios de
        llamada y es el barrido de la tarea **#147**, no un pago al tocar.
    ``propiedades``
        ``{nombre: función}`` — instaladas como ``property``, para los
        ``compute`` sin ``store`` de la referencia. No pisa una existente.
    ``selection_add``
        ``{nombre_campo: [(valor, etiqueta), …]}`` — ≙ el ``selection_add=``
        de la referencia, vía :func:`extend_selection_choices`. Amplía el
        vocabulario de un ``fields.Selection`` ya declarado sin redeclararlo,
        que es lo que preserva los valores de quien lo declaró primero.
    ``ondelete``
        ``{nombre_campo: {valor: política}}`` — ≙ el ``ondelete=`` que la
        fuente declara **junto** al ``selection_add`` en la misma
        redeclaración, y por eso viaja aquí como su hermano y no como un
        parámetro de ``fields.Selection``. Dice qué hacer con las filas que
        guardaban un valor cuando ese valor desaparece; lo consume
        ``IrModelFieldsSelection._process_ondelete``. Todo valor nuevo que el
        mapa no nombre recibe ``'set null'``, como allá.
    ``indexes``
        ``[models.Index(…), …]`` — ≙ el ``index=`` que la referencia declara
        como atributo del campo, vía :func:`add_meta_index`. Es lo que hay que
        usar cuando el addon aporta la columna y el ``Meta`` es de otro addon.
    ``luego``
        ``f(modelo)`` — escotilla para lo que no cae en los cuatro anteriores
        (constraints, receptores de señal).

    **No devuelve el modelo**: en el caso interesante todavía no existe. Quien
    necesite la clase la pide dentro de ``luego``, que la recibe como argumento.
    """
    def aplicar(modelo):
        for nombre, field in (campos or {}).items():
            add_field_if_absent(modelo, nombre, field)
        for nombre, funcion in (metodos or {}).items():
            chain_method(modelo, nombre, funcion)
        for nombre, funcion in (overrides or {}).items():
            wrap_method(modelo, nombre, funcion)
        for nombre, funcion in (propiedades or {}).items():
            if not hasattr(modelo, nombre):
                setattr(modelo, nombre, property(funcion))
        for nombre, extra in (selection_add or {}).items():
            extend_selection_choices(modelo, nombre, extra,
                                     (ondelete or {}).get(nombre))
        for indice in (indexes or ()):
            add_meta_index(modelo, indice)
        if luego is not None:
            luego(modelo)

    apps.lazy_model_operation(aplicar, resolve_model_key(*destino))


def extend_property(modelo, nombre, funcion):
    """Extiende una ``property`` que YA existe — ≙ ``super().PROP + [...]``.

    Es el hermano de ``extend_model(propiedades=…)``, y la frontera entre los
    dos es exactamente la que su nombre dice:

    - ``propiedades=`` **declara** una property que no existía. No pisa una
      existente, a propósito: pisarla borraría la aportación de quien la
      declaró antes.
    - ``extend_property`` **suma a** la que existe. Envuelve el ``fget``
      instalado en ese momento y le pasa su valor a ``funcion``, que devuelve
      el valor ampliado.

    ``funcion(self, anterior)`` recibe el valor del eslabón previo ya
    calculado, que es lo que el ``super().PROP`` de la fuente entrega. Si la
    property no existía todavía, ``anterior`` llega como ``None`` — el mismo
    desenlace que ``super()`` sobre un atributo ausente.

    **Por qué existe.** Sin él, un addon que quisiera sumar a una property
    tenía dos salidas y las dos estaban mal: ``propiedades=``, que el guard de
    ``extend_model`` **descarta en silencio**, o un ``setattr`` a mano
    duplicado por addon. La primera se ejerció y falló sin ruido — ``hr``
    declaraba sus 32 campos de ``SELF_READABLE_FIELDS`` y ninguno llegaba al
    modelo (:ref:`h-api-834`).

    Es idempotente: reinstalar la misma ``funcion`` es un no-op, igual que
    ``chain_method``.
    """
    previo = getattr(modelo, nombre, None)
    if isinstance(previo, property):
        fget_previo = previo.fget
        if getattr(fget_previo, '_extendida_por', None) is funcion:
            return          # ya está en la cadena
    else:
        fget_previo = None

    def fget(self):
        anterior = fget_previo(self) if fget_previo is not None else None
        return funcion(self, anterior)

    fget.__name__ = nombre
    fget._extendida_por = funcion
    setattr(modelo, nombre, property(fget))
