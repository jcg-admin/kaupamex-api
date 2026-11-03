"""``_get_xml_tree`` reconoce el XML por su contenido.

≙ ``odoo19c: addons/account/models/account_document_import_mixin.py:481-493``:
un adjunto XML que llega por correo trae ``text/plain``, y la fuente lo
reconoce con ``guess_mimetype(raw)`` aunque el nombre no termine en ``.xml``.
"""

from addons.account.models.account_document_import_mixin import (
    AccountDocumentImportMixin)

XML = b'<?xml version="1.0"?><Invoice><ID>F-1</ID></Invoice>'


def test_plain_text_mail_attachment_is_read_as_xml_by_its_content():
    tree = AccountDocumentImportMixin._get_xml_tree(
        {'name': 'factura', 'mimetype': 'text/plain', 'raw': XML})
    assert tree is not None
    assert tree.tag == 'Invoice'


def test_plain_text_that_is_not_xml_gives_no_tree():
    tree = AccountDocumentImportMixin._get_xml_tree(
        {'name': 'nota', 'mimetype': 'text/plain', 'raw': b'hola mundo'})
    assert tree is None
