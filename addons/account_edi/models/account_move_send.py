r"""``account.move.send`` — lo que ``account_edi`` le cuelga (≙ ``_inherit``).

Adaptación de ``odoo19c: account_edi/models/account_move_send.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3, 19 líneas)
— atribución y aviso de licencia preservados (DEC-KX-03).

Dos símbolos, los 2 portados
================================

.. list-table::
   :header-rows: 1
   :widths: 35 15 50

   * - Símbolo
     - Estado
     - Nota
   * - ``_get_mail_attachment_from_doc``
     - portado
     - nuevo — ``@classmethod``, sin colisión (ver ``chain_method``)
   * - ``_get_invoice_extra_attachments``
     - portado
     - **combinación**, no relevo — ``combine=extend_list`` preserva el
       orden de la referencia (primero lo de ``account``, después lo de
       ``account_edi``), ver ``orm/method_chain.py``

``sudo()`` — divergencia uniforme del módulo
==================================================

``doc.sudo().attachment_id`` de la referencia → ``doc.attachment`` directo,
mismo criterio que el resto de este dominio (``account_edi_document.py``,
``ir_attachment.py``): sin ACL de campo que saltarse en este puerto.
"""
from addons.account.models.account_move_send import AccountMoveSend
from addons.base.models.ir_attachment import IrAttachment
from orm.method_chain import chain_method, extend_list


def _get_mail_attachment_from_doc(cls, doc):
    """≙ ``_get_mail_attachment_from_doc`` (``odoo19c: :5-9``).

    Nuevo — sin contraparte previa en ``AccountMoveSend`` (medido:
    ``grep -n "_get_mail_attachment_from_doc"
    addons/account/models/account_move_send.py`` → 0 hits), así que
    ``chain_method`` lo instala tal cual (rama ``previous is None``).
    """
    attachment = doc.attachment
    if attachment and attachment.res_model and attachment.res_id:
        return attachment
    return None


def _get_invoice_extra_attachments_edi(cls, move):
    """≙ la parte de ``account_edi`` de ``_get_invoice_extra_attachments``
    (``odoo19c: :11-19``): los adjuntos de cada documento EDI del asiento
    que YA están vinculados a un registro (``_get_mail_attachment_from_doc``
    filtra los que no). Se combina con lo que ``account`` ya aporta vía
    ``combine=extend_list`` (ver el docstring del módulo).
    """
    extra = []
    for doc in move.edi_document_ids.all():
        attachment = cls._get_mail_attachment_from_doc(doc)
        if attachment is not None:
            extra.append(attachment)
    return extra


def apply_account_edi_extensions():
    """≙ ``_inherit = 'account.move.send'`` de ``account_edi``.

    ``chain_method`` en vez de ``setattr``: aunque hoy sea la única
    extensión de ``_get_invoice_extra_attachments`` en el árbol, encadenar
    preserva la de ``account`` si otro addon la instala primero
    (:ref:`h-api-364`).
    """
    chain_method(AccountMoveSend, '_get_mail_attachment_from_doc',
                 classmethod(_get_mail_attachment_from_doc))
    chain_method(AccountMoveSend, '_get_invoice_extra_attachments',
                 classmethod(_get_invoice_extra_attachments_edi),
                 combine=extend_list)
