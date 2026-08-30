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
import logging

from django.apps import apps
from django.db import connections
from django.db.models.signals import class_prepared
from django.dispatch import receiver

from tools.lru import LRU

_logger = logging.getLogger('kaupamex.registry')

__all__ = [
    'apps', 'connections',
    'MODELS_BY_NAME', 'name_of', 'model_by_name', 'model_by_key',
    'resolve_model_key', 'check_table_matches_name',
    'registrants_without_table',
    'clear_cache', 'clear_all_caches', 'cache_of', 'cache_invalidated',
    'many2one_company_dependents', 'loaded_xmlids',
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
