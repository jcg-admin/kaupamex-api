"""``tools.misc`` — espejo de ``odoo/tools/misc.py`` (sólo símbolos con consumidor).

Regla de este archivo: cada símbolo llega aquí cuando un addon portado lo
importa (``from tools.misc import X``, espejo de ``from odoo.tools.misc
import X``), y **antes de portarlo se decide** si Django/DRF/stdlib ya lo
resuelven (directiva ejecutor 2026-08-02). La decisión queda en el docstring
del símbolo — no se porta por completitud.

Adaptado de Odoo Community ``odoo/tools/misc.py`` (LGPL-3) — atribución y
aviso de licencia preservados (DEC-KX-03).
"""
import enum
import hmac as hmac_lib
import os
import re
import sys
import tempfile
import typing
import unicodedata
from collections import defaultdict
from collections.abc import (Callable, Iterable, Iterator, Mapping,
                             MutableMapping, MutableSet)
from contextlib import contextmanager
from difflib import HtmlDiff
from functools import reduce
from itertools import islice, repeat, starmap

import datetime

from django.apps import apps
from django.db import connections
from django.utils import formats as django_formats
from django.utils import translation as django_translation
from django.utils.crypto import salted_hmac
from django.utils.html import escape as django_html_escape
from lxml import etree

from modules.module import ADDONS_PATHS
from tools import config

# Formatos de fecha del servidor — verbatim de la referencia
# (``odoo19c: odoo/tools/misc.py:535-542``). Son el formato en que la fuente
# serializa una fecha o un instante hacia el cliente y hacia el fichero de
# datos, y con el que ``fields.Date.to_date``/``to_string`` convierten.
#
# Se portan aunque PostgreSQL guarde ``date``/``timestamp`` nativos: el
# formato no gobierna la columna, gobierna la **cadena** — el valor que llega
# en un CSV de localización o en un XML de datos viene con esta forma, y sin
# la constante cada consumidor la escribiría a mano.
DEFAULT_SERVER_DATE_FORMAT = "%Y-%m-%d"
DEFAULT_SERVER_TIME_FORMAT = "%H:%M:%S"
DEFAULT_SERVER_DATETIME_FORMAT = "%s %s" % (
    DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_TIME_FORMAT)

# ``DATE_LENGTH`` — el recorte que ``to_date`` aplica antes de ``strptime``
# (``odoo19c: odoo/tools/misc.py:544``). Se calcula, no se escribe: la
# referencia lo deriva del propio formato para que los dos no puedan divergir.
DATE_LENGTH = len(datetime.date.today().strftime(DEFAULT_SERVER_DATE_FORMAT))

# ``DATETIME_FORMATS_MAP`` — verbatim de la referencia
# (``odoo19c: odoo/tools/misc.py:544-586``). El ``strftime`` de Python sólo
# admite las directivas que la ``libc`` de la plataforma provee; el mapa las
# reduce a las del C89, disponibles en toda implementación. Lo consume
# ``res.lang`` para rechazar el formato que no sobreviviría al viaje de ida y
# vuelta (``_disallowed_datetime_patterns``).
DATETIME_FORMATS_MAP = {
    '%C': '',                      # siglo
    '%D': '%m/%d/%Y',              # modificado %y->%Y
    '%e': '%d',
    '%E': '',                      # modificador especial
    '%F': '%Y-%m-%d',
    '%g': '%Y',                    # modificado %y->%Y
    '%G': '%Y',
    '%h': '%b',
    '%k': '%H',
    '%l': '%I',
    '%n': '\n',
    '%O': '',                      # modificador especial
    '%P': '%p',
    '%R': '%H:%M',
    '%r': '%I:%M:%S %p',
    '%s': '',                      # segundos desde la época
    '%T': '%H:%M:%S',
    '%t': ' ',                     # tabulador
    '%u': ' %w',
    '%V': '%W',
    '%y': '%Y',                    # %y funciona pero es ambiguo; se usa %Y
    '%+': '%Y-%m-%d %H:%M:%S',

    # ``%Z`` causa al menos dos problemas, y por eso se retira entero:
    #  - los nombres de huso que se usan no siempre los reconoce ``strptime``,
    #    así que la conversión no es reversible en ambos sentidos;
    #  - ``strftime`` lo sustituye por cadena vacía cuando el ``datetime`` no
    #    trae ``tzinfo``, y la cadena resultante ya no parsea contra el mismo
    #    formato.
    '%z': '',
    '%Z': '',
}

# Variables de tipo de la referencia (``odoo19c: odoo/tools/misc.py:70-72``),
# que las declara para los genéricos de esta misma familia de colecciones.
K = typing.TypeVar('K')
T = typing.TypeVar('T')

# ``Sentinel``/``SENTINEL`` — el centinela de "parámetro no dado", verbatim de
# la referencia (``odoo19c: odoo/tools/misc.py:131-136``). Se porta porque
# ``tools.lru.LRU`` lo consume para distinguir "no hay default" de ``None``,
# igual que allá: ``None`` es un valor legítimo de caché y no puede servir de
# marca de ausencia.


class Sentinel(enum.Enum):
    """Clase para tipar parámetros cuyo default es un centinela."""
    SENTINEL = -1


SENTINEL = Sentinel.SENTINEL


# ``consteq`` — comparación en tiempo constante.
#
# La referencia lo define como alias del stdlib (``misc.py:1668``:
# ``consteq = hmac_lib.compare_digest``). No hay nada que portar: se replica
# el mismo alias. Django ofrece ``django.utils.crypto.constant_time_compare``,
# que es un wrapper de esta misma función — se usa el stdlib directo, igual
# que la referencia.
consteq = hmac_lib.compare_digest


class ReadonlyDict(Mapping[K, T], typing.Generic[K, T]):
    """Mapa inmodificable, ni siquiera con ``dict.update`` — ≙ ``misc.py:1671-1706``.

    Se parece a un ``frozendict``, con una desventaja y una ventaja:

    - ``dict.update`` funciona sobre un ``frozendict`` y **no** sobre un
      ``ReadonlyDict``;
    - ``json.dumps`` conoce un ``frozendict`` de serie y **no** conoce un
      ``ReadonlyDict``.

    Las dos salen del mismo hecho: ``frozendict`` hereda de ``dict`` y
    ``ReadonlyDict`` hereda de ``collections.abc.Mapping``. Según lo que haga
    falta —impedir de verdad que el mapa se modifique, por seguridad, o que
    ``json.dumps`` lo acepte— se elige uno u otro.

    Aquí se porta el estricto, y su precio se paga en
    :func:`tools.json.json_default`, que le da su propia rama.

    ``types.MappingProxyType`` del stdlib **no** lo sustituye: es una vista
    sobre el diccionario original, así que mutar el original cambia lo que la
    vista muestra. Aquí ``__init__`` copia (``dict(data)``), que es lo que
    hace inmodificable al resultado y no sólo a su interfaz.

    Ejemplo::

        data = ReadonlyDict({'foo': 'bar'})
        data['baz'] = 'xyz'                 # lanza excepción
        data.update({'baz': 'xyz'})         # lanza excepción
        dict.update(data, {'baz': 'xyz'})   # lanza excepción
    """
    __slots__ = ('_data__',)

    def __init__(self, data):
        self._data__ = dict(data)

    def __contains__(self, key: K):
        return key in self._data__

    def __getitem__(self, key: K) -> T:
        return self._data__[key]

    def __len__(self):
        return len(self._data__)

    def __iter__(self):
        return iter(self._data__)


def str2bool(s, default=None):
    """Interpreta un string como booleano. ≙ ``odoo/tools/misc.py:493-517``.

    Decisión de equivalencia (medida 2026-08-02): no hay sustituto instalado
    con contrato público —

    - ``distutils.util.strtobool`` se eliminó del stdlib en Python 3.12.
    - DRF trae **exactamente el mismo vocabulario** en
      ``rest_framework.fields.BooleanField.TRUE_VALUES/FALSE_VALUES``
      (verificado: ``{'y','yes','1','true','t','on'}`` /
      ``{'n','no','0','false','f','off'}``), pero es un detalle interno de un
      serializer-field, no una utilidad importable para leer parámetros.

    Se porta fiel (sin el ``DeprecationWarning`` de tipos no-str: aquí un
    no-str sin default es directamente ``ValueError``). El consumidor
    principal es la lectura de ``SystemParameter`` (≙ ``get_param``).
    """
    if type(s) is bool:
        return s
    if isinstance(s, str):
        s = s.lower()
        if s in ('y', 'yes', '1', 'true', 't', 'on'):
            return True
        if s in ('n', 'no', '0', 'false', 'f', 'off'):
            return False
    if default is None:
        raise ValueError('Use 0/1/yes/no/true/false/on/off')
    return bool(default)


def hmac(scope, message, hash_function=None):
    """HMAC con secreto del despliegue. ≙ ``odoo/tools/misc.py:1781-1793``.

    La referencia firma con el config-param ``database.secret``; el mecanismo
    nativo Django para "HMAC con el secreto del despliegue + salt por uso" es
    ``django.utils.crypto.salted_hmac`` (``SECRET_KEY`` como clave,
    ``key_salt`` = el ``scope`` de la referencia). Se adapta sobre él en vez
    de duplicar la derivación de clave.

    Divergencia declarada: la firma de la referencia recibe ``env`` (para
    leer el parámetro con sudo); aquí el secreto es ``settings.SECRET_KEY``
    vía ``salted_hmac``, así que ``env`` desaparece del contrato.

    :param scope: ámbito de la firma (mismo mensaje, distinto uso → distinta
        firma). Obligatorio y no vacío, igual que la referencia.
    :param message: mensaje a autenticar (``str`` o ``bytes``).
    :return: digest hexadecimal (``str``).
    """
    if not scope:
        raise ValueError('Non-empty scope required')
    kwargs = {'algorithm': hash_function} if hash_function else {}
    return salted_hmac(scope, message, **kwargs).hexdigest()


# ``SKIPPED_ELEMENT_TYPES`` — nodos lxml que no son elementos "reales".
#
# Portado verbatim de la referencia (``odoo19c: odoo/tools/misc.py:117``):
# comentarios, processing-instructions y entidades, que el motor de herencia
# de vistas (``tools/template_inheritance.py``) debe saltar al recorrer los
# specs. No hay equivalente Django/stdlib: es vocabulario de lxml.
SKIPPED_ELEMENT_TYPES = (
    etree._Comment, etree._ProcessingInstruction,
    etree.CommentBase, etree.PIBase, etree._Entity,
)

def _addons_paths():
    """Las raíces bajo las que :func:`file_path` admite abrir.

    ≙ el ``[*odoo.addons.__path__, config.root_path]`` de la fuente
    (``odoo19c: odoo/tools/misc.py:224``). Las dos raíces de addons las declara
    ``modules.module.ADDONS_PATHS``, que es donde este árbol las fija una sola
    vez; leerlas de ahí en vez de recomponerlas evita la segunda fuente de
    verdad que ``calibration-verified-numbers.md`` prohíbe. La tercera es
    ``config.root_path()`` — allá el paquete ``odoo/``, aquí ``src/``, la misma
    relación que ``tools.config.root_path`` ya declara.

    El import es de módulo hermano y NO cierra ciclo: ``modules/module.py``
    importa ``ast``, ``importlib``, ``os``, ``typing``, ``pathlib`` y
    ``release``; ``tools/config.py`` importa ``pathlib`` y las settings de
    Django — ninguno importa ``tools.misc`` (medido).
    """
    return [str(path) for path in ADDONS_PATHS] + [config.root_path()]


def _file_open_tmp_paths(env):
    """Las raíces temporales registradas en la transacción de ``env``.

    ≙ ``env.transaction._Transaction__file_open_tmp_paths``
    (``odoo19c: odoo/tools/misc.py:225`` y ``:311``).

    DIVERGENCIA DE MECANISMO, no de contrato: la fuente cuelga la lista de su
    objeto ``Transaction``, que este ORM no tiene —``orm/environments.py`` es
    un ``ContextVar`` sin clase ``Environment`` ni ``Transaction``—. Su
    equivalente fiel es el objeto ``connections[alias]`` de Django: es quien
    **posee la transacción** (``atomic`` opera sobre él), y es ``local`` al
    hilo, así que la raíz temporal no se filtra a otra transacción en curso.
    Por eso el parámetro conserva el nombre ``env`` de la fuente y lleva el
    alias de conexión.

    La lista se crea al primer uso: una conexión que nunca instaló un módulo
    desde un zip no tiene por qué llevar el atributo.
    """
    connection = connections[env]
    try:
        return connection._file_open_tmp_paths
    except AttributeError:
        paths = []
        connection._file_open_tmp_paths = paths
        return paths


def file_path(file_path, filter_ext=('',), env=None, *, check_exists=True):
    """≙ ``file_path`` (``odoo19c: odoo/tools/misc.py:196-250``).

    «Verify that a file exists under a known ``addons_path`` directory and
    return its full path.»

    Es una **guarda de confinamiento**, no una comodidad: el cargador de datos
    abre rutas que vienen del manifiesto de un addon, y sin ella un
    ``'../../etc/passwd'`` saldría del árbol. La comprobación es la de la
    fuente: se normaliza la ruta, se compone contra cada raíz, y **sólo se
    acepta si el resultado sigue empezando por esa raíz** — que es lo que
    ``..`` no puede burlar después de ``normpath``.

    Dos conjuntos de raíces, como en la fuente, y el primero **excluye** al
    segundo:

    - Si la ruta es relativa y su primera componente nombra un addon **ya
      importado**, las raíces son las de ese addon y ninguna más. Dos árboles
      con un addon homónimo no se pisan: gana el que el proceso cargó, y una
      raíz temporal no puede suplantarlo.
    - Si no, son las raíces fijas más las temporales que
      :func:`file_open_temporary_directory` haya registrado en ``env``.

    :param file_path: ruta absoluta, o relativa a cualquier raíz de addons.
    :param filter_ext: extensiones admitidas (minúscula, con punto).
    :param env: alias de conexión cuya transacción puede tener raíces
        temporales; sin él, no se consultan (ver :func:`_file_open_tmp_paths`).
    :param check_exists: comprobar que el archivo existe (por defecto sí).
    :raise FileNotFoundError: si no está bajo ninguna raíz conocida.
    :raise ValueError: si su extensión no está en ``filter_ext``.
    """
    is_abs = os.path.isabs(file_path)
    normalized_path = os.path.normpath(os.path.normcase(file_path))

    if filter_ext and not normalized_path.lower().endswith(filter_ext):
        raise ValueError('Unsupported file: ' + file_path)

    # ignore leading 'addons/' if present, it's the final component of
    # root_path, but may sometimes be included in relative paths
    normalized_path = normalized_path.removeprefix('addons' + os.sep)
    file_path_split = normalized_path.split(os.path.sep)

    if not is_abs and (module := sys.modules.get(f'addons.{file_path_split[0]}')):
        addons_paths = list(map(os.path.dirname, module.__path__))
    else:
        temporary_paths = _file_open_tmp_paths(env) if env else []
        addons_paths = [*_addons_paths(), *temporary_paths]

    for addons_dir in addons_paths:
        # final path sep required to avoid partial match
        parent_path = os.path.normpath(os.path.normcase(addons_dir)) + os.sep
        if is_abs:
            candidate = normalized_path
        else:
            candidate = os.path.normpath(
                os.path.join(parent_path, normalized_path))
        if candidate.startswith(parent_path) and (
            # we check existence when asked or we have multiple paths to check
            # (there is one possibility for absolute paths)
            (not check_exists and (is_abs or len(addons_paths) == 1))
            or os.path.exists(candidate)
        ):
            return candidate

    raise FileNotFoundError('File not found: ' + file_path)


def file_open(name, mode='r', filter_ext=(), env=None):
    """≙ ``file_open`` (``odoo19c: odoo/tools/misc.py:253-286``).

    «Open a file from within the ``addons_path`` directories, as an absolute or
    relative path.»

    Abre **sólo** lo que :func:`file_path` acepta, así que hereda su
    confinamiento —``env`` incluido: sin él, una raíz temporal registrada no se
    consulta—. Las dos precauciones de la fuente se portan enteras:

    - En modo texto fuerza ``utf-8``, con su motivo verbatim: *"system locale
      could affect default encoding, even with the latest Python 3 versions"*.
    - En modo de escritura **rechaza crear archivos nuevos** (*"Don't let
      create new files"*): un cargador que puede escribir donde ya hay algo es
      una cosa; uno que puede sembrar archivos nuevos bajo el árbol de addons
      es otra.
    """
    path = file_path(name, filter_ext=filter_ext, env=env, check_exists=False)
    encoding = None
    if 'b' not in mode:
        # Force encoding for text mode, as system locale could affect default
        # encoding, even with the latest Python 3 versions.
        encoding = 'utf-8'
    if any(m in mode for m in ('w', 'x', 'a')) and not os.path.isfile(path):
        # Don't let create new files
        raise FileNotFoundError(f'Not a file: {path}')
    return open(path, mode, encoding=encoding)


@contextmanager
def file_open_temporary_directory(env):
    """≙ ``file_open_temporary_directory`` (``odoo19c: odoo/tools/misc.py:305-313``).

    «Create and return a temporary directory added to the directories
    ``file_open`` is allowed to read from.»

    Sirve a la instalación de un módulo desde un zip subido: lo que se acaba de
    extraer tiene que ser legible por ``file_open`` **sin** abrir el árbol
    entero ni por más tiempo del que dure la operación. De ahí la forma exacta
    de la fuente, que se porta verbatim:

    - el directorio lo crea y lo borra ``tempfile.TemporaryDirectory``;
    - el registro se retira en un ``finally``, así que una excepción en el
      cuerpo no deja la raíz abierta para el resto del proceso — el fallo
      silencioso que este ``finally`` existe para impedir.

    :param env: alias de conexión cuya transacción registra la raíz.
    :return: la ruta del directorio temporal.
    """
    with tempfile.TemporaryDirectory() as module_dir:
        paths = _file_open_tmp_paths(env)
        try:
            paths.append(module_dir)
            yield module_dir
        finally:
            paths.remove(module_dir)


# ``html_escape`` — escape HTML para mensajes construidos a mano.
#
# La referencia lo define como alias de ``markupsafe.escape``
# (``odoo19c: odoo/tools/misc.py:1305``). Aquí lo resuelve Django
# (``django.utils.html.escape``): mismo contrato para el único consumidor
# actual (mensajes de error del motor de herencia), sin añadir ``markupsafe``
# como dependencia — el criterio de este archivo: stdlib/Django antes que una
# dependencia nueva, con la decisión anotada.
html_escape = django_html_escape


def partition(pred: Callable[[T], bool], elems: Iterable[T]) -> tuple[list[T], list[T]]:
    """≙ ``partition`` (``odoo19c: odoo/tools/misc.py:373``).

    Docstring de la fuente, verbatim: *"Return a pair equivalent to:
    ``filter(pred, elems), filter(lambda x: not pred(x), elems)``"*.

    Se porta —en vez de escribir las dos comprensiones donde haga falta—
    porque recorre el iterable **una sola vez**: el predicado se evalúa una vez
    por elemento, no dos. Su primer consumidor aquí son las fusiones n-arias de
    ``orm/domains.py``, que reparten las condiciones de un bloque entre las que
    llevan un subdominio y las que no.
    """
    yes: list[T] = []
    nos: list[T] = []
    for elem in elems:
        (yes if pred(elem) else nos).append(elem)
    return yes, nos


def split_every(n, iterable, piece_maker=tuple):
    """≙ ``split_every`` (``odoo19c: odoo/tools/misc.py:684-697``).

    «Splits an iterable into length-n pieces. The last piece will be shorter if
    ``n`` does not evenly divide the iterable length.»

    Se porta en vez de resolverse con Django o stdlib porque **ninguno de los
    dos lo trae**: ``itertools.batched`` existe desde Python 3.12 y sería el
    candidato, pero fija ``piece_maker=tuple`` y la referencia lo declara
    parametrizable —``odoo19c: addons/stock/models/stock_rule.py:710`` lo llama
    con el default, pero el árbol lo usa con ``list`` y con ``set`` en otros
    sitios—. Portar la firma entera cuesta ocho líneas y evita que el primer
    consumidor con otro ``piece_maker`` tenga que reintroducirlo.

    Las tres sobrecargas de ``typing.overload`` de la fuente (``:669-681``) no
    se portan: son anotación para el verificador de tipos, no conducta.

    :param n: tamaño máximo de cada trozo.
    :param iterable: iterable a trocear.
    :param piece_maker: invocable que recoge cada trozo de su rebanada; **debe
        consumir la rebanada entera**.
    """
    iterator = iter(iterable)
    piece = piece_maker(islice(iterator, n))
    while piece:
        yield piece
        piece = piece_maker(islice(iterator, n))


def is_list_of(values, type_):
    """≙ ``is_list_of`` (``odoo19c: odoo/tools/misc.py:1924-1930``).

    «Return True if the given values is a list / tuple of the given type.»

    Se porta en vez de escribirse en línea porque es el guardián de forma de
    ``Properties._list_to_dict``: distingue *"una lista de definiciones"* de
    cualquier otra cosa que llegue del cargador, y ese predicado se cita en el
    mensaje de error.
    """
    return isinstance(values, (list, tuple)) and all(
        isinstance(item, type_) for item in values)


def has_list_types(values, types):
    """≙ ``has_list_types`` (``odoo19c: odoo/tools/misc.py:1933-1943``).

    «Return True if the given values have the same types as the one given in
    argument, in the same order.»

    Es lo que deja a ``_remove_display_name`` distinguir un ``many2one`` ya
    reducido (``35``) de la pareja que manda el cliente (``(35, 'Bob')``) sin
    adivinar por longitud.
    """
    return (
        isinstance(values, (list, tuple)) and len(values) == len(types)
        and all(starmap(isinstance, zip(values, types)))
    )


def freehash(arg: typing.Any) -> int:
    """≙ ``freehash`` (``odoo19c: odoo/tools/misc.py:940-949``).

    Hash de cualquier objeto, incluidos los que no lo admiten. El nombre lo
    dice: *hash libre* de la exigencia de que el argumento sea hashable.

    La cascada de la fuente, verbatim: primero ``hash`` normal; si lanza, un
    ``Mapping`` se congela en un :class:`frozendict` y se hashea; un
    ``Iterable`` se hashea por el ``frozenset`` de los hashes libres de sus
    elementos; y lo que no es ninguna de las dos cae en ``id(arg)``.

    Esa última rama es la que hace que la función **nunca** lance, y también
    la que la vuelve inconsistente entre procesos: dos objetos iguales pero
    distintos dan hashes distintos. Es intencional — su único consumidor es
    :meth:`frozendict.__hash__`, que necesita un entero por valor para poder
    ser clave, no una identidad estable en disco.

    ``functools.reduce`` y ``hash`` del stdlib no lo resuelven: el stdlib
    lanza ``TypeError`` ante una lista o un dict, que es precisamente el caso
    que esta función existe para cubrir.

    :param arg: cualquier objeto, hashable o no.
    :returns: un entero; ``id(arg)`` cuando no hay otra forma de derivarlo.
    """
    try:
        return hash(arg)
    except Exception:
        if isinstance(arg, Mapping):
            return hash(frozendict(arg))
        elif isinstance(arg, Iterable):
            return hash(frozenset(freehash(item) for item in arg))
        else:
            return id(arg)


def clean_context(context: dict) -> dict:
    """≙ ``clean_context`` (``odoo19c: odoo/tools/misc.py:952-956``).

    «This function take a dictionary and remove each entry with its key
    starting with ``default_``.»

    Se porta en vez de resolverse con stdlib porque lo que se elimina no es un
    detalle de forma: las claves ``default_*`` son las que su ORM consume para
    prefijar valores al **crear** un registro. Propagarlas a una operación que
    crea otra cosa —el caso de ``StockScrap.do_replenish``, que dispara un
    abastecimiento— sembraría el registro nuevo con los defaults del formulario
    que lo originó. La referencia limpia el contexto ahí por esa razón exacta
    (``odoo19c: addons/stock/models/stock_scrap.py:171``).

    :param context: diccionario de contexto a limpiar.
    :returns: copia sin las claves ``default_*``.
    """
    return {k: v for k, v in context.items() if not k.startswith('default_')}


class frozendict(dict[K, T], typing.Generic[K, T]):
    """Diccionario inmutable y **hashable** — ≙ ``frozendict`` (``misc.py:959-985``).

    Hereda de ``dict`` y anula los siete mutadores con
    ``NotImplementedError``. Su contraparte estricta es
    :class:`ReadonlyDict`, y la frontera entre las dos ya está declarada en el
    docstring de aquélla: ``frozendict`` cede ante ``dict.update(d, ...)``
    —que salta el método de instancia y llega al de ``dict``— y a cambio
    ``json.dumps`` lo serializa de serie, porque para el codificador es un
    ``dict``.

    Lo que ``ReadonlyDict`` **no** tiene y aquí es el motivo del porte:
    ``__hash__``. Un ``frozendict`` sirve de clave, y ése es su consumidor —
    ``Transaction.field_cache_memo`` en ``orm.environments`` indexa por el
    contexto del campo, que es un mapa.

    ``types.MappingProxyType`` tampoco lo sustituye, por la misma razón que
    en :class:`ReadonlyDict`: es una vista sobre el original, no una copia, y
    además no es hashable.

    :param K: tipo de la clave.
    :param T: tipo del valor.
    """
    __slots__ = ()

    def __delitem__(self, key):
        raise NotImplementedError("'__delitem__' not supported on frozendict")

    def __setitem__(self, key, val):
        raise NotImplementedError("'__setitem__' not supported on frozendict")

    def clear(self):
        raise NotImplementedError("'clear' not supported on frozendict")

    def pop(self, key, default=None):
        raise NotImplementedError("'pop' not supported on frozendict")

    def popitem(self):
        raise NotImplementedError("'popitem' not supported on frozendict")

    def setdefault(self, key, default=None):
        raise NotImplementedError("'setdefault' not supported on frozendict")

    def update(self, *args, **kwargs):
        raise NotImplementedError("'update' not supported on frozendict")

    def __hash__(self) -> int:  # type: ignore[override]
        return hash(frozenset((key, freehash(val)) for key, val in self.items()))


class Collector(dict):
    """Un mapa de clave a tupla — ≙ ``Collector`` (``odoo19c: odoo/tools/misc.py:988``).

    Docstring de la fuente, verbatim: *"A mapping from keys to tuples. This
    implements a relation, and can be seen as a space optimization for
    ``defaultdict(tuple)``"*.

    Las dos mitades del contrato, y ninguna es opcional:

    - **leer lo ausente devuelve** ``()``, **sin crear la entrada**. Por eso NO
      es un ``defaultdict``: con aquél, preguntar por un campo sin inversa lo
      añadiría al mapa, y el mapa se llenaría de entradas vacías al recorrerlo;
    - **asignar vacío borra la clave**, que es lo que mantiene la invariante
      anterior después de un ``discard``.

    La anotación de la fuente es ``Collector[K, T]``; aquí la clase hereda de
    ``dict`` a secas y los tipos viajan en el docstring, igual que en
    :class:`~orm.registry.TriggerTree` y por la misma razón.
    """

    __slots__ = ()

    def __getitem__(self, key):
        return self.get(key, ())

    def __setitem__(self, key, val):
        val = tuple(val)
        if val:
            super().__setitem__(key, val)
        else:
            super().pop(key, None)

    def add(self, key, val):
        """Suma ``val`` a la tupla de ``key``, sin repetirlo."""
        vals = self[key]
        if val not in vals:
            self[key] = vals + (val,)

    def discard_keys_and_values(self, excludes):
        """Retira lo excluido de los dos lados de la relación."""
        for key in excludes:
            self.pop(key, None)
        for key, vals in list(self.items()):
            self[key] = tuple(val for val in vals if val not in excludes)


class StackMap(MutableMapping[K, T], typing.Generic[K, T]):
    """≙ ``StackMap`` (``odoo19c: odoo/tools/misc.py:1016-1054``).

    «A stack of mappings behaving as a single mapping, and used to implement
    nested scopes. The lookups search the stack from top to bottom, and
    returns the first value found. Mutable operations modify the topmost
    mapping only.»

    Su consumidor es ``Transaction.protected`` (``orm/environments.py``): el
    conjunto de campos que un cómputo está protegiendo se apila al entrar en
    ``protecting()`` y se desapila al salir, y la lectura tiene que ver el
    tope y, si no está ahí, lo de abajo. Un ``dict`` llano no lo expresa
    —perdería lo de abajo al asignar— y un ``ChainMap`` de la biblioteca
    estándar busca en el orden **inverso** al de la fuente: el suyo consulta
    el primer mapa primero, y aquí el que manda es el último apilado.
    """
    __slots__ = ['_maps']

    def __init__(self, m: MutableMapping[K, T] | None = None):
        self._maps = [] if m is None else [m]

    def __getitem__(self, key: K) -> T:
        for mapping in reversed(self._maps):
            if key in mapping:
                return mapping[key]
        raise KeyError(key)

    def __setitem__(self, key: K, val: T):
        self._maps[-1][key] = val

    def __delitem__(self, key: K):
        del self._maps[-1][key]

    def __iter__(self) -> Iterator[K]:
        return iter({key for mapping in self._maps for key in mapping})

    def __len__(self) -> int:
        return sum(1 for key in self)

    def __str__(self) -> str:
        return f"<StackMap {self._maps}>"

    def pushmap(self, m: MutableMapping[K, T] | None = None):
        """Apila un mapa nuevo — el que recibirá las escrituras."""
        self._maps.append({} if m is None else m)

    def popmap(self) -> MutableMapping[K, T]:
        """Desapila el mapa del tope y lo devuelve."""
        return self._maps.pop()


class OrderedSet(MutableSet[T], typing.Generic[T]):
    """≙ ``OrderedSet`` (``odoo19c: odoo/tools/misc.py:1057-1096``).

    «A set collection that remembers the elements first insertion order.»

    Se porta en vez de resolverse con stdlib porque **no hay sustituto**: un
    `set` de Python no promete orden, y un `dict` con valores `None` da el
    orden pero no la interfaz de conjunto (`|`, `&`, `-`, `add`, `discard`)
    que la referencia usa. `MutableSet` de `collections.abc` deriva los
    operadores de los tres métodos abstractos, así que la implementación es
    la de la fuente y el resto lo pone la ABC — igual que allá.

    El orden importa donde se usa: ``_action_assign`` acumula los movimientos
    asignados en uno de éstos y luego los escribe en bloque; con un `set` el
    orden de escritura cambiaría entre ejecuciones y con él el orden de los
    quants tocados.
    """

    __slots__ = ['_map']

    def __init__(self, elems: Iterable[T] = ()):
        self._map: dict[T, None] = dict.fromkeys(elems)

    def __contains__(self, elem):
        return elem in self._map

    def __iter__(self):
        return iter(self._map)

    def __len__(self):
        return len(self._map)

    def add(self, elem):
        self._map[elem] = None

    def discard(self, elem):
        self._map.pop(elem, None)

    def update(self, elems):
        self._map.update(zip(elems, repeat(None)))

    def difference_update(self, elems):
        for elem in elems:
            self.discard(elem)

    def __repr__(self):
        return f'{type(self).__name__}({list(self)!r})'

    def intersection(self, *others):
        return reduce(OrderedSet.__and__, others, self)

    def copy(self):
        new_set = OrderedSet()
        new_set._map = self._map.copy()      # copia atómica del dict
        return new_set


class LastOrderedSet(OrderedSet[T], typing.Generic[T]):
    """≙ ``LastOrderedSet`` (``odoo19c: odoo/tools/misc.py:1098-1102``).

    «A set collection that remembers the elements last insertion order.»

    Entra con ``OrderedSet`` porque es su única diferencia —re-insertar mueve
    el elemento al final— y portarlo aparte dejaría el par incompleto.
    """

    def add(self, elem):
        self.discard(elem)
        super().add(elem)


def groupby(iterable: Iterable[T], key: Callable[[T], K] = lambda arg: arg):
    """≙ ``groupby`` (``odoo19c: odoo/tools/misc.py:1201-1210``).

    «Return a collection of pairs ``(key, elements)`` from ``iterable``. The
    ``key`` is a function computing a key value for each element. This
    function is similar to ``itertools.groupby``, but aggregates all elements
    under the same key, not only consecutive elements.»

    La última frase es la razón de portarlo: ``itertools.groupby`` **corta al
    cambiar la clave**, así que sobre una lista sin ordenar devuelve el mismo
    grupo varias veces. Sustituirlo por el del stdlib exigiría ordenar antes
    por la clave — y las claves de sus consumidores son tuplas de registros
    (ubicación, lote, paquete, dueño), que no tienen orden natural.
    """
    groups = defaultdict(list)
    for elem in iterable:
        groups[key(elem)].append(elem)
    return groups.items()


def named_to_positional_printf(string, args):
    """≙ ``named_to_positional_printf`` (``odoo19c: odoo/tools/misc.py:1959``).

    Convierte una plantilla printf con argumentos por nombre
    (``"%(x)s"``) en su equivalente posicional (``"%s"``) con la tupla de
    valores en el orden en que la plantilla los consume. Su consumidor es
    ``tools.sql.SQL``, que la importa igual que la referencia
    (``odoo19c: odoo/tools/sql.py:20``).
    """
    pargs = _PrintfArgs(args)
    return string.replace('%%', '%%%%') % pargs, tuple(pargs.values)


class _PrintfArgs:
    """≙ ``_PrintfArgs`` (``odoo19c: odoo/tools/misc.py:1967``).

    Objeto ayudante: al formatear con ``%``, cada ``%(clave)s`` que la
    plantilla consume registra su valor en orden y se sustituye por ``%s``.
    """
    __slots__ = ('mapping', 'values')

    def __init__(self, mapping):
        self.mapping = mapping
        self.values = []

    def __getitem__(self, key):
        self.values.append(self.mapping[key])
        return "%s"


#: ≙ ``ADDRESS_REGEX`` (``odoo19c: odoo/tools/misc.py:1913``), verbatim.
#:
#: Tres grupos: el nombre de la calle (no codicioso), un número que empieza por
#: dígito, y un segundo número tras un `` - ``. El ``re.DOTALL`` es de la
#: fuente y no es cosmético: una calle capturada de un formulario puede traer
#: un salto de línea, y sin él el ``.`` no lo cruza y el número se pierde.
ADDRESS_REGEX = re.compile(r'^(.*?)(\s[0-9][0-9\S]*)?(?: - (.+))?$',
                           flags=re.DOTALL)


def street_split(street):
    """≙ ``street_split`` (``odoo19c: odoo/tools/misc.py:1914-1921``), verbatim.

    Parte una calle en sus tres piezas. La fuente la consume en
    ``ResPartner._get_street_split`` y la reusan siete addons más —los de
    localización de facturación electrónica (``l10n_ch``, ``l10n_dk_oioubl``)
    y ``payment_adyen``—, que necesitan el número por separado porque el
    formato de intercambio lo pide en su propio campo.

    Devuelve siempre las tres claves; las ausentes son cadena vacía, nunca
    ``None`` — ``match.groups('')`` fija ese valor por defecto.
    """
    match = ADDRESS_REGEX.match(street or '')
    results = match.groups('') if match else ('', '', '')
    return {
        'street_name': results[0].strip(),
        'street_number': results[1].strip(),
        'street_number2': results[2],
    }


def parse_date(value, lang_code=None):
    """≙ ``parse_date`` (``odoo19c: odoo/tools/misc.py:1455-1472``).

    Convierte la fecha que un usuario **teclea** al ``date`` que el ORM
    entiende, y **devuelve la cadena original si no parsea** — que es el
    contrato de la fuente, no un descuido: quien busca «BBVA» en un campo de
    fecha tiene que llegar al buscador de texto, no a un error.

    La fuente usa ``babel.dates.parse_date`` con el *locale* de
    ``res.lang``. Aquí el mecanismo nativo es
    ``django.utils.formats.get_format('DATE_INPUT_FORMATS')``, que es la MISMA
    capacidad por la vía del stack: la lista de formatos de entrada de la
    localización activa. Medido con ``LANGUAGE_CODE = 'es-mx'``:
    ``['%d/%m/%Y', '%d/%m/%y', '%Y%m%d', '%Y-%m-%d']`` — el día antes del mes,
    que es lo que distingue una localización de otra y lo único que babel
    aportaría.

    No se añade ``babel`` como dependencia: medido, no está instalado, y el
    stack ya trae la capacidad.

    :param value: la cadena tecleada.
    :param lang_code: código de idioma; ``None`` usa el activo.
    :return: ``datetime.date`` si alguno de los formatos casa; si no, ``value``
        sin tocar.
    """
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value
    if not isinstance(value, str):
        return value
    for formato in django_formats.get_format('DATE_INPUT_FORMATS',
                                             lang=lang_code):
        try:
            return datetime.datetime.strptime(value, formato).date()
        except (ValueError, TypeError):
            continue
    return value


def get_lang(lang_code=None):
    """≙ ``get_lang`` (``odoo19c: odoo/tools/misc.py:1308-1326``).

    El ``res.lang`` que rige el formateo, resolviendo en el orden de la fuente:
    el código pedido, luego el del contexto, luego el de la empresa, y si
    ninguno está instalado, ``en_US`` o el primero que haya.

    Aquí «el del contexto» es ``django.utils.translation.get_language()``, que
    es el mismo dato por la vía del stack: lo fija el middleware de idioma en
    cada petición. El de la empresa queda para cuando ``ResCompany`` declare su
    idioma — hoy no lo tiene, y **eso es lo que el orden de la fuente cubre**:
    cae al siguiente escalón sin romperse.

    :param lang_code: código de idioma pedido (``es_MX``), o ``None``.
    :return: el registro ``ResLang``, o ``None`` si no hay ninguno instalado.
    """
    res_lang = apps.get_model('base', 'ResLang')
    installed = res_lang.objects.filter(active=True)
    if lang_code:
        chosen = installed.filter(code=lang_code).first()
        if chosen is not None:
            return chosen
    context_lang = django_translation.get_language()
    if context_lang:
        # Django usa ``es-mx``; ``res.lang`` guarda ``es_MX``. Es la misma
        # información con otra convención, no dos datos distintos.
        chosen = installed.filter(
            code__iexact=context_lang.replace('-', '_')).first()
        if chosen is not None:
            return chosen
    return (installed.filter(code='en_US').first()
            or installed.order_by('pk').first())


#: Los cuatro colores que ``get_diff`` pinta sobre la tabla de ``HtmlDiff``:
#: quitado y añadido, y su fondo de celda. El primer par es el esquema oscuro
#: y el segundo el claro, en el orden en que la fuente los declara
#: (``odoo19c: odoo/tools/misc.py:1746-1747``).
DIFF_COLORS_DARK = ('#7f2d2f', '#406a2d', '#51232f', '#3f483b')
DIFF_COLORS_LIGHT = ('#ffc1c0', '#abf2bc', '#ffebe9', '#e6ffec')

#: La hoja de estilo que la fuente inyecta cuando quien llama no trae la suya
#: (``:1748-1767``). Va como constante y no dentro de la función porque lleva
#: cuatro marcadores ``%s`` y anidarla en el cuerpo la hacía ilegible.
DIFF_DEFAULT_STYLE = """
            <style>
                .modal-dialog.modal-lg:has(table.diff) {
                    max-width: 1600px;
                    padding-left: 1.75rem;
                    padding-right: 1.75rem;
                }
                table.diff { width: 100%%; }
                table.diff th.diff_header { width: 50%%; }
                table.diff td.diff_header { white-space: nowrap; }
                table.diff td.diff_header + td { width: 50%%; }
                table.diff td { word-break: break-all; vertical-align: top; }
                table.diff .diff_chg, table.diff .diff_sub, table.diff .diff_add {
                    display: inline-block;
                    color: inherit;
                }
                table.diff .diff_sub, table.diff td:nth-child(3) > .diff_chg { background-color: %s }
                table.diff .diff_add, table.diff td:nth-child(6) > .diff_chg { background-color: %s }
                table.diff td:nth-child(3):has(>.diff_chg, .diff_sub) { background-color: %s }
                table.diff td:nth-child(6):has(>.diff_chg, .diff_add) { background-color: %s }
            </style>
        """


def get_diff(data_from, data_to, custom_style=False, dark_color_scheme=False):
    """≙ ``get_diff`` (``odoo19c: odoo/tools/misc.py:1722-1778``).

    La diferencia entre dos textos, como tabla HTML. El motor es
    ``difflib.HtmlDiff`` de la biblioteca estándar — el mismo que usa la
    fuente— con sus mismos parámetros: ``tabsize=2``, ``context=True`` (sólo
    las líneas que cambian, no el archivo entero) y ``numlines=3``.

    Lo consume ``ServerActionHistoryWizard._compute_code_diff``, que compara
    el código vigente de una acción con el de una revisión guardada.

    :param data_from: par ``(texto, encabezado)`` del lado izquierdo.
    :param data_to: par ``(texto, encabezado)`` del lado derecho.
    :param custom_style: hoja de estilo propia, con su etiqueta ``<style>``.
    :param dark_color_scheme: si el lector usa el esquema oscuro.
    :return: la tabla HTML, con su estilo adjunto.
    """
    def handle_style(html_diff, custom_style, dark_color_scheme):
        """Añade a las clases de ``HtmlDiff`` las de Bootstrap 4.

        La biblioteca marca el DOM con clases propias (``diff_header``,
        ``diff_next``); la fuente les apenda las suyas en vez de reescribir
        el generador, y aquí igual.
        """
        to_append = {
            'diff_header': 'bg-600 text-light text-center align-top px-2',
            'diff_next': 'd-none',
        }
        for old, new in to_append.items():
            html_diff = html_diff.replace(old, '%s %s' % (old, new))
        html_diff = html_diff.replace('nowrap', '')
        colors = DIFF_COLORS_DARK if dark_color_scheme else DIFF_COLORS_LIGHT
        html_diff += custom_style or DIFF_DEFAULT_STYLE % colors
        return html_diff

    diff = HtmlDiff(tabsize=2).make_table(
        data_from[0].splitlines(),
        data_to[0].splitlines(),
        data_from[1],
        data_to[1],
        context=True,  # sólo las líneas de la diferencia, no todo el código
        numlines=3,
    )
    return handle_style(diff, custom_style, dark_color_scheme)


# Los dos espacios que ``format_amount`` inserta, por su nombre Unicode.
# Como constantes y no como escape ``\N{...}`` dentro de la f-string: ahí la
# llave doble que Python exige colisiona con la sintaxis de la propia f-string.
NO_BREAK_SPACE = '\u00a0'
ZERO_WIDTH_NO_BREAK_SPACE = '\ufeff'


def format_amount(amount, currency, lang_code=None, trailing_zeroes=True):
    """≙ ``format_amount`` (``odoo19c: odoo/tools/misc.py:1635-1651``).

    El importe con su símbolo, redondeado a los decimales de la moneda,
    agrupado según la localización y con el símbolo del lado que la moneda
    declara.

    Los dos reemplazos de espacio **no son cosmética**: el espacio duro impide
    que un salto de línea separe la cifra de su símbolo, y el
    ``ZERO WIDTH NO-BREAK SPACE`` tras el signo menos impide que un guion al
    final de línea se lea como partición de palabra. Se portan verbatim.

    :param amount: el importe.
    :param currency: el ``ResCurrency`` que fija redondeo, símbolo y posición.
    :param lang_code: idioma a usar; ``None`` resuelve con ``get_lang``.
    :param trailing_zeroes: si se conservan los ceros finales.
    :return: la cadena formateada.
    """
    fmt = f'%.{currency.decimal_places}f'
    lang = get_lang(lang_code)
    rounded = currency.round(amount)

    if lang is None:
        # Sin ``res.lang`` sembrado, la localización activa de Django tiene la
        # misma información. Es el escalón que la fuente no necesita porque
        # allá ``res.lang`` siempre tiene al menos ``en_US``.
        formatted = django_formats.number_format(
            rounded, decimal_pos=currency.decimal_places, force_grouping=True)
        decimal_point = django_formats.get_format('DECIMAL_SEPARATOR')
    else:
        formatted = lang.format(fmt, rounded, grouping=True)
        decimal_point = lang.decimal_point or '.'

    formatted = (formatted.replace(' ', NO_BREAK_SPACE)
                 .replace('-', '-' + ZERO_WIDTH_NO_BREAK_SPACE))

    if not trailing_zeroes:
        formatted = re.sub(rf'{re.escape(decimal_point)}?0+$', '', formatted)

    symbol = currency.symbol or ''
    if currency.position == 'before':
        return symbol + NO_BREAK_SPACE + formatted
    return formatted + NO_BREAK_SPACE + symbol


def remove_accents(input_str: str) -> str:
    """Sustituye las latinas acentuadas por su equivalente ASCII.

    ≙ ``remove_accents`` (``odoo19c: odoo/tools/misc.py:713-720``), verbatim
    en mecanismo: descomponer en NFKD y descartar los caracteres
    combinantes. Cambia el significado del texto y sólo sirve para algunos
    casos — la fuente lo dice de sí misma, y es cierto: es la aproximación
    barata al ``unaccent`` de PostgreSQL, no su equivalente exacto.

    Su consumidor es el ``ilike`` en memoria de ``Field.filter_function``,
    que compara igual que el lookup ``sql_ilike`` pide al motor.
    """
    if not input_str:
        return input_str
    nkfd_form = unicodedata.normalize('NFKD', input_str)
    return ''.join(c for c in nkfd_form if not unicodedata.combining(c))


class unquote(str):
    """Cadena cuyo ``repr()`` sale sin comillas ni escapes — ≙ ``unquote``
    (``odoo19c: odoo/tools/misc.py:723-743``), verbatim.

    El nombre viene del ``unquote`` de Lisp. Sirve para dejar el nombre
    desnudo de una variable dentro del ``repr()`` de un dict que después se
    evalúa: sin ella, ``{'test': 'active_id'}`` fija la cadena literal; con
    ella, ``{'test': active_id}`` deja la referencia por resolver.

    Aquí lo consume ``IrActionsServer._get_children_domain``, que declara el
    dominio de las hijas con ``model_id`` e ``id`` como nombres a resolver en
    el contexto del cliente, no como valores del registro actual.

    Úsese con cuidado: ``repr()`` deja de ser reversible, que es justo lo que
    esta clase busca.

        >>> unquote('active_id')
        active_id
        >>> {'test': unquote('active_id')}
        {'test': active_id}
    """

    __slots__ = ()

    def __repr__(self):
        return self


class DotDict(dict):
    """≙ ``DotDict`` (``odoo19c: tools/misc.py:1710-1719``) — acceso por punto
    a las claves de un diccionario. ``foo = DotDict({'bar': False}); foo.bar``.
    Un valor que a su vez sea diccionario sale envuelto igual.
    """

    def __getattr__(self, attrib):
        val = self.get(attrib)
        return DotDict(val) if isinstance(val, dict) else val
