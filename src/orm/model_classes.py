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

from django.db.models import Model
from django.db.models.base import ModelBase
from django.db.models.signals import class_prepared
from django.dispatch import receiver

from django.apps import apps

from orm.method_chain import chain_method
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
        if declared not in field_names:
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


def extend_model(*destino, campos=None, metodos=None,
                 propiedades=None, luego=None):
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
        ``{nombre: función}`` — vía ``chain_method``, que preserva la
        implementación previa (el ``super()`` que este idioma no tiene).
    ``propiedades``
        ``{nombre: función}`` — instaladas como ``property``, para los
        ``compute`` sin ``store`` de la referencia. No pisa una existente.
    ``luego``
        ``f(modelo)`` — escotilla para lo que no cae en los tres anteriores
        (índices, constraints, receptores de señal).

    **No devuelve el modelo**: en el caso interesante todavía no existe. Quien
    necesite la clase la pide dentro de ``luego``, que la recibe como argumento.
    """
    def aplicar(modelo):
        for nombre, field in (campos or {}).items():
            add_field_if_absent(modelo, nombre, field)
        for nombre, funcion in (metodos or {}).items():
            chain_method(modelo, nombre, funcion)
        for nombre, funcion in (propiedades or {}).items():
            if not hasattr(modelo, nombre):
                setattr(modelo, nombre, property(funcion))
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
