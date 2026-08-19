r"""``account.edi.xml.ubl_a_nz`` — A-NZ BIS Billing 3.0 (Australia / Nueva Zelanda).

Adaptación de ``odoo19c: addons/account_edi_ubl_cii/models/account_edi_xml_ubl_a_nz.py``
(``odoo-tools@622ddc2a``, LGPL-3, 114 líneas, 9 métodos) — atribución y aviso
de licencia preservados (DEC-KX-03).

Cobertura: **9 de 9 portados, 0 bloqueados.**

Familia ``account_edi_ubl_cii``: clase Python plana con ``@classmethod`` en vez
de ``AbstractModel``, y ``_inherit`` materializado como herencia de Python. La
convención, sus dos consecuencias y la tabla de piezas ausentes que bloquean el
lado de registros están declaradas una sola vez en
``account_edi_common.py`` — no se repiten aquí.
"""
from .account_edi_xml_ubl_bis3 import AccountEdiXmlUBLBIS3


class AccountEdiXmlUbl_A_Nz(AccountEdiXmlUBLBIS3):
    _name = 'account.edi.xml.ubl_a_nz'
    _inherit = ["account.edi.xml.ubl_bis3"]
    _description = "A-NZ BIS Billing 3.0"

    """
    * Documentation: https://github.com/A-NZ-PEPPOL/A-NZ-PEPPOL-BIS-3.0/tree/master/Specifications
    """

    # -------------------------------------------------------------------------
    # EXPORT
    # -------------------------------------------------------------------------

    @classmethod
    def _export_invoice_filename(cls, invoice):
        return f"{invoice.name.replace('/', '_')}_a_nz.xml"

    # -------------------------------------------------------------------------
    # EXPORT: Templates
    # -------------------------------------------------------------------------

    @classmethod
    def _get_customization_id(cls, process_type='billing'):
        if process_type == 'billing':
            return 'urn:cen.eu:en16931:2017#conformant#urn:fdc:peppol.eu:2017:poacc:billing:international:aunz:3.0'

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
        # OVERRIDE
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
        vals['document_node']['cbc:CustomizationID']['_text'] = 'urn:cen.eu:en16931:2017#conformant#urn:fdc:peppol.eu:2017:poacc:billing:international:aunz:3.0'

    @classmethod
    def _ubl_add_party_endpoint_id_node(cls, vals):
        # EXTENDS
        super()._ubl_add_party_endpoint_id_node(vals)
        partner = vals['party_vals']['partner']
        commercial_partner = partner.commercial_partner_id

        if commercial_partner.country_code == 'AU' and commercial_partner.vat:
            vat = commercial_partner.vat.replace(" ", "")
            vals['party_node']['cbc:EndpointID']['_text'] = vat
        elif commercial_partner.country_code == 'NZ' and commercial_partner.company_registry:
            vals['party_node']['cbc:EndpointID']['_text'] = commercial_partner.company_registry

    @classmethod
    def _ubl_add_party_tax_scheme_nodes(cls, vals):
        # EXTENDS
        super()._ubl_add_party_tax_scheme_nodes(vals)
        partner = vals['party_vals']['partner']
        commercial_partner = partner.commercial_partner_id

        if (
            (commercial_partner.country_code == 'AU' and commercial_partner.vat)
            or (commercial_partner.country_code == 'NZ' and commercial_partner.company_registry)
        ):
            vals['party_node']['cac:PartyTaxScheme'] = [{
                'cbc:CompanyID': {
                    '_text': vals['party_node']['cbc:EndpointID']['_text'],
                    'schemeID': None,
                },
                'cac:TaxScheme': {
                    'cbc:ID': {'_text': 'GST'},
                },
            }]

    @classmethod
    def _ubl_add_party_legal_entity_nodes(cls, vals):
        # EXTENDS
        super()._ubl_add_party_legal_entity_nodes(vals)
        partner = vals['party_vals']['partner']
        commercial_partner = partner.commercial_partner_id

        if commercial_partner.country_code == 'AU' and commercial_partner.vat:
            vals['party_node']['cac:PartyLegalEntity'] = [{
                'cbc:RegistrationName': {'_text': commercial_partner.name},
                'cbc:CompanyID': {
                    '_text': vals['party_node']['cbc:EndpointID']['_text'],
                    'schemeID': '0151',
                },
            }]
        elif commercial_partner.country_code == 'NZ' and commercial_partner.company_registry:
            vals['party_node']['cac:PartyLegalEntity'] = [{
                'cbc:RegistrationName': {'_text': commercial_partner.name},
                'cbc:CompanyID': {
                    '_text': vals['party_node']['cbc:EndpointID']['_text'],
                    'schemeID': '0088',
                },
            }]
