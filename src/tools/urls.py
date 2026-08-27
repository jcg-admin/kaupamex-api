"""``tools.urls`` — unión estricta de URLs, fiel a ``odoo/tools/urls.py``.

Adaptación de Odoo ``odoo19c: odoo/tools/urls.py`` (``odoo-tools``, LGPL-3) —
atribución y aviso de licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 2 de 2, más ``__all__``
=====================================================

Medido sobre la fuente (74 líneas, 2 ``def``):

=========================================  =========================================
Símbolo de la referencia (línea)           Aquí
=========================================  =========================================
``__all__ = ['urljoin']`` (4)              verbatim
``_contains_dot_segments`` (7-10)          ``_contains_dot_segments``
``urljoin`` (13-74)                        ``urljoin``
=========================================  =========================================

Divergencia declarada (única): la fuente anota ``_contains_dot_segments(path:
str) -> str`` cuando la función devuelve un booleano (``any(...)``); aquí la
anotación de retorno es ``bool``. El comportamiento es idéntico.

Hasta H-API-701 (tarea #555) estos dos símbolos vivían como funciones de
módulo en ``addons/website/models/website.py`` (``_urljoin_strict`` /
``_contains_dot_segments``) — sitio divergente de la fuente, cuya raíz
espejada es ésta (``src/tools`` ↔ ``odoo/tools``). Este módulo es el hogar;
el reapunte de los consumidores de ``website`` es del pase que consolida.
"""
import re
import urllib.parse

__all__ = ['urljoin']


def _contains_dot_segments(path: str) -> bool:
    """≙ ``_contains_dot_segments`` (``odoo19c: odoo/tools/urls.py:7-10``).

    La mayoría de los servidores decodifica la URL antes de resolver los
    segmentos punto — por eso se evalúa sobre la forma decodificada
    (``%2e%2e`` cuenta como ``..``). El ``errors='strict'`` es el de la
    fuente, verbatim.
    """
    decoded_path = urllib.parse.unquote(path, errors='strict')
    return any(segment in ('.', '..') for segment in decoded_path.split('/'))


def urljoin(base: str, extra: str) -> str:
    """≙ ``urljoin`` (``odoo19c: odoo/tools/urls.py:13-74``).

    Une una base **confiable** con una URL relativa de forma estricta. NO es
    el ``urljoin`` RFC 3986 de ``urllib.parse``: aquél sigue las reglas de
    resolución del estándar; éste impone el comportamiento que el
    desarrollador espera y cierra path traversal, redirects no planeados y
    sobrescrituras accidentales de esquema/host.

    - Se comporta como ``base + '/' + extra``.
    - Conserva esquema y netloc de ``base``; si ``extra`` trae los suyos,
      sólo se admiten si coinciden con la base **y** su path empieza con el
      path de la base.
    - Prohíbe los segmentos ``.`` y ``..`` (también codificados).
    - Fusiona path, query y fragment (query y fragment ganan los de
      ``extra``).

    :param base: URL o path base confiable.
    :param extra: URL relativa (``path``, ``?query``, ``#frag``). Sin esquema
        ni host, salvo que coincidan con ``base``.
    :returns: la URL unida.
    :raises AssertionError: si las entradas no son cadenas.
    :raises ValueError: si ``extra`` trae segmentos punto o es una URL
        absoluta ajena a la base.

    Ejemplos de la fuente::

        >>> urljoin('https://api.example.com/v1/?bar=fiz', '/users/42?bar=bob')
        'https://api.example.com/v1/users/42?bar=bob'

        >>> urljoin('https://api.example.com/data/', '/?lang=fr')
        'https://api.example.com/data/?lang=fr'
    """
    assert isinstance(base, str), "Base URL must be a string"
    assert isinstance(extra, str), "Extra URL must be a string"

    base_scheme, base_netloc, path, _base_query, _base_fragment = (
        urllib.parse.urlsplit(base))
    extra_scheme, extra_netloc, extra_path, extra_query, extra_fragment = (
        urllib.parse.urlsplit(extra))

    if extra_scheme or extra_netloc:
        # Se admite una ``extra`` absoluta sólo si coincide con la base.
        if (extra_scheme != base_scheme or extra_netloc != base_netloc
                or not extra_path.startswith(path)):
            raise ValueError(
                'Extra URL must use same scheme and host as base, and '
                'begin with base path')
        extra_path = extra_path[len(path):]

    if extra_path:
        # Evita que urljoin('/', '\\example.com/') resuelva absoluto a
        # '//example.com/' en un redirect de navegador — verbatim de la
        # fuente, controles C0 y espacio incluidos (la fuente cita el
        # tratamiento de nsStandardURL.cpp en Firefox).
        extra_path = extra_path.lstrip(
            '/\\\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r'
            '\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b'
            '\x1c\x1d\x1e\x1f ')
        path = f'{path}/{extra_path}'

    # Normaliza: foo//bar -> foo/bar (fuente).
    path = re.sub(r'/+', '/', path)

    if _contains_dot_segments(path):
        raise ValueError('Dot segments are not allowed')

    return urllib.parse.urlunsplit(
        (base_scheme, base_netloc, path, extra_query, extra_fragment))
