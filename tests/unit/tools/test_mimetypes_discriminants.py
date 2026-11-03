"""Los discriminantes de ``tools.mimetypes`` que el test de la fuente no
ejerce uno a uno: OOXML, OpenDocument, OLECF y ``neuter_mimetype``
(``odoo19c: odoo/tools/mimetypes.py:30-114, 235-240``)."""

import io
import zipfile

from tools import mimetypes as mt

DOCX = (
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
)


def _zip(entries):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return buffer.getvalue()


class _User:
    def __init__(self, system):
        self.system = system

    def _is_system(self):
        return self.system


def test_ooxml_is_told_by_its_content_types_and_directory():
    data = _zip({'[Content_Types].xml': '<x/>', 'word/document.xml': '<w/>'})
    assert mt._check_ooxml(data) == DOCX
    assert mt.guess_mimetype(data) == DOCX


def test_ooxml_without_content_types_is_not_ooxml():
    assert mt._check_ooxml(_zip({'word/document.xml': '<w/>'})) is False


def test_open_document_declares_its_type_in_the_mimetype_entry():
    odt = 'application/vnd.oasis.opendocument.text'
    data = _zip({'mimetype': odt, 'content.xml': '<c/>'})
    assert mt._check_open_container_format(data) == odt
    assert mt.guess_mimetype(data) == odt


def test_open_document_with_a_malformed_type_is_rejected():
    archive = _zip({'mimetype': 'no es tipo'})
    assert mt._check_open_container_format(archive) is False


def test_olecf_subheader_at_0x200_tells_a_word_document():
    data = (b'\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1' + b'\0' * 0x1F8
            + b'\xEC\xA5\xC1\x00')
    assert mt._check_olecf(data) == 'application/msword'
    sample = data[:0x200] + b'Microsoft Excel'
    assert mt._check_olecf(sample) == 'application/vnd.ms-excel'


def test_an_unknown_zip_stays_zip():
    assert mt.guess_mimetype(_zip({'a.txt': 'x'})) == 'application/zip'


def test_neuter_mimetype_degrades_markup_unless_system():
    assert mt.neuter_mimetype('text/html', _User(False)) == 'text/plain'
    assert mt.neuter_mimetype('image/svg+xml', _User(False)) == 'text/plain'
    assert mt.neuter_mimetype('text/html', _User(True)) == 'text/html'
    assert mt.neuter_mimetype('image/png', _User(False)) == 'image/png'
