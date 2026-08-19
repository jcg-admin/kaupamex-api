r"""``account.edi.xml.ubl_nl`` — SI-UBL 2.0 (NLCIUS).

Adaptación de ``odoo19c: addons/account_edi_ubl_cii/models/account_edi_xml_ubl_nlcius.py``
(``odoo-tools@622ddc2a``, LGPL-3, 121 líneas, 10 métodos) — atribución y aviso
de licencia preservados (DEC-KX-03).

Cobertura: **10 de 10 portados, 0 bloqueados.**

Familia ``account_edi_ubl_cii``: clase Python plana con ``@classmethod`` en vez
de ``AbstractModel``, y ``_inherit`` materializado como herencia de Python. La
convención, sus dos consecuencias y la tabla de piezas ausentes que bloquean el
lado de registros están declaradas una sola vez en
``account_edi_common.py`` — no se repiten aquí.
"""
from .account_edi_xml_ubl_bis3 import AccountEdiXmlUBLBIS3


class AccountEdiXmlUbl_Nl(AccountEdiXmlUBLBIS3):
    _name = 'account.edi.xml.ubl_nl'
    _inherit = ["account.edi.xml.ubl_bis3"]
    _description = "SI-UBL 2.0 (NLCIUS)"

    """
    SI-UBL 2.0 (NLCIUS) and UBL Bis 3 are 2 different formats used in the Netherlands.
    (source: https://github.com/peppolautoriteit-nl/publications/tree/master/NLCIUS-PEPPOLBIS-Differences)
    NLCIUS defines a set of rules
    (source: https://www.softwarepakketten.nl/wiki_uitleg/60&bronw=7/Nadere_specificaties_EN_16931_1_norm_voor_de_Europese_kernfactuur.htm)
    Fortunately, some of these rules are already present in UBL Bis 3, but some are missing.

    For instance, Bis 3 states that the customizationID should be
    "urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0".
    while in NLCIUS:
    "urn:cen.eu:en16931:2017#compliant#urn:fdc:nen.nl:nlcius:v1.0".

    Bis 3 and NLCIUS are thus incompatible. Hence, the two separate formats and the additional rules in this file.

    The trick is to understand which rules are only NLCIUS specific and which are applied to the Bis 3 format.
    """

    # -------------------------------------------------------------------------
    # EXPORT
    # -------------------------------------------------------------------------

    @classmethod
    def _export_invoice_filename(cls, invoice):
        return f"{invoice.name.replace('/', '_')}_nlcius.xml"

    # -------------------------------------------------------------------------
    # EXPORT: Templates
    # -------------------------------------------------------------------------

    @classmethod
    def _get_customization_id(cls, process_type='billing'):
        if process_type == 'billing':
            return 'urn:cen.eu:en16931:2017#compliant#urn:fdc:nen.nl:nlcius:v1.0'

    @classmethod
    def _ubl_default_tax_category_grouping_key(cls, base_line, tax_data, vals, currency):
        # EXTENDS account.edi.xml.ubl_bis3
        grouping_key = super()._ubl_default_tax_category_grouping_key(base_line, tax_data, vals, currency)
        if not grouping_key:
            return

        grouping_key['tax_exemption_reason_code'] = None
        return grouping_key

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
    def _ubl_get_line_allowance_charge_discount_node(cls, vals, discount_values):
        # EXTENDS account.edi.xml.ubl_bis3
        discount_node = super()._ubl_get_line_allowance_charge_discount_node(vals, discount_values)
        discount_node['cbc:AllowanceChargeReasonCode'] = None
        discount_node['cbc:MultiplierFactorNumeric'] = None
        discount_node['cbc:BaseAmount'] = None
        return discount_node

    @classmethod
    def _ubl_add_accounting_supplier_party_identification_nodes(cls, vals):
        # EXTENDS account.edi.xml.ubl_bis3
        super()._ubl_add_accounting_supplier_party_identification_nodes(vals)
        nodes = vals['party_node']['cac:PartyIdentification']
        partner = vals['party_vals']['partner']
        commercial_partner = partner.commercial_partner_id

        if commercial_partner.peppol_endpoint:
            nodes.append({
                'cbc:ID': {
                    '_text': commercial_partner.peppol_endpoint,
                    'schemeID': None,
                },
            })

    @classmethod
    def _ubl_add_accounting_customer_party_identification_nodes(cls, vals):
        # EXTENDS account.edi.xml.ubl_bis3
        super()._ubl_add_accounting_customer_party_identification_nodes(vals)
        partner = vals['party_vals']['partner']
        commercial_partner = partner.commercial_partner_id

        if (
            commercial_partner.country_code == 'NL'
            and commercial_partner.peppol_endpoint
        ):
            vals['party_node']['cac:PartyIdentification'] = [{
                'cbc:ID': {
                    '_text': commercial_partner.peppol_endpoint,
                    'schemeID': commercial_partner.peppol_eas if commercial_partner.peppol_eas in ('0106', '0190') else None,
                },
            }]

    @classmethod
    def _ubl_add_customization_id_node(cls, vals):
        # EXTENDS account.edi.xml.ubl_bis3
        super()._ubl_add_customization_id_node(vals)
        vals['document_node']['cbc:CustomizationID']['_text'] = 'urn:cen.eu:en16931:2017#compliant#urn:fdc:nen.nl:nlcius:v1.0'

    @classmethod
    def _ubl_add_payment_means_nodes(cls, vals):
        # EXTENDS account.edi.xml.ubl_bis3
        super()._ubl_add_payment_means_nodes(vals)
        for node in vals['document_node']['cac:PaymentMeans']:
            # [BR-NL-29] The use of a payment means text (cac:PaymentMeans/cbc:PaymentMeansCode/@name) is not recommended
            node['cbc:PaymentMeansCode']['name'] = None
            node['cbc:PaymentMeansCode']['listID'] = None
