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
import logging
from collections import defaultdict
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.apps import apps
from django.db import DEFAULT_DB_ALIAS, connection, connections

from exceptions import AccessError
from orm import registry
from tools.misc import OrderedSet, StackMap

_logger = logging.getLogger(__name__)

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

    De los ocho ``__slots__`` de la fuente quedan fuera tres, y por razón
    medida, no por conveniencia:

    - ``registry`` — aquí el registro es ``orm.registry``, un módulo, no un
      objeto que la transacción tenga que sostener.
    - ``envs`` / ``default_env`` — la fuente guarda un ``WeakSet`` de entornos
      para volcarlos al hacer ``flush``. Aquí el entorno es este mismo módulo
      de ``contextvars``: no hay N objetos que recorrer.
    - ``cache`` — su propio comentario lo llama «backward-compatible view of
      the cache»: es el nombre viejo de ``field_data``, conservado allá para
      no romper addons. Aquí no hay historial que preservar.

    El ``_Transaction__file_open_tmp_paths`` de la fuente **sí** existe en
    este árbol, y con su nombre: vive en ``tools/misc.py``
    (``file_open_temporary_directory``), donde se portó con la tarea #131.
    """
    __slots__ = ('field_cache_memo', 'field_data', 'field_data_patches',
                 'field_dirty', 'protected', 'tocompute')

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
    __slots__ = ('_uid_override', '_context_override', '_su_override',
                 '_using', '_tokens')

    def __init__(self, cr=None, uid=None, context=None, su=None):
        # La firma es la de la fuente —``Environment(cr, uid, context, su)``—
        # y ``cr`` es aquí el **alias** de la conexión, que es lo que este
        # stack usa para nombrarla; ``None`` significa la de por defecto.
        self._using = cr
        self._uid_override = uid
        self._context_override = context
        self._su_override = su
        self._tokens = []

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
        """Activa los overrides sobre los canales — ver el docstring."""
        if self._uid_override is not None:
            self._tokens.append((_uid, _uid.set(self._uid_override)))
        if self._context_override is not None:
            self._tokens.append((_context, _context.set(
                dict(self._context_override))))
        if self._su_override is not None:
            self._tokens.append((_su, _su.set(bool(self._su_override))))
        return self

    def __exit__(self, exc_type, exc, tb):
        for channel, token in reversed(self._tokens):
            channel.reset(token)
        self._tokens.clear()
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
    """
    with connections[using or DEFAULT_DB_ALIAS].cursor() as cursor:
        cursor.execute(query.code, query.params)
        if cursor.description is None:
            return []
        return cursor.fetchall()


__all__ = [
    'apps', 'connection', 'connections', 'execute_query',
    'get_current_company', 'get_current_companies', 'set_current_company',
    'activate_companies', 'company_scope', 'sudo', 'is_su',
    'get_current_uid', 'get_current_user', 'set_current_uid', 'user_scope',
    'get_context', 'context_scope', 'get_current_tz',
    'Transaction', 'get_transaction', 'transaction_scope',
    'Environment', 'env',
]
