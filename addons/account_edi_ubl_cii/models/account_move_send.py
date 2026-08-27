r"""``account.move.send`` — lo que ``account_edi_ubl_cii`` le cuelga (≙ ``_inherit``).

Adaptación de ``odoo19c: addons/account_edi_ubl_cii/models/account_move_send.py``
(``odoo-tools@622ddc2a``, LGPL-3, 312 líneas) — atribución y aviso de licencia
preservados (DEC-KX-03).

Cobertura: 11 de 11 símbolos presentes — **4 portados, 7 bloqueados**
======================================================================

.. list-table::
   :header-rows: 1
   :widths: 44 12 44

   * - Símbolo
     - Estado
     - Nota
   * - ``_display_attachments_widget``
     - portado
     - lee ``ResPartner._get_ubl_cii_formats_info()``, que **sí** se porta en
       ``res_partner.py`` de este mismo addon
   * - ``_get_ubl_available_attachments``
     - portado
     - **divergencia**: la aritmética de recordsets de la fuente
       (``attachments - accepted``) → listas; y el "recordset vacío" que
       devuelve en la rama temprana → lista vacía
   * - ``_needs_ubl_postprocessing``
     - portado
     - lee sólo el ``dict`` ``invoice_data``
   * - ``_get_invoice_extra_attachments``
     - portado
     - **combinación**, no relevo: ``combine=extend_list`` preserva el orden
       de la fuente (primero lo de ``account``/``account_edi``, después
       ``ubl_cii_xml_id``), mismo criterio que
       ``account_edi/models/account_move_send.py`` ya fijó para este mismo
       método
   * - ``_get_move_constraints``
     - bloqueado
     - ``AccountMove._is_exportable_as_self_invoice`` está bloqueado en
       ``account_move.py`` de este addon (``commercial_partner_id`` /
       ``is_purchase_document`` / ``journal_id.is_self_billing``: 0 hits)
   * - ``_get_alerts``
     - bloqueado
     - ``commercial_partner_id`` (0 hits) e ``IrModule._get()`` (0 hits)
   * - ``_get_placeholder_mail_attachments_data``
     - bloqueado
     - ``commercial_partner_id`` (0 hits) y ``_need_ubl_cii_xml``, bloqueado
   * - ``_hook_invoice_document_before_pdf_report_render``
     - bloqueado
     - ``commercial_partner_id`` (0 hits) y ``_init_invoice_export_values``,
       bloqueado por la envoltura de base-lines
   * - ``_hook_invoice_document_after_pdf_report_render``
     - bloqueado
     - ``odoo.tools.pdf.OdooPdfFileReader``/``Writer`` (``pypdf``: **0** en
       ``uv.lock``) y ``env['ir.qweb']._render`` (sin motor QWeb en este
       árbol)
   * - ``_postprocess_invoice_ubl_xml``
     - bloqueado
     - ``odoo.tools.cleanup_xml_node`` no existe en ``src/tools`` (0 hits) y
       el método embebe el PDF ya renderizado, que depende de la cadena
       anterior
   * - ``_link_invoice_documents``
     - bloqueado
     - ``with_user(SUPERUSER_ID)`` y ``AccountMove.browse`` sobre varios ids:
       el proxy de ``env`` de este addon no emula recordsets (límite ya
       declarado en ``account_edi_common.py``)

``SUPPORTED_FILE_TYPES`` viene de ``account_edi_common.py`` (portada verbatim
allí): es la tabla de mimetypes que UBL admite como adjunto embebido.
"""
from orm.method_chain import chain_method, extend_list

from addons.account.models.account_move_send import AccountMoveSend

from .account_edi_common import SUPPORTED_FILE_TYPES, _blocked, env

__all__ = [
    '_get_ubl_available_attachments',
    'apply_account_edi_ubl_cii_account_move_send_extensions',
]


def _display_attachments_widget(cls, edi_format, sending_methods):
    """≙ ``_display_attachments_widget`` (``odoo19c: :97-103``).

    Devuelve sólo su aporte y ``None`` cuando no aplica, para que
    ``chain_method`` delegue en la implementación previa — el relevo por
    ``None`` que sustituye al ``or super()...`` de la fuente.
    """
    ubl_format_info = env['res.partner']._get_ubl_cii_formats_info()
    return ubl_format_info.get(edi_format, {}).get('embed_attachments') or None


def _get_ubl_available_attachments(cls, mail_attachments_widget,
                                   invoice_edi_format):
    """≙ ``_get_ubl_available_attachments`` (``odoo19c: :105-117``).

    Parte los adjuntos manuales del asistente en (los que el formato admite
    embebidos, los que no).

    DIVERGENCIA declarada: la fuente devuelve **recordsets** y los resta
    (``attachments - accepted_attachments``); aquí son listas, porque el proxy
    de ``env`` de este addon no emula aritmética de recordsets (límite ya
    declarado en ``account_edi_common.py``). El contrato —dos colecciones,
    aceptados y no aceptados, en ese orden— se conserva.
    """
    if not invoice_edi_format or not mail_attachments_widget:
        return [], []
    attachment_ids = [values['id'] for values in mail_attachments_widget
                      if values.get('manual')]
    attachments = env['ir.attachment'].browse(attachment_ids)

    ubl_format_info = env['res.partner']._get_ubl_cii_formats_info().get(
        invoice_edi_format, {})
    if not ubl_format_info.get('embed_attachments'):
        return [], attachments

    accepted_attachments = [attachment for attachment in attachments
                            if attachment.mimetype in SUPPORTED_FILE_TYPES]
    rejected = [attachment for attachment in attachments
                if attachment not in accepted_attachments]
    return accepted_attachments, rejected


def _needs_ubl_postprocessing(cls, invoice_data):
    """≙ ``_needs_ubl_postprocessing`` (``odoo19c: :223-225``) — verbatim.

    Factur-X y ZUGFeRD quedan fuera porque en esos dos el XML va dentro del
    PDF, no al revés.
    """
    return ('ubl_cii_xml_options' in invoice_data
            and invoice_data['ubl_cii_xml_options']['ubl_cii_format']
            not in ('facturx', 'zugferd'))


def _get_invoice_extra_attachments_ubl_cii(cls, move):
    """≙ la parte de ``account_edi_ubl_cii`` de
    ``_get_invoice_extra_attachments`` (``odoo19c: :79-81``): el adjunto del
    XML UBL/CII del asiento. Se **combina** con lo previo (ver la tabla del
    docstring del módulo)."""
    attachment = getattr(move, 'ubl_cii_xml_id', None)
    return [attachment] if attachment else []


def _get_move_constraints(cls, move):
    """≙ ``_get_move_constraints`` (``odoo19c: :23-28``) — **bloqueado**:
    quita la restricción ``not_sale_document`` cuando el asiento es
    autofacturable, y ``AccountMove._is_exportable_as_self_invoice`` está
    bloqueado (ver ``account_move.py`` de este addon)."""
    _blocked('_get_move_constraints',
             'AccountMove._is_exportable_as_self_invoice esta bloqueado '
             '(commercial_partner_id / is_purchase_document: 0 hits)')


def _get_alerts(cls, moves, moves_data):
    """≙ ``_get_alerts`` (``odoo19c: :33-73``) — **bloqueado**:
    ``commercial_partner_id`` e ``IrModule._get()`` no existen (0 hits)."""
    _blocked('_get_alerts',
             'ResPartner.commercial_partner_id e IrModule._get() no existen '
             '(0 hits)')


def _get_placeholder_mail_attachments_data(cls, move, invoice_edi_format=None,
                                           extra_edis=None, pdf_report=None):
    """≙ ``_get_placeholder_mail_attachments_data`` (``odoo19c: :83-95``) —
    **bloqueado**: ``commercial_partner_id`` (0 hits) y ``_need_ubl_cii_xml``,
    bloqueado."""
    _blocked('_get_placeholder_mail_attachments_data',
             'ResPartner.commercial_partner_id no existe (0 hits) y '
             'AccountMove._need_ubl_cii_xml esta bloqueado')


def _hook_invoice_document_before_pdf_report_render(cls, invoice, invoice_data):
    """≙ ``_hook_invoice_document_before_pdf_report_render``
    (``odoo19c: :122-155``) — **bloqueado**: ``commercial_partner_id`` (0 hits)
    y ``_init_invoice_export_values``, bloqueado por la envoltura de
    base-lines de ``account.tax``."""
    _blocked('_hook_invoice_document_before_pdf_report_render',
             'ResPartner.commercial_partner_id no existe (0 hits) y la '
             'envoltura de base-lines de account.tax no se porta')


def _hook_invoice_document_after_pdf_report_render(cls, invoice, invoice_data):
    """≙ ``_hook_invoice_document_after_pdf_report_render``
    (``odoo19c: :157-221``) — **bloqueado**: embebe el XML dentro del PDF con
    ``odoo.tools.pdf.OdooPdfFileReader``/``OdooPdfFileWriter`` (``pypdf``: 0 en
    ``uv.lock``) y renderiza con ``env['ir.qweb']._render`` (sin motor QWeb en
    este árbol, GAP ya declarado por ``account_edi/models/
    ir_actions_report.py``)."""
    _blocked('_hook_invoice_document_after_pdf_report_render',
             'pypdf (0 en uv.lock) y el motor QWeb no existen en este arbol')


def _postprocess_invoice_ubl_xml(cls, invoice, invoice_data):
    """≙ ``_postprocess_invoice_ubl_xml`` (``odoo19c: :227-298``) —
    **bloqueado**: incluye el PDF en el UBL como ``AdditionalDocumentReference``
    y necesita ``odoo.tools.cleanup_xml_node``, que ``src/tools`` no porta
    (0 hits), además del PDF ya renderizado por la cadena anterior."""
    _blocked('_postprocess_invoice_ubl_xml',
             'odoo.tools.cleanup_xml_node no existe en src/tools (0 hits)')


def _link_invoice_documents(cls, invoices_data):
    """≙ ``_link_invoice_documents`` (``odoo19c: :300-312``) — **bloqueado**:
    ``with_user(SUPERUSER_ID)`` y ``browse`` sobre varios ids; el proxy de
    ``env`` de este addon no emula recordsets (límite declarado en
    ``account_edi_common.py``)."""
    _blocked('_link_invoice_documents',
             'with_user(SUPERUSER_ID) y la aritmetica de recordsets no se '
             'emulan (limite declarado del proxy env)')


def apply_account_edi_ubl_cii_account_move_send_extensions():
    """Cuelga sobre ``account.move.send`` lo que este addon aporta — ≙
    ``_inherit = 'account.move.send'``. La llama
    ``AccountEdiUblCiiConfig.ready()``."""
    chain_method(
        AccountMoveSend, '_get_invoice_extra_attachments',
        classmethod(_get_invoice_extra_attachments_ubl_cii),
        combine=extend_list,
    )

    for name, function in (
        ('_display_attachments_widget', classmethod(_display_attachments_widget)),
        ('_get_ubl_available_attachments',
         classmethod(_get_ubl_available_attachments)),
        ('_needs_ubl_postprocessing', classmethod(_needs_ubl_postprocessing)),
        ('_get_move_constraints', classmethod(_get_move_constraints)),
        ('_get_alerts', classmethod(_get_alerts)),
        ('_get_placeholder_mail_attachments_data',
         classmethod(_get_placeholder_mail_attachments_data)),
        ('_hook_invoice_document_before_pdf_report_render',
         classmethod(_hook_invoice_document_before_pdf_report_render)),
        ('_hook_invoice_document_after_pdf_report_render',
         classmethod(_hook_invoice_document_after_pdf_report_render)),
        ('_postprocess_invoice_ubl_xml',
         classmethod(_postprocess_invoice_ubl_xml)),
        ('_link_invoice_documents', classmethod(_link_invoice_documents)),
    ):
        chain_method(AccountMoveSend, name, function)
