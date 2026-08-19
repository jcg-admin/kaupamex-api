"""``base.document.layout`` — la extensión de ``account`` (QR, RFC y cuenta).

Adaptación de Odoo ``addons/account/wizard/base_document_layout.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3 —
atribución y aviso de licencia preservados, DEC-KX-03).

La referencia es una **extensión** (``_inherit``, sin ``_name`` propio) del
asistente de membrete que ``web`` declara — y que este árbol ya porta en
``addons/web/models/base_document_layout.py`` (clase ``BaseDocumentLayout``,
patrón classmethods sin tabla). Esta clase la extiende por herencia normal
de Python, que es como el árbol resuelve ``_inherit`` intra-carga.

Diez símbolos de la referencia (4 campos + 6 defs) — el desglose
=================================================================

==============================  ===========================================
Símbolo de la referencia         Qué pasa aquí
==============================  ===========================================
``from_invoice`` (campo)         NO — flag técnico del diálogo (la vista lo
                                  usa para el iframe de previsualización);
                                  ningún método lo lee.
``qr_code`` (related)            NO — related a ``company.qr_code``
                                  (mostrar QR en documentos), campo no
                                  portado en ``res.company``; su único
                                  consumo (``_get_render_information``)
                                  está además bloqueado (abajo).
``vat`` (related)                PORTADO — parámetro/lectura de
                                  ``company.vat`` (property ya portada en
                                  ``base: res_company.py``, delegación al
                                  partner).
``account_number`` (compute)     PORTADO — ``_compute_account_number`` /
                                  ``_inverse_account_number``
``document_layout_save``         NO — su super (``web``) está entre los 7
                                  declarados ausentes del porte de
                                  ``web/models/base_document_layout.py``, y
                                  su cuerpo propio marca un paso
                                  ``onboarding.onboarding.step`` por xmlid
                                  (data XML de onboarding no portada) y
                                  ajusta ``dialog_size`` (cliente Odoo).
                                  Bloqueado por ese super.
``_get_preview_template``        NO — ídem (elige plantilla QWeb del
                                  iframe; QWeb no es superficie de este
                                  árbol).
``_get_render_information``      NO — ídem (contexto de render QWeb).
``_compute_account_number``      PORTADO
``_compute_preview``             NO — override vacío que sólo añade
                                  ``@api.depends`` al compute del super,
                                  declarado ausente allá.
``_inverse_account_number``      PORTADO (con la creación directa de la
                                  cuenta bancaria — ver abajo)
==============================  ===========================================

Divergencia declarada — ``_find_or_create_bank_account``
=========================================================

La rama "el partner no tiene cuentas" de ``_inverse_account_number`` llama
``res.partner.bank._find_or_create_bank_account`` (helper de ``base`` no
portado; medido: 0 hits en ``src/addons/base/models/res_partner_bank.py``).
El material sí existe (``ResPartnerBank`` con ``acc_number`` /
``allow_out_payment``), así que la creación se hace directa —
``porte-completo-no-parcial.md``: se construye, no se excusa. El flag
``allow_company_account_creation`` de la referencia gobierna la variante
"cuenta de la empresa"; aquí la cuenta se crea siempre del partner del
wizard, que es el caso que este flujo ejerce.
"""
from addons.base.models import ResPartnerBank
from addons.web.models.base_document_layout import BaseDocumentLayout as WebBaseDocumentLayout


class BaseDocumentLayout(WebBaseDocumentLayout):
    """≙ la extensión de ``base.document.layout`` que hace ``account``.
    Sin ``_name`` propio, igual que la fuente."""

    _inherit = 'base.document.layout'

    class Meta:
        abstract = True
        managed = False

    @classmethod
    def _compute_account_number(cls, partner):
        """≙ ``_compute_account_number`` — el número de la primera cuenta
        bancaria del partner (``bank_ids`` de la referencia ≡
        ``bank_accounts`` aquí), o cadena vacía."""
        bank = partner.bank_accounts.first() if partner is not None else None
        if bank is not None:
            return bank.acc_number or ''
        return ''

    @classmethod
    def _inverse_account_number(cls, partner, account_number, company=None):
        """≙ ``_inverse_account_number`` — edita la primera cuenta del
        partner, o crea una nueva (creación directa — ver la divergencia
        declarada del módulo).

        El baile ``allow_out_payment = False → acc_number → True`` de la
        referencia existe porque cambiar el número debe re-autorizar los
        pagos salientes; se conserva.
        """
        if partner is None or not account_number:
            return None
        bank = partner.bank_accounts.first()
        if bank is not None:
            if bank.acc_number != account_number:
                bank.allow_out_payment = False
                bank.acc_number = account_number
                bank.allow_out_payment = True
                bank.save()
            return bank
        # ``company`` se acepta por paridad de firma con la referencia;
        # ``ResPartnerBank`` no declara FK a empresa (la cuenta es del
        # partner), así que no se persiste.
        return ResPartnerBank.objects.create(
            acc_number=account_number,
            partner=partner,
            allow_out_payment=True,
        )
