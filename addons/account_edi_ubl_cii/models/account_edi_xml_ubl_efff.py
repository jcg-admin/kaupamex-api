r"""``account.edi.xml.ubl_efff`` — E-FFF (Bélgica).

Adaptación de ``odoo19c: addons/account_edi_ubl_cii/models/account_edi_xml_ubl_efff.py``
(``odoo-tools@622ddc2a``, LGPL-3, 20 líneas, 1 método) — atribución y aviso de
licencia preservados (DEC-KX-03).

Cobertura: **1 de 1 portado, 0 bloqueados.** El único método compone el nombre
del archivo con la convención oficial belga; lee ``company_id.partner_id.
commercial_partner_id.vat``, que es la cadena de la referencia y se conserva
verbatim — cuando ``account.move`` gane su mitad *factura*, funciona sin tocar
este archivo.

Familia ``account_edi_ubl_cii``: clase Python plana con ``@classmethod`` en vez
de ``AbstractModel``, y ``_inherit`` materializado como herencia de Python. La
convención, sus dos consecuencias y la tabla de piezas ausentes que bloquean el
lado de registros están declaradas una sola vez en
``account_edi_common.py`` — no se repiten aquí.
"""
import re

from .account_edi_xml_ubl_20 import AccountEdiXmlUBL20


class AccountEdiXmlUbl_Efff(AccountEdiXmlUBL20):
    _name = 'account.edi.xml.ubl_efff'
    _inherit = ["account.edi.xml.ubl_20"]
    _description = "E-FFF (BE)"

    # -------------------------------------------------------------------------
    # EXPORT
    # -------------------------------------------------------------------------

    @classmethod
    def _export_invoice_filename(cls, invoice):
        # official naming convention
        vat = invoice.company_id.partner_id.commercial_partner_id.vat
        return 'efff_%s%s%s.xml' % (vat or '', '_' if vat else '', re.sub(r'[\W_]', '', invoice.name))
