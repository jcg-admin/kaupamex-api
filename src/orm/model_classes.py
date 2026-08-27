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
from django.db.models import Model
from django.db.models.base import ModelBase

from django.apps import apps

from orm.method_chain import chain_method
from orm.registry import resolve_model_key

__all__ = [
    'ModelBase', 'is_model_class', 'is_model_definition',
    'extend_model', 'extend_property', 'add_field_if_absent', 'model_key',
]


def is_model_class(cls) -> bool:
    """``True`` si ``cls`` es una clase de modelo (subclase de ``models.Model``).
    Equivale a ``odoo.orm.model_classes.is_model_class`` — sobre ``ModelBase``."""
    return isinstance(cls, ModelBase) and issubclass(cls, Model)


def is_model_definition(cls) -> bool:
    """``True`` si ``cls`` es una definición concreta (no abstracta). Equivale a
    ``odoo.orm.model_classes.is_model_definition`` — sobre ``Model._meta``."""
    return is_model_class(cls) and not cls._meta.abstract


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
