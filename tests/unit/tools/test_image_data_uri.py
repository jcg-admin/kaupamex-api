"""``tools.image.image_data_uri`` — la URL ``data:`` de una imagen en base64
(tarea #285, primer tramo: los dos símbolos que ``ir.qweb`` consume).

Adaptación de ``odoo19c: odoo/tools/image.py:32-38,564-572`` (LGPL-3) —
atribución y aviso de licencia preservados (DEC-KX-03).
"""
import base64

import pytest

from tools.image import FILETYPE_BASE64_MAGICWORD, image_data_uri


class TestTheFirstByteDecidesTheMimetype:
    """≙ ``FILETYPE_BASE64_MAGICWORD.get(base64_source[:1], 'png')``."""

    @pytest.mark.parametrize('raw, mimetype', [
        (b'\xff\xd8\xff', 'jpg'),          # JPEG → base64 empieza por '/'
        (b'GIF89a', 'gif'),                # GIF → 'R'
        (b'\x89PNG', 'png'),               # PNG → 'i'
        (b'<svg', 'svg+xml'),              # SVG → 'P'
        (b'RIFF', 'webp'),                 # WEBP → 'U'
    ])
    def test_each_magic_word_maps_to_its_format(self, raw, mimetype):
        source = base64.b64encode(raw)
        assert source[:1] in FILETYPE_BASE64_MAGICWORD
        assert image_data_uri(source) == (
            f'data:image/{mimetype};base64,{source.decode()}')

    def test_an_unknown_first_byte_falls_back_to_png(self):
        source = base64.b64encode(b'\x00\x01\x02')
        assert source[:1] not in FILETYPE_BASE64_MAGICWORD
        assert image_data_uri(source).startswith('data:image/png;base64,')

    def test_the_payload_is_the_base64_text_untouched(self):
        source = base64.b64encode(b'\x89PNG\r\n\x1a\n')
        assert image_data_uri(source).split(',', 1)[1] == source.decode()
