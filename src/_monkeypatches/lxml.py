"""Parche de ``lxml`` — porte de ``odoo/_monkeypatches/lxml.py`` (Odoo 19).

Adaptación de ``odoo/_monkeypatches/lxml.py`` (``odoo19c:``, LGPL-3 → copia
con atribución, DEC-KX-03); el cuerpo es verbatim salvo el import de
``parse_version``, que aquí vive en ``tools.parse_version``.

Dos parches, cada uno condicionado a la versión instalada:

- entre lxml 4.6.0 y 5.2.0, un atributo ``style`` con varias URL de datos se
  borraba por error; se corrige ``lxml.html.clean._find_image_dataurls``;
- libxml2 2.14.0 dejó de envolver en ``<p>`` el texto suelto. Se envuelven
  ``lxml.html.fromstring`` y ``lxml.html.document_fromstring`` para conservar
  el comportamiento de antes, del que dependen el saneador de
  ``tools/mail.py`` y sus pruebas.

**No es un no-op aquí, y se midió.** Con lxml 6.1.1 y libxml2 2.14.6,
``html.document_fromstring('yop')`` da ``<html><body>yop</body></html>`` y
``html_sanitize('yop')`` daba ``<span>yop</span>``; la fuente espera
``<p>yop</p>`` (``odoo19c: odoo/addons/base/tests/test_mail.py:50``).

*Métrica:* ``etree.LIBXML_VERSION`` y la salida de ``document_fromstring``,
medidos el 2026-11-19.
*Ciega a:* otra versión de libxml2: el primer parche sólo actúa con lxml
anterior a 5.2.0, el segundo sólo con libxml2 2.14.0 o posterior.

Como ``pytz.py``, lo llama su consumidor —``tools/mail.py``— al importarse,
porque el cargador perezoso de la raíz no está portado (ver
``_monkeypatches/__init__.py``).
"""
import lxml.html.clean
import re

from importlib.metadata import version
from lxml.etree import LIBXML_VERSION

from tools.parse_version import parse_version


def patch_module():
    # between these versions having a couple data urls in a style attribute
    # or style node removes the attribute or node erroneously
    if (parse_version("4.6.0") <= parse_version(version('lxml'))
            < parse_version("5.2.0")):
        lxml.html.clean._find_image_dataurls = re.compile(
            r'data:image/(.+?);base64,').findall

    # libxml2 >= 2.14.0 stopped implicitly wrapping plain text in <p> tags.
    # We patch lxml.html parsers here to maintain compatibility across
    # versions.
    if LIBXML_VERSION >= (2, 14, 0):
        RE_STARTS_WITH_TAG = r'^\s*<[\w!-]'
        RE_STARTS_WITH_TAG_STR = re.compile(RE_STARTS_WITH_TAG)
        RE_STARTS_WITH_TAG_BYTES = re.compile(
            RE_STARTS_WITH_TAG.encode('ascii'))

        orig_fromstring = lxml.html.fromstring
        orig_document_fromstring = lxml.html.document_fromstring

        def _wrap_text_node(html):
            if isinstance(html, bytes):
                if not RE_STARTS_WITH_TAG_BYTES.match(html):
                    return b"<p>%s</p>" % html.lstrip()
            else:
                if not RE_STARTS_WITH_TAG_STR.match(html):
                    return "<p>%s</p>" % html.lstrip()
            return html

        def fromstring(html, *args, **kwargs):
            return orig_fromstring(_wrap_text_node(html), *args, **kwargs)

        def document_fromstring(html, *args, **kwargs):
            return orig_document_fromstring(
                _wrap_text_node(html), *args, **kwargs)

        lxml.html.fromstring = fromstring
        lxml.html.document_fromstring = document_fromstring
