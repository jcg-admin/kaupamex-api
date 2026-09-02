"""Utilidades de imagen — ≙ ``odoo/tools/image.py`` (``odoo19c:``, LGPL-3,
603 líneas). Atribución y aviso de licencia preservados (DEC-KX-03).

Porte en curso — 2 de 22 símbolos en este archivo (tarea #285)
==============================================================

Medido con AST sobre la fuente: 16 ``def``/``class`` + 6 constantes. Este pase
porta los dos que consume ``ir.qweb._prepare_environment``
(``odoo19c: base/models/ir_qweb.py:1313``, vía
``_get_converted_image_data_uri``): ``FILETYPE_BASE64_MAGICWORD`` (``:32-38``)
e ``image_data_uri`` (``:564-572``). Los 20 restantes —``ImageProcess`` y su
familia sobre Pillow— los porta la tarea **#285** en este mismo archivo; el
sitio es éste porque la referencia los declara aquí
(``atributos-de-clase-de-modelo.md``, segunda cláusula).
"""

#: ≙ ``FILETYPE_BASE64_MAGICWORD`` (``:32-38``): el primer byte del base64
#: delata el formato — es el mismo truco de la fuente, verbatim.
FILETYPE_BASE64_MAGICWORD = {
    b'/': 'jpg',
    b'R': 'gif',
    b'i': 'png',
    b'P': 'svg+xml',
    b'U': 'webp',
}


def image_data_uri(base64_source: bytes) -> str:
    """≙ ``image_data_uri`` (``:564-572``) — la URL ``data:`` de RFC 2397
    para cualquier imagen soportada (PNG, GIF, JPG, SVG, WEBP); PNG cuando el
    primer byte no delata el tipo.
    """
    return 'data:image/%s;base64,%s' % (
        FILETYPE_BASE64_MAGICWORD.get(base64_source[:1], 'png'),
        base64_source.decode(),
    )
