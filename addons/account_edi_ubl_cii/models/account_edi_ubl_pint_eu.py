r"""``account.edi.ubl_pint_eu`` — la capa PINT-EU (PINT + CEN EN 16931).

Adaptación de ``odoo19c: addons/account_edi_ubl_cii/models/account_edi_ubl_pint_eu.py``
(``odoo-tools@622ddc2a``, LGPL-3, 137 líneas, 6 métodos) — atribución y aviso
de licencia preservados (DEC-KX-03).

Cobertura: **6 de 6 portados, 0 bloqueados.**

Herencia múltiple: la fuente declara
``_inherit = ['account.edi.ubl_pint', 'account.edi.ubl_cen_en16931']`` y aquí
las bases van **en ese mismo orden**, que es lo que preserva la precedencia.
La linearización C3 resultante es válida y se verificó al escribir el archivo
(ambas ramas convergen en ``AccountEdiUBL`` → ``AccountEdiCommon``).

Familia ``account_edi_ubl_cii``: clase Python plana con ``@classmethod`` en vez
de ``AbstractModel``, y ``_inherit`` materializado como herencia de Python. La
convención, sus dos consecuencias y la tabla de piezas ausentes que bloquean el
lado de registros están declaradas una sola vez en
``account_edi_common.py`` — no se repiten aquí.
"""
from addons.account.tools import dict_to_xml
from tools.translate import _

from .account_edi_common import EUROPEAN_ECONOMIC_AREA_COUNTRY_CODES
from .account_edi_ubl_cen_en16931 import AccountEdiUBLCenEn16931
from .account_edi_ubl_pint import AccountEdiUBLPint


class AccountEdiUBLPintEU(AccountEdiUBLPint, AccountEdiUBLCenEn16931):
    _name = "account.edi.ubl_pint_eu"
    _inherit = ['account.edi.ubl_pint', 'account.edi.ubl_cen_en16931']
    _description = "UBL PINT-EU Layer"

    @classmethod
    def _ubl_add_customization_id_node(cls, vals):
        super()._ubl_add_customization_id_node(vals)
        if cls._is_document(vals, 'invoice', 'credit_note'):
            vals['document_node']['cbc:CustomizationID']['_text'] = 'urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0'
        elif cls._is_document(vals, 'self_invoice', 'self_credit_note'):
            vals['document_node']['cbc:CustomizationID']['_text'] = 'urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:selfbilling:3.0'

    @classmethod
    def _ubl_add_profile_id_node(cls, vals):
        super()._ubl_add_profile_id_node(vals)
        if cls._is_document(vals, 'invoice', 'credit_note'):
            vals['document_node']['cbc:ProfileID']['_text'] = 'urn:fdc:peppol.eu:2017:poacc:billing:01:1.0'
        elif cls._is_document(vals, 'self_invoice', 'self_credit_note'):
            vals['document_node']['cbc:ProfileID']['_text'] = 'urn:fdc:peppol.eu:2017:poacc:selfbilling:01:1.0'

    @classmethod
    def _ubl_get_delivery_node_from_delivery_address(cls, vals):
        # Intracom delivery inside European area.
        node = super()._ubl_get_delivery_node_from_delivery_address(vals)

        if cls._is_document(vals, 'invoice', 'self_invoice', 'credit_note', 'self_credit_note'):
            invoice = vals['invoice']
            customer = vals['customer']
            supplier = vals['supplier']
            if (
                customer.country_id.code in EUROPEAN_ECONOMIC_AREA_COUNTRY_CODES
                and supplier.country_id.code in EUROPEAN_ECONOMIC_AREA_COUNTRY_CODES
                and supplier.country_id != customer.country_id
            ):
                node['cbc:ActualDeliveryDate']['_text'] = invoice.invoice_date

        return node

    @classmethod
    def _ubl_add_payment_means_nodes(cls, vals):
        super()._ubl_add_payment_means_nodes(vals)

        if cls._is_document(vals, 'invoice', 'self_invoice', 'credit_note', 'self_credit_note'):
            # [DK] In Denmark payment code 30 is not allowed. Hardcode to 1 ("unknown")
            # as we cannot deduce this information from the invoice.
            customer = vals['customer'].commercial_partner_id
            if customer.country_code == 'DK':
                nodes = vals['document_node']['cac:PaymentMeans']
                for node in nodes:
                    node['cbc:PaymentMeansCode']['_text'] = 1
                    node['cbc:PaymentMeansCode']['name'] = 'unknown'

    @classmethod
    def _ubl_add_billing_reference_nodes(cls, vals):
        super()._ubl_add_billing_reference_nodes(vals)

        if cls._is_document(vals, 'credit_note'):
            # [NL-R-001] For suppliers in the Netherlands, if the document is a creditnote, the document MUST
            # contain an invoice reference (cac:BillingReference/cac:InvoiceDocumentReference/cbc:ID)
            credit_note = vals['invoice']
            nodes = vals['document_node']['cac:BillingReference']
            if (
                vals['supplier'].country_code == 'NL'
                and credit_note.ref
                and not nodes
            ):
                nodes.append({
                    'cac:InvoiceDocumentReference': {
                        'cbc:ID': {'_text': credit_note.ref},
                    }
                })

    @classmethod
    def _export_document_node_constraints(cls, vals):
        constraints = super()._export_document_node_constraints(vals)
        document_node = vals['document_node']
        nsmap = document_node['_nsmap']

        if cls._is_document(vals, 'invoice', 'self_invoice', 'credit_note', 'self_credit_note'):
            # PEPPOL-EN16931-R003: A buyer reference or purchase order reference MUST be provided.
            if (
                not vals['document_node']['cbc:BuyerReference']
                and not vals['document_node']['cac:OrderReference']
            ):
                constraints['cen_en16931_buyer_reference_and_order_reference_must_not_be_both_present'] = _("A buyer reference or purchase order reference must be provided.")

        if (
            cls._is_document(vals, 'invoice', 'credit_note')
            and document_node['cac:AccountingSupplierParty']['cac:Party']['cac:PostalAddress']['cac:Country']['cbc:IdentificationCode']['_text'] == 'NL'
        ):

            # [NL-R-002] For suppliers in the Netherlands the supplier's address (cac:AccountingSupplierParty/cac:Party
            # /cac:PostalAddress) MUST contain street name (cbc:StreetName), city (cbc:CityName) and post code (cbc:PostalZone)
            constraints.update({
                'nl_r_002_street': cls._check_required_fields(vals['supplier'], 'street'),
                'nl_r_002_zip': cls._check_required_fields(vals['supplier'], 'zip'),
                'nl_r_002_city': cls._check_required_fields(vals['supplier'], 'city'),
            })

            # [NL-R-003] For suppliers in the Netherlands, the legal entity identifier MUST be either a
            # KVK or OIN number (schemeID 0106 or 0190)
            if all(node['cbc:CompanyID'] not in ('0106', '0190') for node in document_node['cac:AccountingSupplierParty']['cac:Party']['cac:PartyLegalEntity']):
                constraints['nl_r_003'] = cls._check_required_fields(vals['supplier'], 'vat')

            # [NL-R-007] For suppliers in the Netherlands, the supplier MUST provide a means of payment
            # (cac:PaymentMeans) if the payment is from customer to supplier
            if not document_node['cac:PaymentMeans']:
                constraints['nl_r_007'] = cls._check_required_fields(vals['invoice'], 'partner_bank_id')

            if document_node['cac:AccountingCustomerParty']['cac:Party']['cac:PostalAddress']['cac:Country']['cbc:IdentificationCode']['_text'] == 'NL':
                # [NL-R-004] For suppliers in the Netherlands, if the customer is in the Netherlands, the customer
                # address (cac:AccountingCustomerParty/cac:Party/cac:PostalAddress) MUST contain the street name
                # (cbc:StreetName), the city (cbc:CityName) and post code (cbc:PostalZone)
                constraints.update({
                    'nl_r_004_street': cls._check_required_fields(vals['customer'], 'street'),
                    'nl_r_004_city': cls._check_required_fields(vals['customer'], 'city'),
                    'nl_r_004_zip': cls._check_required_fields(vals['customer'], 'zip'),
                })

                # [NL-R-005] For suppliers in the Netherlands, if the customer is in the Netherlands,
                # the customer's legal entity identifier MUST be either a KVK or OIN number (schemeID 0106 or 0190)
                if all(node['cbc:CompanyID'] not in ('0106', '0190') for node in document_node['cac:AccountingCustomerParty']['cac:Party']['cac:PartyLegalEntity']):
                    constraints['nl_r_005'] = cls._check_required_fields(vals['customer'], 'vat')

        if (
            cls._is_document(vals, 'credit_note')
            and document_node['cac:AccountingSupplierParty']['cac:Party']['cac:PostalAddress']['cac:Country']['cbc:IdentificationCode']['_text'] == 'NL'
            and all(
                dict_to_xml(bill_ref_node['cac:InvoiceDocumentReference']['cbc:ID'], nsmap=nsmap, tag='cbc:ID') is None
                for bill_ref_node in document_node['cac:BillingReference']
            )
        ):
            # [NL-R-001] For suppliers in the Netherlands, if the document is a creditnote, the document MUST contain
            # an invoice reference.
            constraints['nl_r_001'] = cls._check_required_fields(vals['invoice'], 'ref')

        return constraints
