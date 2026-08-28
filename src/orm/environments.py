"""``Environment`` — fiel a ``odoo/orm/environments.py`` (Odoo 19).

En Odoo el ``Environment`` (``self.env``) es el contexto de ejecución que ata
tres cosas a cada recordset: el **cursor** de la transacción (``env.cr``), el
**usuario** actual (``env.uid`` / ``env.user`` / ``env.su`` para sudo) y el
**contexto** (``env.context``, dict de solo lectura). Además indexa los modelos
por nombre (``env['res.partner']``) y cachea registros dentro de la transacción.

Mapeo a Django — **cada pieza del Environment ya existe en Django**, dispersa en
distintos lugares en vez de un único objeto:

=====================  =========================================================
Odoo ``env.*``         Equivalente Django
=====================  =========================================================
``env.cr`` (cursor)    ``django.db.connection`` / ``connections[alias]``;
                       la transacción se maneja con ``transaction.atomic``
``env.uid`` / ``.user``  ``request.user`` (autenticación DRF/Django)
``env.su`` (sudo)      ``user.is_superuser`` / correr sin filtros de permiso
``env.context``        ``request`` + ``get_language()`` (i18n) + kwargs de vista
``env['model.name']``  ``apps.get_model(...)`` / import directo del modelo
cache por transacción  el ORM de Django gestiona su propio caché de queries
=====================  =========================================================

Por eso este archivo es un **stub delgado y documentado, no una
reimplementación**: recrear ``Environment`` sobre Django duplicaría el registro
de apps, el manejo de conexiones y la autenticación que Django ya provee. Un
addon portado que en Odoo escribía ``self.env.user`` se adapta a
``request.user``; ``self.env['res.partner']`` a ``apps.get_model('base',
'ResPartner')`` o al import directo del modelo. Cuando un flujo concreto necesite
azúcar de acceso (p. ej. un helper ``env(request)`` que exponga ``user`` +
``lang`` + ``company``), se añade aquí como conveniencia sobre las piezas
nativas, sin reintroducir el motor.
"""
from contextlib import contextmanager
from contextvars import ContextVar

from django.apps import apps
from django.db import DEFAULT_DB_ALIAS, connection, connections

from exceptions import AccessError

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
    'get_context', 'context_scope',
]
