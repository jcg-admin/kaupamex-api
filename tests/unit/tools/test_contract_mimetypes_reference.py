"""``tools.mimetypes.guess_mimetype`` medido contra la fuente ejecutada.

Se carga ``odoo19c: odoo/tools/mimetypes.py`` por ruta —sólo importa la
biblioteca estándar, y ``magic`` de forma opcional— y se compara
``guess_mimetype`` sobre contenidos construidos en memoria: los formatos que
el detector decide por firma, los contenedores ZIP de Office y de
OpenDocument que decide abriendo el archivo, y los bordes (vacío,
``bytearray``, texto).

*Métrica:* el tipo devuelto —o el nombre de la excepción— por contenido.
``python-magic`` no está instalado, así que la ruta normal de los dos lados
es el detector propio. La rama de ``magic`` se mide aparte: los dos archivos
se cargan por ruta con un ``magic`` sustituto registrado durante la carga,
que devuelve un tipo fijo por contenido —incluidos los genéricos que
disparan los subdetectores de OLE y de ZIP—.

*Ciega a:* lo que libmagic real respondería a cada contenido —el sustituto lo
fija la prueba— y a toda divergencia que la fuente comparta con nosotros.
"""
import importlib.util
import io
import pathlib
import sys
import types
import zipfile

import pytest

from tools import mimetypes as ported

pytestmark = pytest.mark.unit

_REPO = pathlib.Path(__file__).resolve().parents[3]
_SPEC = importlib.util.spec_from_file_location(
    'reference_roots_for_mimetypes', _REPO / 'scripts' / 'reference_roots.py')
reference_roots = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(reference_roots)


def zipped(entries):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        for name, content in entries:
            archive.writestr(name, content)
    return buffer.getvalue()


SAMPLES = {
    'pdf': b'%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj',
    'png': b'\x89PNG\r\n\x1a\n' + b'\x00' * 20,
    'jpeg': b'\xff\xd8\xff\xe0\x00\x10JFIF\x00',
    'gif87': b'GIF87a' + b'\x00' * 10,
    'gif89': b'GIF89a' + b'\x00' * 10,
    'bmp': b'BM' + b'\x00' * 20,
    'webp': b'RIFF\x24\x00\x00\x00WEBPVP8 ' + b'\x00' * 10,
    'riff not webp': b'RIFF\x24\x00\x00\x00WAVEfmt ',
    'svg': (b'<?xml version="1.0"?>\n'
            b'<svg xmlns="http://www.w3.org/2000/svg"/>'),
    'svg bare': b'<svg width="1"></svg>',
    'xml': b'<?xml version="1.0"?><root/>',
    'text': b'hello world',
    'empty': b'',
    'docx': zipped([('[Content_Types].xml', '<x/>'),
                    ('word/document.xml', '<w/>')]),
    'xlsx': zipped([('[Content_Types].xml', '<x/>'),
                    ('xl/workbook.xml', '<w/>')]),
    'pptx': zipped([('[Content_Types].xml', '<x/>'),
                    ('ppt/presentation.xml', '<p/>')]),
    'odt': zipped([('mimetype', 'application/vnd.oasis.opendocument.text'),
                   ('content.xml', '<c/>')]),
    'ods bad mimetype': zipped([('mimetype', 'not a/mime type!'),
                                ('content.xml', '<c/>')]),
    'plain zip': zipped([('a.txt', 'a')]),
    'broken zip': b'PK\x03\x04' + b'\x00' * 30,
    'ole': b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1' + b'\x00' * 40,
    # Un ``.doc``: la misma firma OLE y su subcabecera en el desplazamiento
    # 0x200, que es lo que el subdetector de la fuente reconoce.
    'doc': (b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'
            + b'\x00' * (0x200 - 8) + b'\xec\xa5\xc1\x00' + b'\x00' * 16),
}


#: Lo que el ``magic`` sustituto responde, por el contenido que recibe.
MAGIC_ANSWERS = {
    'pdf': 'application/pdf', 'text': 'text/plain',
    'empty': 'application/octet-stream', 'png': 'application/octet-stream',
    'docx': 'application/zip', 'plain zip': 'application/zip',
    'broken zip': 'application/zip', 'ole': 'application/CDFV2',
    'doc': 'application/x-ole-storage',
    'svg': 'image/svg+xml',
}


def load_with_magic(name, path):
    """Carga ``path`` con un ``magic`` sustituto, y lo retira después."""
    by_head = {SAMPLES[key][:2048]: answer
               for key, answer in MAGIC_ANSWERS.items()}
    stand_in = types.ModuleType('magic')
    stand_in.from_buffer = lambda data, mime: by_head[bytes(data)]
    saved = sys.modules.get('magic')
    sys.modules['magic'] = stand_in
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if saved is None:
            sys.modules.pop('magic', None)
        else:
            sys.modules['magic'] = saved


def reference_module():
    try:
        root = pathlib.Path(reference_roots.tree('odoo19c'))
    except Exception:
        return None
    path = root / 'odoo' / 'tools' / 'mimetypes.py'
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location('reference_mimetypes', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope='module')
def reference():
    module = reference_module()
    if module is None:
        pytest.skip('la referencia no está montada en esta sesión')
    return module


def outcome(call):
    try:
        return ('value', call())
    except Exception as error:
        return ('raises', type(error).__name__)


class TestGuessMimetypeMatchesTheReference:

    @pytest.mark.parametrize('name', sorted(SAMPLES))
    def test_the_guess_matches(self, reference, name):
        data = SAMPLES[name]
        for value in (data, bytearray(data)):
            assert outcome(lambda v=value: ported.guess_mimetype(v)) == \
                outcome(lambda v=value: reference.guess_mimetype(v))
        assert outcome(lambda: ported.guess_mimetype(data, default='x/y')) \
            == outcome(lambda: reference.guess_mimetype(data, default='x/y'))

    def test_both_sides_take_the_same_branch(self, reference):
        assert (ported.magic is None) == \
            (reference.guess_mimetype is reference._odoo_guess_mimetype)


class TestTheMagicBranchMatchesTheReference:

    def test_every_answer_is_post_processed_as_in_the_reference(
            self, reference):
        root = pathlib.Path(reference_roots.tree('odoo19c'))
        theirs = load_with_magic(
            'reference_mimetypes_with_magic',
            root / 'odoo' / 'tools' / 'mimetypes.py')
        ours = load_with_magic(
            'ported_mimetypes_with_magic',
            _REPO / 'src' / 'tools' / 'mimetypes.py')
        assert theirs.guess_mimetype is not theirs._odoo_guess_mimetype
        for name in sorted(MAGIC_ANSWERS):
            for value in (SAMPLES[name], bytearray(SAMPLES[name])):
                assert outcome(lambda v=value: ours.guess_mimetype(v)) == \
                    outcome(lambda v=value: theirs.guess_mimetype(v)), name
        assert outcome(lambda: ours.guess_mimetype('text')) == \
            outcome(lambda: theirs.guess_mimetype('text'))


class TestGuessMimetypeLiterally:
    """Casos escritos a mano: el diferencial no dice cuál se rompió."""

    def test_a_docx_is_recognized_by_its_directory(self):
        assert ported.guess_mimetype(SAMPLES['docx']) == (
            'application/vnd.openxmlformats-officedocument'
            '.wordprocessingml.document')

    def test_the_default_applies_to_unknown_content(self):
        assert ported.guess_mimetype(b'\x00\x01', default='x/y') == 'x/y'
