"""``tools.i18n`` — espejo de ``odoo19c: odoo/tools/i18n.py``.

Dos capacidades de localización que ni Django ni la biblioteca estándar traen:
enumerar una lista con el conector del idioma activo (*«enero, febrero y
marzo»*, no *«enero, febrero, marzo»*) y traducir el código de idioma de la
forma XPG de Python a la forma BCP 47 que consume el cliente JavaScript.

Adaptado de Odoo Community (LGPL-3, ``__manifest__`` del núcleo) — copia con
adaptación y atribución preservada (DEC-KX-03).
"""
from __future__ import annotations

import re
import typing
from typing import Literal

from babel import lists

from tools.misc import babel_locale_parse, get_lang

if typing.TYPE_CHECKING:
    from collections.abc import Iterable

#: El código de idioma en la sintaxis XPG de Python:
#: ``language[_territory][.codeset][@modifier]``. Se porta verbatim, comentario
#: incluido: la fuente declara ahí que **no** admite ``.codeset`` porque no lo
#: usa, y esa exclusión es parte del contrato — un código con codeset no casa y
#: ``py_to_js_locale`` lo devuelve sin tocar en vez de mutilarlo.
XPG_LOCALE_RE = re.compile(
    r"""^
    ([a-z]+)      # el idioma
    (_[A-Z\d]+)?  # quizá _territorio
    # sin soporte de .codeset (no se usa)
    (@.+)?        # quizá @modificador
    $""",
    re.VERBOSE,
)


def format_list(
    env,
    lst: Iterable,
    style: Literal['standard', 'standard-short', 'or', 'or-short', 'unit',
                   'unit-short', 'unit-narrow'] = 'standard',
    lang_code: str | None = None,
) -> str:
    """Enumera ``lst`` con el patrón de lista del idioma, en el estilo pedido.

    Los estilos los define babel según la especificación Unicode TR35-49:

    * ``standard`` — la enumeración con «y» para elementos arbitrarios;
      p. ej. *«enero, febrero y marzo»*.
    * ``standard-short`` — su versión corta, para valores abreviados;
      p. ej. *«ene., feb. y mar.»*.
    * ``or`` — la enumeración con «o»; p. ej. *«enero, febrero o marzo»*.
    * ``or-short`` — su versión corta; p. ej. *«ene., feb. o mar.»*.
    * ``unit`` — para unidades escritas enteras; p. ej. *«3 pies, 7 pulgadas»*.
    * ``unit-short`` — para unidades abreviadas; p. ej. *«3 ft, 7 in»*.
    * ``unit-narrow`` — para unidades donde el espacio en pantalla es mínimo;
      p. ej. *«3′ 7″»*.

    Detalle en
    https://www.unicode.org/reports/tr35/tr35-49/tr35-general.html#ListPatterns.

    El estilo se degrada dos veces, y las dos son de la fuente: un idioma puede
    no declarar el patrón pedido —``style not in locale.list_patterns``— y babel
    puede lanzar ``KeyError`` al resolverlo pese a estar declarado. En ambos
    casos se cae a ``standard`` en vez de fallar: quien formatea una lista la
    está mostrando, y un estilo ausente no puede tumbar la respuesta.

    **Divergencia declarada — ``env``.** La firma es la de la fuente, que
    resuelve el idioma con ``get_lang(env)`` leyendo ``env.context['lang']``.
    Aquí :func:`tools.misc.get_lang` no recibe entorno: lee el idioma activo de
    ``django.utils.translation``, que es el mismo dato por la vía del stack —lo
    fija el middleware de idioma en cada petición— y esa divergencia ya está
    declarada en su propio docstring. El parámetro se conserva para que el
    contrato sea el de la fuente y un puerto que llame a este símbolo no tenga
    que reescribir su llamada; no se consume.

    :param env: el entorno del ORM; se acepta por fidelidad de contrato (ver
        arriba).
    :param lst: los elementos que se enumeran.
    :param style: el estilo de enumeración.
    :param lang_code: el idioma (``es_MX``); ``None`` usa el activo.
    :return: la lista ya enumerada.
    """
    if not lang_code:
        # Corto igual que la fuente (``lang_code or get_lang(env).code``): con
        # un código explícito no se consulta ``res.lang``. La guarda del
        # ``None`` es la única diferencia — allá ``get_lang`` siempre devuelve
        # un registro porque ``en_US`` está instalado por construcción; aquí
        # puede no haber ninguno todavía, y entonces se deja que
        # ``babel_locale_parse`` aplique su propia cadena de respaldo.
        lang = get_lang()
        lang_code = lang.code if lang else None
    locale = babel_locale_parse(lang_code)
    # Un idioma puede no declarar el estilo pedido.
    if style not in locale.list_patterns:
        style = 'standard'
    try:
        return lists.format_list([str(el) for el in lst], style, locale)
    except KeyError:
        return lists.format_list([str(el) for el in lst], 'standard', locale)


def py_to_js_locale(locale: str) -> str:
    """Convierte un código de idioma de la forma de Python a la de JavaScript.

    Casi siempre la conversión es sustituir ``_`` por ``-``; p. ej.
    ``fr_BE`` → ``fr-BE``.

    La excepción es el serbio, que se escribe indistintamente en alfabeto
    latino y cirílico: su código lleva un modificador que dice cuál usar, y en
    BCP 47 ese dato es una subetiqueta de escritura. P. ej. ``sr@latin`` →
    ``sr-Latn``.

    BCP 47 (JavaScript):
        ``language[-extlang][-script][-region][-variant][-extension][-privateuse]``
        https://www.ietf.org/rfc/rfc5646.txt
    Sintaxis XPG (Python):
        ``language[_territory][.codeset][@modifier]``
        https://www.gnu.org/software/libc/manual/html_node/Locale-Names.html

    :param locale: el código en la forma de Python.
    :return: el código en la forma de JavaScript, o el mismo valor sin tocar si
        no casa con :data:`XPG_LOCALE_RE`.
    """
    match_ = XPG_LOCALE_RE.match(locale)
    if not match_:
        return locale
    language, territory, modifier = match_.groups()
    subtags = [language]
    if modifier == '@Cyrl':
        subtags.append('Cyrl')
    elif modifier == '@latin':
        subtags.append('Latn')
    if territory:
        subtags.append(territory.removeprefix('_'))
    return '-'.join(subtags)
