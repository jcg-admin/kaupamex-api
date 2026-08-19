"""``download_docs`` — descarga de adjuntos y documentos legales de facturas.

Adaptación de Odoo ``addons/account/controllers/download_docs.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3 —
atribución y aviso de licencia preservados, DEC-KX-03).

El controller de la referencia (``http.Controller`` + ``@http.route``) se
porta como clase con métodos que reciben ``request`` y devuelven
``HttpResponse`` binarios — el cableado de URLs es del orquestador
(``urls.py`` queda fuera de este pase por directiva; este archivo no toca
el wiring existente). ``auth='user'`` de las tres rutas ≙ la capa DRF con
capacidad ``invoices`` al cablear (``authz_catalog.py`` del addon).

Seis símbolos de la referencia (2 funciones + 1 clase con 3 defs)
==================================================================

=====================================  ====================================
Símbolo de la referencia                Qué pasa aquí
=====================================  ====================================
``_get_headers``                        PORTADO (``content_disposition`` de
                                         ``odoo.http`` no está portado — se
                                         compone inline el mismo header)
``_build_zip_from_data``                PORTADO — verbatim
``download_invoice_attachments``        PORTADO (parcial declarado, ver su
                                         docstring)
``download_invoice_documents_filetype`` PORTADO (delegación bloqueada por
                                         ``account.move._get_invoice_legal_
                                         documents`` / ``_all`` — la
                                         generación de documentos legales
                                         (PDF/XML EDI) no está portada en
                                         ``account_move.py``; la llamada se
                                         escribe verbatim y falla en voz
                                         alta hasta que aterrice)
``download_move_attachments``           PORTADO (ídem con
                                         ``_get_move_zip_export_docs``; su
                                         helper interno
                                         ``rename_duplicates`` es puro y se
                                         porta verbatim)
=====================================  ====================================

Divergencias declaradas:

- ``attachments._build_zip_from_attachments`` (helper de ``ir.attachment``
  no portado) → el zip se compone aquí con ``_build_zip_from_data`` sobre
  ``attachment.datas`` (el ``FileField`` que el puerto de ``IrAttachment``
  declara como contenido; ``raw`` de la referencia ≙ ``datas.read()``).
- ``invoice._get_invoice_report_filename(extension='zip')`` no está portado
  → nombre ``invoices.zip`` (la rama multi-factura ya usa ese fallback en
  la referencia).
- ``attachments.check_access('read')`` ≙ la capa DRF (capacidad
  ``invoices``, fail-closed) al cablear la vista — no ACL por registro.
"""
import io
import zipfile
from itertools import chain

from django.http import HttpResponse

from addons.account.models.account_move import AccountMove
from addons.base.models import IrAttachment
from exceptions import UserError
from tools.translate import _


def _get_headers(filename, filetype, content):
    """≙ ``_get_headers`` — los cuatro headers de la descarga.

    ``content_disposition(filename)`` de ``odoo.http`` (no portado) se
    compone inline: ``attachment; filename=...`` es todo lo que produce.
    """
    return [
        ('Content-Type', filetype),
        ('Content-Length', len(content)),
        ('Content-Disposition', f'attachment; filename="{filename}"'),
        ('X-Content-Type-Options', 'nosniff'),
    ]


def _build_zip_from_data(docs_data):
    """≙ ``_build_zip_from_data`` — verbatim: un zip DEFLATE con un archivo
    por dict ``{'filename', 'content'}``."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w',
                         compression=zipfile.ZIP_DEFLATED) as zipfile_obj:
        for doc_data in docs_data:
            zipfile_obj.writestr(doc_data['filename'], doc_data['content'])
    return buffer.getvalue()


def _make_response(content, headers):
    """El ``request.make_response`` de la referencia, sobre Django."""
    response = HttpResponse(content)
    for key, value in headers:
        response[key] = value
    return response


def _attachment_raw(attachment):
    """``attachment.raw`` de la referencia — aquí el ``FileField``."""
    if not attachment.datas:
        return b''
    content = attachment.datas.read()
    attachment.datas.seek(0)
    return content


class AccountDocumentDownloadController:
    """≙ ``AccountDocumentDownloadController`` — las tres rutas de descarga.
    El cableado de URLs es del orquestador (ver el docstring del módulo)."""

    def download_invoice_attachments(self, request, attachment_ids):
        """≙ ``GET /account/download_invoice_attachments/<attachments>`` —
        un adjunto directo, o el zip de varios (parcial declarado — ver el
        docstring del módulo)."""
        attachments = list(IrAttachment.objects.filter(
            pk__in=list(attachment_ids)))
        assert all(attachment.res_id
                   and attachment.res_model == 'account.move'
                   for attachment in attachments)
        if len(attachments) == 1:
            attachment = attachments[0]
            content = _attachment_raw(attachment)
            headers = _get_headers(attachment.name, attachment.mimetype,
                                   content)
            return _make_response(content, headers)
        # ≙ la rama multi-adjunto: el nombre por factura única
        # (_get_invoice_report_filename) no está portado — fallback.
        filename = _('invoices') + '.zip'
        content = _build_zip_from_data([
            {'filename': attachment.name,
             'content': _attachment_raw(attachment)}
            for attachment in attachments
        ])
        headers = _get_headers(filename, 'zip', content)
        return _make_response(content, headers)

    def download_invoice_documents_filetype(self, request, invoice_ids,
                                             filetype, allow_fallback=True):
        """≙ ``GET /account/download_invoice_documents/<invoices>/<filetype>``
        — delegación bloqueada por ``_get_invoice_legal_documents``/``_all``
        de ``account.move`` (ver la tabla del módulo); la mecánica de
        respuesta (uno directo / varios en zip) ya queda escrita."""
        invoices = list(AccountMove.objects.filter(pk__in=list(invoice_ids)))
        docs_data = []
        for invoice in invoices:
            if filetype == 'all' and (doc_data := invoice._get_invoice_legal_documents_all(allow_fallback=allow_fallback)):
                docs_data += doc_data
            elif doc_data := invoice._get_invoice_legal_documents(filetype, allow_fallback=allow_fallback):
                if (errors := doc_data.get('errors')) and len(invoices) == 1:
                    raise UserError(_('Error while creating XML:\n- %s')
                                    % '\n- '.join(errors))
                docs_data.append(doc_data)
        if len(docs_data) == 1:
            doc_data = docs_data[0]
            headers = _get_headers(doc_data['filename'],
                                   doc_data['filetype'], doc_data['content'])
            return _make_response(doc_data['content'], headers)
        if len(docs_data) > 1:
            zip_content = _build_zip_from_data(docs_data)
            headers = _get_headers(_('invoices') + '.zip', 'zip', zip_content)
            return _make_response(zip_content, headers)
        return None

    def download_move_attachments(self, request, move_ids):
        """≙ ``GET /account/download_move_attachments/<moves>`` — el zip de
        exportación por asiento. Delegación bloqueada por
        ``_get_move_zip_export_docs`` de ``account.move`` (ver la tabla del
        módulo); ``rename_duplicates`` se porta verbatim."""

        def rename_duplicates(docs):
            seen = {}
            for doc in docs:
                name = doc["filename"]
                if name not in seen:
                    seen[name] = 0
                else:
                    seen[name] += 1
                    base, *ext = name.rsplit('.', 1)
                    new_name = f"{base} ({seen[name]})" + (
                        f".{ext[0]}" if ext else "")
                    doc["filename"] = new_name
                    seen[new_name] = 0
            return docs

        moves = list(AccountMove.objects.filter(pk__in=list(move_ids)))
        if docs_data := list(chain.from_iterable(
                move._get_move_zip_export_docs() for move in moves)):
            docs_data = rename_duplicates(docs_data)
            zip_content = _build_zip_from_data(docs_data)
            headers = _get_headers(_('Invoices') + '.zip', 'zip', zip_content)
            return _make_response(zip_content, headers)
        return None
