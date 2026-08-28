"""``tools.misc`` — espejo de ``odoo/tools/misc.py`` (sólo símbolos con consumidor).

Regla de este archivo: cada símbolo llega aquí cuando un addon portado lo
importa (``from tools.misc import X``, espejo de ``from odoo.tools.misc
import X``), y **antes de portarlo se decide** si Django/DRF/stdlib ya lo
resuelven (directiva ejecutor 2026-08-02). La decisión queda en el docstring
del símbolo — no se porta por completitud.

Adaptado de Odoo Community ``odoo/tools/misc.py`` (LGPL-3) — atribución y
aviso de licencia preservados (DEC-KX-03).
"""
import hmac as hmac_lib
import re
import typing
from collections import defaultdict
from collections.abc import Callable, Iterable, MutableSet
from functools import reduce
from itertools import islice, repeat

import datetime

from django.apps import apps
from django.utils import formats as django_formats
from django.utils import translation as django_translation
from django.utils.crypto import salted_hmac
from django.utils.html import escape as django_html_escape
from lxml import etree

# Variables de tipo de la referencia (``odoo19c: odoo/tools/misc.py:70-72``),
# que las declara para los genéricos de esta misma familia de colecciones.
K = typing.TypeVar('K')
T = typing.TypeVar('T')

# ``consteq`` — comparación en tiempo constante.
#
# La referencia lo define como alias del stdlib (``misc.py:1668``:
# ``consteq = hmac_lib.compare_digest``). No hay nada que portar: se replica
# el mismo alias. Django ofrece ``django.utils.crypto.constant_time_compare``,
# que es un wrapper de esta misma función — se usa el stdlib directo, igual
# que la referencia.
consteq = hmac_lib.compare_digest


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

# ``html_escape`` — escape HTML para mensajes construidos a mano.
#
# La referencia lo define como alias de ``markupsafe.escape``
# (``odoo19c: odoo/tools/misc.py:1305``). Aquí lo resuelve Django
# (``django.utils.html.escape``): mismo contrato para el único consumidor
# actual (mensajes de error del motor de herencia), sin añadir ``markupsafe``
# como dependencia — el criterio de este archivo: stdlib/Django antes que una
# dependencia nueva, con la decisión anotada.
html_escape = django_html_escape


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
