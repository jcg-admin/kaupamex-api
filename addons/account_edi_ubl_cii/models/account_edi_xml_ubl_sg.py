r"""``account.edi.xml.ubl_sg`` — SG BIS Billing 3.0 (Singapur).

Adaptación de ``odoo19c: addons/account_edi_ubl_cii/models/account_edi_xml_ubl_sg.py``
(``odoo-tools@622ddc2a``, LGPL-3, 84 líneas, 8 métodos) — atribución y aviso de
licencia preservados (DEC-KX-03).

Cobertura: **8 de 8 portados, 0 bloqueados.**

Documentación del formato: https://www.peppolguide.sg/billing/bis/

Familia ``account_edi_ubl_cii``: clase Python plana con ``@classmethod`` en vez
de ``AbstractModel``, y ``_inherit`` materializado como herencia de Python. La
convención, sus dos consecuencias y la tabla de piezas ausentes que bloquean el
lado de registros están declaradas una sola vez en
``account_edi_common.py`` — no se repiten aquí.
"""
from .account_edi_xml_ubl_bis3 import AccountEdiXmlUBLBIS3


class AccountEdiXmlUbl_Sg(AccountEdiXmlUBLBIS3):
    _name = 'account.edi.xml.ubl_sg'
    _inherit = ["account.edi.xml.ubl_bis3"]
    _description = "SG BIS Billing 3.0"

    """
    Documentation: https://www.peppolguide.sg/billing/bis/
    """

    # -------------------------------------------------------------------------
    # EXPORT
    # -------------------------------------------------------------------------

    @classmethod
    def _export_invoice_filename(cls, invoice):
        return f"{invoice.name.replace('/', '_')}_sg.xml"

    # -------------------------------------------------------------------------
    # EXPORT: Templates
    # -------------------------------------------------------------------------

    @classmethod
    def _get_customization_id(cls, process_type='billing'):
        if process_type == 'billing':
            return 'urn:cen.eu:en16931:2017#conformant#urn:fdc:peppol.eu:2017:poacc:billing:international:sg:3.0'

    @classmethod
    def _ubl_default_tax_category_grouping_key(cls, base_line, tax_data, vals, currency):
        # EXTENDS account.edi.xml.ubl_bis3
        grouping_key = super()._ubl_default_tax_category_grouping_key(base_line, tax_data, vals, currency)
        if not grouping_key:
            return

        grouping_key['tax_exemption_reason'] = None
        grouping_key['tax_exemption_reason_code'] = None

        # For reference: https://www.peppolguide.sg/billing/bis/#_gst_category_codes
        if not tax_data or tax_data['tax'].amount == 0.0:
            grouping_key['tax_category_code'] = 'ZR'
        else:
            grouping_key['tax_category_code'] = 'SR'

        return grouping_key

    @classmethod
    def _ubl_get_line_allowance_charge_discount_node(cls, vals, discount_values):
        # EXTENDS account.edi.xml.ubl_bis3
        discount_node = super()._ubl_get_line_allowance_charge_discount_node(vals, discount_values)
        discount_node['cbc:AllowanceChargeReason'] = None
        discount_node['cbc:MultiplierFactorNumeric'] = None
        discount_node['cbc:BaseAmount'] = None
        return discount_node

    @classmethod
    def _ubl_add_tax_currency_code_node(cls, vals):
        # OVERRIDE account.edi.xml.ubl_bis3
        cls._ubl_add_tax_currency_code_node_empty(vals)

    @classmethod
    def _ubl_tax_totals_node_grouping_key(cls, base_line, tax_data, vals, currency):
        # EXTENDS account.edi.xml.ubl_bis3
        tax_total_keys = super()._ubl_tax_totals_node_grouping_key(base_line, tax_data, vals, currency)

        company_currency = vals['company'].currency_id
        if (
            tax_total_keys['tax_total_key']
            and company_currency != vals['currency']
            and tax_total_keys['tax_total_key']['currency'] == company_currency
        ):
            tax_total_keys['tax_total_key'] = None

        return tax_total_keys

    @classmethod
    def _ubl_add_customization_id_node(cls, vals):
        # EXTENDS account.edi.xml.ubl_bis3
        super()._ubl_add_customization_id_node(vals)
        vals['document_node']['cbc:CustomizationID']['_text'] = 'urn:cen.eu:en16931:2017#conformant#urn:fdc:peppol.eu:2017:poacc:billing:international:sg:3.0'

    @classmethod
    def _ubl_add_payment_means_nodes(cls, vals):
        # EXTENDS account.edi.xml.ubl_bis3
        super()._ubl_add_payment_means_nodes(vals)
        # https://www.peppolguide.sg/billing/bis/#_payment_means_information
        vals['document_node']['cac:PaymentMeans'][0]['cbc:PaymentMeansCode'] = {
            '_text': 54,
            'name': 'Credit Card',
        }
