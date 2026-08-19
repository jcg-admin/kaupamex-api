r"""``account.move.send.wizard`` — lo que ``account_edi_ubl_cii`` le cuelga.

Adaptación de ``odoo19c: addons/account_edi_ubl_cii/wizard/account_move_send_wizard.py``
(``odoo-tools@622ddc2a``, LGPL-3, 21 líneas) — atribución y aviso de licencia
preservados (DEC-KX-03).

Un símbolo, portado
====================

``_compute_attachments_not_supported`` — llena el hook que
``account/wizard/account_move_send_wizard.py:345-348`` deja vacío (``{}``
verbatim, con el comentario *"el hook que las localizaciones EDI llenan"*).
Éste es el addon que lo llena, así que el porte cierra la pareja.

Dos divergencias, las dos por la forma que ``account`` ya fijó en este árbol
=============================================================================

1. **``@classmethod`` sin ``self``.** El método de la referencia es de
   instancia y recorre ``for wizard in self`` (recordset). Aquí
   ``AccountMoveSendWizard._compute_attachments_not_supported`` ya es un
   ``@classmethod`` **sin argumentos** que devuelve ``{}``; para encadenarse
   con ``chain_method`` hay que respetar esa firma, así que los dos datos que
   la fuente lee del wizard (``invoice_edi_format`` y
   ``mail_attachments_widget``) pasan a ser **parámetros opcionales**. Con los
   valores por defecto el método devuelve ``{}``, que es exactamente lo que
   ``account`` devolvía: ningún llamador existente cambia de comportamiento.
2. **``@api.depends('invoice_edi_format', 'mail_attachments_widget')``** no
   tiene contraparte: en este árbol el cómputo lo dispara el llamador, no un
   grafo de dependencias del ORM. Misma divergencia que
   ``account/wizard/account_move_send_wizard.py`` ya declaró para el resto de
   sus ``_compute_*``.

``_get_ubl_available_attachments`` vive en ``models/account_move_send.py`` de
este mismo addon (portado allí) y ``_get_ubl_cii_formats_info`` lo cuelga
``models/res_partner.py`` sobre ``base.ResPartner``; los dos se invocan desde
aquí, con imports al top (``no-lazy-imports.md``) y sin ciclo — ninguno de los
dos módulos importa este.
"""
from orm.method_chain import chain_method
from tools.translate import _

from addons.account.wizard.account_move_send_wizard import AccountMoveSendWizard
from addons.base.models.res_partner import ResPartner

from ..models.account_move_send import _get_ubl_available_attachments


def _compute_attachments_not_supported(cls, invoice_edi_format=None,
                                       mail_attachments_widget=None):
    """≙ ``_compute_attachments_not_supported`` (``odoo19c: :6-21``).

    Devuelve ``{id_adjunto: motivo}`` para los adjuntos manuales que el formato
    EDI elegido **no** puede embeber. Ver las dos divergencias en el docstring
    del módulo.
    """
    formats_info = ResPartner._get_ubl_cii_formats_info()
    if not formats_info.get(invoice_edi_format):
        return {}

    _attachments_to_embed, attachments_not_supported = \
        _get_ubl_available_attachments(
            cls, mail_attachments_widget, invoice_edi_format)
    return {
        attachment.id: _("Unsupported file type via %s", invoice_edi_format)
        for attachment in attachments_not_supported
    }


def apply_account_edi_ubl_cii_send_wizard_extensions():
    """Cuelga sobre ``account.move.send.wizard`` el único método del archivo —
    ≙ ``_inherit``. La llama ``AccountEdiUblCiiConfig.ready()``."""
    chain_method(AccountMoveSendWizard, '_compute_attachments_not_supported',
                 classmethod(_compute_attachments_not_supported))


__all__ = ['apply_account_edi_ubl_cii_send_wizard_extensions']
