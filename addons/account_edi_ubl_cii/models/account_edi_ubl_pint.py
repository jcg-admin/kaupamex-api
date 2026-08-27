r"""``account.edi.ubl_pint`` — la capa PINT (Peppol INTernational) sobre UBL.

Adaptación de ``odoo19c: addons/account_edi_ubl_cii/models/account_edi_ubl_pint.py``
(``odoo-tools@622ddc2a``, LGPL-3, 421 líneas, 29 métodos) — atribución y aviso
de licencia preservados (DEC-KX-03).

Cobertura: 29 de 29 presentes — **27 portados, 2 bloqueados**
=============================================================

* ``_ubl_add_notes_nodes_all_invoices`` — bloqueado: agrega importes con
  ``env['account.tax']`` (envoltura de base-lines, 0 hits) y formatea con
  ``formatLang``.
* ``_init_invoice_export_values`` — bloqueado por la misma envoltura.

``NON_BREAKING_SPACE`` (``odoo19c: odoo/tools/misc.py:125``) no existe en
``src/tools/misc.py``; se declara aquí como constante de módulo con el mismo
valor (``\N{NO-BREAK SPACE}``). Su hogar correcto sería ``src/tools/misc.py``,
fuera del write-set de este pase.

Familia ``account_edi_ubl_cii``: clase Python plana con ``@classmethod`` en vez
de ``AbstractModel``, y ``_inherit`` materializado como herencia de Python. La
convención, sus dos consecuencias y la tabla de piezas ausentes que bloquean el
lado de registros están declaradas una sola vez en
``account_edi_common.py`` — no se repiten aquí.
"""
from .account_edi_common import FloatFmt, _blocked
from .account_edi_ubl import AccountEdiUBL

#: ≙ ``odoo.tools.misc.NON_BREAKING_SPACE`` — ver el docstring del módulo.
NON_BREAKING_SPACE = '\N{NO-BREAK SPACE}'


class AccountEdiUBLPint(AccountEdiUBL):
    _name = "account.edi.ubl_pint"
    _inherit = 'account.edi.ubl'
    _description = "UBL PINT"

    # -------------------------------------------------------------------------
    # EXPORT: NODES
    # -------------------------------------------------------------------------

    @classmethod
    def _ubl_add_invoice_type_code_node(cls, vals):
        super()._ubl_add_invoice_type_code_node(vals)

        if cls._is_document(vals, 'invoice'):
            vals['document_node']['cbc:InvoiceTypeCode']['_text'] = 380
        elif cls._is_document(vals, 'self_invoice'):
            vals['document_node']['cbc:InvoiceTypeCode']['_text'] = 389

    @classmethod
    def _ubl_add_credit_note_type_code_node(cls, vals):
        super()._ubl_add_credit_note_type_code_node(vals)

        if cls._is_document(vals, 'credit_note'):
            vals['document_node']['cbc:CreditNoteTypeCode']['_text'] = 381
        elif cls._is_document(vals, 'self_credit_note'):
            vals['document_node']['cbc:CreditNoteTypeCode']['_text'] = 261

    @classmethod
    def _ubl_add_notes_nodes_all_invoices(cls, vals):
        """≙ ``_ubl_add_notes_nodes_all_invoices`` (odoo19c: :32-71) — **bloqueado**: la envoltura de base-lines de account.tax no se porta (0 hits) y formatLang no existe."""
        _blocked("_ubl_add_notes_nodes_all_invoices", "la envoltura de base-lines de account.tax no se porta (0 hits) y formatLang no existe")

    @classmethod
    def _ubl_add_notes_nodes(cls, vals):
        # [ibr-sr-51]-Note (ibt-022) MUST occur maximum once
        super()._ubl_add_notes_nodes(vals)

        if cls._is_document(vals, 'invoice', 'credit_note', 'self_invoice', 'self_credit_note'):
            cls._ubl_add_notes_nodes_all_invoices(vals)

    @classmethod
    def _ubl_add_delivery_nodes(cls, vals):
        # [ibr-107]-Deliver to information (ibg-13) MUST occur maximum once.
        super()._ubl_add_delivery_nodes(vals)

        if cls._is_document(vals, 'invoice', 'credit_note', 'self_invoice', 'self_credit_note'):
            document_node = vals['document_node']
            if document_node['cac:Delivery']:
                document_node['cac:Delivery'] = document_node['cac:Delivery'][0]
            else:
                document_node['cac:Delivery'] = None

    @classmethod
    def _ubl_add_document_currency_code_node(cls, vals):
        # The currency in which the invoice is issued and in which all monetary amounts are expressed.
        # [ibr-005]-An Invoice MUST have an Invoice currency code (ibt-005).
        # [ibr-cl-04]-Invoice currency code (ibt-005) MUST be coded using ISO code list 4217 alpha-3
        super()._ubl_add_document_currency_code_node(vals)
        vals['document_node']['cbc:DocumentCurrencyCode']['_text'] = vals['currency'].name

    @classmethod
    def _ubl_add_tax_currency_code_node(cls, vals):
        # The currency used for TAX accounting and reporting purposes as accepted or required in the country of the Seller.
        # [ibr-077]-Tax accounting currency code (ibt-006) MUST be different from invoice currency code (ibt-005) when provided.
        # [ibr-cl-05]-Tax currency code (ibt-006) MUST be coded using ISO code list 4217 alpha-3
        super()._ubl_add_tax_currency_code_node(vals)
        company_currency = vals['company'].currency_id
        if vals['document_node']['cbc:DocumentCurrencyCode']['_text'] != company_currency.name:
            vals['document_node']['cbc:TaxCurrencyCode']['_text'] = company_currency.name

    @classmethod
    def _ubl_add_buyer_reference_node(cls, vals):
        super()._ubl_add_buyer_reference_node(vals)

        customer = vals['customer']
        if customer_ref := customer.commercial_partner_id.ref:
            vals['document_node']['cbc:BuyerReference']['_text'] = customer_ref

    @classmethod
    def _ubl_add_billing_reference_nodes(cls, vals):
        # A group of business terms providing information on one or more preceding Invoices.
        # [ibr-055]-Each Preceding Invoice reference (ibg-03) MUST contain a Preceding Invoice reference (ibt-025).
        # [ibr-sr-06]-Preceding invoice reference (ibt-025) MUST occur maximum once
        super()._ubl_add_billing_reference_nodes(vals)

        if cls._is_document(vals, 'credit_note', 'self_credit_note'):
            credit_note = vals['invoice']
            payment_term_lines = credit_note.line_ids.filtered(lambda line: line.account_id.account_type == 'asset_receivable')
            preceding_invoice_names = [
                preceding_invoice_name
                for preceding_invoice_name in (
                    payment_term_lines
                    .matched_credit_ids.credit_move_id.move_id
                    .mapped('name')
                )
                if preceding_invoice_name and preceding_invoice_name != '/'
            ]

            nodes = vals['document_node']['cac:BillingReference']
            for preceding_invoice_name in preceding_invoice_names:
                nodes.append({
                    'cac:InvoiceDocumentReference': {
                        'cbc:ID': {'_text': preceding_invoice_name},
                    }
                })

    @classmethod
    def _ubl_get_partner_address_node(cls, vals, partner):
        node = super()._ubl_get_partner_address_node(vals, partner)
        node['cbc:CountrySubentityCode'] = None
        node['cac:Country']['cbc:Name'] = None
        return node

    @classmethod
    def _ubl_add_party_endpoint_id_node(cls, vals):
        super()._ubl_add_party_endpoint_id_node(vals)
        partner = vals['party_vals']['partner']
        commercial_partner = partner.commercial_partner_id
        if commercial_partner.peppol_endpoint and commercial_partner.peppol_eas:
            vals['party_node']['cbc:EndpointID']['_text'] = commercial_partner.peppol_endpoint
            vals['party_node']['cbc:EndpointID']['schemeID'] = commercial_partner.peppol_eas

    @classmethod
    def _ubl_add_party_identification_nodes(cls, vals):
        super()._ubl_add_party_identification_nodes(vals)
        cls._ubl_add_party_identification_nodes_iso_6523_icd(vals)

        nodes = vals['party_node']['cac:PartyIdentification']
        partner = vals['party_vals']['partner']
        commercial_partner = partner.commercial_partner_id
        country_code = commercial_partner.country_code

        if not nodes and commercial_partner.ref and country_code != 'DK':  # DK-R-013
            nodes.append({
                'cbc:ID': {
                    '_text': commercial_partner.ref,
                    'schemeID': None,
                },
            })

    @classmethod
    def _ubl_add_party_tax_scheme_nodes(cls, vals):
        super()._ubl_add_party_tax_scheme_nodes(vals)
        if vals['no_party_tax_scheme']:
            return

        super()._ubl_add_party_tax_scheme_nodes_vat_gst(vals)

        partner = vals['party_vals']['partner']
        commercial_partner = partner.commercial_partner_id
        nodes = vals['party_node']['cac:PartyTaxScheme']
        if not nodes and commercial_partner.peppol_endpoint and commercial_partner.peppol_eas:
            # TaxScheme based on partner's EAS/Endpoint.
            nodes.append({
                'cbc:CompanyID': {'_text': commercial_partner.peppol_endpoint},
                'cac:TaxScheme': {
                    'cbc:ID': {'_text': commercial_partner.peppol_eas},
                },
            })

    @classmethod
    def _ubl_add_party_legal_entity_nodes(cls, vals):
        super()._ubl_add_party_legal_entity_nodes(vals)
        cls._ubl_add_party_legal_entity_nodes_iso_6523_icd(vals)

    @classmethod
    def _ubl_add_accounting_supplier_party_tax_scheme_nodes(cls, vals):
        super()._ubl_add_accounting_supplier_party_tax_scheme_nodes(vals)
        nodes = vals['party_node']['cac:PartyTaxScheme']
        partner = vals['party_vals']['partner']
        commercial_partner = partner.commercial_partner_id
        country_code = commercial_partner.country_code

        if country_code == 'NO':
            # [NO-R-002] For Norwegian suppliers, most invoice issuers are required to append
            # "Foretaksregisteret" to their invoice.
            nodes.append({
                'cbc:CompanyID': {'_text': "Foretaksregisteret"},
                'cac:TaxScheme': {
                    'cbc:ID': {'_text': "TAX"},
                },
            })
        elif country_code == 'SE':
            # [SE-R-005] For Swedish suppliers, when using Seller tax registration identifier,
            # 'Godkänd för F-skatt' must be stated
            nodes.append({
                'cbc:CompanyID': {'_text': "GODKÄND FÖR F-SKATT"},
                'cac:TaxScheme': {
                    'cbc:ID': {'_text': "TAX"},
                },
            })

    @classmethod
    def _ubl_add_delivery_party_endpoint_id_node(cls, vals):
        pass

    @classmethod
    def _ubl_add_delivery_party_identification_nodes(cls, vals):
        pass

    @classmethod
    def _ubl_add_delivery_party_postal_address_node(cls, vals):
        pass

    @classmethod
    def _ubl_add_delivery_party_tax_scheme_nodes(cls, vals):
        pass

    @classmethod
    def _ubl_add_delivery_party_legal_entity_nodes(cls, vals):
        pass

    @classmethod
    def _ubl_add_delivery_party_contact_node(cls, vals):
        pass

    @classmethod
    def _ubl_get_payment_means_payee_financial_account_institution_branch_node_from_partner_bank(cls, vals, partner_bank):
        node = super()._ubl_get_payment_means_payee_financial_account_institution_branch_node_from_partner_bank(vals, partner_bank)
        if node:
            node['cbc:ID']['schemeID'] = None
            node['cac:FinancialInstitution'] = None
        return node

    @classmethod
    def _ubl_add_payment_means_nodes_all_invoices(cls, vals):
        invoice = vals['invoice']
        nodes = vals['document_node']['cac:PaymentMeans']

        if invoice.move_type == 'out_invoice':
            if invoice.partner_bank_id:
                payment_means_code, payment_means_name = 30, 'credit transfer'
            else:
                payment_means_code, payment_means_name = 'ZZZ', 'mutually defined'
        else:
            payment_means_code, payment_means_name = 57, 'standing agreement'

        partner_bank = invoice.partner_bank_id
        payment_means_node = {
            'cbc:PaymentMeansCode': {
                '_text': payment_means_code,
                'name': payment_means_name,
            },
            'cbc:PaymentID': {'_text': invoice.payment_reference or invoice.name},
        }

        if partner_bank:
            payment_means_node['cac:PayeeFinancialAccount'] = cls._ubl_get_payment_means_payee_financial_account_node_from_partner_bank(vals, partner_bank)
        else:
            payment_means_node['cac:PayeeFinancialAccount'] = None

        nodes.append(payment_means_node)

    @classmethod
    def _ubl_add_payment_means_nodes(cls, vals):
        super()._ubl_add_payment_means_nodes(vals)

        if cls._is_document(vals, 'invoice', 'credit_note', 'self_invoice', 'self_credit_note'):
            cls._ubl_add_payment_means_nodes_all_invoices(vals)

    @classmethod
    def _ubl_get_tax_subtotal_node(cls, vals, tax_subtotal):
        # This override is a fix for the taxes engine.
        # Currently the taxes computation is not perfect for PINT and then,
        # produce discrepancies between the tax's base amount and the sum of base amount of lines.
        node = super()._ubl_get_tax_subtotal_node(vals, tax_subtotal)

        # [BR-S-08]/[BR-E-08]/[BR-Z-08]/... cac:TaxSubtotal -> cbc:TaxableAmount should be
        # computed based on the cbc:LineExtensionAmount of each line linked to the tax.
        # This applies to all tax category codes (S, E, Z, AE, etc.) as each has a
        # corresponding BR-*-08 schematron rule requiring this consistency.
        currency = tax_subtotal['currency']
        corresponding_line_node_amounts = [
            line_node['cbc:LineExtensionAmount']['_text']
            for tax_category_node in node['cac:TaxCategory']
            for line_key in ('cac:InvoiceLine', 'cac:CreditNoteLine')
            for line_node in vals['document_node'].get(line_key, [])
            for line_node_tax_category_node in line_node['cac:Item']['cac:ClassifiedTaxCategory']
            if (
                    line_node_tax_category_node['cbc:ID']['_text'] == tax_category_node['cbc:ID']['_text']
                    and line_node_tax_category_node['cbc:Percent']['_text'] == tax_category_node['cbc:Percent']['_text']
                    and line_node_tax_category_node['_currency'] == tax_category_node['_currency']
            )
            ] + [
            -allowance_node['cbc:Amount']['_text']
            for tax_category_node in node['cac:TaxCategory']
            for allowance_node in vals['document_node']['cac:AllowanceCharge']
            if allowance_node['cbc:ChargeIndicator']['_text'] == 'false'
            for allowance_node_tax_category_node in allowance_node['cac:TaxCategory']
            if (
                    allowance_node_tax_category_node['cbc:ID']['_text'] == tax_category_node['cbc:ID']['_text']
                    and allowance_node_tax_category_node['cbc:Percent']['_text'] == tax_category_node['cbc:Percent']['_text']
                    and allowance_node_tax_category_node['_currency'] == tax_category_node['_currency']
            )
            ] + [
            allowance_node['cbc:Amount']['_text']
            for tax_category_node in node['cac:TaxCategory']
            for allowance_node in vals['document_node']['cac:AllowanceCharge']
            if allowance_node['cbc:ChargeIndicator']['_text'] == 'true'
            for allowance_node_tax_category_node in allowance_node['cac:TaxCategory']
            if (
                    allowance_node_tax_category_node['cbc:ID']['_text'] == tax_category_node['cbc:ID']['_text']
                    and allowance_node_tax_category_node['cbc:Percent']['_text'] == tax_category_node['cbc:Percent']['_text']
                    and allowance_node_tax_category_node['_currency'] == tax_category_node['_currency']
            )
        ]
        if corresponding_line_node_amounts:
            node['cbc:TaxableAmount'] = {
                '_text': FloatFmt(sum(corresponding_line_node_amounts), min_dp=currency.decimal_places),
                'currencyID': currency.name,
            }

        # Percent is not reported in TaxSubtotal
        node['cbc:Percent']['_text'] = None

        return node

    @classmethod
    def _ubl_tax_totals_node_grouping_key(cls, base_line, tax_data, vals, currency):
        tax_total_keys = super()._ubl_tax_totals_node_grouping_key(base_line, tax_data, vals, currency)

        # WithholdingTaxTotal is not allowed.
        # Instead, withholding tax amounts are reported as a PrepaidAmount.
        if tax_total_keys['tax_total_key'] and tax_total_keys['tax_total_key']['is_withholding']:
            tax_total_keys['tax_total_key'] = None

        # In case of multi-currencies, there will be 2 TaxTotals but the one expressed in
        # foreign currency must not have any TaxSubtotal.
        company_currency = vals['company'].currency_id
        if (
            tax_total_keys['tax_subtotal_key']
            and company_currency != vals['currency']
            and tax_total_keys['tax_subtotal_key']['currency'] == company_currency
        ):
            tax_total_keys['tax_subtotal_key'] = None

        return tax_total_keys

    @classmethod
    def _ubl_add_legal_monetary_total_payable_rounding_amount_node(cls, vals):
        super()._ubl_add_legal_monetary_total_payable_rounding_amount_node(vals)
        currency = vals['currency']
        node = vals['legal_monetary_total_node']

        if cls._is_document(vals, 'invoice', 'credit_note', 'self_invoice', 'self_credit_note'):
            tax_withholding_amount = vals['_ubl_values']['tax_withholding_amount']

            # WithholdingTaxTotal is not allowed.
            # Instead, withholding tax amounts are reported as a PrepaidAmount.
            # Since the UBL layer is putting the difference between TaxInclusiveAmount and the total
            # amount of the base_lines in PayableRoundingAmount, the withholding tax amount ends there.
            # Let's remove them since they are accounted in PrepaidAmount.
            if tax_withholding_amount:
                payable_rounding_amount_node = node['cbc:PayableRoundingAmount']
                payable_rounding_amount = (payable_rounding_amount_node['_text'] or 0.0) + tax_withholding_amount
                if currency.is_zero(payable_rounding_amount):
                    payable_rounding_amount_node['_text'] = None
                    payable_rounding_amount_node['currencyID'] = None
                else:
                    payable_rounding_amount_node['_text'] = FloatFmt(payable_rounding_amount, min_dp=currency.decimal_places)
                    payable_rounding_amount_node['currencyID'] = currency.name

    @classmethod
    def _ubl_add_legal_monetary_total_prepaid_payable_amount_node(cls, vals, in_foreign_currency=True):
        super()._ubl_add_legal_monetary_total_prepaid_payable_amount_node(vals, in_foreign_currency=in_foreign_currency)
        currency = vals['currency_id'] if in_foreign_currency else vals['company_currency']
        node = vals['legal_monetary_total_node']

        if cls._is_document(vals, 'invoice', 'credit_note', 'self_invoice', 'self_credit_note'):
            node['cbc:PrepaidAmount']['_text'] = FloatFmt(
                node['cbc:PrepaidAmount']['_text']
                # WithholdingTaxTotal is not allowed.
                # Instead, withholding tax amounts are reported as a PrepaidAmount.
                # Suppose an invoice of 1000 with a tax 21% +100 -100.
                # The super will compute a PrepaidAmount or 0.0 and a PayableAmount or 1000.
                # This extension is there to increase PrepaidAmount to 210 and PayableAmount to 1210.
                + vals['_ubl_values']['tax_withholding_amount'],
                min_dp=currency.decimal_places,
            )

    @classmethod
    def _init_invoice_export_values(cls, invoice):
        """≙ ``_init_invoice_export_values`` (odoo19c: :396-421) — **bloqueado**: la envoltura de base-lines de account.tax no se porta (0 hits)."""
        _blocked("_init_invoice_export_values", "la envoltura de base-lines de account.tax no se porta (0 hits)")
