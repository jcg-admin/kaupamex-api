"""``account.autopost.bills.wizard`` — el aviso "¿automatizar este proveedor?".

Adaptación de Odoo ``addons/account/wizard/account_autopost_bills_wizard.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3 —
atribución y aviso de licencia preservados, DEC-KX-03).

``TransientModel`` → clase con classmethods, no tabla — mismo patrón que
``account_debit_note.AccountDebitNoteWizard`` (ver su docstring): el estado
del wizard lo pasa el llamador como argumentos.

Seis símbolos de la referencia — tres se portan, tres se declaran (medido)
===========================================================================

===============================  =========================================
Símbolo de la referencia          Qué pasa aquí
===============================  =========================================
``partner_id`` (campo)            PORTADO — parámetro ``partner``
``partner_name`` (related)        NO — sólo etiqueta del diálogo Odoo
                                   (``related='partner_id.name'``), sin
                                   lector de negocio.
``nb_unmodified_bills`` (campo)   NO — sólo texto informativo del diálogo
                                   ("N facturas sin modificar"); ningún
                                   método lo consume.
``action_automate_partner``       PORTADO
``action_ask_later``              PORTADO
``action_never_automate_partner`` PORTADO
===============================  =========================================

Bloqueado por ``res_partner.autopost_bills``
=============================================

Las tres acciones escriben ``partner.autopost_bills`` — un campo que la
referencia declara en su extensión de ``res.partner`` dentro del MISMO addon
(``odoo19c: addons/account/models/partner.py``), y que este árbol aún no
porta (medido: ``grep -rn "autopost_bills" src/ addons/`` → sólo menciones
en prosa). Los métodos se portan con la escritura verbatim: mientras el
campo no exista, ``save(update_fields=['autopost_bills'])`` falla en voz
alta (``ValueError`` de Django) en vez de no-opear en silencio. Se cierra
solo cuando el porte de la extensión de ``res.partner`` de ``account``
aterrice — no requiere tocar este archivo.
"""
from orm.models_transient import TransientModel


class AccountAutopostBillsWizard(TransientModel):
    """≙ ``account.autopost.bills.wizard`` — tras publicar N facturas de un
    proveedor sin editarlas, la referencia ofrece automatizar su publicación.
    """

    _name = 'account.autopost.bills.wizard'
    _description = "Autopost Bills Wizard"

    class Meta:
        abstract = True
        managed = False

    @classmethod
    def _write_autopost(cls, partner, value):
        """La escritura común de las tres acciones (helper propio, no de la
        referencia — allá el ``for wizard in self`` la repite inline)."""
        partner.autopost_bills = value
        partner.save(update_fields=['autopost_bills'])
        return partner

    @classmethod
    def action_automate_partner(cls, partner):
        """≙ ``action_automate_partner`` — publicar siempre en automático."""
        return cls._write_autopost(partner, 'always')

    @classmethod
    def action_ask_later(cls, partner):
        """≙ ``action_ask_later`` — volver a preguntar la próxima vez."""
        return cls._write_autopost(partner, 'ask')

    @classmethod
    def action_never_automate_partner(cls, partner):
        """≙ ``action_never_automate_partner`` — nunca automatizar."""
        return cls._write_autopost(partner, 'never')
