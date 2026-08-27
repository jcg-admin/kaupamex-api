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
from django.apps import apps
from django.db import connections
from django.db.models.signals import class_prepared
from django.dispatch import receiver

__all__ = [
    'apps', 'connections',
    'MODELS_BY_NAME', 'name_of', 'model_by_name',
    'resolve_model_key', 'check_table_matches_name',
]


#: ``'product.removal' -> <class ProductRemoval>``. Ver :func:`_ensure_seeded`
#: sobre por qué se puebla por dos vías y no por una.
MODELS_BY_NAME = {}


def _register(model):
    """Anota el modelo bajo su ``_name``, rechazando el nombre duplicado."""
    name = model.__dict__.get('_name')
    if not name:
        return
    previous = MODELS_BY_NAME.get(name)
    if previous is not None and previous is not model:
        raise ValueError(
            f'Dos modelos declaran _name={name!r}: '
            f'{previous._meta.label} y {model._meta.label}. '
            f'El nombre punteado identifica un modelo, no una familia.'
        )
    MODELS_BY_NAME[name] = model


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
    """
    if models_found is None:
        _ensure_seeded()
        models_found = list(MODELS_BY_NAME.values())
    divergences = []
    for model in models_found:
        name = name_of(model)
        if not name:
            continue
        expected = name.replace('.', '_')
        actual = model._meta.db_table
        if expected != actual:
            divergences.append((model._meta.label, name, expected, actual))
    return divergences

