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
from itertools import islice

from django.utils.crypto import salted_hmac
from django.utils.html import escape as django_html_escape
from lxml import etree

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
