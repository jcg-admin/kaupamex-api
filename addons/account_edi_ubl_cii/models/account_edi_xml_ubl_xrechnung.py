r"""``account.edi.xml.ubl_de`` — BIS3 DE (XRechnung).

Adaptación de ``odoo19c: addons/account_edi_ubl_cii/models/account_edi_xml_ubl_xrechnung.py``
(``odoo-tools@622ddc2a``, LGPL-3, 125 líneas, 11 métodos) — atribución y aviso
de licencia preservados (DEC-KX-03).

Cobertura: **11 de 11 portados, 0 bloqueados.**

Familia ``account_edi_ubl_cii``: clase Python plana con ``@classmethod`` en vez
de ``AbstractModel``, y ``_inherit`` materializado como herencia de Python. La
convención, sus dos consecuencias y la tabla de piezas ausentes que bloquean el
lado de registros están declaradas una sola vez en
``account_edi_common.py`` — no se repiten aquí.
"""
from .account_edi_xml_ubl_bis3 import AccountEdiXmlUBLBIS3


class AccountEdiXmlUbl_De(AccountEdiXmlUBLBIS3):
    _name = 'account.edi.xml.ubl_de'
    _inherit = ["account.edi.xml.ubl_bis3"]
    _description = "BIS3 DE (XRechnung)"

    # -------------------------------------------------------------------------
    # EXPORT
    # -------------------------------------------------------------------------

    @classmethod
    def _export_invoice_filename(cls, invoice):
        return f"{invoice.name.replace('/', '_')}_xrechnung.xml"

    @classmethod
    def _export_invoice_constraints(cls, invoice, vals):
        # EXTENDS account.edi.xml.ubl_bis3
        constraints = super()._export_invoice_constraints(invoice, vals)

        constraints.update({
            'bis3_de_supplier_telephone_required': cls._check_required_fields(vals['supplier'], ['phone']),
            'bis3_de_supplier_electronic_mail_required': cls._check_required_fields(vals['supplier'], 'email'),
        })

        return constraints

    # -------------------------------------------------------------------------
    # EXPORT: Templates
    # -------------------------------------------------------------------------

    @classmethod
    def _get_customization_id(cls, process_type='billing'):
        if process_type == 'billing':
            return 'urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0'

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
        vals['document_node']['cbc:CustomizationID']['_text'] = 'urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0'

    @classmethod
    def _ubl_add_buyer_reference_node(cls, vals):
        # EXTENDS account.edi.xml.ubl_bis3
        super()._ubl_add_buyer_reference_node(vals)
        node = vals['document_node']['cbc:BuyerReference']

        customer = vals['customer'].commercial_partner_id
        if customer.peppol_eas == "0204":
            node['_text'] = customer.peppol_endpoint

        if not node['_text']:
            node['_text'] = 'N/A'

    @classmethod
    def _ubl_add_party_endpoint_id_node(cls, vals):
        # EXTENDS account.edi.xml.ubl_bis3
        super()._ubl_add_party_endpoint_id_node(vals)
        partner = vals['party_vals']['partner']

        if not vals['party_node']['cbc:EndpointID']['_text'] and partner.email:
            vals['party_node']['cbc:EndpointID'] = {
                '_text': partner.email,
                'schemeID': 'EM'
            }

    @classmethod
    def _ubl_add_party_tax_scheme_nodes(cls, vals):
        # EXTENDS account.edi.xml.ubl_bis3
        super()._ubl_add_party_tax_scheme_nodes(vals)
        nodes = vals['party_node']['cac:PartyTaxScheme']
        partner = vals['party_vals']['partner']
        commercial_partner = partner.commercial_partner_id

        if (
            not nodes
            and commercial_partner.peppol_eas
        ):
            nodes.append({
                'cbc:CompanyID': {'_text': None},
                'cac:TaxScheme': {
                    'cbc:ID': {'_text': commercial_partner.peppol_eas},
                },
            })

    @classmethod
    def _ubl_add_party_legal_entity_nodes(cls, vals):
        # EXTENDS account.edi.xml.ubl_bis3
        super()._ubl_add_party_legal_entity_nodes(vals)
        nodes = vals['party_node']['cac:PartyLegalEntity']
        partner = vals['party_vals']['partner']
        commercial_partner = partner.commercial_partner_id

        if (
            not nodes
            and commercial_partner.name
        ):
            nodes.append({
                'cbc:RegistrationName': {'_text': commercial_partner.name},
                'cbc:CompanyID': {
                    '_text': None,
                    'schemeID': None,
                },
            })

    @classmethod
    def _ubl_get_line_allowance_charge_discount_node(cls, vals, discount_values):
        # EXTENDS account.edi.xml.ubl_bis3
        discount_node = super()._ubl_get_line_allowance_charge_discount_node(vals, discount_values)
        discount_node['cbc:AllowanceChargeReason'] = None
        discount_node['cbc:MultiplierFactorNumeric'] = None
        discount_node['cbc:BaseAmount'] = None
        return discount_node
