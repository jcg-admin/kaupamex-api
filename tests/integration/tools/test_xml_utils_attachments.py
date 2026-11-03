"""``tools.xml_utils`` contra ``ir.attachment`` real: el resolvedor, la
validación por nombre de adjunto y la descarga de XSD
(``odoo19c: odoo/tools/xml_utils.py:45-117, 207-336``)."""

import io
import zipfile

import pytest
import requests

from orm.utils import SUPERUSER_ID
from exceptions import UserError
from orm.environments import Environment, env
from tools import xml_utils

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def superuser_environment(db):
    """El ``self.env`` de un ``TransactionCase`` de la fuente es el del
    superusuario (``odoo19c: odoo/tests/common.py``); es el que usa
    ``tests/integration/test_orm/conftest.py``. Sin él, el entorno ambiental
    no tiene usuario con grupos y la ACL de ``ir.attachment`` deniega."""
    with Environment(None, SUPERUSER_ID, {}):
        yield


TYPES = b"""<?xml version="1.0"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:simpleType name="Code"><xs:restriction base="xs:string">
    <xs:pattern value="F-[0-9]+"/>
  </xs:restriction></xs:simpleType>
</xs:schema>"""

MAIN = b"""<?xml version="1.0"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:include schemaLocation="types.xsd"/>
  <xs:element name="Invoice">
    <xs:complexType><xs:sequence>
      <xs:element name="ID" type="Code"/>
    </xs:sequence></xs:complexType>
  </xs:element>
</xs:schema>"""


def _attach(name, raw):
    return env()['ir.attachment'].create(
        {'name': name, 'raw': raw, 'public': True})


def test_the_resolver_finds_an_include_among_the_prefixed_attachments():
    _attach('probe_mod.types.xsd', TYPES)
    _attach('probe_mod.main.xsd', MAIN)
    xml_utils._check_with_xsd(
        b'<Invoice><ID>F-12</ID></Invoice>', 'probe_mod.main.xsd',
        env(), 'probe_mod')
    with pytest.raises(UserError):
        xml_utils._check_with_xsd(
            b'<Invoice><ID>X</ID></Invoice>', 'probe_mod.main.xsd',
            env(), 'probe_mod')


def test_a_missing_schema_attachment_is_file_not_found():
    with pytest.raises(FileNotFoundError):
        xml_utils._check_with_xsd(b'<a/>', 'nope.xsd', env())


def test_validate_xml_from_attachment_skips_a_missing_schema(caplog):
    with caplog.at_level('INFO', logger='tools.xml_utils'):
        xml_utils.validate_xml_from_attachment(env(), b'<a/>', 'nope.xsd')
    assert 'XSD file not found, skipping validation' in caplog.text


class _Response:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        return None


def test_load_xsd_files_from_url_saves_a_single_schema(monkeypatch):
    monkeypatch.setattr(requests, 'get', lambda url, timeout: _Response(TYPES))
    saved = xml_utils.load_xsd_files_from_url(
        env(), 'https://x.test/types.xsd', xsd_name_prefix='probe_dl')
    assert saved.name == 'probe_dl.types.xsd'
    assert saved.raw == TYPES
    again = xml_utils.load_xsd_files_from_url(
        env(), 'https://x.test/types.xsd', xsd_name_prefix='probe_dl')
    assert again.id == saved.id


def test_load_xsd_files_from_url_unpacks_a_zip_with_its_filter(monkeypatch):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr('xsd/types.xsd', TYPES)
        archive.writestr('xsd/main.xsd', MAIN)
        archive.writestr('README.txt', 'x')
    monkeypatch.setattr(
        requests, 'get', lambda url, timeout: _Response(buffer.getvalue()))
    saved = xml_utils.load_xsd_files_from_url(
        env(), 'https://x.test/pack.zip', xsd_name_prefix='probe_zip',
        xsd_names_filter=['main.xsd', 'types.xsd'])
    names = sorted(saved.mapped('name'))
    assert names == ['probe_zip.main.xsd', 'probe_zip.types.xsd']


def test_load_xsd_files_from_url_reports_a_connection_error(monkeypatch):
    def refuse(url, timeout):
        raise requests.exceptions.ConnectionError('refused')
    monkeypatch.setattr(requests, 'get', refuse)
    url = 'https://x.test/a.xsd'
    assert xml_utils.load_xsd_files_from_url(env(), url) is False
