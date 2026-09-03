"""``Environment`` — fiel a ``odoo/orm/environments.py`` (Odoo 19).

En Odoo el ``Environment`` (``self.env``) es el contexto de ejecución que ata
tres cosas a cada recordset: el **cursor** de la transacción (``env.cr``), el
**usuario** actual (``env.uid`` / ``env.user`` / ``env.su`` para sudo) y el
**contexto** (``env.context``, dict de solo lectura). Además indexa los modelos
por nombre (``env['res.partner']``) y cachea registros dentro de la transacción.

Dónde vive cada pieza — medido, no supuesto
============================================

Este archivo declaraba una tabla titulada «**cada pieza del Environment ya
existe en Django**» y concluía que era «un stub delgado y documentado, no una
reimplementación». Medido fila por fila el 2026-08-30: de las seis, **una**
era cierta. Las otras cinco describían un diseño anterior a DEC-AISL-04 —el
que este mismo archivo superó cuando construyó sus dos canales— o
sencillamente no funcionaban.

=====================  ==========  ==============================================
Odoo ``env.*``         Veredicto   Quién lo resuelve **aquí**
=====================  ==========  ==============================================
``env.cr`` (cursor)    cierto      ``django.db.connection`` / ``connections``;
                                   la transacción del motor, ``atomic``
``env.uid`` / ``.user``  stale     ``get_current_uid`` / ``get_current_user``
                                   de este módulo — NO ``request.user``
``env.su`` (sudo)      stale       ``is_su`` / ``sudo`` de este módulo — el
                                   canal de elevación de DEC-AISL-04, que NO
                                   es ``user.is_superuser``
``env.context``        stale       ``get_context`` / ``context_scope``
``env['model.name']``  **falso**   :class:`Environment`, construida aquí.
                                   ``apps.get_model('res.partner')`` levanta
                                   ``LookupError: No installed app with label
                                   'res'`` — un nombre de la referencia no es
                                   una etiqueta de app de Django
cache por transacción  **falso**   :class:`Transaction`, construida aquí
=====================  ==========  ==============================================

*Métrica:* invocación real de cada símbolo contra el árbol instalado
(``tests/unit/orm/test_environments_transaction.py``).
*Ciega a:* si algún consumidor sigue leyendo ``request.user`` en vez del canal
—eso lo mide el barrido de la tarea #124, no esta tabla.

El azúcar SÍ se puede construir, y se construyó
================================================

La pregunta del ejecutor al leer la tabla fue exacta: *«ellos tienen esta
azúcar sintáctica ``env['model.name']``, ¿nosotros podríamos crearla?»*. La
respuesta medida es que sí, y sin ninguna dependencia de fuera: las ocho
piezas del ``Environment`` ya vivían en este árbol, dispersas. Lo único que
faltaba era el objeto que las ata, que es justo lo que la fuente aporta.

Las tres filas ``stale`` de arriba dejan de serlo por la misma vía: ``env.uid``,
``env.su`` y ``env.context`` son hoy propiedades de :class:`Environment` que
leen el canal. El objeto **no** sustituye a los canales ni los duplica — es
una vista sobre ellos, y ésa es la decisión de diseño que evita el segundo
almacén.

Las tres filas ``stale`` no eran mentira cuando se escribieron: describían el
plan de delegar en Django. Lo que las volvió falsas fue construir los canales
—y nadie volvió a leer la tabla. Es la clase de H-DOCS-148: dos referentes
del mismo repo que dejan de coincidir sin que nada lo delate.

La fila del caché es la que más costó
======================================

El caché de Django es de **consultas** —un ``QuerySet._result_cache``, atado
al queryset y no a la transacción— y el de la referencia es de **campos**: un
mapa ``{campo: {id: valor}}`` que vive lo que dura la transacción, que todos
los recordsets comparten, y sobre el que se apoyan el cómputo diferido
(``tocompute``), el volcado de escrituras (``field_dirty``) y la protección de
campos durante un cómputo (``protected``). No cumplen la misma función:
``Field._get_cache`` no tiene dónde apoyarse en el caché de un queryset.

Por eso :class:`Transaction` se **construye** aquí (``odoo19c:
odoo/orm/environments.py:552``). Las primitivas estaban todas: ``contextvars``
para el alcance, ``defaultdict`` para los mapas, y ``OrderedSet`` /
``StackMap`` de ``tools/misc.py`` para el orden de inserción y el apilado de
alcances.
"""
import functools
import logging
import warnings
import weakref
from collections import defaultdict
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import timezone
from pprint import pformat
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.apps import apps
from django.db import DEFAULT_DB_ALIAS, connection, connections, models
from django.utils import translation
from django.utils.functional import Promise
from django.utils.translation.trans_real import to_language

from exceptions import AccessError, CacheMiss
from orm import registry
from orm.utils import (SUPERUSER_ID, browse, model_of, model_field_registry,
                       model_of_field, record_ids)
from tools.func import reset_cached_properties
from tools.misc import SENTINEL, OrderedSet, StackMap, frozendict
from tools.query import Query
from tools.sql import SQL, execute_sql
from tools.translate import _translate_and_format

_logger = logging.getLogger(__name__)

#: ≙ ``MAX_FIXPOINT_ITERATIONS`` (``odoo19c: odoo/orm/environments.py:37``).
#: El tope de vueltas que el volcado da buscando el punto fijo: cada vuelta
#: puede disparar cómputos que ensucien más campos, y sin tope el ciclo no
#: termina. Su consumidor es el par ``flush``/``_recompute_all`` del
#: ``Environment`` (``:370`` y ``:382``), que se porta en la tarea #324.
MAX_FIXPOINT_ITERATIONS = 10

#: ≙ ``EMPTY_DICT`` (``:635``) — «sentinel value for optional parameters».
#: Un mapa vacío inmutable: se puede compartir como valor por omisión sin
#: que nadie lo mute por accidente.
EMPTY_DICT = frozendict()

# === Los DOS canales del entorno (DEC-AISL-04) =============================
# Réplica de la separación de la referencia, verificada idéntica en las dos
# poblaciones:
#
# - **Canal del DATO** — qué compañías están activadas: ``env.companies`` /
#   ``env.company`` (``odoo19c: odoo/orm/environments.py`` — ctx
#   ``allowed_company_ids`` validado contra lo permitido del usuario, con
#   ``AccessError`` si trae contenido no autorizado; en 18c el símbolo vive
#   en ``odoo/api.py`` — citar por símbolo, no por ruta).
# - **Canal de ELEVACIÓN** — operar por encima de las reglas: ``env.su`` /
#   ``sudo()`` (``odoo19c: orm/models.py:5954``; ``odoo18c: api.py:674-679``).
#   NO cambia al usuario; sólo omite las guardas. Y — verbatim del docstring
#   de la fuente — *"No sanity checks applied in sudo mode!"*: bajo ``su`` la
#   validación de compañías no aplica (habilita flujos inter-company).
#
# Antes de esta separación, la elevación se codificaba como ``company=None``
# (centinela EN el canal del dato): cualquier ruta sin middleware quedaba
# indistinguible del operador. Ahora la ausencia de dato DENIEGA y elevar es
# un acto explícito (``sudo()``).
#
# ``ContextVar`` (no globals) para ser seguro bajo async/threads. Los puebla
# ``CompanyContextMiddleware`` (``addons.base.models.ir_http`` — allá vive el
# enlace request→entorno, como ``ir.http`` en la referencia).

_current_companies: ContextVar = ContextVar('current_companies', default=())
_su: ContextVar = ContextVar('su', default=False)
_uid: ContextVar = ContextVar('uid', default=None)


# --- Canal del actor -------------------------------------------------------
# El TERCER eje del entorno, y el que faltaba. La referencia los declara
# juntos y separados (``odoo19c: odoo/orm/environments.py:54-56``)::
#
#     uid: int
#     context: frozendict
#     su: bool
#
# QUIÉN actúa (``uid``) no es QUÉ datos ve (``companies``) ni SI está elevado
# (``su``): tres razones de cambio distintas en un mismo objeto.
#
# Su ausencia tuvo un costo medido: ``bus`` no tenía de dónde sacar el
# ``self.env.user`` que la referencia usa en ``ir_attachment._bus_channel``, y
# lo compensó ensanchando la firma de **todos** los ``_bus_channel`` con un
# parámetro ``actor``. Un contrato entero cambiado para cubrir la carencia de
# un solo caso — lo contrario de una responsabilidad por clase. Ver H-API-277.

def get_current_uid():
    """PK del usuario que actúa — el ``env.uid`` de la referencia."""
    return _uid.get()


def get_current_user():
    """Registro del usuario que actúa — el ``env.user`` de la referencia.

    La fuente **no guarda el registro**: guarda el identificador y lo
    materializa al pedirlo (``odoo19c: orm/environments.py:213`` —
    ``self(su=True)['res.users'].browse(self.uid)``). Se replica igual para
    que el entorno no retenga objetos vivos entre peticiones que comparten
    hilo bajo WSGI.
    """
    uid = _uid.get()
    if uid is None:
        return None
    return apps.get_model('base', 'ResUsers').objects.filter(pk=uid).first()


def set_current_uid(uid):
    """Fija el usuario que actúa (o lo limpia con ``None``)."""
    _uid.set(uid)


@contextmanager
def user_scope(uid):
    """Actúa como ese usuario en el bloque y **restaura** el valor previo."""
    token = _uid.set(uid)
    try:
        yield
    finally:
        _uid.reset(token)


# --- Canal de elevación ----------------------------------------------------

def is_su():
    """¿El contexto actual está elevado? — el ``env.su`` de la referencia."""
    return _su.get()


def is_system():
    """¿Elevado, o el actor pertenece al grupo de administración?

    ≙ ``Environment.is_system`` (``odoo19c: odoo/orm/environments.py:187-190``),
    verbatim: *"Return whether the current user has group 'Settings', or is in
    superuser mode"* — ``return self.su or self.user._is_system()``.

    Es la guarda de las acciones que tocan la **instalación** del producto, no
    su dato: desinstalar un módulo, reescribir el reflejo del registro. Se
    distingue de ``is_su()``, que es sólo el canal de elevación, y de una
    comprobación de permiso por modelo, que acota el dato y no la plataforma.

    El actor se consulta por conducta y no por tipo (``getattr`` sobre
    ``_is_system``): este módulo lo importa ``base``, así que nombrar aquí a
    ``ResUsers`` cerraría el ciclo. Un actor sin ese método —ninguno hoy en el
    árbol— no es del sistema, que es el desenlace conservador.
    """
    if is_su():
        return True
    user = get_current_user()
    if user is None:
        return False
    checker = getattr(user, '_is_system', None)
    return bool(checker and checker())


@contextmanager
def sudo(flag=True):
    """Eleva el bloque por encima de las reglas — el ``sudo()`` de la fuente.

    No cambia al usuario; omite el filtrado por compañía (y, cuando
    ``ir_rule`` se cablee, sus reglas). Mismo warning que la referencia:
    usarlo puede cruzar los límites de aislamiento entre compañías — por eso
    es un bloque explícito y acotado, nunca un default.
    """
    token = _su.set(bool(flag))
    try:
        yield
    finally:
        _su.reset(token)


# --- Canal del dato --------------------------------------------------------

def get_current_companies():
    """Tupla de PKs de las compañías ACTIVADAS — el ``env.companies``."""
    return _current_companies.get()


def get_current_company():
    """PK de la compañía actual (la primera activada) — el ``env.company``.

    ``None`` = sin compañía en contexto. Ya NO significa elevación: la regla
    multi-company sembrada (``[('company_id','in',company_ids)]``) con cero
    activadas da ``IN []`` → cero filas (fail-closed como dato).
    """
    companies = _current_companies.get()
    return companies[0] if companies else None


def set_current_company(company_id):
    """Activa una sola compañía (o limpia con ``None``)."""
    _current_companies.set(() if company_id is None else (company_id,))


def activate_companies(requested_ids, permitted_ids):
    """Valida y activa el conjunto pedido — el cómputo de ``env.companies``.

    Fiel a la fuente: lo pedido (ctx ``allowed_company_ids``) se valida
    contra lo permitido del usuario y el excedente es ``AccessError``;
    vacío cae al permitido completo (*"fallback on current user
    companies"*). Bajo ``su`` no hay sanity check (verbatim del docstring
    de la referencia).
    """
    requested = tuple(requested_ids or ())
    permitted = tuple(permitted_ids or ())
    if not requested:
        _current_companies.set(permitted)
        return permitted
    if not is_su() and set(requested) - set(permitted):
        raise AccessError('Access to unauthorized or invalid companies.')
    _current_companies.set(requested)
    return requested


@contextmanager
def company_scope(company_id):
    """Activa la compañía en el bloque y **restaura** el valor previo."""
    token = _current_companies.set(
        () if company_id is None else (company_id,))
    try:
        yield
    finally:
        _current_companies.reset(token)


# El manager ``CompanyScopedManager`` que vivía aquí (transitorio) se retiró
# en DEC-AISL-04 §4: el aislamiento por fila es DATO — record rules
# (``addons.base.models.ir_rule``, dominio ``[('company_id','in',
# company_ids)]``) aplicadas por ``RuleScopedManager`` de ese módulo.

# --- Canal del contexto ----------------------------------------------------
# El eje que faltaba de los TRES que la fuente declara juntos
# (``odoo19c: odoo/orm/environments.py:54-56`` — ``uid``, ``context``, ``su``).
# ``uid`` y ``su`` ya vivían aquí; ``context`` no, y su ausencia se notó al
# portar ``Website.get_current_website`` (tarea #535), cuyo segundo escalón de
# resolución es literalmente ``self.env.context.get('website_id')``: un cron o
# una llamada interna declara sobre qué sitio opera sin que haya petición.
#
# Es un dict de **sólo lectura** por diseño, igual que el ``frozendict`` de la
# fuente: se entra con ``context_scope`` y se sale restaurando. Así nadie muta
# el contexto de quien lo llamó.

_context: ContextVar = ContextVar('context', default=None)


def get_context():
    """El contexto en curso — el ``env.context`` de la referencia.

    Devuelve un dict **vacío** fuera de todo ``context_scope``, no ``None``,
    para que el llamador escriba ``get_context().get('clave')`` sin guarda.
    """
    return _context.get() or {}


@contextmanager
def context_scope(**values):
    """Añade claves al contexto en el bloque y **restaura** el previo.

    Las claves se **suman** a las que ya hubiera, como el ``with_context`` de
    la fuente: entrar a un contexto no borra lo que trae el de fuera.
    """
    token = _context.set({**get_context(), **values})
    try:
        yield
    finally:
        _context.reset(token)


def get_current_tz():
    """Zona horaria en curso — el ``env.tz`` de la referencia.

    ≙ ``Environment.tz`` (``odoo19c: odoo/orm/environments.py:285-294``):
    manda la clave ``tz`` del contexto y, si no está, la del usuario que
    actúa; ante una zona inválida se registra en depuración y se devuelve UTC,
    igual que la fuente.

    DIVERGENCIA DE MECANISMO, declarada: la fuente resuelve con ``pytz``;
    aquí con ``zoneinfo``. Es la misma adaptación que
    ``res_users._set_tz_from_request`` declara para ``available_timezones()``.

    Corregido 2026-08-29 — decía *«``pytz``, que no está instalado aquí»*.
    ``pytz`` **sí** está instalado desde el porte de ``tools/safe_eval`` —la fuente lo expone a toda expresión almacenada (``safe_eval.py:498``) y sin él ese porte no cierra—, pero **no** es el mecanismo de husos de este árbol: Django 6 lo abandonó y su propio ``django.utils.timezone`` resuelve por ``zoneinfo``, que lee la misma base de datos IANA.

    La ausencia de usuario no es un error: fuera de una petición no hay quien
    fije zona, y la fuente también cae a UTC.
    """
    tz_name = get_context().get('tz')
    if not tz_name:
        user = get_current_user()
        tz_name = getattr(user, 'tz', None) if user is not None else None
    if tz_name:
        try:
            return ZoneInfo(tz_name)
        except (ZoneInfoNotFoundError, ValueError):
            _logger.debug("Zona horaria inválida %r", tz_name, exc_info=True)
    return timezone.utc


class Transaction:
    """≙ ``Transaction`` (``odoo19c: odoo/orm/environments.py:552``).

    «A object holding ORM data structures for a transaction.»

    Las cinco estructuras que se portan son las que tienen consumidor hoy:

    ================== ==========================================================
    Estructura         Quién la consume
    ================== ==========================================================
    ``field_data``     ``Field._get_cache`` — el mapa ``{campo: {id: valor}}``
    ``field_dirty``    ``Field._update_cache`` — lo escrito en caché y no
                       volcado aún a la base
    ``field_data_patches`` los ids que un x2many suma a un valor que todavía no
                       está en caché
    ``protected``      ``Field.compute_value`` — los campos que un cómputo
                       protege mientras corre, apilados por alcance
    ``tocompute``      ``Field.recompute`` — los cómputos pendientes
    ================== ==========================================================

    De los ocho ``__slots__`` de la fuente queda fuera **uno**, y por razón
    medida, no por conveniencia:

    - ``registry`` — aquí el registro es ``orm.registry``, un módulo, no un
      objeto que la transacción tenga que sostener. Lo que una reconstrucción
      del suyo produce son sus mapas derivados, y eso es lo que
      :meth:`reset` invalida con ``registry.clear_field_depends()``.

    ``envs`` y ``default_env`` **sí se portan** desde la tarea #324, y la
    versión anterior de este docstring los daba por descartados con una razón
    que no se sostiene: decía que «el entorno es este mismo módulo de
    ``contextvars``, no hay N objetos que recorrer». Sí los hay —
    :class:`Environment` es una clase y se instancia— y sin ellos ni
    :meth:`flush` ni :meth:`reset` se pueden portar: los dos recorren los
    entornos vivos. La corrección entra por la Clausula 2 del principio rector.
    Lo único que cambia de mecanismo es el contenedor: una **lista de
    referencias débiles** en vez de un ``WeakSet``, porque
    :meth:`Environment.__hash__` lee el canal ambiental y no es estable.

    ``cache`` **sí se porta**, y la versión anterior de este docstring lo
    describía mal: no es «el nombre viejo de ``field_data``» sino la
    :class:`Cache`, una fachada de 28 métodos cuyo almacén **es**
    ``field_data``. El comentario de la fuente que se citaba —«backward-compatible
    view of the cache»— acompaña a ``field_data``, no a ``cache``. La
    corrección entra por la Clausula 2 del principio rector: estado heredado
    incorrecto se corrige donde se encuentra.

    El ``_Transaction__file_open_tmp_paths`` de la fuente **sí** existe en
    este árbol, y con su nombre: vive en ``tools/misc.py``
    (``file_open_temporary_directory``), donde se portó con la tarea #131.
    """
    __slots__ = ('cache', 'default_env', 'envs', 'field_cache_memo',
                 'field_data', 'field_data_patches', 'field_dirty',
                 'protected', 'tocompute')

    def __init__(self):
        #: ``{campo: datos_gestionados_por_el_campo}``. Suele ser un mapa de
        #: id a valor, pero cada campo lo usa como necesite — el
        #: ``company_dependent``, por ejemplo, guarda un nivel más.
        self.field_data = defaultdict(dict)
        #: ``{campo: OrderedSet[id]}`` — lo cambiado en caché y aún no escrito.
        self.field_dirty = defaultdict(OrderedSet)
        #: ``{campo: {id: [ids]}}`` — ids que sumar al valor de un x2many que
        #: todavía no está en caché.
        self.field_data_patches = defaultdict(lambda: defaultdict(list))
        #: ``{campo: OrderedSet[id]}`` apilado por alcance — los campos que un
        #: cómputo protege mientras corre.
        self.protected = StackMap()
        #: ``{campo: OrderedSet[id]}`` — los cómputos pendientes.
        self.tocompute = defaultdict(OrderedSet)
        #: ≙ ``Transaction.cache`` — la fachada de lectura y escritura sobre
        #: las estructuras de arriba. No guarda nada propio: su ``__slots__``
        #: es sólo la transacción que la sostiene.
        self.cache = Cache(self)
        #: ``{(campo, clave_de_contexto): mapa}`` — el memo de
        #: ``Field._get_cache``, para no rehacer la resolución del cubo en
        #: cada lectura.
        #:
        #: La fuente lo cuelga del ``Environment`` (``_field_cache_memo``,
        #: ``odoo19c: odoo/orm/fields.py:1534``) y aquí cuelga de la
        #: transacción. **No es un cambio de contrato, es su hogar
        #: correcto**: el propio docstring de la fuente ata la vida del memo
        #: a la transacción —*"unless the transaction was entirely
        #: invalidated"*—, y aquí ``Environment`` declara ``__eq__`` y
        #: ``__hash__``, así que se compara por valor y se reconstruye a
        #: voluntad; un memo por instancia fallaría entre dos entornos
        #: iguales y no ahorraría nada.
        self.field_cache_memo = {}
        #: ≙ ``Transaction.envs`` (``odoo19c: odoo/orm/environments.py:557``)
        #: — los entornos vivos de esta transacción. La fuente usa un
        #: ``WeakSet``; aquí es una **lista de referencias débiles**, y la
        #: razón está medida: :meth:`Environment.__hash__` lee el canal
        #: ambiental, así que su hash NO es estable y un ``WeakSet`` perdería
        #: el elemento en cuanto alguien abriera un ``context_scope``. La
        #: búsqueda de la fuente es de todos modos un recorrido lineal con
        #: ``==`` (``:73-75``), que es exactamente lo que la lista entrega —
        #: sin exigir hashabilidad. La poda de las muertas la hace
        #: :func:`_live_envs`.
        self.envs = []
        #: ≙ ``Transaction.default_env`` (``:558``) — «the default
        #: transaction's environment is the first one with a valid uid»
        #: (``:85-87``). Es quien :meth:`flush` usa para volcar.
        self.default_env = None

    def invalidate_field_data(self, spec=None):
        """Vacía el caché de campos, entero o el tramo que ``spec`` nombre.

        ≙ ``Transaction.invalidate_field_data``. ``spec`` es un iterable de
        ``(campo, ids)``; ``ids`` en ``None`` borra el campo entero.
        """
        if spec is None:
            self.field_data.clear()
            #: El memo guarda la instancia del mapa, no su contenido. Vaciar
            #: ``field_data`` hace que la siguiente lectura construya un mapa
            #: NUEVO, así que un memo superviviente serviría el viejo y las
            #: escrituras se perderían en silencio. Es el caso que el
            #: docstring de la fuente nombra: *"unless the transaction was
            #: entirely invalidated"*.
            self.field_cache_memo.clear()
            return
        for field, ids in spec:
            cache = self.field_data.get(field)
            if not cache:
                continue
            if ids is None:
                cache.clear()
                continue
            for record_id in ids:
                cache.pop(record_id, None)

    def flush(self):
        """Vuelca los cómputos y las escrituras pendientes de la transacción.

        ≙ ``Transaction.flush`` (``odoo19c: odoo/orm/environments.py:589-598``).
        Docstring de la fuente, verbatim: *"Flush pending computations and
        updates in the transaction"*.

        El respaldo —volcar como usuario público cuando no hay ``default_env``—
        se porta con su aviso: la fuente lo emite dentro del bucle, antes de
        romperlo en la primera vuelta, así que sólo sale una vez aunque haya N
        entornos. Se conserva ese orden.
        """
        if self.default_env is not None:
            self.default_env.flush_all()
            return
        for environment in _live_envs(self):
            _logger.warning("Missing default_env, flushing as public user")
            public_user = environment.ref('base.public_user')
            Environment(environment._using, public_user.pk, {}).flush_all()
            break

    def reset(self):
        """Reinicia la transacción tras recargar el registro.

        ≙ ``Transaction.reset`` (``:610-618``). Docstring de la fuente,
        verbatim: *"Reset the transaction.  This clears the transaction, and
        reassigns the registry on all its environments.  This operation is
        strongly recommended after reloading the registry"*.

        **La reasignación del registro toma aquí la forma que el registro
        tiene.** Allá es un objeto por base y se reconstruye
        (``self.registry = Registry(self.registry.db_name)``); aquí es un
        módulo, y lo que una reconstrucción produce son sus mapas derivados de
        lo declarado, que es justo lo que ``registry.clear_field_depends()``
        vacía. Por eso el orden importa: primero se invalida lo derivado,
        después se tira lo que cada entorno memorizó sobre ello —``
        _field_depends_context`` es una ``functools.cached_property`` y
        seguiría sirviendo el mapa viejo—, y sólo entonces se limpia la
        transacción.
        """
        registry.clear_field_depends()
        for environment in _live_envs(self):
            reset_cached_properties(environment)
        self.clear()

    def clear(self):
        """≙ ``Transaction.clear`` — vacía cachés y cómputos pendientes."""
        self.invalidate_field_data()
        self.field_cache_memo.clear()
        self.field_data_patches.clear()
        self.field_dirty.clear()
        self.tocompute.clear()


#: La transacción en curso. Un ``ContextVar`` y no un ``threading.local``
#: por la misma razón que los otros canales de este módulo: una vista async
#: y un ``Task`` de asyncio comparten hilo, y el ``local`` los mezclaría.
_transaction = ContextVar('kaupamex_transaction', default=None)


def get_transaction():
    """La transacción en curso, creándola si aún no hay una.

    ≙ ``env.transaction``. La fuente la ata al cursor; aquí al alcance de
    ejecución, que es lo que este módulo ya gobierna para usuario, empresa y
    contexto.
    """
    current = _transaction.get()
    if current is None:
        current = Transaction()
        _transaction.set(current)
    return current


@contextmanager
def transaction_scope():
    """Abre una transacción del ORM y la cierra al salir.

    Al salir **vacía** las estructuras: una entrada de caché que sobreviva a
    su transacción es un valor que ya no describe ninguna fila. Es el
    ``Transaction.clear()`` que la fuente llama al terminar.

    No sustituye a ``django.db.transaction.atomic`` ni compite con él: aquél
    gobierna el ``COMMIT``/``ROLLBACK`` del motor, éste el estado del ORM que
    vive **encima**. Se anidan, y el orden natural es ``atomic`` por fuera.
    """
    previous = _transaction.get()
    current = Transaction()
    token = _transaction.set(current)
    try:
        yield current
    finally:
        current.clear()
        _transaction.reset(token)
        if previous is not None:
            _transaction.set(previous)


def _live_envs(transaction):
    """Los entornos vivos de ``transaction``, podando las referencias muertas.

    ≙ recorrer ``transaction.envs`` en la fuente, donde es un ``WeakSet`` y la
    poda la hace el recolector. Aquí ``envs`` es una lista de referencias
    débiles —ver el comentario de :class:`Transaction`— así que la referencia
    muerta queda en la lista hasta que alguien la recorre; este recorrido es
    ese alguien.
    """
    alive = []
    for reference in list(transaction.envs):
        environment = reference()
        if environment is None:
            transaction.envs.remove(reference)
        else:
            alive.append(environment)
    return alive


class Environment:
    """≙ ``Environment`` (``odoo19c: odoo/orm/environments.py:40-549``).

    El azúcar que la referencia usa en cada línea de cada addon::

        self.env['res.partner']        # el modelo por su nombre
        self.env.user                  # quién actúa
        self.env.company               # sobre qué empresa
        self.env.context.get('lang')   # con qué contexto
        self.env.cr                    # el cursor de la transacción

    **Construido, no delegado.** El docstring de este módulo declaraba que
    ``env['model.name']`` lo cubría ``apps.get_model(...)``, y medido no lo
    cubre: ``apps.get_model('res.partner')`` levanta ``LookupError: No
    installed app with label 'res'`` — un nombre de la referencia tiene un
    punto pero no es ``app_label.ModelName``. Las primitivas para construirlo
    sí estaban todas, y ninguna es de fuera del stack:

    ============================  ==============================================
    Pieza del ``Environment``     Primitiva de este árbol
    ============================  ==============================================
    ``env['nombre']``             ``orm.registry.MODELS_BY_NAME``
    ``env.cr``                    ``django.db.connections[alias]``
    ``env.uid`` / ``env.user``    el canal del dato de este módulo
    ``env.su``                    el canal de elevación de DEC-AISL-04
    ``env.context``               el canal del contexto
    ``env.company`` / ``companies``  el canal de empresa
    ``env.transaction``           :class:`Transaction`, de este módulo
    ``env.lang`` / ``env.tz``     ``django.utils.translation`` + ``get_current_tz``
    ============================  ==============================================

    **Es una vista, no un segundo almacén.** Cada lectura consulta el canal
    ambiental en ese momento; el objeto no copia valores al construirse. Por
    eso conviven sin discrepar con el código que ya lee ``get_current_uid()``
    directamente: son la misma fuente vista de dos formas. Un objeto que
    guardara copias sería un segundo almacén que hay que sincronizar, y
    discreparía del canal en cuanto alguien abriera un ``user_scope``.

    Los **overrides explícitos** (``env(user=…, context=…, su=…)``) sí se
    guardan, y ganan sobre el canal para esa instancia. Al usarla como gestor
    de contexto se **activan** sobre los canales, para que el código que lee
    el canal directamente vea lo mismo::

        with env(su=True) as elevado:
            ...   # aquí ``is_su()`` también devuelve True

    Sin ese activado el objeto sería decorativo: dos vistas del entorno que
    no coinciden es peor que una sola.
    """
    #: **Sin ``__slots__``, y no por descuido.** La clase los declaraba, y el
    #: porte de ``__new__``/``__setattr__`` (tarea #324) los retira: el
    #: mecanismo de la fuente vive en el ``__dict__`` de la instancia —
    #: ``__setattr__`` decide con ``name in vars(self)`` (``:93``),
    #: ``functools.cached_property`` guarda ahí su resultado, y
    #: ``reset_cached_properties`` lo borra de ahí—. Con ``__slots__`` los tres
    #: quedan sin receptor: ``vars()`` de un objeto ranurado levanta
    #: ``TypeError``. El ahorro de memoria que los ranuras daban pesa aún menos
    #: desde que ``__new__`` agrupa: hay un entorno por juego de ejes, no uno
    #: por construcción.

    def __new__(cls, cr=None, uid=None, context=None, su=None):
        """El entorno se **agrupa por transacción**: dos construcciones con los
        mismos ejes devuelven el MISMO objeto.

        ≙ ``Environment.__new__`` (``odoo19c: odoo/orm/environments.py:64-89``).
        La firma es la de la fuente —``Environment(cr, uid, context, su)``— y
        ``cr`` es aquí el **alias** de la conexión, que es lo que este stack usa
        para nombrarla; ``None`` significa la de por defecto.

        Tres divergencias de mecanismo, las tres medidas:

        - **La guarda del primer argumento.** La fuente exige
          ``isinstance(cr, BaseCursor)``; aquí el cursor es la conexión de
          Django y lo que se recibe es su alias, así que la guarda equivalente
          es que el alias esté declarado. ``None`` pasa: es la de por defecto.
        - **La transacción no cuelga del cursor.** Allá
          ``cr.transaction`` la crea si falta (``:70-72``); aquí la transacción
          es un ``ContextVar`` de este módulo y :func:`get_transaction` hace
          exactamente eso mismo — crearla si falta.
        - **La búsqueda compara los OVERRIDES, no los valores resueltos.** La
          fuente compara ``env.uid``/``env.su``/``env.context``, que allá son
          los valores fijados en la construcción. Aquí esos tres son vistas del
          canal ambiental y cambian dentro de la vida del objeto; lo que
          identifica a la instancia es lo que guarda, que son sus overrides.
          Comparar los resueltos agruparía dos entornos que el contexto separa
          un instante después.

        Lo que **no** cambia: la elevación implícita del super-usuario
        (``:66-67``), el registro en ``transaction.envs`` y la elección del
        ``default_env`` como el primero con un uid entero y no vacío.
        """
        assert cr is None or cr in connections, (
            'cr nombra la conexión por su alias; %r no está declarado' % (cr,))
        if uid == SUPERUSER_ID:
            su = True

        transaction = get_transaction()

        for environment in _live_envs(transaction):
            if (environment._using == cr
                    and environment._uid_override == uid
                    and environment._su_override == su
                    and environment._context_override == context):
                return environment

        self = object.__new__(cls)
        self._using = cr
        self._uid_override = uid
        self._context_override = context
        self._su_override = su
        #: La pila de marcos de activación — una lista por cada ``with``
        #: abierto sobre ESTE objeto. Era una lista plana, y con ``__new__``
        #: agrupando dejó de bastar: dos ``with`` anidados sobre el mismo
        #: entorno compartirían el objeto, y un ``__exit__`` que vacía la lista
        #: entera devolvería los canales del marco de fuera al salir del de
        #: dentro. Un marco por entrada mantiene la disciplina LIFO que
        #: ``ContextVar.reset`` exige.
        self._tokens = []
        transaction.envs.append(weakref.ref(self))
        if transaction.default_env is None and uid and isinstance(uid, int):
            transaction.default_env = self
        return self

    def __setattr__(self, name, value):
        """≙ ``Environment.__setattr__`` (``:91-95``) — una vez inicializado,
        los atributos son de sólo lectura; para variar un eje se deriva otro
        entorno con ``env(...)``.

        La ``functools.cached_property`` no pasa por aquí: escribe directamente
        en ``instance.__dict__``. Por eso memorizar un valor derivado no choca
        con la guarda, y ``reset_cached_properties`` puede borrarlo.
        """
        if name in vars(self):
            raise AttributeError(
                f"Attribute {name!r} is read-only, call `env()` instead")
        return super().__setattr__(name, value)

    # --- el índice de modelos, que es el azúcar que motivó la clase --------

    def __getitem__(self, model_name):
        """``env['res.partner']`` → la clase del modelo.

        ≙ ``Environment.__getitem__`` (``:105``). Resuelve por el nombre de la
        referencia; como respaldo acepta la etiqueta ``app.Modelo`` de Django,
        que es la única forma de alcanzar un modelo propio del L0 que no
        declara ``_name``.
        """
        model = registry.MODELS_BY_NAME.get(model_name)
        if model is not None:
            return model
        if '.' in model_name:
            label, _, klass = model_name.partition('.')
            try:
                return apps.get_model(label, klass)
            except LookupError:
                # silent OK because el respaldo por etiqueta es el SEGUNDO
                # intento: que Django no conozca esa etiqueta no es el
                # desenlace, es que este camino no resolvió. El error que sí
                # informa es el ``KeyError`` de abajo, que nombra lo que se
                # pidió — igual que la fuente, que lanza su propio error tras
                # agotar el registro.
                pass
        raise KeyError(model_name)

    def __contains__(self, model_name):
        """≙ ``Environment.__contains__`` (``:101``) — «test whether the given
        model exists»."""
        try:
            self[model_name]
        except KeyError:
            return False
        return True

    def __iter__(self):
        """≙ ``Environment.__iter__`` (``:109``) — los nombres de modelo."""
        return iter(registry.MODELS_BY_NAME)

    def __len__(self):
        """≙ ``Environment.__len__`` (``:113``) — cuántos modelos hay."""
        return len(registry.MODELS_BY_NAME)

    # --- identidad del objeto ---------------------------------------------

    def __eq__(self, other):
        """≙ ``Environment.__eq__`` (``:117``) — dos entornos son el mismo si
        coinciden sus tres ejes y su conexión."""
        if not isinstance(other, Environment):
            return NotImplemented
        return (self.uid, self.su, self.context, self._using) == (
            other.uid, other.su, other.context, other._using)

    def __ne__(self, other):
        result = self.__eq__(other)
        return result if result is NotImplemented else not result

    def __hash__(self):
        """El contexto es un dict: se congela para poder hashear."""
        return hash((self.uid, self.su, self._using,
                     frozenset(self.context.items())))

    def __repr__(self):
        return (f'<Environment uid={self.uid} su={self.su} '
                f'company={self.company_id}>')

    # --- derivar otro entorno ---------------------------------------------

    def __call__(self, cr=None, user=None, context=None, su=None):
        """≙ ``Environment.__call__`` (``:126``) — un entorno derivado.

        «Return an environment based on ``self``» — los ejes que no se nombran
        se heredan. ``user`` admite el registro o su PK, igual que allá.
        """
        uid = self.uid if user is None else getattr(user, 'pk', user)
        return Environment(
            cr=self._using if cr is None else cr,
            uid=uid,
            context=self.context if context is None else context,
            su=self.su if su is None else su,
        )

    def __enter__(self):
        """Activa los overrides sobre los canales — ver el docstring.

        Cada entrada apila **su propio marco**: el mismo objeto puede estar
        dentro de dos ``with`` anidados desde que ``__new__`` agrupa, y sin el
        marco el ``__exit__`` de dentro devolvería también los tokens de fuera.
        """
        frame = []
        if self._uid_override is not None:
            frame.append((_uid, _uid.set(self._uid_override)))
        if self._context_override is not None:
            frame.append((_context, _context.set(
                dict(self._context_override))))
        if self._su_override is not None:
            frame.append((_su, _su.set(bool(self._su_override))))
        self._tokens.append(frame)
        return self

    def __exit__(self, exc_type, exc, tb):
        frame = self._tokens.pop() if self._tokens else []
        for channel, token in reversed(frame):
            channel.reset(token)
        return False

    # --- los tres ejes, leídos del canal salvo override --------------------

    @property
    def cr(self):
        """≙ ``env.cr`` — la conexión, que es el cursor de este stack."""
        return connections[self._using or DEFAULT_DB_ALIAS]

    @property
    def uid(self):
        """≙ ``env.uid`` — la PK de quien actúa."""
        return self._uid_override if self._uid_override is not None \
            else get_current_uid()

    @property
    def su(self):
        """≙ ``env.su`` — si el bloque está elevado."""
        return bool(self._su_override) if self._su_override is not None \
            else is_su()

    @property
    def context(self):
        """≙ ``env.context`` — el contexto, de solo lectura como allá."""
        values = self._context_override
        return dict(values if values is not None else get_context())

    @property
    def user(self):
        """≙ ``env.user`` (``:213``) — el registro de quien actúa."""
        if self._uid_override is None:
            return get_current_user()
        model = registry.MODELS_BY_NAME.get('res.users')
        if model is None:
            return None
        return model.objects.filter(pk=self._uid_override).first()

    # --- empresa, idioma, zona --------------------------------------------

    @property
    def company_id(self):
        """La PK de la empresa activa — el eje que la fuente resuelve en
        ``env.company.id``. Se expone aparte porque aquí el canal guarda la
        PK y materializar el registro cuesta una consulta."""
        return get_current_company()

    @property
    def company(self):
        """≙ ``env.company`` (``:236``) — el registro de la empresa activa."""
        company_id = get_current_company()
        if company_id is None:
            return None
        model = registry.MODELS_BY_NAME.get('res.company')
        if model is None:
            return None
        return model.objects.filter(pk=company_id).first()

    @property
    def companies(self):
        """≙ ``env.companies`` (``:262``) — las empresas activas."""
        ids = get_current_companies()
        model = registry.MODELS_BY_NAME.get('res.company')
        if model is None or not ids:
            return []
        return list(model.objects.filter(pk__in=ids))

    @property
    def lang(self):
        """≙ ``env.lang`` (``:294``) — el idioma del contexto, o ``None``.

        La fuente devuelve ``None`` cuando el contexto no lo declara, y esa
        distinción importa: ``_description_string`` sólo traduce si hay
        idioma. Por eso NO cae al idioma activo de Django, que siempre tiene
        uno.
        """
        value = self.context.get('lang')
        return value or None

    @property
    def tz(self):
        """≙ ``env.tz`` — la zona horaria efectiva."""
        return get_current_tz()

    # --- el registro y la transacción --------------------------------------

    @property
    def registry(self):
        """≙ ``env.registry`` (``:172``) — aquí el registro es un módulo."""
        return registry

    @property
    def transaction(self):
        """≙ ``env.transaction`` — la transacción del ORM en curso."""
        return get_transaction()

    # --- las vistas de la transacción y del registro -----------------------
    #
    # La fuente declara las cinco como ``functools.cached_property``, y aquí
    # sólo la última lo es. **No es una preferencia: es que allá el objeto es
    # inmutable y aquí no.** ``Environment.transaction`` de la fuente se fija
    # en ``__new__`` (``:80``), así que memorizar ``transaction.cache`` es
    # memorizar algo que no puede cambiar. Aquí ``transaction`` es una vista de
    # un ``ContextVar``: memorizar su caché serviría la de la transacción vieja
    # en cuanto entrara otra, y el fallo sería silencioso — se leería y se
    # escribiría en un almacén que ya nadie vuelca.
    #
    # ``_field_depends_context`` **sí** se memoriza, y es la excepción con
    # receptor: lo que devuelve es un objeto del módulo ``orm.registry``, que
    # no cambia de identidad; lo que cambia es su contenido, y quien lo
    # invalida es :meth:`Transaction.reset` llamando a
    # ``reset_cached_properties`` sobre cada entorno — que es exactamente el
    # motivo por el que la fuente escribió ese método.

    @property
    def _protected(self):
        """≙ ``Environment._protected`` (``:198-200``) — «Return the protected
        map of the transaction»."""
        return self.transaction.protected

    @property
    def cache(self):
        """≙ ``Environment.cache`` (``:203-205``) — «Return the cache object of
        the transaction»."""
        return self.transaction.cache

    @property
    def _field_dirty(self):
        """≙ ``Environment._field_dirty`` (``:507-509``) — «Map fields to set of
        dirty ids»."""
        return self.transaction.field_dirty

    @property
    def _field_cache_memo(self):
        """≙ ``Environment._field_cache_memo`` (``:502-504``) — «Memo for
        `Field._get_cache(env)`.  Do not use it».

        Allá el memo nace vacío en el entorno; aquí cuelga de la transacción, y
        la razón está escrita en :class:`Transaction`: el propio docstring de
        la fuente ata su vida a la transacción —*"unless the transaction was
        entirely invalidated"*—, y aquí el entorno se compara por valor, así
        que un memo por instancia fallaría entre dos entornos iguales.
        """
        return self.transaction.field_cache_memo

    @functools.cached_property
    def _field_depends_context(self):
        """≙ ``Environment._field_depends_context`` (``:512-513``) — el mapa
        ``campo -> claves de contexto de las que depende``."""
        return self.registry.field_depends_context

    # --- idioma ------------------------------------------------------------

    @property
    def _lang(self):
        """≙ ``Environment._lang`` (``:305-313``) — «Return the technical
        language code of the current context for **model_terms** translated
        field».

        El prefijo ``'_'`` no es decorativo: marca el pseudo-idioma con que la
        referencia sirve los términos **sin traducir** cuando el cliente está
        editando o revisando traducciones, para que el editor vea el original.

        Plana y no memorizada, por lo mismo que las cuatro de arriba: allá el
        ``context`` es un ``frozendict`` fijado en la construcción; aquí es una
        vista del canal y cambia dentro de la vida del objeto.
        """
        context = self.context
        lang = self.lang or 'en_US'
        if context.get('edit_translations') or context.get('check_translations'):
            lang = '_' + lang
        return lang

    def _(self, source, *args, **kwargs):
        """Traduce ``source`` con el idioma de ESTE entorno.

        ≙ ``Environment._`` (``:315-348``). Docstring de la fuente, verbatim:
        *"Translate the term using current environment's language"*. Uso::

            self.env._("hello world")
            self.env._("hello %s", "test")
            self.env._(LAZY_TRANSLATION)

        :param source: el texto a traducir, o una traducción perezosa.
        :param args: argumentos posicionales de ``%``; excluyentes con kwargs.
        :param kwargs: argumentos nombrados de ``%(nombre)s``.
        :return: el texto traducido.

        **Qué cambia de mecanismo, y qué no.** Lo que no cambia es el contrato:
        el idioma sale del entorno y no del hilo, las dos formas de argumento
        son excluyentes, una fuente que no es texto ni perezosa levanta
        ``TypeError``, y un fallo de traducción no propaga — se registra en
        ``debug`` y se devuelve la fuente.

        Lo que cambia es **quién es la traducción perezosa** y **cómo se elige
        el catálogo**:

        - Allá es una ``LazyGettext`` con su ``_translate(lang)``; aquí
          ``tools.translate._`` devuelve el proxy perezoso de Django
          (``django.utils.functional.Promise``), y resolverlo bajo un idioma es
          convertirlo a texto dentro de ``translation.override``. La clase
          ``LazyGettext`` no se porta porque no tiene consumidor —la razón está
          medida en el docstring de ``tools/translate.py``—; lo que se porta es
          la rama que la atiende, sobre el perezoso que este árbol sí produce.
        - Allá el catálogo se elige **por módulo**, y la fuente lo descubre del
          marco de llamada (``get_translated_module(2)``). El catálogo de
          Django no tiene esa llave: fusiona los ``locale/`` de las apps en uno
          por idioma, así que el nombre del módulo no discrimina nada y
          descubrirlo sería medir un eje que el receptor no tiene. Darle esa
          llave es la tarea **#185**, que es quien construye el catálogo por
          idioma; hasta entonces la selección es por idioma y el módulo no
          participa.

        El código de idioma se traduce al de Django (``es_MX`` → ``es-mx``) con
        el propio ``to_language`` del paquete instalado: son dos escrituras del
        mismo idioma, no dos idiomas.
        """
        lang = self.lang or 'en_US'
        if isinstance(source, str):
            assert not (args and kwargs), "Use args or kwargs, not both"
        elif isinstance(source, Promise):
            assert not args and not kwargs, (
                "All args should come from the lazy text")
            with translation.override(to_language(lang)):
                return str(source)
        else:
            raise TypeError(f"Cannot translate {source!r}")
        try:
            with translation.override(to_language(lang)):
                return _translate_and_format(source, args, kwargs)
        except Exception:  # noqa: BLE001 — la fuente traga igual (``:346``)
            _logger.debug('translation went wrong for "%r", skipped', source,
                          exc_info=True)
        return source

    # --- reinicio de la transacción ----------------------------------------

    def reset(self):
        """≙ ``Environment.reset`` (``:59-62``) — «Reset the transaction, see
        :meth:`Transaction.reset`».

        La fuente la marcó obsoleta en 19.0 y su cuerpo es la delegación más el
        aviso; se porta con los dos, aviso incluido: retirarlo dejaría de avisar
        justo a quien la sigue llamando.
        """
        warnings.warn("Since 19.0, use directly `transaction.reset()`",
                      DeprecationWarning)
        self.transaction.reset()

    # --- cómputos y volcado ------------------------------------------------

    def _recompute_all(self):
        """Procesa todos los cómputos pendientes.

        ≙ ``Environment._recompute_all`` (``:368-378``). Docstring de la
        fuente, verbatim: *"Process all pending computations"*.

        El ``for ... else`` es el de la fuente y no un adorno: el ``else`` de un
        bucle corre cuando NO hubo ``break``, o sea cuando las
        ``MAX_FIXPOINT_ITERATIONS`` vueltas se agotaron sin llegar al punto
        fijo. Ahí el aviso es lo único que separa un cómputo que se realimenta
        de un cuelgue.

        **El modelo del campo se resuelve por ``field.model``**, no por
        ``self[field.model_name]``: aquí quien liga el campo es Django y lo que
        deja es la clase — es la resolución de dos vías que
        :func:`~orm.utils.model_of_field` declara. Y lo que recibe el método es
        ``model.objects.none()``, que es el equivalente del recordset vacío con
        que la fuente lo invoca; ``env[nombre]`` devuelve aquí la **clase**, y
        una clase no trae el método ligado.
        """
        for _ in range(MAX_FIXPOINT_ITERATIONS):
            fields_ = [field for field, ids in self.transaction.tocompute.items()
                       if any(ids)]
            if not fields_:
                break
            for field in fields_:
                model = model_of_field(field, registry)
                if model is None:
                    raise KeyError(getattr(field, 'model_name', '') or repr(field))
                model.objects.none()._recompute_field(field)
        else:
            _logger.warning("Too many iterations for recomputing fields!")

    def flush_all(self):
        """Vuelca a la base todos los cómputos y escrituras pendientes.

        ≙ ``Environment.flush_all`` (``:380-390``). Docstring de la fuente,
        verbatim: *"Flush all pending computations and updates to the
        database"*.

        La fuente agrupa por ``field.model_name``; aquí se agrupa por la
        **clase**, que es lo que ``field.model`` entrega, y el conjunto es un
        ``OrderedSet`` por lo mismo que allá: el orden de volcado tiene que ser
        determinista.

        El filtro ``if ids`` no está en la fuente y aquí hace falta: su
        ``_field_dirty`` es un ``defaultdict`` igual que el nuestro, pero allá
        ``_flush`` **saca** las claves al volcar, mientras que cualquier lectura
        de un campo por índice crea aquí una entrada vacía. Sin el filtro esas
        entradas vacías darían diez vueltas y un aviso que no describe nada.
        """
        for _ in range(MAX_FIXPOINT_ITERATIONS):
            self._recompute_all()
            models_to_flush = OrderedSet()
            for field, ids in list(self._field_dirty.items()):
                if not ids:
                    continue
                model = model_of_field(field, registry)
                if model is None:
                    raise KeyError(getattr(field, 'model_name', '') or repr(field))
                models_to_flush.add(model)
            if not models_to_flush:
                break
            for model in models_to_flush:
                model.objects.none().flush_model()
        else:
            _logger.warning("Too many iterations for flushing fields!")

    def flush_query(self, query):
        """Vuelca los campos que ``query`` declara en su metadata.

        ≙ ``Environment.flush_query`` (``:515-525``). Docstring de la fuente,
        verbatim: *"Flush all the fields in the metadata of ``query``"*.

        Es el volcado **acotado** que precede a una consulta: sin él la
        consulta leería de la base valores que sólo están en la caché. Los
        campos los declara el propio ``SQL`` al componerse
        (``to_flush=self`` en ``orm/fields.py``), así que la lista no se
        adivina: viaja con la consulta.
        """
        fields_to_flush = tuple(query.to_flush)
        if not fields_to_flush:
            return

        names_to_flush = defaultdict(OrderedSet)
        for field in fields_to_flush:
            model = model_of_field(field, registry)
            if model is None:
                raise KeyError(getattr(field, 'model_name', '') or repr(field))
            names_to_flush[model].add(field.name)
        for model, field_names in names_to_flush.items():
            model.objects.none().flush_model(list(field_names))

    # --- las tres guardas de elevación -------------------------------------

    def is_superuser(self):
        """≙ ``Environment.is_superuser`` (``:178``)."""
        return self.su

    def is_admin(self):
        """≙ ``Environment.is_admin`` (``:182``) — elevado, o del grupo de
        administración de ajustes."""
        return self.su or is_system()

    def is_system(self):
        """≙ ``Environment.is_system`` (``:187``)."""
        return self.su or is_system()

    # --- protección de campos durante un cómputo ---------------------------

    def is_protected(self, field, record_id):
        """≙ ``Environment.is_protected`` (``:392``)."""
        try:
            return record_id in self.transaction.protected[field]
        except KeyError:
            return False

    def protected(self, field):
        """≙ ``Environment.protected`` (``:398``) — los ids protegidos."""
        try:
            return self.transaction.protected[field]
        except KeyError:
            return OrderedSet()

    @contextmanager
    def protecting(self, fields, records=None):
        """≙ ``Environment.protecting`` (``:403``).

        Apila un alcance de protección y lo desapila al salir — que es la
        razón por la que ``Transaction.protected`` es un ``StackMap`` y no un
        dict: al salir tiene que reaparecer lo de abajo, no perderse.
        """
        transaction = self.transaction
        ids = OrderedSet() if records is None else OrderedSet(records)
        transaction.protected.pushmap({field: ids for field in fields})
        try:
            yield self
        finally:
            transaction.protected.popmap()

    # --- cómputos pendientes ------------------------------------------------

    def fields_to_compute(self):
        """≙ ``Environment.fields_to_compute`` (``:435``)."""
        return [field for field, ids in self.transaction.tocompute.items() if ids]

    def records_to_compute(self, field):
        """≙ ``Environment.records_to_compute`` (``:439``) — los ids pendientes."""
        return self.transaction.tocompute.get(field) or OrderedSet()

    def is_to_compute(self, field, record_id):
        """≙ ``Environment.is_to_compute`` (``:444``)."""
        return record_id in (self.transaction.tocompute.get(field) or ())

    def not_to_compute(self, field, record_ids):
        """≙ ``Environment.not_to_compute`` (``:448``) — los que NO lo están."""
        pending = self.transaction.tocompute.get(field) or ()
        return [i for i in record_ids if i not in pending]

    def add_to_compute(self, field, record_ids):
        """≙ ``Environment.add_to_compute`` (``:453``)."""
        self.transaction.tocompute[field].update(record_ids)

    def remove_to_compute(self, field, record_ids):
        """≙ ``Environment.remove_to_compute`` (``:460``)."""
        pending = self.transaction.tocompute.get(field)
        if not pending:
            return
        for record_id in record_ids:
            pending.discard(record_id)

    # --- caché ---------------------------------------------------------------

    def cache_key(self, field):
        """≙ ``Environment.cache_key`` (``:471``) — la clave con que un campo
        que depende del contexto separa sus valores.

        La fuente compone la clave con cada entrada de ``_depends_context``.
        Aquí lo mismo, leyendo el canal del contexto y los dos ejes que la
        fuente trata aparte (``company`` y ``uid``).
        """
        keys = []
        for name in (field._depends_context or ()):
            if name == 'company':
                keys.append(self.company_id)
            elif name == 'uid':
                keys.append(self.uid)
            elif name == 'active_test':
                keys.append(self.context.get('active_test', True))
            else:
                keys.append(self.context.get(name))
        return tuple(keys)

    def invalidate_all(self, flush=True):
        """≙ ``Environment.invalidate_all`` (``:357``)."""
        self.transaction.invalidate_field_data()

    def clear(self):
        """≙ ``Environment.clear`` (``:350``)."""
        self.transaction.clear()

    # --- consultas ------------------------------------------------------------

    def execute_query(self, query):
        """≙ ``Environment.execute_query`` (``:527``)."""
        return execute_query(query, using=self._using)

    def execute_query_dict(self, query):
        """≙ ``Environment.execute_query_dict`` (``:537``) — filas como dicts."""
        with self.cr.cursor() as cursor:
            cursor.execute(query.code, query.params)
            if cursor.description is None:
                return []
            columnas = [c[0] for c in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]

    def ref(self, xml_id, raise_if_not_found=True):
        """≙ ``Environment.ref`` (``:158``) — el registro de un XML id.

        Delega en ``ir.model.data``, que es quien guarda el mapa. Devuelve
        ``None`` en vez de levantar cuando ``raise_if_not_found`` es falso,
        igual que allá.
        """
        model = registry.MODELS_BY_NAME.get('ir.model.data')
        if model is None:
            if raise_if_not_found:
                raise ValueError(f'ir.model.data no está en el registro: {xml_id!r}')
            return None
        return model.ref(xml_id, raise_if_not_found=raise_if_not_found,
                          using=self._using or DEFAULT_DB_ALIAS)


class Cache:
    """La fachada de lectura y escritura del caché de registros.

    ≙ ``Cache`` (``odoo19c: odoo/orm/environments.py:638``). Su docstring
    describe el almacén, y ese almacén es aquí ``Transaction.field_data``:

        «For most fields, the cache is simply a mapping from a record and a
        field to a value. In the case of context-dependent fields, the mapping
        also depends on the environment of the given record. For the sake of
        performance, the cache is first partitioned by field, then by record.»

    La otra mitad del contrato son las entradas **sucias** — las que difieren
    de la base y representan escrituras pendientes. Sólo tienen sentido en un
    campo almacenado, y si un campo sucio depende del contexto, **todos** sus
    valores en ese registro cuentan como sucios.

    Tres divergencias de mecanismo, declaradas
    ==========================================

    Ninguna recorta el porte: los 28 símbolos de la fuente están, con su
    nombre, su firma y su comportamiento. Lo que cambia es de dónde sale cada
    pieza del entorno.

    1. **El entorno es ambiente, no un atributo del registro.** La fuente
       escribe ``field._get_cache(model.env)``; aquí el entorno lo sirve
       :func:`env`, que lo lee de los ``ContextVar`` de este módulo. El
       parámetro ``model`` de :meth:`_get_field_cache` y
       :meth:`_set_field_cache` **conserva su firma** —la fuente lo declara y
       algún addon podría pasarlo— pero no decide el entorno.
    2. **No hay recordset.** ``records._ids`` es :func:`~orm.utils.record_ids`,
       ``model.browse(ids)`` es :func:`~orm.utils.browse`, y
       ``records.browse(...)`` —que en la fuente sale gratis porque el
       recordset es su propia clase— necesita además
       :func:`~orm.utils.model_of`.
    3. **El registro es un módulo.** ``self.transaction.registry`` no existe:
       la transacción no sostiene el registro (ver el docstring de
       :class:`Transaction`), así que se consulta ``orm.registry`` directo.

    Los diez métodos deprecados se portan CON su categoría
    ======================================================

    La fuente marca diez métodos como obsoletos y **no lo hace de forma
    uniforme**: cuatro pasan ``DeprecationWarning`` explícito
    (:meth:`insert_missing`, :meth:`patch`, :meth:`patch_and_set`,
    :meth:`get_records_different_from`) y seis llaman a ``warnings.warn`` a
    secas, que por omisión emite ``UserWarning``
    (:meth:`get_until_miss`, :meth:`get_dirty_fields`,
    :meth:`filtered_dirty_records`, :meth:`filtered_clean_records`,
    :meth:`has_dirty_fields`, :meth:`clear_dirty_field`).

    El porte copia la categoría de cada uno tal cual. Homogeneizarlas sería
    más limpio y **cambiaría el contrato**: un filtro de avisos que sólo
    silencia ``DeprecationWarning`` se comporta distinto ante cada mitad, y
    quien escriba ese filtro contra la fuente lo escribiría contra el nuestro.
    """
    __slots__ = ('transaction',)

    def __init__(self, transaction):
        self.transaction = transaction

    def __repr__(self):
        # para depurar: el contenido del caché, con las banderas de sucio
        # marcadas como estrellas
        data = {}
        for field, field_cache in sorted(self.transaction.field_data.items(),
                                         key=lambda item: str(item[0])):
            dirty_ids = self.transaction.field_dirty.get(field, ())
            if field in registry.field_depends_context:
                data[field] = {
                    key: {
                        Starred(id_) if id_ in dirty_ids else id_:
                            val if field.type != 'binary' else '<binary>'
                        for id_, val in key_cache.items()
                    }
                    for key, key_cache in field_cache.items()
                }
            else:
                data[field] = {
                    Starred(id_) if id_ in dirty_ids else id_:
                        val if field.type != 'binary' else '<binary>'
                    for id_, val in field_cache.items()
                }
        return repr(data)

    def _get_field_cache(self, model, field):
        """El mapa del campo, para leerlo — no para modificarlo."""
        return self._set_field_cache(model, field)

    def _set_field_cache(self, model, field):
        """El mapa del campo, para modificarlo.

        ``model`` conserva la firma de la fuente y no elige el entorno: aquí
        es ambiente (divergencia 1 del docstring de la clase).
        """
        return field._get_cache(env())

    def contains(self, record, field):
        """Si ``record`` tiene valor para ``field``."""
        return record_ids(record)[0] in self._get_field_cache(record, field)

    def contains_field(self, field):
        """Si ``field`` tiene valor para al menos un registro."""
        cache = self.transaction.field_data.get(field)
        if not cache:
            return False
        # las llaves de 'cache' son tuplas si 'field' depende del contexto,
        # e ids de registro en cualquier otro caso
        if field in registry.field_depends_context:
            return any(value for value in cache.values())
        return True

    def get(self, record, field, default=SENTINEL):
        """El valor de ``field`` para ``record``."""
        try:
            field_cache = self._get_field_cache(record, field)
            return field_cache[record_ids(record)[0]]
        except KeyError:
            if default is SENTINEL:
                raise CacheMiss(record, field) from None
            return default

    def set(self, record, field, value, dirty=False):
        """Fija el valor de ``field`` para ``record``.

        Un campo limpio se puede ensuciar; al revés, no. Escribir sobre un
        campo sucio sin ``dirty=True`` es un error de programación.

        :param dirty: si ``field`` queda sucio en ``record`` tras la escritura
        """
        field._update_cache(record, value, dirty=dirty)

    def update(self, records, field, values, dirty=False):
        """Fija los valores de ``field`` para varios ``records``.

        Misma regla que :meth:`set` sobre el sucio.

        :param dirty: si ``field`` queda sucio en cada registro
        """
        for record, value in zip(records, values):
            field._update_cache(record, value, dirty=dirty)

    def update_raw(self, records, field, values, dirty=False):
        """Variante de :meth:`update` sin la lógica de campos traducidos.

        El ``records.with_context(prefetch_langs=True)`` de la fuente es aquí
        un alcance de contexto: no hay recordset que envolver.
        """
        if field.translate:
            with context_scope(prefetch_langs=True):
                for record, value in zip(records, values):
                    field._update_cache(record, value, dirty=dirty)
            return
        for record, value in zip(records, values):
            field._update_cache(record, value, dirty=dirty)

    def insert_missing(self, records, field, values):
        """Fija ``field`` sólo en los registros que aún no tienen valor.

        No sobreescribe lo que ya está en caché.
        """
        warnings.warn("Since 19.0, use Field._insert_cache", DeprecationWarning)
        field._insert_cache(records, values)

    def patch(self, records, field, new_id):
        """Aplica un parche a un x2many sobre registros nuevos.

        El parche consiste en sumar ``new_id`` a su valor en caché. Si el
        valor todavía no está en caché, se aplicará cuando lo esté, vía
        :meth:`patch_and_set`.
        """
        warnings.warn("Since 19.0, this method is internal", DeprecationWarning)
        # ``assert isinstance(field, _RelationalMulti)`` de la fuente (``:763``).
        # Allá exige un import perezoso para romper el ciclo; aquí la clase es
        # ``models.ManyToManyField`` y el import va al top, porque
        # ``django.db.models`` no conoce este árbol. ``One2many`` **no** entra
        # en la aserción y es ausencia declarada, no descuido: aquí es una
        # clase plana sin participación en la caché — su desenlace va con el
        # porte de su lado SQL, tareas #243 y #244.
        assert isinstance(field, models.ManyToManyField), (
            "Cache.patch solo opera sobre un x2many; recibio %r" % (field,))
        # La fuente envuelve el id con ``comodel.browse(new_id)`` sólo para
        # entregarle a ``_update_inverse`` algo con ``.id``, y allá eso no
        # consulta nada. Aquí ``browse`` **es una consulta** y un ``NewId`` no
        # tiene fila que traer: el envoltorio volvería vacío y el id se
        # perdería. Por eso viaja crudo — ver ``single_record_id`` en
        # ``orm/fields_relational.py``, que declara la divergencia.
        field._update_inverse(records, new_id)

    def patch_and_set(self, record, field, value):
        """Como :meth:`set`, pero aplica los parches pendientes a ``value`` y
        devuelve el valor que quedó realmente en caché.
        """
        warnings.warn("Since 19.0, this method is internal", DeprecationWarning)
        field._update_cache(record, value)
        return self.get(record, field)

    def remove(self, record, field):
        """Quita el valor de ``field`` para ``record``."""
        assert record_ids(record)[0] not in self.transaction.field_dirty.get(field, ())
        try:
            field_cache = self._set_field_cache(record, field)
            del field_cache[record_ids(record)[0]]
        except KeyError:
            # silent OK because quitar lo que no esta es un no-op, y la fuente
            # lo escribe igual (``:776-782``): ``remove`` es idempotente por
            # contrato. Lo que SI levanta es el ``assert`` de arriba — quitar
            # un valor sucio si es un error de programacion.
            pass

    def get_values(self, records, field):
        """Los valores cacheados de ``field`` para ``records``.

        Los ids sin valor se **saltan**; el generador no se corta.
        """
        field_cache = self._get_field_cache(records, field)
        for record_id in record_ids(records):
            try:
                yield field_cache[record_id]
            except KeyError:
                # silent OK because saltar el hueco ES el contrato del metodo,
                # portado verbatim de ``:750`` — su hermano ``get_until_miss``
                # es el que corta en el primer hueco, y la pareja no tendria
                # sentido si este tambien cortara.
                pass

    def get_until_miss(self, records, field):
        """Los valores cacheados de ``field`` **hasta el primer hueco**."""
        warnings.warn("Since 19.0, this is managed directly by Field")
        field_cache = self._get_field_cache(records, field)
        vals = []
        for record_id in record_ids(records):
            try:
                vals.append(field_cache[record_id])
            except KeyError:
                break
        return vals

    def get_records_different_from(self, records, field, value):
        """El subconjunto de ``records`` que NO tiene ``value`` en ``field``."""
        warnings.warn("Since 19.0, becomes internal function of fields", DeprecationWarning)
        return field._filter_not_equal(records, value)

    def get_fields(self, record):
        """Los campos que tienen valor para ``record``.

        ``record._fields`` de la fuente es aquí
        :func:`~orm.utils.model_field_registry` sobre su clase: el mapa vive
        en el modelo, no en la fila.
        """
        record_id = record_ids(record)[0]
        for name, field in model_field_registry(model_of(record)).items():
            if name != 'id' and record_id in self._get_field_cache(record, field):
                yield field

    def get_records(self, model, field, all_contexts=False):
        """Los registros de ``model`` que tienen valor para ``field``.

        Por omisión mira el contexto en curso; con ``all_contexts`` mira
        **todos** los contextos.
        """
        if all_contexts and field in registry.field_depends_context:
            field_cache = self.transaction.field_data.get(field, EMPTY_DICT)
            ids = OrderedSet(id_ for sub_cache in field_cache.values() for id_ in sub_cache)
        else:
            ids = self._get_field_cache(model, field)
        return browse(model, ids)

    def get_missing_ids(self, records, field):
        """Los ids de ``records`` que no tienen valor para ``field``."""
        return field._cache_missing_ids(records)

    def get_dirty_fields(self):
        """Los campos que tienen registros sucios en caché."""
        warnings.warn("Since 19.0, don't use Cache to manipulate dirty fields")
        return self.transaction.field_dirty.keys()

    def filtered_dirty_records(self, records, field):
        """Los ``records`` en que ``field`` está sucio."""
        warnings.warn("Since 19.0, don't use Cache to manipulate dirty fields")
        dirties = self.transaction.field_dirty.get(field, ())
        return browse(model_of(records),
                      [id_ for id_ in record_ids(records) if id_ in dirties])

    def filtered_clean_records(self, records, field):
        """Los ``records`` en que ``field`` NO está sucio."""
        warnings.warn("Since 19.0, don't use Cache to manipulate dirty fields")
        dirties = self.transaction.field_dirty.get(field, ())
        return browse(model_of(records),
                      [id_ for id_ in record_ids(records) if id_ not in dirties])

    def has_dirty_fields(self, records, fields=None):
        """Si alguno de ``records`` tiene campos sucios.

        :param fields: una colección de campos, o ``None`` para cualquier
            campo de ``records``
        """
        warnings.warn("Since 19.0, don't use Cache to manipulate dirty fields")
        ids = record_ids(records)
        if fields is None:
            model_name = getattr(model_of(records), '_name', '')
            return any(
                not ids_sucios.isdisjoint(ids)
                for field, ids_sucios in self.transaction.field_dirty.items()
                if field.model_name == model_name
            )
        else:
            return any(
                field in self.transaction.field_dirty
                and not self.transaction.field_dirty[field].isdisjoint(ids)
                for field in fields
            )

    def clear_dirty_field(self, field):
        """Limpia ``field`` en todos los registros y devuelve los ids que
        estaban sucios.
        """
        warnings.warn("Since 19.0, don't use Cache to manipulate dirty fields")
        return self.transaction.field_dirty.pop(field, ())

    def invalidate(self, spec=None):
        """Invalida el caché, entero o el tramo que ``spec`` nombre.

        Invalidar un campo dependiente del contexto en un registro invalida
        **todos** sus valores en ese registro — en todos los entornos.

        La operación es insegura por omisión: invalidar un campo sucio tira el
        valor que estaba por escribirse en la base.

            spec = [(campo, ids), (campo, None), ...]

        El ``next(iter(self.transaction.envs))`` de la fuente es aquí
        :func:`env`: no hay conjunto de entornos del que sacar uno cualquiera
        (divergencia 1), y el ambiente **es** el entorno en curso.
        """
        if spec is None:
            self.transaction.invalidate_field_data()
            return
        entorno = env()
        for field, ids in spec:
            field._invalidate_cache(entorno, ids)

    def clear(self):
        """Invalida el caché y sus banderas de sucio."""
        self.transaction.invalidate_field_data()
        self.transaction.field_dirty.clear()
        self.transaction.field_data_patches.clear()

    def check(self, env):
        """Comprueba la consistencia del caché contra la base, para ``env``.

        Cuatro piezas divergen del cuerpo de la fuente, y las cuatro se
        declaran aquí porque ninguna recorta lo que el método comprueba:

        - ``model._table`` es ``model._meta.db_table``;
        - ``model._table_sql`` **no tiene contraparte** — es el ``SQL`` con
          que la fuente nombra una tabla que puede ser una vista. Aquí
          ``Query`` ya usa ``SQL.identifier(alias)`` cuando no se le pasa
          tabla, que es exactamente lo que ese argumento produce para una
          tabla normal;
        - ``model._field_to_sql`` sólo existe en los modelos que adoptan
          ``FieldSqlMixin``. Para el resto se compone la columna directa, que
          es lo que ese método devuelve para un campo con columna — y el
          bucle de fuera ya filtró a exactamente esos;
        - ``env.cr.execute`` + ``fetchall`` son ``env.execute_query``, que
          devuelve las filas.

        Y ``env[field.model_name]`` se resuelve por ``field.model``: aquí
        ``model_name`` es un atributo de clase con ``''`` por omisión, así que
        un campo de Django sin declararlo no se podría resolver por nombre —
        mientras que ``field.model`` lo pone el propio ``contribute_to_class``.
        """
        depends_context = env.registry.field_depends_context
        invalids = []

        def process(model, field, field_cache):
            # ignora registros nuevos y los que están por volcarse
            dirty_ids = self.transaction.field_dirty.get(field, ())
            ids = [id_ for id_ in field_cache if id_ and id_ not in dirty_ids]
            if not ids:
                return

            # selecciona la columna para esos ids
            tabla = model._meta.db_table
            query = Query(env, tabla)
            sql_id = SQL.identifier(tabla, 'id')
            if hasattr(model, '_field_to_sql'):
                sql_field = model._field_to_sql(tabla, field.name, query)
            else:
                sql_field = SQL.identifier(tabla, field.column)
            if field.type == 'binary' and (
                get_context().get('bin_size') or get_context().get('bin_size_' + field.name)
            ):
                sql_field = SQL('pg_size_pretty(length(%s)::bigint)', sql_field)
            query.add_where(SQL("%s IN %s", sql_id, tuple(ids)))

            # compara lo devuelto con lo que hay en caché
            for id_, value in env.execute_query(query.select(sql_id, sql_field)):
                cached = field_cache[id_]
                if value == cached or (not value and not cached):
                    continue
                invalids.append((browse(model, (id_,)), field,
                                 {'cached': cached, 'fetched': value}))

        for field, field_cache in self.transaction.field_data.items():
            # sólo campos con columna
            if not field.store or not field.column_type or field.translate or field.company_dependent:
                continue

            model = field.model
            if field in depends_context:
                for context_keys, inner_cache in field_cache.items():
                    context = dict(zip(depends_context[field], context_keys))
                    if 'company' in context:
                        # la llave 'company' del caché viene en realidad de la
                        # clave de contexto 'allowed_company_ids' (ver
                        # env.company y env.cache_key())
                        context['allowed_company_ids'] = [context.pop('company')]
                    with context_scope(**context):
                        process(model, field, inner_cache)
            else:
                process(model, field, field_cache)

        if invalids:
            _logger.warning("Invalid cache: %s", pformat(invalids))


class Starred:
    """Ayudante para ``repr`` de un valor con una estrella detrás."""
    __slots__ = ['value']

    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f"{self.value!r}*"


def env():
    """El entorno de este alcance — ≙ ``self.env`` de la referencia.

    Se llama en vez de ser un singleton porque el entorno es una **vista** de
    los canales: construirlo es barato y así nunca guarda una lectura vieja.
    """
    return Environment()


def execute_query(query, using=None):
    """≙ ``Environment.execute_query`` (``odoo19c: odoo/orm/environments.py:527``).

    Ejecuta el ``SQL`` recibido y devuelve sus filas como lista de tuplas, o
    la lista vacía cuando la sentencia no devuelve tabla. Es la única pieza
    del ``Environment`` que ``tools/query.py`` necesita: un ``Query`` compone
    su SELECT y alguien tiene que correrlo.

    **La divergencia, y es la que este archivo ya declara arriba:** allá es un
    método del ``Environment``, que ata cursor, usuario y contexto en un solo
    objeto; aquí el cursor es ``connections[alias]`` y el parámetro que lo
    nombra es ``using``, el de Django. El ``flush_query`` de la fuente no tiene
    contraparte porque el ORM de Django no difiere escrituras a un caché
    propio: lo que se escribió ya está en la transacción cuando esta función
    corre.

    **Y el cuerpo ya no vive aquí.** Ejecutar el SQL bajó a
    ``tools.sql.execute_sql`` porque ``tools/query.py`` lo necesita y este
    módulo necesita a ``Query`` para ``Cache.check``: con el cuerpo aquí los
    dos se importaban mutuamente, y la excepción #3 de ``no-lazy-imports``
    exige el arreglo estructural, no el import perezoso. El nombre y el
    contrato de esta función no cambian — sigue siendo la puerta que la
    referencia nombra.
    """
    return execute_sql(query, using=using)


__all__ = [
    'apps', 'connection', 'connections', 'execute_query',
    'get_current_company', 'get_current_companies', 'set_current_company',
    'activate_companies', 'company_scope', 'sudo', 'is_su',
    'get_current_uid', 'get_current_user', 'set_current_uid', 'user_scope',
    'get_context', 'context_scope', 'get_current_tz',
    'Transaction', 'get_transaction', 'transaction_scope',
    'Environment', 'env',
    'Cache', 'Starred', 'EMPTY_DICT', 'MAX_FIXPOINT_ITERATIONS',
]
