"""``Registry`` — fiel a ``odoo/orm/registry.py`` (Odoo 19).

En Odoo el ``Registry`` es el mapa **por base de datos** de nombre de modelo →
clase de modelo (``registry['res.partner']``). Se construye al cargar los addons
de esa DB, cachea la estructura de modelos/campos y coordina el setup del schema.
Es singleton por ``db_name`` (``Registry(db_name)`` devuelve el existente).

Mapeo a Django — **Django ya provee el registro de modelos**, y por eso este
archivo es un stub delgado documentado, no una reimplementación:

===================================  ===================================================
Odoo ``Registry``                    Equivalente Django
===================================  ===================================================
``Registry(db_name)``                ``django.apps.apps`` (registro global de apps)
``registry['res.partner']``          ``apps.get_model('base', 'ResPartner')``
por-DB (multi-tenant)                ``django.db.connections`` + DB router
                                     (``orm/routers.py``, ya presente: multi-DB
                                     DB-per-company SOL-091)
setup de schema al boot              migraciones Django (``makemigrations`` /
                                     ``migrate``)
caché de estructura modelo/campo     metadata ``Model._meta`` (campos, índices, FKs)
===================================  ===================================================

Recrear ``Registry`` sobre Django duplicaría ``django.apps`` y el manejo de
conexiones. La **dimensión por-DB** (que en Odoo justifica un registry por
tenant) aquí la cubre el router multi-DB de ``orm/routers.py`` + ``connections``.
Un addon portado que leía ``self.env.registry[name]`` se adapta a
``apps.get_model(...)``; el "singleton por DB" a ``connections[alias]``.

``_name`` — el mapa nombre punteado → clase
=============================================

La referencia guarda ese mapa **aquí**: ``Registry.models: dict[str,
type[BaseModel]]`` (``odoo19c: odoo/orm/registry.py:222``), con
``__getitem__``/``__setitem__`` (``:317-323``) como interfaz. Este archivo
recrea esa mitad, que es la única de ``Registry`` sin contraparte directa en
Django: ``apps.get_model`` indexa por ``(app_label, ClassName)``, no por el
nombre punteado de la fuente.

Añadido 2026-08-14 por directiva del ejecutor —*"nosotros queremos hacer
esto"*, sobre un modelo que declara ``_name`` y ``_description``. Vive en
``registry.py`` y no en un archivo propio porque **la referencia no tiene un
archivo propio**: tenerlo sería la divergencia de forma que :ref:`h-api-568`
registra.
"""
import inspect
import logging
import sys
from collections import defaultdict
from collections.abc import Callable, Collection, Iterator

from django.apps import apps
from django.db import connections
from django.db.models.signals import class_prepared
from django.dispatch import receiver
from psycopg import sql as pg_sql

# El modulo, no el nombre: ``orm.environments`` importa este modulo (``:98``),
# asi que ligar ``sudo`` aqui daria ImportError segun quien cargue primero.
# Importar el MODULO liga el objeto ya presente en ``sys.modules`` aunque este
# a medio inicializar, y el atributo se resuelve al llamar. Es un import de
# nivel de modulo — no una excepcion a ``no-lazy-imports.md``.
import orm.environments

from orm.utils import model_field_registry
from tools.lru import LRU
from tools.misc import Collector, OrderedSet
from tools.sql import SQL

_logger = logging.getLogger('kaupamex.registry')

__all__ = [
    'apps', 'connections',
    'MODELS_BY_NAME', 'name_of', 'model_by_name', 'model_by_key',
    'resolve_model_key', 'check_table_matches_name',
    'registrants_without_table',
    'clear_cache', 'clear_all_caches', 'cache_of', 'cache_invalidated',
    'many2one_company_dependents', 'loaded_xmlids',
    'not_null_fields', 'is_not_null',
    '_unaccent',
    'constraint_methods', 'ondelete_methods', 'onchange_methods',
    'clear_marked_methods',
]

#: ≙ ``Registry.loaded_xmlids`` — los identificadores externos que el cargador
#: de data ha visto en esta carga. Lo puebla ``IrModelData._update_xmlids`` y
#: lo consume ``_process_end``, que borra lo que la data ya no declara: una
#: fila con módulo, sin ``noupdate`` y **ausente** de este conjunto es un
#: registro que su módulo dejó de declarar.
loaded_xmlids = set()


#: Tamaño de cada caché de método de modelo, verbatim de la referencia
#: (``odoo19c: odoo/orm/registry.py:51-59``).
_REGISTRY_CACHES = {
    'default': 8192,
    'assets': 512,
    'stable': 1024,
    'templates': 1024,
    'routing': 1024,  # 2 entradas por sitio web
    'routing.rewrites': 8192,  # entradas de url_rewrite
    'templates.cached_values': 2048,  # arbitrario
    'groups': 64,  # ver res.groups
}

#: Dependencias de invalidación, tal cual la referencia (``:64-71``):
#: ``{ 'clave': ('contenedor_1', 'contenedor_3', ...) }``
_CACHES_BY_KEY = {
    'default': ('default', 'templates.cached_values'),
    'assets': ('assets', 'templates.cached_values'),
    'stable': ('stable', 'default', 'templates.cached_values'),
    'templates': ('templates', 'templates.cached_values'),
    'routing': ('routing', 'routing.rewrites', 'templates.cached_values'),
    # el procesamiento de grupos se guarda en la vista
    'groups': ('groups', 'templates', 'templates.cached_values'),
}

#: Los contenedores vivos. La referencia los cuelga de la instancia de
#: ``Registry`` (``self.__caches``, ``:233``) porque allá hay un registry por
#: base de datos; aquí el registry es el módulo —la dimensión por-DB la cubre
#: el router de ``orm/routers.py``, como declara el encabezado— así que los
#: contenedores son estado de módulo. Es la misma estructura, en el único
#: singleton que este árbol tiene.
_CACHES = {name: LRU(size) for name, size in _REGISTRY_CACHES.items()}

#: Nombres de caché vaciados desde el último ciclo, ≙ ``Registry.cache_invalidated``
#: (``odoo19c: odoo/orm/registry.py:238``). Lo consume la señal entre procesos.
cache_invalidated = set()


def _unaccent(x):
    """Envuelve ``x`` en la llamada SQL ``unaccent(...)``, repartiendo por tipo.

    ≙ ``_unaccent`` (``odoo19c: odoo/orm/registry.py:76-81``). La fuente lo
    asigna a ``Registry.unaccent`` cuando la extension esta instalada
    (``:289``) y la identidad cuando no; sus consumidores alla son el indice
    trigram (``:862-864``) y el compilador de ``ilike`` de ``osv/expression``
    (``:449``).

    **Divergencia de mecanismo, no de contrato.** La fuente tipa la tercera
    rama con ``psycopg2.sql.Composable``; este arbol corre **psycopg 3**
    (medido: ``psycopg.__version__`` == ``3.3.4``), cuyo homonimo vive en
    ``psycopg.sql``. Es la misma clase con el mismo nombre en otro paquete,
    asi que la rama se conserva entera apuntada al paquete que este stack
    instala — no se recorta.

    Las tres ramas devuelven tres tipos distintos, igual que la fuente: un
    ``SQL`` compuesto, un ``psycopg.sql.Composed``, y la interpolacion de
    cadena para el resto.

    **Que extension.** La que provee la funcion es ``unaccent``, el contrib de
    PostgreSQL. Se crea en toda base que el ORM construya
    (``base/migrations/0084_unaccent_extension.py``) y tambien la declara el
    provisioner (``db: provisioners/postgresql/db_setup.sh:194-195``); hacen
    falta las dos, porque pytest levanta sus bases desde las migraciones y ahi
    el provisioner no pasa.

    Lo que la fuente pregunta, sin embargo, **no es la extension sino la
    funcion**: ``modules.db.has_unaccent`` mira ``pg_proc``, asi que cualquier
    homonima de un argumento sirve. El ``provolatile`` decide aparte si es
    indexable.

    **Quien lo cablea.** ``orm.fields.UNACCENT_ENABLED`` es ``True`` desde
    2026-09-03, y con el las dos vias de compilacion a la vez: el lookup
    ``SqlILike`` envuelve los dos lados y el predicado en memoria normaliza con
    ``remove_accents``.
    """
    if isinstance(x, SQL):
        return SQL("unaccent(%s)", x)
    if isinstance(x, pg_sql.Composable):
        return pg_sql.SQL('unaccent({})').format(x)
    return f'unaccent({x})'


def cache_of(cache_name):
    """El contenedor vivo de ``cache_name`` ≙ ``Registry.__caches[name]``."""
    return _CACHES[cache_name]


def clear_cache(*cache_names):
    """Vacía las cachés de los métodos decorados con ``tools.ormcache`` cuyo
    nombre esté en ``cache_names`` ≙ ``Registry.clear_cache``
    (``odoo19c: odoo/orm/registry.py:971-987``).
    """
    cache_names = cache_names or ('default',)
    assert not any('.' in cache_name for cache_name in cache_names)
    for cache_name in cache_names:
        for cache in _CACHES_BY_KEY[cache_name]:
            _CACHES[cache].clear()
        cache_invalidated.add(cache_name)

    # información sobre la causa de la invalidación
    if _logger.isEnabledFor(logging.DEBUG):
        # podría interesar en info, pero antes hay que minimizar la
        # invalidación, sobre todo en setup de tests y crons
        _logger.debug('Invalidating %s model caches', ','.join(cache_names))


def clear_all_caches():
    """Vacía todas las cachés de los métodos decorados con ``tools.ormcache``
    ≙ ``Registry.clear_all_caches`` (``odoo19c: odoo/orm/registry.py:989-1001``).
    """
    for cache_name, caches in _CACHES_BY_KEY.items():
        for cache in caches:
            _CACHES[cache].clear()
        cache_invalidated.add(cache_name)

    _logger.debug('Invalidating all model caches')


#: ``'product.removal' -> <class ProductRemoval>``. Ver :func:`_ensure_seeded`
#: sobre por qué se puebla por dos vías y no por una.
MODELS_BY_NAME = {}


def _register(model):
    """Anota el modelo bajo su ``_name``, rechazando el nombre duplicado.

    El paso hermano —resolver ``_rec_name``— vive en ``orm/model_classes.py``,
    que es donde la fuente lo declara, y **no** se llama desde aquí: este
    módulo es el que ``model_classes`` importa, así que la llamada inversa
    cerraría el ciclo. Cada uno cuelga de la señal por su lado.
    """
    name = model.__dict__.get('_name')
    if not name:
        return
    previous = MODELS_BY_NAME.get(name)
    if previous is not None and previous is not model:
        label = lambda cls: getattr(getattr(cls, '_meta', None), 'label',
                                    cls.__name__)
        raise ValueError(
            f'Dos modelos declaran _name={name!r}: '
            f'{label(previous)} y {label(model)}. '
            f'El nombre punteado identifica un modelo, no una familia.'
        )
    MODELS_BY_NAME[name] = model


def register_abstract(cls):
    """Anota bajo su ``_name`` una clase que **no** es modelo de Django.

    ≙ lo que la referencia obtiene gratis: allá ``ir.fields.converter`` es un
    ``AbstractModel``, así que su registro lo conoce y ``env['ir.fields.converter']``
    lo devuelve. Aquí una clase sin columnas no pasa por ``ModelBase``, así que
    la señal ``class_prepared`` nunca dispara para ella y hay que anotarla a
    mano — es la misma tabla y el mismo nombre punteado, sólo que por la puerta
    que este stack deja abierta.

    Se usa donde la referencia usa ``env[...]`` sobre un modelo abstracto: un
    consumidor que no puede importar la clase (porque cerraría ciclo) la
    resuelve por nombre, igual que allá.
    """
    _register(cls)
    return cls


@receiver(class_prepared, dispatch_uid='orm.registry.register_name')
def _register_name(sender, **kwargs):
    """Registra el ``_name`` del modelo recién construido, si lo declara.

    ``class_prepared`` dispara al final de ``ModelBase.__new__``, así que el
    modelo ya tiene ``_meta`` poblado. Un modelo sin ``_name`` no se registra —
    no es un error: los 290 del árbol están así hasta que se toquen.
    """
    _register(sender)


def _ensure_seeded():
    """Barre el registro de Django si la señal llegó tarde.

    **La señal sola no basta, y la razón es la misma de** ``H-API-577``: sólo
    dispara para los modelos preparados **después** de importar este módulo. Si
    algo lo importa tras ``django.setup()`` —un test, un guion, un ``ready()``
    tardío— la tabla queda vacía y el nombre punteado no resuelve, sin error
    que lo delate.

    Medido: con el módulo importado al final de un guion, el registro daba
    ``[]`` con ``ProductRemoval`` ya cargado y declarando su ``_name``.

    Por eso hay dos vías, y ninguna sobra: la señal cubre lo que llega después,
    este barrido cubre lo que ya estaba. Corre una sola vez por proceso porque
    ``apps.get_models()`` es barato pero no gratis, y se salta si el registro de
    apps aún no está listo — en ese caso la señal es la única vía y es correcta.
    """
    if _ensure_seeded.hecho or not apps.ready:
        return
    for model in apps.get_models(include_auto_created=True):
        _register(model)
    _ensure_seeded.hecho = True


_ensure_seeded.hecho = False


def name_of(model):
    """El ``_name`` declarado del modelo, o ``None``.

    Se lee de ``__dict__`` y no con ``getattr`` a propósito: con ``getattr``
    una subclase heredaría el ``_name`` de su padre y diría ser el mismo modelo.
    """
    return model.__dict__.get('_name')


def model_by_name(name):
    """La clase que declara ese ``_name``, o ``None`` si no está cargada."""
    _ensure_seeded()
    return MODELS_BY_NAME.get(name)


def model_by_key(key):
    """La clase de un modelo nombrado en **cualquiera** de las dos formas.

    Puente que nuestra divergencia de almacenamiento necesita, y que la fuente
    no necesita: allá ``self.env[name]`` sólo admite el nombre punteado porque
    es el único que existe. Aquí conviven dos:

    - ``'res.partner'`` — el ``_name`` de la referencia, que es la clave de
      :data:`MODELS_BY_NAME`;
    - ``'base.ResPartner'`` — el *label* de Django, que es lo que guardan las
      columnas de texto que apuntan a un modelo (``ir_model.model``,
      ``ir_actions_server.model_name``, ``ir_rule.model_name``).

    Devuelve ``None`` si ninguna de las dos resuelve, en vez de levantar: sus
    consumidores leen una **columna**, y una fila puede sobrevivir al modelo
    que nombraba (módulo desinstalado, clase renombrada). Es el mismo criterio
    con que ``IrModel.django_model`` devuelve ``None``.

    :func:`resolve_model_key` es la hermana que **sí** levanta, porque su
    consumidor —``extend_model``— nombra un destino que el programador escribió
    y cuya ausencia es un error de programa, no un dato viejo.
    """
    if not key:
        return None
    _ensure_seeded()
    model = MODELS_BY_NAME.get(key)
    if model is not None:
        return model
    try:
        app_label, model_name = key.split('.', 1)
    except ValueError:
        return None
    try:
        return apps.get_model(app_label, model_name)
    except LookupError:
        return None


def resolve_model_key(*args):
    """Normaliza las dos formas de nombrar un modelo a la clave de Django.

    Acepta:

    - ``resolve_model_key('product.removal')`` — el nombre de la referencia,
      **si** el modelo ya está registrado;
    - ``resolve_model_key('stock', 'ProductRemoval')`` — el par de Django, que
      no exige que el modelo exista todavía.

    Devuelve siempre ``(app_label, model_name_en_minúscula)``, que es la clave
    que ``Apps.do_pending_operations`` reconstruye (ver ``H-API-577``).

    El nombre punteado **sólo** resuelve si el modelo está cargado: la tabla la
    puebla la señal, y antes de que el módulo se importe no hay nada que
    consultar. Para el caso tardío —extender algo aún no cargado— hay que dar el
    par de Django. Es la única asimetría entre las dos formas, y es inherente:
    la referencia no la tiene porque su registro conoce todos los nombres antes
    de construir ninguna clase.
    """
    if len(args) == 2:
        label, name = args
        return (label, name.lower())
    if len(args) != 1:
        raise TypeError(
            'resolve_model_key acepta "app.Modelo" (dos argumentos) o '
            'el nombre punteado de la referencia (uno), no %d' % len(args))

    dotted_name = args[0]
    _ensure_seeded()
    model = MODELS_BY_NAME.get(dotted_name)
    if model is None:
        raise LookupError(
            f'Ningún modelo cargado declara _name={dotted_name!r}. '
            f'Si el destino todavía no se ha importado, nómbralo con el par '
            f'de Django: extend_model("app", "Modelo", …).'
        )
    return (model._meta.app_label, model._meta.model_name)


def check_table_matches_name(models_found=None):
    """¿Coincide ``db_table`` con lo que la referencia derivaría de ``_name``?

    La referencia obtiene la tabla por sustitución; aquí es una declaración
    humana, así que las dos pueden divergir sin que nada avise. Devuelve la
    lista de ``(label, _name, db_table_esperado, db_table_real)`` que NO
    coinciden — vacía si todo cuadra.

    Sólo mira los modelos que declaran ``_name``: el resto no tiene con qué
    comparar, y contarlos como divergencia sería medir su ausencia, no su
    forma.

    **Un registrante sin tabla no es una divergencia — es otra población.**
    El registro por nombre admite clases que no son modelos de Django: el
    equivalente del ``AbstractModel`` de la fuente, que declara ``_name`` y no
    tiene tabla (``IrFieldsConverter`` es uno). Preguntarle su ``db_table``
    reventaba con ``AttributeError``, así que este check moría en vez de dar
    veredicto. Ahora se apartan, **y se pueden contar** con
    :func:`registrants_without_table` — un salto silencioso dejaría el verde
    sin discriminar «no hay divergencias» de «no pude comparar».

    **``_table`` gana sobre la sustitución**, como en la fuente: allá
    ``model_cls._table = model_cls._name.replace('.', '_')``
    (``odoo19c: odoo/orm/model_classes.py:266``) es sólo el **default**, y una
    clase que declara ``_table`` lo sobreescribe. Nueve de los diez modelos de
    ``ir_actions.py`` lo hacen (``ir.actions.act_window`` → ``ir_act_window``),
    así que sin honrarlo este check reportaría como divergencia la forma que la
    referencia declara a propósito.
    """
    if models_found is None:
        _ensure_seeded()
        models_found = list(MODELS_BY_NAME.values())
    divergences = []
    for model in models_found:
        name = name_of(model)
        if not name:
            continue
        meta = getattr(model, '_meta', None)
        if meta is None:
            continue                      # sin tabla: lo cuenta el hermano
        expected = model.__dict__.get('_table') or name.replace('.', '_')
        actual = meta.db_table
        if expected != actual:
            divergences.append((meta.label, name, expected, actual))
    return divergences


def registrants_without_table(models_found=None):
    """Los registrantes por ``_name`` que NO tienen tabla que comparar.

    Es el denominador que :func:`check_table_matches_name` aparta. Devuelve
    ``(nombre_de_clase, _name)`` de cada clase que declara ``_name`` sin ser un
    modelo de Django — el equivalente aquí del ``AbstractModel`` de la fuente,
    que en el registro existe y en el catálogo de tablas no.

    Se exporta para que el salto sea **medible** y no silencioso: sin esta
    función, un cero de divergencias no distinguiría «todo cuadra» de «no había
    nada que comparar».
    """
    if models_found is None:
        _ensure_seeded()
        models_found = list(MODELS_BY_NAME.values())
    return [
        (model.__name__, name_of(model))
        for model in models_found
        if name_of(model) and getattr(model, '_meta', None) is None
    ]



def many2one_company_dependents(model_label):
    """Los ``Many2one`` dependientes de empresa que apuntan a este modelo.

    ≙ ``Registry.many2one_company_dependents``
    (``odoo19c: odoo/orm/registry.py``), el mapa que la fuente indexa por
    ``_name`` del modelo apuntado. Lo consume ``base_partner_merge``: al
    fusionar dos contactos hay que repuntar también los valores por empresa
    que guardan su id dentro de un ``jsonb``, y una FK del catálogo no los ve.

    DIVERGENCIA DE MECANISMO, declarada: allá es un atributo memorizado del
    ``Registry``, que se puebla al cargar el registro; aquí se deriva de
    ``apps.get_models()`` en la llamada. El coste es el recorrido de los
    modelos instalados, que su único llamador paga una vez por fusión — no un
    bucle caliente. Memorizarlo exigiría invalidarlo, y no hay evento que lo
    dispare: el conjunto de campos no cambia en caliente.

    **Devuelve vacío por dato, no por construcción.** Hoy ningún ``Many2one``
    se declara ``company_dependent`` porque su despachador todavía no lo
    cablea (tarea **#129**); el día que uno lo haga, aparece aquí solo.

    :param model_label: la etiqueta del modelo apuntado (``app.Modelo``).
    :returns: lista de ``(modelo, campo)`` — el par que el llamador necesita
        para nombrar tabla y columna.
    """
    encontrados = []
    for model in apps.get_models():
        for field in model._meta.get_fields():
            if not getattr(field, 'company_dependent', False):
                continue
            if getattr(field, 'base_type', None) != 'many2one':
                continue
            related = getattr(field, 'company_dependent_comodel', None)
            if related == model_label:
                encontrados.append((model, field))
    return encontrados


# ═══════════════════════════════════════════════════════════════════════════
# ``field_depends`` — ≙ ``odoo19c: odoo/orm/registry.py:252-253``
# ═══════════════════════════════════════════════════════════════════════════
#
# Allá son dos ``Collector`` que el setup del registro **puebla** al cargar los
# addons (``:410-474``): ``field_depends[campo]`` da los nombres punteados de
# los que ese campo depende, y ``field_depends_context[campo]`` las claves de
# contexto. El consumidor directo es ``Field._description_depends``
# (``odoo/orm/fields.py:902``), que los publica al cliente.
#
# Aquí no hay fase de setup que poblar: Django carga los modelos y termina. Así
# que el mapa se **deriva** de lo ya declarado, y se deriva una sola vez —
# ``@api.depends`` deja su tupla en ``func._depends`` (``orm/decorators.py:23``),
# y un campo calculado nombra su método en ``compute``.
#
# La derivación es la misma información por otro camino: allá el decorador la
# entrega al setup, aquí el mapa va a buscarla al método. Lo que NO se hereda
# es la invalidación parcial de ``:474``, que existe porque allá el registro se
# reconstruye por base; aquí se vacía entero con :func:`clear_field_depends`.


class _DerivedCollector:
    """Mapa campo → tupla, derivado de lo declarado y cacheado entero.

    ≙ ``Collector`` (``odoo19c: odoo/tools/misc.py``) en su lado de lectura:
    un campo sin entrada devuelve la tupla vacía, nunca ``KeyError``. Esa
    parte del contrato importa — ``_description_depends`` lo consulta para
    todo campo, tenga o no dependencias declaradas.
    """

    def __init__(self, marker):
        self.marker = marker
        self._table = None

    @staticmethod
    def _resolve(declared, model):
        """La tupla de lo declarado, resolviendo la forma invocable.

        ``@api.depends`` y ``@api.constrains`` admiten **un solo argumento
        invocable** en vez de nombres (``odoo19c: odoo/orm/decorators.py:265``
        — *"One may also pass a single function as argument. In that case, the
        dependencies are given by calling the function with the field's
        model"*). La fuente lo resuelve al leerlo, en
        ``odoo19c: odoo/orm/fields.py:595``::

            depends.extend(deps(model) if callable(deps) else deps)

        Aquí el lector es este colector, así que la resolución vive aquí. Sin
        ella un ``_depends`` invocable reventaba con ``TypeError`` al pasar por
        ``tuple()`` — la forma existía en el decorador y no tenía quien la
        leyera.
        """
        if callable(declared):
            declared = declared(model)
        return tuple(declared)

    def _build(self):
        table = {}
        for model in apps.get_models():
            for field in model._meta.get_fields():
                declared = getattr(field, self.marker, None)
                if declared is None:
                    compute = getattr(field, 'compute', None)
                    method = getattr(model, compute, None) if compute else None
                    declared = getattr(method, self.marker, None)
                if declared:
                    table[field] = self._resolve(declared, model)
        return table

    def __getitem__(self, field):
        if self._table is None:
            self._table = self._build()
        return self._table.get(field, ())

    def __contains__(self, field):
        return bool(self[field])

    def clear(self):
        """≙ ``Collector.clear`` (``:421-422``) — el mapa se vuelve a derivar
        en la siguiente consulta."""
        self._table = None


#: ≙ ``Registry.field_depends`` (``:252``).
field_depends = _DerivedCollector('_depends')

#: ≙ ``Registry.field_depends_context`` (``:253``).
field_depends_context = _DerivedCollector('_depends_context')


class _MarkedMethodCollector:
    """Metodos de un modelo que llevan un marcador, derivados y cacheados.

    Es el hermano de :class:`_DerivedCollector` para el otro eje: aquel recorre
    los CAMPOS de cada modelo buscando un marcador; este recorre los METODOS de
    un modelo dado. Los dos derivan de lo declarado y los dos se invalidan
    enteros.

    **Donde vive el memo, y por que no en la clase.** La fuente declara los
    tres como ``@property`` sobre ``BaseModel`` y memoiza el resultado EN LA
    CLASE del modelo (``odoo19c: odoo/orm/models.py:544``, ``:556``, ``:592``:
    *"optimization: memoize result on cls, it will not be recomputed"*). Aqui
    ``BaseModel`` es el ``Model`` de Django: colgarle una ``property`` nuestra
    alcanzaria a ``auth``, ``contenttypes`` y a todo modelo de tercero — la
    colision que barre la tarea **#98**. El memo vive en este mapa, y el reset
    que ``_prepare_setup`` hace reasignando la property (``model_classes.py:
    344-346``) es aqui :func:`clear_marked_methods`.

    **``getattr_static``, no ``getmembers``, y no es preferencia.** La fuente
    usa ``inspect.getmembers``, que LEE cada atributo — alla eso es inocuo. Un
    modelo de Django declara descriptores que se resuelven al leerlos
    (``orm.fields_nonstored.NonStored`` calcula su default consultando el
    registro), asi que recorrer la clase con ``getattr`` los ejecutaria.
    ``getattr_static`` devuelve el objeto sin dispararlos. Es la misma razon
    por la que ``addons/web/models/models.py`` ya lo hacia en su copia local.

    *Metrica:* atributos de la clase, resueltos sin ejecutar descriptores, que
    declaren el marcador.
    *Ciega a:* un metodo que el modelo resuelva en un ``__getattr__`` propio —
    no aparece en ``dir()``. Es la misma ceguera que ``_delegable_field_names``
    declara para su eje.
    """

    def __init__(self, marker):
        self.marker = marker
        self._table = {}

    def _marked(self, model_cls):
        """Los metodos de ``model_cls`` que declaran el marcador.

        ≙ el ``getmembers(cls, is_constraint)`` de la fuente (``:534``), cuyo
        predicado es ``callable(func) and hasattr(func, '_constrains')``.
        """
        found = []
        for name in dir(model_cls):
            if name.startswith('__'):
                continue
            try:
                attr = inspect.getattr_static(model_cls, name)
            except AttributeError:
                continue
            func = getattr(attr, '__func__', attr)
            if callable(func) and getattr(func, self.marker, None) is not None:
                found.append((name, func))
        found.sort()
        return found

    def __call__(self, model_cls):
        if model_cls not in self._table:
            self._table[model_cls] = self._build(model_cls)
        return self._table[model_cls]

    def clear(self):
        """El reset de ``_prepare_setup`` (``model_classes.py:344-346``)."""
        self._table = {}


class _ConstraintMethods(_MarkedMethodCollector):
    """≙ ``BaseModel._constraint_methods`` (``odoo19c: odoo/orm/models.py:
    519-546``) — «Return a list of methods implementing Python constraints».

    Devuelve una **tupla**, no la lista de la fuente: ningun consumidor la
    muta, y es la forma que los colectores de este modulo ya tienen. Los
    nombres declarados siguen en ``func._constrains``, que es donde
    :func:`~orm.models._validate_fields` los lee.

    **La forma invocable se envuelve, no se sobreescribe.** La fuente admite
    ``@api.constrains(lambda self: self._get_plan_fnames())`` y resuelve la
    llamada en un **proxy** con los nombres ya fijos (``:526-532``), dejando
    intacto el ``_constrains`` invocable del metodo original. Medido en
    ``odoo19c``: **5** declarantes, uno de ellos en ``base``
    (``res_company.py:426``); aqui **0** todavia.

    Reescribir el atributo sobre el propio metodo —que es lo que esta clase
    hacia hasta la tarea **#334**— parece equivalente y no lo es: **destruye
    el invocable en la primera lectura**. Tras un
    :func:`clear_marked_methods` el metodo ya solo tendria la tupla de aquella
    vez, asi que un ``lambda`` cuyo resultado dependa del estado —los cinco de
    la fuente llaman a un metodo del modelo— quedaria congelado en su primera
    respuesta. La fuente re-resuelve en cada reconstruccion porque nunca toca
    el original.

    **A quien se le pasa el invocable** es la unica divergencia: la fuente lo
    llama con ``self.sudo()``, un recordset vacio y elevado. Aqui el analogo
    de un recordset vacio es una **instancia sin guardar**, y la elevacion es
    un gestor de contexto (``orm.environments.sudo``) en vez de un receptor
    distinto — la misma asimetria que :func:`~orm.models._validate_fields`
    declara para su eje.

    **Los dos avisos se portan** (``:539-542``): un nombre que no es campo, y
    un campo que no se puede escribir. Sin ellos un ``@api.constrains`` con
    una errata queda mudo, que es justo lo que la fuente evita.
    """

    def __init__(self):
        super().__init__('_constrains')

    def _build(self, model_cls):
        methods = []
        for name, func in self._marked(model_cls):
            if callable(func._constrains):
                func = self._wrap(func, model_cls)
            self._warn_about_declared_names(model_cls, name, func)
            methods.append(func)
        return tuple(methods)

    @staticmethod
    def _wrap(func, model_cls):
        """El proxy de la fuente (``:526-532``), con los nombres ya resueltos.

        Deja ``func._constrains`` invocable donde estaba: el proxy es otro
        objeto, y el original sigue disponible para la proxima reconstruccion.
        """
        with orm.environments.sudo():
            names = tuple(func._constrains(model_cls()))

        def wrapper(self):
            return func(self)

        wrapper._constrains = names
        wrapper.__name__ = getattr(func, '__name__', 'wrapper')
        wrapper.__doc__ = func.__doc__
        return wrapper

    @staticmethod
    def _warn_about_declared_names(model_cls, attr, func):
        """≙ los dos avisos de la fuente (``odoo19c: odoo/orm/models.py:
        539-542``), verbatim en su texto.

        Lee el mapa con ``model_field_registry``, que es lo que ``_fields``
        devuelve (``orm/models.py:1449``), y lo lee **de la clase**: aquel es
        una property de instancia y fabricar una fila solo para leer su
        registro seria trabajo por nada.

        *Ciega a:* un nombre que el modelo resuelva fuera de ``_fields`` —
        misma ceguera que ``_fields`` ya declara para su propio contrato— y a
        una clase sin ``_meta``, que no es un modelo y por tanto no declara
        campo alguno contra el que comparar.
        """
        if not hasattr(model_cls, '_meta'):
            return
        fields = model_field_registry(model_cls)
        for name in func._constrains:
            field = fields.get(name)
            if not field:
                _logger.warning(
                    "method %s.%s: @constrains parameter %r is not a field name",
                    getattr(model_cls, '_name', model_cls.__name__), attr, name)
            elif not (getattr(field, 'store', False)
                      or getattr(field, 'inverse', None)
                      or getattr(field, 'inherited', False)):
                _logger.warning(
                    "method %s.%s: @constrains parameter %r is not writeable",
                    getattr(model_cls, '_name', model_cls.__name__), attr, name)


class _OndeleteMethods(_MarkedMethodCollector):
    """≙ ``BaseModel._ondelete_methods`` (``models.py:548-558``) — «Return a
    list of methods implementing checks before unlinking».

    El valor del marcador **no es un booleano de presencia**: es el
    ``at_uninstall`` que el decorador guarda, y ``unlink`` lo lee para decidir
    si el metodo corre tambien al desinstalar el modulo (``:4207``: *"func.
    _ondelete is True if it should be called during uninstallation"*). Por eso
    el colector no puede filtrar por verdad — un ``at_uninstall=False`` es
    ``False`` y sigue siendo un metodo marcado.
    """

    def __init__(self):
        super().__init__('_ondelete')

    def _build(self, model_cls):
        return tuple(func for _name, func in self._marked(model_cls))


class _OnchangeMethods(_MarkedMethodCollector):
    """≙ ``BaseModel._onchange_methods`` (``models.py:560-593``) — «Return a
    dictionary mapping field names to onchange methods».

    Devuelve un ``dict`` de tuplas donde la fuente devuelve un
    ``defaultdict(list)``. La diferencia es observable en un solo punto y a
    favor: ``_has_onchange`` pregunta ``field.name in self._onchange_methods``
    (``:6970``), y sobre un ``defaultdict`` una lectura previa por ``[]``
    habria creado la clave. Con un ``dict`` la ausencia se mantiene ausente.

    **La mitad de ``change_default`` no se porta todavia.** La fuente anade un
    metodo sintetico por cada campo con ``change_default`` (``:583-589``), que
    lee los valores por defecto de ``ir.default`` para la condicion
    ``campo=valor``. Medido: **0** campos declaran ``change_default`` en este
    arbol, asi que el bucle no tendria sobre que iterar. Queda como DESCONOCIDO
    con condicion de cierre — se porta en cuanto el primer campo lo declare, y
    su sucesor es la tarea **#335**.
    """

    def __init__(self):
        super().__init__('_onchange')

    def _build(self, model_cls):
        methods = defaultdict(list)
        for _name, func in self._marked(model_cls):
            for field_name in func._onchange:
                methods[field_name].append(func)
        return {name: tuple(funcs) for name, funcs in methods.items()}


#: ≙ ``BaseModel._constraint_methods`` (``odoo19c: odoo/orm/models.py:519``).
constraint_methods = _ConstraintMethods()

#: ≙ ``BaseModel._ondelete_methods`` (``:548``).
ondelete_methods = _OndeleteMethods()

#: ≙ ``BaseModel._onchange_methods`` (``:560``).
onchange_methods = _OnchangeMethods()


def clear_marked_methods():
    """Vacia los tres mapas de metodo marcado.

    ≙ el bloque de ``_prepare_setup`` que reasigna las tres propiedades
    memoizadas (``odoo19c: odoo/orm/model_classes.py:343-346``: *"reset
    properties memoized on model_cls"*). Alla el reset es por modelo porque el
    memo vive en su clase; aqui el mapa es de modulo y se vacia entero, con el
    mismo criterio que :func:`clear_field_depends` ya declara para su eje.
    """
    constraint_methods.clear()
    ondelete_methods.clear()
    onchange_methods.clear()


class _ComputedGrouper:
    """Mapa campo → los campos que calcula el MISMO método.

    ≙ ``Registry.field_computed`` (``odoo19c: odoo/orm/registry.py:515``). Su
    contrato tiene dos mitades y las dos importan:

    - un campo calculado devuelve la lista de **todos** los campos de su
      modelo que declaran ese mismo ``compute``, incluido él. Es lo que
      ``Field.compute_value`` recorre para desmarcar el cómputo pendiente de
      todo el grupo, no sólo del campo por el que se entró;
    - un campo **sin** ``compute`` no está en el mapa. La fuente lo consulta
      con ``[]`` y deja que reviente, porque llamarlo sobre un campo no
      calculado es un error de programación, no un caso.

    Por eso NO hereda de :class:`_DerivedCollector`: aquél devuelve la tupla
    vacía ante lo ausente, que aquí escondería justo ese error.
    """

    def __init__(self):
        self._table = None

    def _build(self):
        table = {}
        for model in apps.get_models():
            groups = defaultdict(list)
            for field in model._meta.get_fields():
                compute = getattr(field, 'compute', None)
                if compute:
                    table[field] = group = groups[compute]
                    group.append(field)
        return table

    def __getitem__(self, field):
        if self._table is None:
            self._table = self._build()
        return self._table[field]

    def __contains__(self, field):
        if self._table is None:
            self._table = self._build()
        return field in self._table

    def clear(self):
        self._table = None


#: ≙ ``Registry.field_computed`` (``:515``).
field_computed = _ComputedGrouper()


class _TriggerRegistry:
    """El grafo de disparo: qué recalcular cuando un campo cambia.

    ≙ el bloque de ``Registry`` que va de ``field_inverses`` (``:506``) a
    ``is_modifying_relations`` (``:670``). Es la **inversa** de la capa A:
    aquélla sabe recalcular un campo; esto sabe QUÉ campos hay que recalcular
    y por qué camino llegar a las filas afectadas.

    Es una clase y no seis funciones sueltas porque los tres mapas
    —``field_inverses``, los disparadores y el caché de árboles— se derivan del
    mismo recorrido y se vacían juntos. Separarlos dejaría tres invalidaciones
    que alguien tendría que acordarse de llamar en orden.

    La inversa la trae el stack, y por eso ``setup_inverses`` no se porta
    =====================================================================

    La fuente construye ``field_inverses`` llamando a un ``setup_inverses``
    **por clase de campo** (``One2many`` liga con su ``inverse_name``,
    ``Many2many`` con su tabla de relación) porque su ORM no guarda la vuelta.
    Django sí: ``field.remote_field`` es la relación inversa, y
    ``_meta.get_fields()`` la publica como un objeto propio junto a los campos
    concretos. Aquí el mapa se **deriva** de eso.

    Es divergencia de mecanismo, no de alcance: el contenido del mapa es el
    mismo —cada lado de una relación apunta al otro— y se obtiene sin la
    ceremonia que la fuente necesita. Cierra el DESCONOCIDO que
    ``fields_relational.py`` declaró sobre ``setup_inverses`` (tarea **#244**),
    cuya razón era que este árbol no tenía caché de campos; desde la capa A la
    tiene.
    """

    def __init__(self):
        self._inverses = None
        self._triggers = None
        self._trees = {}
        self._modifying = {}

    # --- la relación inversa, derivada de Django ---------------------------

    @property
    def field_inverses(self):
        """≙ ``Registry.field_inverses`` (``:506``) — cada lado de una
        relación apunta al otro."""
        if self._inverses is None:
            self._inverses = self._build_inverses()
        return self._inverses

    @staticmethod
    def _build_inverses():
        inverses = Collector()
        for model in apps.get_models():
            for field in model._meta.get_fields():
                remote = getattr(field, 'remote_field', None)
                if remote is None:
                    continue
                # ``remote_field`` del concreto es el objeto de relación
                # inversa, y el de éste es el concreto: la vuelta es simétrica
                # y basta con anotar las dos direcciones de cada par.
                inverses.add(field, remote)
                inverses.add(remote, field)
        return inverses

    # --- los disparadores, invirtiendo lo declarado ------------------------

    def field_triggers(self):
        """La inversa de las dependencias: ``{campo: {ruta: campos}}``.

        ≙ ``Registry._field_triggers`` (``:645``). Docstring de la fuente,
        verbatim: *"the inverse of field dependencies, as a dictionary like
        ``{field: {path: fields}}``, where ``field`` is a dependency, ``path``
        is a sequence of fields to inverse and ``fields`` is a collection of
        fields that depend on ``field``"*.

        Es un método y no una propiedad porque la fuente lo declara con guion
        bajo —es interno— y aquí un atributo de módulo con el mismo nombre
        chocaría con el mapa público. El guion bajo se conserva en el nombre
        del atributo, no en el del método (``porte-completo-no-parcial.md``:
        el guion bajo es contrato, y este símbolo es el que el motor llama).
        """
        if self._triggers is None:
            self._triggers = self._build_triggers()
        return self._triggers

    @staticmethod
    def _build_triggers():
        triggers = defaultdict(lambda: defaultdict(OrderedSet))
        for model in apps.get_models():
            # Un modelo abstracto de Django no está en ``get_models()``, así
            # que el ``if Model._abstract: continue`` de la fuente no tiene
            # nada que saltarse aquí.
            for field in model._meta.get_fields():
                resolve = getattr(field, 'resolve_depends', None)
                if resolve is None:
                    continue
                for dependency in resolve(sys.modules[__name__]):
                    *path, dep_field = dependency
                    triggers[dep_field][tuple(reversed(path))].add(field)
        return triggers

    # --- el árbol y sus lectores -------------------------------------------

    def get_field_trigger_tree(self, field):
        """El árbol de disparo de un campo, por cierre transitivo.

        ≙ ``Registry.get_field_trigger_tree`` (``:594``).
        """
        try:
            return self._trees[field]
        except KeyError:
            # silent OK because es el fallo del memo, no un error: la ausencia
            # de la clave ES la respuesta «todavía no está calculado», y el
            # cuerpo que sigue lo calcula. La fuente lo escribe igual
            # (``odoo19c: odoo/orm/registry.py:598-601``).
            pass

        triggers = self.field_triggers()
        if field not in triggers:
            return TriggerTree()

        def transitive_triggers(field, prefix=(), seen=()):
            if field in seen or field not in triggers:
                return
            for path, targets in triggers[field].items():
                full_path = concat(prefix, path)
                yield full_path, targets
                for target in targets:
                    yield from transitive_triggers(
                        target, full_path, seen + (field,))

        def concat(seq1, seq2):
            """Cancela el par ida-vuelta: bajar por un ``many2one`` y subir
            por su ``one2many`` deja el recorrido donde estaba."""
            if seq1 and seq2:
                first, second = seq1[-1], seq2[0]
                if _is_round_trip(first, second):
                    return concat(seq1[:-1], seq2[1:])
            return seq1 + seq2

        tree = TriggerTree()
        for path, targets in transitive_triggers(field):
            current = tree
            for label in path:
                current = current.increase(label)
            if current.root:
                current.root.update(targets)
            else:
                current.root = OrderedSet(targets)

        self._trees[field] = tree
        return tree

    def get_trigger_tree(self, fields_changed, select=bool):
        """El árbol a recorrer cuando ``fields_changed`` han cambiado.

        ≙ ``Registry.get_trigger_tree`` (``:554``). ``select`` decide qué
        campos se conservan en los nodos, para descartar los que no interesan.
        """
        triggers = self.field_triggers()
        trees = [self.get_field_trigger_tree(field)
                 for field in fields_changed if field in triggers]
        return TriggerTree.merge(trees, select)

    def get_dependent_fields(self, field):
        """Los campos que dependen de ``field`` — ≙ ``:567``."""
        if field not in self.field_triggers():
            return
        for tree in self.get_field_trigger_tree(field).depth_first():
            yield from tree.root

    def is_modifying_relations(self, field):
        """Si tocar ``field`` puede cambiar QUÉ filas dependen de él.

        ≙ ``Registry.is_modifying_relations`` (``:670``). Docstring de la
        fuente, verbatim: *"Return whether ``field`` has dependent fields on
        some records, and that modifying ``field`` might change the dependent
        records"*.
        """
        try:
            return self._modifying[field]
        except KeyError:
            inverses = self.field_inverses
            result = field in self.field_triggers() and bool(
                _is_relational(field) or inverses[field] or any(
                    _is_relational(dep) or inverses[dep]
                    for dep in self.get_dependent_fields(field)))
            self._modifying[field] = result
            return result

    # --- invalidación ------------------------------------------------------

    def clear(self):
        """Vacía los cuatro mapas derivados.

        ≙ el tramo de ``Registry._discard_fields`` (``:573``) que los descarta.
        **Los cuatro juntos**: el caché de árboles guarda instancias derivadas
        de los disparadores, así que vaciar uno y no el otro serviría un árbol
        construido sobre un grafo que ya no existe — el mismo defecto que el
        memo de ``_get_cache`` tenía frente a ``invalidate_field_data``.
        """
        self._inverses = None
        self._triggers = None
        self._trees.clear()
        self._modifying.clear()


def _is_relational(field):
    """Si el campo lleva a otro modelo — ≙ ``Field.relational`` de la fuente.

    Se lee de ``is_relation`` de Django, que es donde este stack lo declara,
    y no de un atributo ``relational`` que habría que instalar en cada clase.
    """
    return bool(getattr(field, 'is_relation', False))


def _is_round_trip(first, second):
    """Si ``second`` deshace el paso que ``first`` dio.

    ≙ la comprobación que ``concat`` hace en la fuente
    (``many2one`` seguido del ``one2many`` que lo invierte). Aquí la decide la
    propia relación inversa de Django en vez de comparar cuatro nombres a
    mano: ``second`` deshace a ``first`` cuando es exactamente su
    ``remote_field``, en cualquiera de los dos sentidos.
    """
    return (getattr(first, 'remote_field', None) is second
            or getattr(second, 'remote_field', None) is first)


#: La instancia única del grafo — el registro aquí es un módulo, no una
#: instancia por base (divergencia declarada en la cabecera de este archivo).
_triggers = _TriggerRegistry()


def field_triggers():
    """≙ ``Registry._field_triggers`` — ver :meth:`_TriggerRegistry.field_triggers`."""
    return _triggers.field_triggers()


def get_field_trigger_tree(field):
    """≙ ``Registry.get_field_trigger_tree``."""
    return _triggers.get_field_trigger_tree(field)


def get_trigger_tree(fields_changed, select=bool):
    """≙ ``Registry.get_trigger_tree``."""
    return _triggers.get_trigger_tree(fields_changed, select)


def get_dependent_fields(field):
    """≙ ``Registry.get_dependent_fields``."""
    return _triggers.get_dependent_fields(field)


def is_modifying_relations(field):
    """≙ ``Registry.is_modifying_relations``."""
    return _triggers.is_modifying_relations(field)


class _FieldInversesProxy:
    """``registry.field_inverses`` como el mapa que la fuente expone.

    La fuente lo declara ``cached_property``, así que se lee como atributo. Un
    módulo no tiene propiedades, y una función obligaría a escribir
    ``field_inverses()[campo]`` — que es otra firma. El proxy conserva la de la
    fuente delegando en la instancia.
    """

    def __getitem__(self, field):
        return _triggers.field_inverses[field]

    def __contains__(self, field):
        return field in _triggers.field_inverses

    def __iter__(self):
        return iter(_triggers.field_inverses)

    def __len__(self):
        return len(_triggers.field_inverses)


#: ≙ ``Registry.field_inverses`` (``:506``).
field_inverses = _FieldInversesProxy()


def clear_field_depends():
    """Vacía los mapas derivados de lo declarado.

    Se llama cuando cambia lo declarado — un modelo nuevo registrado, un campo
    extendido. NO hay invalidación parcial como en ``:474``: allá el registro
    se reconstruye por base y merece el detalle; aquí la derivación entera
    cuesta un recorrido de ``apps.get_models()``.
    """
    field_depends.clear()
    field_depends_context.clear()
    field_computed.clear()
    _triggers.clear()


class DummyRLock:
    """≙ ``DummyRLock`` (``odoo19c: odoo/orm/registry.py:1189-1198``).

    Docstring de la fuente, verbatim: *"Dummy reentrant lock, to be used while
    running rpc and js tests"*.

    Es un **objeto nulo**: cumple el protocolo de ``threading.RLock`` sin
    tomar nada. La fuente lo sustituye en ``Registry._lock`` mientras corren
    las pruebas de RPC y de JS, donde el cerrojo real serializaría peticiones
    que la prueba necesita concurrentes.

    ``__exit__`` devuelve ``None`` a propósito, así que la excepción del
    bloque **se propaga**: un cerrojo nulo no es un ``try`` mudo.
    """

    def acquire(self):
        pass

    def release(self):
        pass

    def __enter__(self):
        self.acquire()

    def __exit__(self, type, value, traceback):
        self.release()


class TriggerTree(dict):
    """≙ ``TriggerTree`` (``odoo19c: odoo/orm/registry.py:1201-1269``).

    Docstring de la fuente, verbatim: *"The triggers of a field F is a tree
    that contains the fields that depend on F, together with the fields to
    inverse to find out which records to recompute"*.

    El árbol que la fuente dibuja: G depende de F, H de ``X.F``, I de
    ``W.X.F``, y J de ``Y.F``::

                                 [G]
                               X/   \\Y
                             [H]     [J]
                           W/
                         [I]

    Y para qué sirve, verbatim: *"when F is modified on records, mark G to
    recompute on records, mark H to recompute on ``inverse(X, records)``, mark
    I to recompute on ``inverse(W, inverse(X, records))``, mark J to recompute
    on ``inverse(Y, records)``"*.

    La **clave** de cada nodo es el campo a invertir; la **raíz** de cada nodo
    son los campos a recalcular en ese punto del recorrido.

    Divergencia de anotación, no de mecanismo
    =========================================

    La fuente declara ``dict['Field', 'TriggerTree']``. Aquí la clase hereda de
    ``dict`` a secas y la anotación viaja en el docstring: ``Field`` es el ciclo
    duro de siete que el orden de porte midió, y **la clave no crea dependencia
    real** — el árbol nunca invoca nada del campo, sólo lo usa como clave
    hasheable y lo guarda en su raíz. Esperar a ``Field`` para portar esto sería
    confundir una anotación con un acoplamiento.
    """

    __slots__ = ['root']

    # pylint: disable=keyword-arg-before-vararg
    def __init__(self, root: Collection = (), *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.root = root

    def __bool__(self) -> bool:
        return bool(self.root or len(self))

    def __repr__(self) -> str:
        return f"TriggerTree(root={self.root!r}, {super().__repr__()})"

    def increase(self, key) -> 'TriggerTree':
        """El subárbol de ``key``, creándolo vacío si aún no existe."""
        try:
            return self[key]
        except KeyError:
            subtree = self[key] = TriggerTree()
            return subtree

    def depth_first(self) -> Iterator['TriggerTree']:
        """Cada nodo del árbol, el padre antes que sus hijos."""
        yield self
        for subtree in self.values():
            yield from subtree.depth_first()

    @classmethod
    def merge(cls, trees: list, select: Callable = bool) -> 'TriggerTree':
        """≙ ``merge`` (``odoo19c: :1249-1269``).

        Docstring de la fuente, verbatim: *"Merge trigger trees into a single
        tree. The function ``select`` is called on every field to determine
        which fields should be kept in the tree nodes. This enables to discard
        some fields from the tree nodes"*.

        Un subárbol que ``select`` deja vacío **no se conserva**: su
        ``__bool__`` es falso y la rama desaparece del resultado.
        """
        root_fields = OrderedSet()             # los campos del nodo raíz
        subtrees_to_merge = defaultdict(list)  # subárboles a fundir, por clave

        for tree in trees:
            root_fields.update(tree.root)
            for label, subtree in tree.items():
                subtrees_to_merge[label].append(subtree)

        # El nodo raíz se queda con los campos para los que ``select`` es cierto.
        result = cls([field for field in root_fields if select(field)])
        for label, subtrees in subtrees_to_merge.items():
            subtree = cls.merge(subtrees, select)
            if subtree:
                result[label] = subtree

        return result


def not_null_fields(model=None):
    """≙ ``Registry.not_null_fields`` (``odoo19c: odoo/orm/registry.py:267``).

    El conjunto de campos cuya **columna** rechaza el nulo. Su consumidor en
    la fuente son tres sitios que deciden si una condición tiene que contemplar
    la fila sin valor: ``domains._optimize_in_required``,
    ``fields.Field.condition_to_sql`` (``:1279``) y el lado relacional
    (``fields_relational.py:487,1156``).

    **La divergencia de mecanismo, declarada.** La fuente lo puebla en
    ``check_null_constraints`` (``:786-801``): consulta ``pg_attribute`` por
    ``attnotnull`` y lo cruza con lo que el campo *declara*
    (``field.required and field.store``), avisando cuando el esquema y la
    declaración no coinciden. Ese cruce existe porque allá el DDL lo emite el
    propio ORM y puede quedar atrás de la declaración.

    Aquí el DDL lo emiten las migraciones de Django, que derivan la restricción
    de ``null=False`` — declaración y esquema no pueden divergir sin que una
    migración lo registre. Por eso el conjunto se deriva de ``field.null``, y
    el cruce contra ``pg_attribute`` sería medir dos veces la misma fuente.

    Se conserva de la fuente: la **pk siempre entra** (``:795-797``, la rama
    ``field_name == 'id'`` que no consulta el esquema), y sólo se miran los
    modelos con tabla — el ``Model._auto and not Model._abstract`` de allá es
    aquí el modelo concreto de Django.

    :param model: si se da, sólo sus campos; si no, los de todo el registro.
    :returns: ``set`` de instancias de campo.
    """
    candidates = [model] if model is not None else apps.get_models(include_auto_created=True)
    result = set()
    for candidate in candidates:
        meta = getattr(candidate, '_meta', None)
        if meta is None or meta.abstract or meta.proxy or not meta.managed:
            continue
        for field in meta.concrete_fields:
            if field.primary_key or not field.null:
                result.add(field)
    return result


def is_not_null(field):
    """Si la columna de este campo rechaza el nulo — el uso puntual.

    ``not_null_fields()`` recorre el registro entero; un optimizador de dominio
    pregunta por **un** campo y no necesita pagar ese recorrido.

    **Las dos vías tienen que dar la misma respuesta**, y la primera versión de
    este atajo no lo hacía: leía ``field.null`` sin exigir que el campo tuviera
    columna. Un ``ManyToManyField`` declara ``null=False`` —Django avisa de que
    ahí el atributo *no tiene efecto*, porque la nulabilidad vive en la tabla
    intermedia— así que el atajo lo daba por NOT NULL y el conjunto no.

    Medido sobre el registro: **88 de 5345** campos discrepaban (87
    ``ManyToManyField`` y 1 ``GenericForeignKey``). El coste no era teórico:
    ``_optimize_in_required`` recortaba el ``False`` de un dominio sobre un
    M2M, y ``Domain('groups', 'like', '')`` sobre ``ir.rule`` colapsaba a
    ``TRUE`` en vez de quedarse como comparación contra la columna.

    Por eso las dos condiciones que ``not_null_fields`` aplica al recorrer
    —campo **concreto**, modelo con tabla— se aplican aquí una a una. Con
    ellas, las dos vías coinciden en los 5407 campos medidos.
    """
    if not getattr(field, 'concrete', False):
        return False
    meta = getattr(getattr(field, 'model', None), '_meta', None)
    if meta is None or meta.abstract or meta.proxy or not meta.managed:
        return False
    return bool(getattr(field, 'primary_key', False)) or not getattr(field, 'null', True)
