r"""``ir.attachment`` — lo que ``account_edi`` le cuelga (≙ ``_inherit``).

Adaptación de ``odoo19c: account_edi/models/ir_attachment.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3, 16 líneas)
— atribución y aviso de licencia preservados (DEC-KX-03).

Un símbolo, portado — ``@api.ondelete`` → señal ``pre_delete``
=====================================================================

La referencia decora ``_unlink_except_government_document`` con
``@api.ondelete(at_uninstall=False)``: el ORM de Odoo lo invoca
automáticamente ANTES de cada ``unlink()`` y bloquea el borrado si el método
levanta. Este ORM (Django) no tiene ese decorador; el punto de intercepción
equivalente — que cubre tanto ``instance.delete()`` como
``QuerySet.delete()`` en lote, porque Django desactiva su optimización de
fast-delete en cuanto hay un receptor conectado — es la señal
``django.db.models.signals.pre_delete``. Mismo patrón que
``account_payment/models/account_journal.py::_unlink_except_linked_to_
payment_provider`` ya usa para su propio ``@api.ondelete``.

``sudo()`` — divergencia uniforme con el resto de este dominio: la búsqueda
de documentos EDI vinculados se hace sin elevar privilegios (sin ACL a nivel
de campo en este puerto, ver ``account_edi_document.py``).
"""
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from addons.account_edi.models.account_edi_document import AccountEdiDocument
from addons.base.models.ir_attachment import IrAttachment
from exceptions import UserError
from tools.translate import _


@receiver(pre_delete, sender=IrAttachment,
          dispatch_uid='account_edi.unlink_except_government_document')
def _unlink_except_government_document(sender, instance, **kwargs):
    """≙ ``_unlink_except_government_document`` (``odoo19c: account_edi/
    models/ir_attachment.py:8-15``): no se borra un adjunto que sea un
    documento EDI ya enviado al gobierno a través de un formato con
    web-service."""
    linked_documents = AccountEdiDocument.objects.filter(
        attachment_id=instance,
    ).select_related('edi_format_id')
    linked_with_web_services = [
        d for d in linked_documents if d.edi_format_id._needs_web_services()
    ]
    if linked_with_web_services:
        raise UserError(_(
            "You can't unlink an attachment being an EDI document sent to "
            "the government."))


def apply_account_edi_extensions():
    """≙ ``_inherit = 'ir.attachment'`` de ``account_edi``.

    El receptor ``@receiver`` se conecta al importar este módulo; esta
    función se define por uniformidad con ``AccountEdiConfig.ready()``.
    """
    return None
