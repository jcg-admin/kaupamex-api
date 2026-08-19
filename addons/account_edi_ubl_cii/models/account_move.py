r"""``account.move`` — lo que ``account_edi_ubl_cii`` le cuelga (≙ ``_inherit``).

Adaptación de ``odoo19c: addons/account_edi_ubl_cii/models/account_move.py``
(``odoo-tools@622ddc2a``, LGPL-3, 402 líneas) — atribución y aviso de licencia
preservados (DEC-KX-03).

Cobertura: 20 de 20 símbolos presentes — **6 portados, 14 bloqueados**
=======================================================================

**Los 6 portados** son los que sólo leen el XML o componen un ``dict``:
``_compute_filename``, ``action_invoice_download_ubl``,
``_get_import_file_type``, ``_unwrap_attachment``,
``_ubl_parse_attached_document`` y ``_get_line_vals_list``. El bloque de
identificación de formato de ``_get_import_file_type`` —el que decide entre
``ubl_de``, ``ubl_nl``, ``ubl_a_nz``, ``ubl_sg``, ``ubl_bis3``, ``ubl_20``,
``ubl_21`` y ``cii`` leyendo ``CustomizationID``/``UBLVersionID``— se porta
verbatim: es la tabla que hace utilizable todo el resto del addon.

**Los 14 bloqueados** y su pieza, medida (``grep -rn … addons/ src/`` → 0 hits):

.. list-table::
   :header-rows: 1
   :widths: 46 54

   * - Símbolos
     - Pieza ausente
   * - ``_get_invoice_legal_documents`` · ``get_extra_print_items`` ·
       ``_is_exportable_as_self_invoice``
     - ``AccountMove.commercial_partner_id`` (y
       ``journal_id.is_self_billing``)
   * - ``_ungroup_lines`` · ``_group_lines_by_tax`` ·
       ``_get_line_vals_group_by_tax`` ·
       ``action_group_ungroup_lines_by_tax`` ·
       ``_check_move_for_group_ungroup_lines_by_tax`` · ``_has_lines_grouped``
     - ``AccountMove.invoice_line_ids`` y ``message_post`` (``AccountMove`` no
       hereda ``MailThread`` en este árbol). Los dos últimos además agregan
       importes con ``env['account.tax']``, la envoltura de base-lines que
       ``account/models/account_tax.py:82-90`` declara no portada
   * - ``_get_fields_to_detach``
     - recorre ``self._fields`` (introspección del ORM de la referencia)
   * - ``_post_process_link_to_purchase_order``
     - ``AccountMove._check_company_domain``
   * - ``_get_edi_decoder``
     - ``env.registry[model]._inherit_children`` — el grafo de herencia del
       ORM de la referencia. Aquí ``_inherit`` es herencia de Python y el
       equivalente sería ``__subclasses__()``; no se improvisa porque el
       método decide **qué decodificador** atiende un archivo, y equivocarlo
       importa un documento con el constructor incorrecto en silencio
   * - ``_need_ubl_cii_xml``
     - ``AccountMove.is_sale_document()`` (0 hits) y
       ``_is_exportable_as_self_invoice``, bloqueado
   * - ``_get_specific_tax``
     - ``AccountMoveLine._predict_specific_tax`` (0 hits)

Tres campos — los tres declarados, dos con divergencia
=======================================================

* ``ubl_cii_xml_file`` — ``fields.Binary`` en la referencia con
  ``attachment=True``, es decir persistido **fuera de la columna**, en
  ``ir.attachment``. Este árbol no tiene ese mecanismo, así que se declara
  como columna binaria; el adjunto vinculado se modela con el campo siguiente.
* ``ubl_cii_xml_id`` — en la referencia es ``compute=`` sobre
  ``_compute_linked_attachment_id`` (0 hits aquí), que es la mitad de ese
  mismo mecanismo ``attachment=True``. **Divergencia:** se declara como FK
  real y nulable a ``base.IrAttachment``, el mismo criterio y el mismo destino
  que ``account_edi/models/account_edi_document.py:171`` usa para su
  ``attachment``.
* ``ubl_cii_xml_filename`` — ``compute`` sin ``store`` → ``property``.

``re`` no se importa: su único consumidor en la fuente es
``_get_line_vals_group_by_tax``, bloqueado.

``ensure_one()`` — divergencia declarada una vez
=================================================

La referencia lo llama al entrar en varios métodos porque allí ``self`` es un
recordset que podría traer N registros. Aquí ``self`` es **una instancia de
Django**, que ya es exactamente un registro: el guard no tiene objeto y se
retira. No es un símbolo omitido — es una precondición que el tipo ya
garantiza.
"""
import binascii
from base64 import b64decode
from contextlib import suppress

from lxml import etree

import fields
from django.db import models as django_models
from orm.method_chain import chain_method
from orm.model_classes import add_field_if_absent

from addons.account.models.account_move import AccountMove

from .account_edi_common import _blocked


def _extra_fields():
    """Los dos campos con columna real (ver "Tres campos" en el docstring)."""
    return {
        'ubl_cii_xml_file': fields.Binary(
            null=True, blank=True,
            verbose_name='UBL/CII File',
            help_text='XML UBL/CII del asiento (Odoo ubl_cii_xml_file; su '
                      'attachment=True no tiene contraparte aquí).',
        ),
        'ubl_cii_xml_id': fields.Many2one(
            'base.IrAttachment', on_delete=django_models.SET_NULL,
            null=True, blank=True, related_name='ubl_cii_moves',
            verbose_name='Attachment',
            help_text='Adjunto que lleva el XML UBL/CII (Odoo ubl_cii_xml_id, '
                      'allí computado por _compute_linked_attachment_id).',
        ),
    }


def _compute_filename(self):
    """≙ ``_compute_filename`` (``odoo19c: :37-41``).

    ``compute`` sin ``store`` → ``property``: el nombre del archivo es el del
    adjunto vinculado.
    """
    attachment = self.ubl_cii_xml_id
    return attachment.name if attachment else ''


def action_invoice_download_ubl(self):
    """≙ ``action_invoice_download_ubl`` (``odoo19c: :47-52``).

    DIVERGENCIA: ``self.ids`` (recordset) → ``[self.pk]`` — ver "``ensure_one``"
    en el docstring del módulo. La URL se conserva verbatim.
    """
    return {
        'type': 'ir.actions.act_url',
        'url': f'/account/download_invoice_documents/{self.pk}/ubl'
               f'?allow_fallback=true',
        'target': 'download',
    }


def _get_import_file_type(self, file_data):
    """≙ ``_get_import_file_type`` (``odoo19c: :251-279``) — verbatim.

    Identifica el formato UBL/CII del árbol XML. Devuelve ``None`` para lo que
    no reconoce, y ``chain_method`` delega entonces en la implementación previa
    (el relevo por ``None`` que sustituye al ``return super()`` de la fuente).
    """
    if (tree := file_data['xml_tree']) is not None:
        if etree.QName(tree).localname == 'AttachedDocument':
            return 'account.edi.xml.ubl.attached_document'
        if tree.tag == ('{urn:un:unece:uncefact:data:standard:'
                        'CrossIndustryInvoice:100}CrossIndustryInvoice'):
            return 'account.edi.xml.cii'
        if customization_id := tree.findtext('{*}CustomizationID'):
            if 'xrechnung' in customization_id:
                return 'account.edi.xml.ubl_de'
            if customization_id == ('urn:cen.eu:en16931:2017#compliant#'
                                    'urn:fdc:nen.nl:nlcius:v1.0'):
                return 'account.edi.xml.ubl_nl'
            if customization_id == ('urn:cen.eu:en16931:2017#conformant#'
                                    'urn:fdc:peppol.eu:2017:poacc:billing:'
                                    'international:aunz:3.0'):
                return 'account.edi.xml.ubl_a_nz'
            if customization_id == ('urn:cen.eu:en16931:2017#conformant#'
                                    'urn:fdc:peppol.eu:2017:poacc:billing:'
                                    'international:sg:3.0'):
                return 'account.edi.xml.ubl_sg'
            if customization_id == ('urn:cen.eu:en16931:2017#compliant#'
                                    'urn:fdc:peppol.eu:2017:poacc:billing:3.0'):
                return 'account.edi.xml.ubl_bis3'
        if ubl_version := tree.findtext('{*}UBLVersionID'):
            if ubl_version == '2.0':
                return 'account.edi.xml.ubl_20'
            if ubl_version in ('2.1', '2.2', '2.3'):
                return 'account.edi.xml.ubl_21'
        if customization_id := tree.findtext('{*}CustomizationID'):
            if 'urn:cen.eu:en16931:2017' in customization_id:
                return 'account.edi.xml.ubl_bis3'
    return None


def _ubl_parse_attached_document(cls, tree):
    """≙ ``_ubl_parse_attached_document`` (``odoo19c: :308-342``) — verbatim.

    En UBL, un ``AttachedDocument`` es un envoltorio de otros archivos UBL. La
    especificación guarda el documento original en el nodo ``Attachment`` de
    más arriba: o como ``Attachment/EmbeddedDocumentBinaryObject``, o (en casos
    especiales) como una cadena CDATA en
    ``Attachment/ExternalReference/Description``. Hay que resolverlo antes de
    pasar el archivo original al decodificador.
    """
    attachment_node = tree.find('{*}Attachment')
    if attachment_node is None:
        return '', None

    attachment_binary_data = attachment_node.find(
        './{*}EmbeddedDocumentBinaryObject')
    if attachment_binary_data is not None \
            and attachment_binary_data.attrib.get('mimeCode') in (
                'application/xml', 'text/xml'):
        with suppress(etree.XMLSyntaxError, binascii.Error):
            content_1 = b64decode(attachment_binary_data.text)
            return content_1, etree.fromstring(content_1)

    external_reference = attachment_node.find('./{*}ExternalReference')
    if external_reference is not None:
        description = external_reference.findtext('./{*}Description')
        mime_code = external_reference.findtext('./{*}MimeCode')

        if description and mime_code in ('application/xml', 'text/xml'):
            content_2 = description.encode('utf-8')
            with suppress(etree.XMLSyntaxError):
                return content_2, etree.fromstring(content_2)

    # Si ni EmbeddedDocumentBinaryObject ni ExternalReference/Description se
    # dejan decodificar como XML, se cae al contenido del primero.
    return content_1, None


def _unwrap_attachment(self, file_data, recurse=True):
    """≙ ``_unwrap_attachment`` (``odoo19c: :281-306``).

    DIVERGENCIA: ``guess_mimetype`` de ``odoo.tools.mimetypes`` no existe en
    este árbol (0 hits); el equivalente es
    ``IrBinary._guess_mimetype(filename)``, que decide por **nombre de
    archivo**, no por contenido. Como aquí el contenido siempre es XML —lo
    acaba de parsear ``_ubl_parse_attached_document``— se fija
    ``'application/xml'``, que es lo que la fuente deduciría del mismo dato.
    """
    if file_data['import_file_type'] != 'account.edi.xml.ubl.attached_document':
        return None

    content, tree = type(self)._ubl_parse_attached_document(
        file_data['xml_tree'])
    if not content:
        return []

    embedded_file_data = {
        'name': file_data['name'],
        'raw': content,
        'xml_tree': tree,
        'mimetype': 'application/xml',
        'attachment': None,
        'origin_attachment': file_data['origin_attachment'],
        'origin_import_file_type': file_data['origin_import_file_type'],
    }
    embedded_file_data['import_file_type'] = self._get_import_file_type(
        embedded_file_data)

    embedded = [embedded_file_data]
    if recurse:
        embedded.extend(self._unwrap_attachments(embedded, recurse=True))

    return embedded


def _get_line_vals_list(cls, lines_vals):
    """≙ ``_get_line_vals_list`` (``odoo19c: :379-392``).

    Compone los valores de las líneas de factura a partir de
    ``[(nombre, cantidad, precio, impuestos), ...]``.

    DIVERGENCIA: ``[Command.set(tax_ids)]`` → la lista de ids tal cual.
    ``Command`` es el idioma x2many del ORM de la referencia (una tripleta
    ``(6, 0, ids)``); aquí un M2M se asigna con la lista de ids, que expresa lo
    mismo sin el envoltorio.
    """
    return [{
        # Por delante de las líneas 'reales' de la factura.
        'sequence': 0,
        'name': name,
        'quantity': quantity,
        'price_unit': price_unit,
        'tax_ids': list(tax_ids),
    } for name, quantity, price_unit, tax_ids in lines_vals]


# -----------------------------------------------------------------------------
# BLOQUEADOS — piezas nombradas ausentes (ver la tabla del docstring)
# -----------------------------------------------------------------------------

def _get_fields_to_detach(self):
    """≙ ``_get_fields_to_detach`` (``odoo19c: :57-62``) — **bloqueado**:
    extiende una lista que produce ``account`` recorriendo ``self._fields``
    (introspección del ORM de la referencia; 0 hits del método base)."""
    _blocked('_get_fields_to_detach',
             'AccountMove._get_fields_to_detach() no existe (0 hits)')


def _get_invoice_legal_documents(self, filetype, allow_fallback=False):
    """≙ ``_get_invoice_legal_documents`` (``odoo19c: :64-90``) —
    **bloqueado**: ``commercial_partner_id`` no existe (0 hits)."""
    _blocked('_get_invoice_legal_documents',
             'AccountMove.commercial_partner_id no existe (0 hits)')


def get_extra_print_items(self):
    """≙ ``get_extra_print_items`` (``odoo19c: :92-111``) — **bloqueado**:
    misma pieza que ``_get_invoice_legal_documents``."""
    _blocked('get_extra_print_items',
             'AccountMove.commercial_partner_id no existe (0 hits)')


def action_group_ungroup_lines_by_tax(self):
    """≙ ``action_group_ungroup_lines_by_tax`` (``odoo19c: :113-123``) —
    **bloqueado**: orquesta ``_group_lines_by_tax``/``_ungroup_lines``."""
    _blocked('action_group_ungroup_lines_by_tax',
             'AccountMove.invoice_line_ids no existe (0 hits)')


def _ungroup_lines(self):
    """≙ ``_ungroup_lines`` (``odoo19c: :125-146``) — **bloqueado**:
    ``invoice_line_ids`` (0 hits) y ``message_post`` (AccountMove no hereda
    MailThread en este árbol)."""
    _blocked('_ungroup_lines',
             'AccountMove.invoice_line_ids y message_post no existen (0 hits)')


def _group_lines_by_tax(self):
    """≙ ``_group_lines_by_tax`` (``odoo19c: :148-159``) — **bloqueado**:
    misma pieza que ``_ungroup_lines``."""
    _blocked('_group_lines_by_tax',
             'AccountMove.invoice_line_ids y message_post no existen (0 hits)')


def _get_line_vals_group_by_tax(self):
    """≙ ``_get_line_vals_group_by_tax`` (``odoo19c: :161-199``) —
    **bloqueado**: ``invoice_line_ids`` más la envoltura de base-lines de
    ``account.tax``, que ``account/models/account_tax.py:82-90`` declara no
    portada."""
    _blocked('_get_line_vals_group_by_tax',
             'AccountMove.invoice_line_ids y la envoltura de base-lines de '
             'account.tax no existen (0 hits)')


def _check_move_for_group_ungroup_lines_by_tax(self):
    """≙ ``_check_move_for_group_ungroup_lines_by_tax`` (``odoo19c: :201-207``)
    — **bloqueado**: lee el estado y las líneas de factura del asiento."""
    _blocked('_check_move_for_group_ungroup_lines_by_tax',
             'AccountMove.invoice_line_ids no existe (0 hits)')


def _has_lines_grouped(self):
    """≙ ``_has_lines_grouped`` (``odoo19c: :209-219``) — **bloqueado**: misma
    pieza."""
    _blocked('_has_lines_grouped',
             'AccountMove.invoice_line_ids no existe (0 hits)')


def _post_process_link_to_purchase_order(self, order_reference):
    """≙ ``_post_process_link_to_purchase_order`` (``odoo19c: :222-245``) —
    **bloqueado**: ``AccountMove._check_company_domain`` no existe (0 hits)."""
    _blocked('_post_process_link_to_purchase_order',
             'AccountMove._check_company_domain() no existe (0 hits)')


def _get_edi_decoder(self, file_data, new=False):
    """≙ ``_get_edi_decoder`` (``odoo19c: :344-361``) — **bloqueado**:
    recorre ``env.registry[model]._inherit_children``, el grafo de herencia del
    ORM de la referencia. Ver la nota de la tabla del docstring: aquí
    ``_inherit`` es herencia de Python y el análogo sería ``__subclasses__()``,
    pero este método decide **qué decodificador** atiende un archivo y
    equivocarlo importaría el documento con el constructor incorrecto sin que
    nada lo delate."""
    _blocked('_get_edi_decoder',
             'env.registry[...]._inherit_children (grafo de herencia del ORM '
             'de la referencia) no tiene analogo')


def _need_ubl_cii_xml(self, ubl_cii_format):
    """≙ ``_need_ubl_cii_xml`` (``odoo19c: :363-367``) — **bloqueado**:
    ``AccountMove.is_sale_document()`` no existe (0 hits) y
    ``_is_exportable_as_self_invoice`` está bloqueado."""
    _blocked('_need_ubl_cii_xml',
             'AccountMove.is_sale_document() no existe (0 hits)')


def _is_exportable_as_self_invoice(self):
    """≙ ``_is_exportable_as_self_invoice`` (``odoo19c: :369-377``) —
    **bloqueado**: ``commercial_partner_id``, ``is_purchase_document()`` y
    ``journal_id.is_self_billing`` no existen (0 hits)."""
    _blocked('_is_exportable_as_self_invoice',
             'AccountMove.commercial_partner_id/is_purchase_document y '
             'AccountJournal.is_self_billing no existen (0 hits)')


def _get_specific_tax(self, name, amount_type, amount, tax_type):
    """≙ ``_get_specific_tax`` (``odoo19c: :394-402``) — **bloqueado**:
    ``AccountMoveLine._predict_specific_tax`` no existe (0 hits). La rama de
    la fuente que lo comprueba con ``hasattr`` devuelve el recordset vacío;
    aquí se levanta en vez de devolver ``None``, para no convertir un bloqueo
    en un dato falso."""
    _blocked('_get_specific_tax',
             'AccountMoveLine._predict_specific_tax() no existe (0 hits)')


def apply_account_edi_ubl_cii_account_move_extensions():
    """Cuelga sobre ``account.AccountMove`` lo que este addon aporta — ≙
    ``_inherit = 'account.move'``. La llama ``AccountEdiUblCiiConfig.ready()``."""
    for name, field in _extra_fields().items():
        add_field_if_absent(AccountMove, name, field)

    if not hasattr(AccountMove, 'ubl_cii_xml_filename'):
        AccountMove.ubl_cii_xml_filename = property(_compute_filename)

    for name, function in (
        ('action_invoice_download_ubl', action_invoice_download_ubl),
        ('_get_import_file_type', _get_import_file_type),
        ('_unwrap_attachment', _unwrap_attachment),
        ('_ubl_parse_attached_document', classmethod(_ubl_parse_attached_document)),
        ('_get_line_vals_list', classmethod(_get_line_vals_list)),
        ('_get_fields_to_detach', _get_fields_to_detach),
        ('_get_invoice_legal_documents', _get_invoice_legal_documents),
        ('get_extra_print_items', get_extra_print_items),
        ('action_group_ungroup_lines_by_tax', action_group_ungroup_lines_by_tax),
        ('_ungroup_lines', _ungroup_lines),
        ('_group_lines_by_tax', _group_lines_by_tax),
        ('_get_line_vals_group_by_tax', _get_line_vals_group_by_tax),
        ('_check_move_for_group_ungroup_lines_by_tax',
         _check_move_for_group_ungroup_lines_by_tax),
        ('_has_lines_grouped', _has_lines_grouped),
        ('_post_process_link_to_purchase_order',
         _post_process_link_to_purchase_order),
        ('_get_edi_decoder', _get_edi_decoder),
        ('_need_ubl_cii_xml', _need_ubl_cii_xml),
        ('_is_exportable_as_self_invoice', _is_exportable_as_self_invoice),
        ('_get_specific_tax', _get_specific_tax),
    ):
        chain_method(AccountMove, name, function)


__all__ = ['apply_account_edi_ubl_cii_account_move_extensions']
