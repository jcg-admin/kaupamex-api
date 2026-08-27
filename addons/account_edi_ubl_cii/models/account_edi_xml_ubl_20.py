r"""``account.edi.xml.ubl_20`` — el generador y lector de UBL 2.0.

Adaptación de ``odoo19c: addons/account_edi_ubl_cii/models/account_edi_xml_ubl_20.py``
(``odoo-tools@622ddc2a``, LGPL-3, 1319 líneas, 88 métodos) — atribución y aviso
de licencia preservados (DEC-KX-03).

Cobertura: 88 de 88 presentes — **76 portados, 12 bloqueados**
===============================================================

Los 12 bloqueados son una sola causa con tres caras:

* **nueve** agregan importes por impuesto con
  ``env['account.tax']._aggregate_base_line[s]_tax_details`` /
  ``_aggregate_base_lines_aggregated_values`` — la envoltura de base-lines que
  ``account/models/account_tax.py:82-90`` declara **no portada** (0 hits);
  uno de ellos (``_add_document_line_price_nodes``) además necesita
  ``env['decimal.precision'].precision_get``, que tampoco existe;
* **uno** (``_import_fill_invoice``) es la puerta del importador y necesita
  ``env['account.incoterms']`` más los idiomas ``Command``/``fields.Date`` del
  ORM de la referencia;
* **dos** (``add_invoice_optional_nodes`` y su gemelo de línea) recorren
  ``record._fields`` y hacen ``isinstance(record, models.Model)`` —
  introspección del ORM de la referencia; este árbol usa ``Meta`` de Django y
  no expone ``_fields``. Son los que inyectan los campos de estudio
  ``x_studio_peppol_*`` (ver ``tools/ubl_20_optional_fields.py``).

Los 76 portados operan sobre ``dict`` y se portan verbatim.

Familia ``account_edi_ubl_cii``: clase Python plana con ``@classmethod`` en vez
de ``AbstractModel``, y ``_inherit`` materializado como herencia de Python. La
convención, sus dos consecuencias y la tabla de piezas ausentes que bloquean el
lado de registros están declaradas una sola vez en
``account_edi_common.py`` — no se repiten aquí.
"""
from lxml import etree

from addons.account.tools import dict_to_xml
from tools.float_utils import float_is_zero
from tools.mail import html2plaintext

from ..tools import CreditNote, DebitNote, Invoice
from ..tools.ubl_20_optional_fields import (
    PEPPOL_CREDIT_NOTE_OPTIONAL_FIELDS,
    PEPPOL_CREDIT_NOTE_OPTIONAL_LINE_FIELDS,
    PEPPOL_INVOICE_OPTIONAL_FIELDS,
    PEPPOL_INVOICE_OPTIONAL_LINE_FIELDS,
)
from .account_edi_common import EAS_MAPPING, FloatFmt, _blocked
from .account_edi_ubl import AccountEdiUBL


UBL_NAMESPACES = {
    'cbc': "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    'cac': "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
}


class AccountEdiXmlUBL20(AccountEdiUBL):
    _name = "account.edi.xml.ubl_20"
    _inherit = 'account.edi.ubl'
    _description = "UBL 2.0"

    @classmethod
    def _find_value(cls, xpath, tree, nsmap=False):
        # EXTENDS account.edi.common
        return super()._find_value(xpath, tree, UBL_NAMESPACES)

    # -------------------------------------------------------------------------
    # EXPORT
    # -------------------------------------------------------------------------

    @classmethod
    def _export_invoice_filename(cls, invoice):
        return f"{invoice.name.replace('/', '_')}_ubl_20.xml"

    @classmethod
    def _get_document_type_code_node(cls, invoice, invoice_data):
        """Returns the `DocumentTypeCode` node tag"""
        # To be overriden by custom format if required
        pass

    @classmethod
    def _export_invoice(cls, invoice):
        """ Generates an UBL 2.0 xml for a given invoice. """
        # 1. Validate the structure of the taxes
        cls._validate_taxes(invoice.invoice_line_ids.tax_ids)

        # 2. Instantiate the XML builder
        vals = {'invoice': invoice.with_context(lang=invoice.partner_id.lang)}
        document_node = cls._get_invoice_node(vals)

        # 3. Run constraints
        vals['document_node'] = document_node
        template = cls._get_document_template(vals)
        nsmap = document_node['_nsmap'] = cls._get_document_nsmap(vals)
        errors = [constraint for constraint in cls._export_invoice_constraints(invoice, vals).values() if constraint]

        # 4. Render the XML
        xml_content = dict_to_xml(document_node, nsmap=nsmap, template=template)

        # 5. Format the XML
        return etree.tostring(xml_content, xml_declaration=True, encoding='UTF-8'), set(errors)

    # -------------------------------------------------------------------------
    # EXPORT: Helpers
    # -------------------------------------------------------------------------

    @classmethod
    def _get_document_template(cls, vals):
        return {
            'invoice': Invoice,
            'credit_note': CreditNote,
            'debit_note': DebitNote,
        }[vals['document_type']]

    @classmethod
    def _get_document_nsmap(cls, vals):
        return {
            None: {
                'invoice': "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
                'credit_note': "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2",
                'debit_note': "urn:oasis:names:specification:ubl:schema:xsd:DebitNote-2",
                'order': "urn:oasis:names:specification:ubl:schema:xsd:Order-2",
            }[vals['document_type']],
            'cac': "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
            'cbc': "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
            'ext': "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
        }

    @classmethod
    def format_float(cls, amount, precision_digits=2):
        return FloatFmt(amount, precision_digits)

    @classmethod
    def _get_tags_for_document_type(cls, vals):
        return {
            'document_type_code': {
                'invoice': 'cbc:InvoiceTypeCode',
                'credit_note': 'cbc:CreditNoteTypeCode',
                'debit_note': None,
                'order': 'cbc:OrderTypeCode',
            }[vals['document_type']],
            'monetary_total': {
                'invoice': 'cac:LegalMonetaryTotal',
                'credit_note': 'cac:LegalMonetaryTotal',
                'debit_note': 'cac:RequestedMonetaryTotal',
                'order': 'cac:AnticipatedMonetaryTotal',
            }[vals['document_type']],
            'document_line': {
                'invoice': 'cac:InvoiceLine',
                'credit_note': 'cac:CreditNoteLine',
                'debit_note': 'cac:DebitNoteLine',
                'order': 'cac:OrderLine',
            }[vals['document_type']],
            'line_quantity': {
                'invoice': 'cbc:InvoicedQuantity',
                'credit_note': 'cbc:CreditedQuantity',
                'debit_note': 'cbc:DebitedQuantity',
                'order': 'cbc:Quantity',
            }[vals['document_type']]
        }

    @classmethod
    def _is_document_allowance_charge(cls, base_line):
        """ Whether the base line should be treated as a document-level AllowanceCharge. """
        return base_line['special_type'] == 'early_payment'

    # -------------------------------------------------------------------------
    # EXPORT: account.move specific templates
    # -------------------------------------------------------------------------

    @classmethod
    def _get_invoice_node(cls, vals):
        cls._add_invoice_config_vals(vals)
        cls._add_invoice_base_lines_vals(vals)
        cls._add_invoice_currency_vals(vals)
        cls._add_invoice_tax_grouping_function_vals(vals)
        cls._setup_base_lines(vals)
        cls._add_invoice_monetary_totals_vals(vals)

        document_node = {}
        cls._add_invoice_header_nodes(document_node, vals)
        cls._add_invoice_accounting_supplier_party_nodes(document_node, vals)
        cls._add_invoice_accounting_customer_party_nodes(document_node, vals)
        cls._add_invoice_seller_supplier_party_nodes(document_node, vals)

        if vals['document_type'] == 'invoice':
            cls._add_invoice_delivery_nodes(document_node, vals)
            cls._add_invoice_payment_means_nodes(document_node, vals)
            cls._add_invoice_payment_terms_nodes(document_node, vals)

        cls._add_invoice_line_nodes(document_node, vals)
        cls._add_invoice_allowance_charge_nodes(document_node, vals)
        cls._add_invoice_exchange_rate_nodes(document_node, vals)
        cls._add_invoice_tax_total_nodes(document_node, vals)
        cls._add_invoice_monetary_total_nodes(document_node, vals)
        cls._add_invoice_optional_nodes(document_node, vals)
        return document_node

    @classmethod
    def _add_invoice_config_vals(cls, vals):
        """≙ ``_add_invoice_config_vals`` (odoo19c: :150-177) — **bloqueado**: env['account.move']._fields (introspeccion) y la mitad factura de account.move no existen (0 hits)."""
        _blocked("_add_invoice_config_vals", "env['account.move']._fields (introspeccion) y la mitad factura de account.move no existen (0 hits)")

    @classmethod
    def _dispatch_base_lines_recycling_contribution_taxes(cls, base_lines, company, vals):
        """ Extract recycling contribution taxes such as RECUPEL, AUVIBEL, etc from the current base lines.
        Instead, add them under 'base_line' -> '_ubl_values' -> 'recycling_contribution_data' to be reported
        as allowances/charges.

        From a 'base_line' having
            price_unit = 99
            tax_ids = RECUPEL of 1 + 21% tax
            total_excluded_currency = 99
            total_included_currency = 121
            taxes_data = [1, 21]
            recycling_contribution_data = []
        ... turn it to:
            price_unit = 99
            tax_ids = 21% tax
            total_excluded_currency = 99
            total_included_currency = 121
            taxes_data = [21]
            recycling_contribution_data = [1]

        :param base_lines:  The original 'base_lines' of the document.
        :param company:     The company owning the 'base_lines'.
        :param vals:        Some custom data.
        """
        if not vals['fixed_taxes_as_allowance_charges']:
            return

        # Turn recycling contribution taxes into allowance/charge.
        # To distinguish them from emptying taxes, we know that one is taxed and not the other.
        def is_recycling_contribution(tax_data):
            if not tax_data:
                return

            tax = tax_data['tax']
            return tax.amount_type == 'fixed' and tax.include_base_amount

        for base_line in base_lines:
            tax_details = base_line['tax_details']
            taxes_data = tax_details['taxes_data']
            recycling_contribution_taxes_data = base_line['_ubl_values']['recycling_contribution_taxes_data']

            new_taxes_data = tax_details['taxes_data'] = []
            for tax_data in taxes_data:
                if is_recycling_contribution(tax_data):
                    recycling_contribution_taxes_data.append({'tax_data': tax_data})
                    tax_details['raw_total_excluded_currency'] += tax_data['raw_tax_amount_currency']
                    tax_details['raw_total_excluded'] += tax_data['raw_tax_amount']
                    tax_details['total_excluded_currency'] += tax_data['tax_amount_currency']
                    tax_details['total_excluded'] += tax_data['tax_amount']
                else:
                    new_taxes_data.append(tax_data)

    @classmethod
    def _turn_emptying_taxes_as_new_base_lines(cls, base_lines, company, vals):
        if not vals['fixed_taxes_as_allowance_charges']:
            return base_lines
        return cls._ubl_turn_emptying_taxes_as_new_base_lines(base_lines, company, vals)

    @classmethod
    def _add_invoice_base_lines_vals(cls, vals):
        invoice = vals['invoice']
        vals['base_lines'], _tax_lines = invoice._get_rounded_base_and_tax_lines()

    @classmethod
    def _setup_base_lines(cls, vals):
        base_lines = vals['base_lines']
        company = vals['company']

        for base_line in base_lines:
            # Allow retrieving the invoice line from the base_line.
            base_line['_invoice_line'] = base_line['record']
            line_name = base_line['record'] and base_line['record'].name
            base_line['_line_name'] = line_name and line_name.replace('\n', ' ')

            # Allow retrieving some custom values coming from manipulations of base lines.
            base_line['_ubl_values'] = {
                'recycling_contribution_taxes_data': [],
            }

        # Manage taxes for recycling contribution such as RECUPEL / AUVIBEL.
        cls._dispatch_base_lines_recycling_contribution_taxes(base_lines, company, vals)

        # Manage taxes for emptying.
        base_lines = cls._turn_emptying_taxes_as_new_base_lines(base_lines, company, vals)

        # Extract cash rounding lines.
        vals['base_lines'] = [base_line for base_line in base_lines if base_line['special_type'] != 'cash_rounding']
        vals['cash_rounding_base_lines'] = [base_line for base_line in base_lines if base_line['special_type'] == 'cash_rounding']

    @classmethod
    def _add_invoice_currency_vals(cls, vals):
        cls._add_document_currency_vals(vals)

    @classmethod
    def _add_invoice_tax_grouping_function_vals(cls, vals):
        cls._add_document_tax_grouping_function_vals(vals)

    @classmethod
    def _add_invoice_monetary_totals_vals(cls, vals):
        cls._add_document_monetary_total_vals(vals)

    @classmethod
    def _add_invoice_header_nodes(cls, document_node, vals):
        invoice = vals['invoice']
        document_node.update({
            'cbc:UBLVersionID': {'_text': '2.0'},
            'cbc:ID': {'_text': invoice.name},
            'cbc:IssueDate': {'_text': invoice.invoice_date},
            'cbc:InvoiceTypeCode': {'_text': 389 if vals['process_type'] == 'selfbilling' else 380} if vals['document_type'] == 'invoice' else None,
            'cbc:Note': {'_text': html2plaintext(invoice.narration) if invoice.narration else None},
            'cbc:DocumentCurrencyCode': {'_text': invoice.currency_id.name},
            'cac:OrderReference': {
                # OrderReference/ID (order_reference) is mandatory inside the OrderReference node
                'cbc:ID': {'_text': invoice.ref or invoice.name},
                # OrderReference/SalesOrderID (sales_order_id) is optional
                'cbc:SalesOrderID': {
                    '_text': ",".join(invoice.invoice_line_ids.sale_line_ids.order_id.mapped('name'))
                } if 'sale_line_ids' in invoice.invoice_line_ids._fields else None,
            }
        })

    @classmethod
    def _add_invoice_accounting_supplier_party_nodes(cls, document_node, vals):
        document_node['cac:AccountingSupplierParty'] = {
            'cac:Party': cls._get_party_node({**vals, 'partner': vals['supplier'], 'role': 'supplier'}),
        }

    @classmethod
    def _add_invoice_accounting_customer_party_nodes(cls, document_node, vals):
        document_node['cac:AccountingCustomerParty'] = {
            'cac:Party': cls._get_party_node({**vals, 'partner': vals['customer'], 'role': 'customer'}),
        }

    @classmethod
    def _add_invoice_seller_supplier_party_nodes(cls, document_node, vals):
        pass

    @classmethod
    def _add_invoice_delivery_nodes(cls, document_node, vals):
        invoice = vals['invoice']
        partner_shipping = vals['partner_shipping']
        document_node['cac:Delivery'] = {
            'cbc:ActualDeliveryDate': {'_text': invoice.delivery_date},
            'cac:DeliveryLocation': {
                'cac:Address': cls._get_address_node({'partner': partner_shipping}),
            },
        }
        # TODO master: clean that code a bit hacky, when the module account_add_gln is merged with account
        if gln := 'global_location_number' in partner_shipping._fields and partner_shipping.global_location_number:
            document_node['cac:Delivery']['cac:DeliveryLocation'].update({
                'cbc:ID': {'schemeID': '0088', '_text': gln},
            })

    @classmethod
    def _add_invoice_payment_means_nodes(cls, document_node, vals):
        invoice = vals['invoice']
        if invoice.move_type == 'out_invoice':
            if invoice.partner_bank_id:
                payment_means_code, payment_means_name = 30, 'credit transfer'
            else:
                payment_means_code, payment_means_name = 'ZZZ', 'mutually defined'
        else:
            payment_means_code, payment_means_name = 57, 'standing agreement'

        # in Denmark payment code 30 is not allowed. we hardcode it to 1 ("unknown") for now
        # as we cannot deduce this information from the invoice
        if invoice.partner_id.country_code == 'DK':
            payment_means_code, payment_means_name = 1, 'unknown'

        document_node['cac:PaymentMeans'] = {
            'cbc:PaymentMeansCode': {
                '_text': payment_means_code,
                'name': payment_means_name,
            },
            'cbc:PaymentDueDate': {'_text': invoice.invoice_date_due or invoice.invoice_date},
            'cbc:InstructionID': {'_text': invoice.payment_reference},
            'cbc:PaymentID': {'_text': invoice.payment_reference or invoice.name},
            'cac:PayeeFinancialAccount': cls._get_financial_account_node({
                **vals, 'partner_bank': invoice.partner_bank_id
            }) if invoice.partner_bank_id else None
        }

    @classmethod
    def _add_invoice_payment_terms_nodes(cls, document_node, vals):
        invoice = vals['invoice']
        payment_term = invoice.invoice_payment_term_id
        if payment_term:
            document_node['cac:PaymentTerms'] = {
                # The payment term's note is automatically embedded in a <p> tag in Odoo
                'cbc:Note': {'_text': html2plaintext(payment_term.note)}
            }

    @classmethod
    def _add_invoice_allowance_charge_nodes(cls, document_node, vals):
        cls._add_document_allowance_charge_nodes(document_node, vals)

    @classmethod
    def _add_invoice_exchange_rate_nodes(cls, document_node, vals):
        pass

    @classmethod
    def _add_invoice_tax_total_nodes(cls, document_node, vals):
        cls._add_document_tax_total_nodes(document_node, vals)

    @classmethod
    def _add_invoice_monetary_total_nodes(cls, document_node, vals):
        cls._add_document_monetary_total_nodes(document_node, vals)
        monetary_total_tag = cls._get_tags_for_document_type(vals)['monetary_total']
        invoice = vals['invoice']
        document_node[monetary_total_tag].update({
            'cbc:PrepaidAmount': {
                '_text': cls.format_float(invoice.amount_total - invoice.amount_residual, vals['currency_dp']),
                'currencyID': vals['currency_name'],
            },
            'cbc:PayableRoundingAmount': {
                '_text': cls.format_float(vals['cash_rounding_base_amount_currency'], vals['currency_dp']),
                'currencyID': vals['currency_name'],
            } if vals['cash_rounding_base_amount_currency'] else None,
            'cbc:PayableAmount': {
                '_text': cls.format_float(invoice.amount_residual, vals['currency_dp']),
                'currencyID': vals['currency_name'],
            },
        })

    @classmethod
    def _add_invoice_optional_nodes(cls, document_node, vals):
        if (vals['document_type'] == 'invoice'):
            cls.add_invoice_optional_nodes(document_node, vals, PEPPOL_INVOICE_OPTIONAL_FIELDS)
        elif (vals['document_type'] == 'credit_note'):
            cls.add_invoice_optional_nodes(document_node, vals, PEPPOL_CREDIT_NOTE_OPTIONAL_FIELDS)

    @classmethod
    def add_invoice_optional_nodes(cls, document_node, vals, optional_fields):
        """≙ ``add_invoice_optional_nodes`` (odoo19c: :392-403) — **bloqueado**: recorre move._fields (introspeccion del ORM de la referencia): este arbol usa Meta de Django y no expone _fields."""
        _blocked("add_invoice_optional_nodes", "recorre move._fields (introspeccion del ORM de la referencia): este arbol usa Meta de Django y no expone _fields")

    @classmethod
    def _get_invoice_line_node(cls, vals):
        cls._add_invoice_line_vals(vals)

        line_node = {}
        cls._add_invoice_line_id_nodes(line_node, vals)
        cls._add_invoice_line_note_nodes(line_node, vals)
        cls._add_invoice_line_period_nodes(line_node, vals)
        cls._add_invoice_line_allowance_charge_nodes(line_node, vals)
        cls._add_invoice_line_amount_nodes(line_node, vals)
        cls._add_invoice_line_tax_total_nodes(line_node, vals)
        cls._add_invoice_line_item_nodes(line_node, vals)
        cls._add_invoice_line_tax_category_nodes(line_node, vals)
        cls._add_invoice_line_price_nodes(line_node, vals)
        cls._add_invoice_line_pricing_reference_nodes(line_node, vals)
        cls._add_invoice_line_optional_nodes(line_node, vals)
        return line_node

    @classmethod
    def _add_invoice_line_nodes(cls, document_node, vals):
        line_idx = 1

        line_tag = cls._get_tags_for_document_type(vals)['document_line']
        document_node[line_tag] = line_nodes = []
        for base_line in vals['base_lines']:
            # Only use product lines to generate the UBL InvoiceLines.
            # Other lines should be represented as AllowanceCharges.
            if not cls._is_document_allowance_charge(base_line):
                line_vals = {
                    **vals,
                    'line_idx': line_idx,
                    'base_line': base_line,
                }
                line_node = cls._get_invoice_line_node(line_vals)
                line_nodes.append(line_node)
                line_idx += 1

    @classmethod
    def _add_invoice_line_vals(cls, vals):
        cls._add_document_line_vals(vals)

    @classmethod
    def _add_invoice_line_id_nodes(cls, line_node, vals):
        cls._add_document_line_id_nodes(line_node, vals)

    @classmethod
    def _add_invoice_line_note_nodes(cls, line_node, vals):
        cls._add_document_line_note_nodes(line_node, vals)

    @classmethod
    def _add_invoice_line_amount_nodes(cls, line_node, vals):
        cls._add_document_line_amount_nodes(line_node, vals)

    @classmethod
    def _add_invoice_line_period_nodes(cls, line_node, vals):
        pass

    @classmethod
    def _add_invoice_line_allowance_charge_nodes(cls, line_node, vals):
        cls._add_document_line_allowance_charge_nodes(line_node, vals)

    @classmethod
    def _add_invoice_line_tax_total_nodes(cls, line_node, vals):
        cls._add_document_line_tax_total_nodes(line_node, vals)

    @classmethod
    def _add_invoice_line_item_nodes(cls, line_node, vals):
        cls._add_document_line_item_nodes(line_node, vals)

        line_name = vals['base_line']['_line_name']
        if line_name:
            line_node['cac:Item']['cbc:Description']['_text'] = line_name
            if not line_node['cac:Item']['cbc:Name']['_text']:
                line_node['cac:Item']['cbc:Name']['_text'] = line_name

    @classmethod
    def _add_invoice_line_tax_category_nodes(cls, line_node, vals):
        cls._add_document_line_tax_category_nodes(line_node, vals)

    @classmethod
    def _add_invoice_line_price_nodes(cls, line_node, vals):
        cls._add_document_line_price_nodes(line_node, vals)

    @classmethod
    def _add_invoice_line_pricing_reference_nodes(cls, line_node, vals):
        pass

    @classmethod
    def _add_invoice_line_optional_nodes(cls, line_node, vals):
        if (vals['document_type'] == 'invoice'):
            cls.add_invoice_line_optional_nodes(line_node, vals, PEPPOL_INVOICE_OPTIONAL_LINE_FIELDS)
        elif (vals['document_type'] == 'credit_note'):
            cls.add_invoice_line_optional_nodes(line_node, vals, PEPPOL_CREDIT_NOTE_OPTIONAL_LINE_FIELDS)

    @classmethod
    def add_invoice_line_optional_nodes(cls, line_node, vals, optional_line_fields):
        """≙ ``add_invoice_line_optional_nodes`` (odoo19c: :485-506) — **bloqueado**: isinstance(record, models.Model) + record._fields: introspeccion del ORM de la referencia, sin analogo."""
        _blocked("add_invoice_line_optional_nodes", "isinstance(record, models.Model) + record._fields: introspeccion del ORM de la referencia, sin analogo")

    # -------------------------------------------------------------------------
    # EXPORT: Generic templates
    # -------------------------------------------------------------------------

    @classmethod
    def _add_document_currency_vals(cls, vals):
        """ Add the 'currency_suffix', 'currency_dp' and 'currency_name'. """
        vals['currency_suffix'] = '' if vals['use_company_currency'] else '_currency'

        currency = vals['company_currency_id'] if vals['use_company_currency'] else vals['currency_id']
        vals['currency_dp'] = cls._get_currency_decimal_places(currency)
        vals['currency_name'] = currency.name

    @classmethod
    def _add_document_tax_grouping_function_vals(cls, vals):
        # Add the grouping functions for the monetary totals and tax totals
        customer = vals['customer']
        supplier = vals['supplier']

        # This function will be used when computing the monetary totals on the document level.
        # It should return True for all taxes which should be included in the total.
        def total_grouping_function(base_line, tax_data):
            return True

        # This function will be used when computing the tax totals on the document and line level.
        # It should group taxes together according to the tax catagory with which they will be reported.
        # Any taxes that should be included in the tax totals should be included.
        def tax_grouping_function(base_line, tax_data):
            tax = tax_data and tax_data['tax']
            return {
                'tax_category_code': cls._get_tax_category_code(customer.commercial_partner_id, supplier, tax),
                **cls._get_tax_exemption_reason(customer.commercial_partner_id, supplier, tax),
                # Reverse-charge taxes with +100/-100% repartition lines are used in vendor bills.
                # In a self-billed invoice, we report them from the seller's perspective, so
                # we change their percentage to 0%.
                'amount': tax.amount if tax and not tax.has_negative_factor else 0.0,
                'amount_type': tax.amount_type if tax else 'percent',
            }

        vals['total_grouping_function'] = total_grouping_function
        vals['tax_grouping_function'] = tax_grouping_function

    @classmethod
    def _add_document_monetary_total_vals(cls, vals):
        # Compute the monetary totals for the document
        """≙ ``_add_document_monetary_total_vals`` (odoo19c: :548-605) — **bloqueado**: la envoltura de base-lines de account.tax no se porta (0 hits)."""
        _blocked("_add_document_monetary_total_vals", "la envoltura de base-lines de account.tax no se porta (0 hits)")

    # -------------------------------------------------------------------------
    # EXPORT: Generic templates - partner-related nodes
    # -------------------------------------------------------------------------

    @classmethod
    def _get_address_node(cls, vals):
        """ Generic helper to generate the Address node for a res.partner or res.bank. """
        partner = vals['partner']
        country_key = 'country' if partner._name == 'res.bank' else 'country_id'
        state_key = 'state' if partner._name == 'res.bank' else 'state_id'
        country = partner[country_key]
        state = partner[state_key]

        return {
            'cbc:StreetName': {'_text': partner.street},
            'cbc:AdditionalStreetName': {'_text': partner.street2},
            'cbc:CityName': {'_text': partner.city},
            'cbc:PostalZone': {'_text': partner.zip},
            'cbc:CountrySubentity': {'_text': state.name},
            'cbc:CountrySubentityCode': {'_text': state.code},
            'cac:Country': {
                'cbc:IdentificationCode': {'_text': country.code},
                'cbc:Name': {'_text': country.name},
            },
        }

    @classmethod
    def _get_party_node(cls, vals):
        """ Generic helper to generate the Party node for a res.partner. """
        partner = vals['partner']
        commercial_partner = partner.commercial_partner_id
        party_node = {
            'cbc:EndpointID': {
                '_text': None,
                'schemeID': None,
            },
            'cac:PartyIdentification': {
                'cbc:ID': {'_text': commercial_partner.ref},
            },
            'cac:PartyName': {
                'cbc:Name': {'_text': partner.display_name if partner.name else commercial_partner.display_name},
            },
            'cac:PostalAddress': cls._get_address_node(vals),
            'cac:PartyLegalEntity': {
                'cbc:RegistrationName': {'_text': commercial_partner.name},
                'cbc:CompanyID': {'_text': commercial_partner.vat},
                'cac:RegistrationAddress': cls._get_address_node({**vals, 'partner': commercial_partner}),
            },
            'cac:Contact': {
                'cbc:ID': {'_text': partner.id},
                'cbc:Name': {'_text': partner.name},
                'cbc:Telephone': {'_text': partner.phone},
                'cbc:ElectronicMail': {'_text': partner.email},
            },
        }
        if partner.vat and partner.vat != '/':
            party_node['cac:PartyTaxScheme'] = {
                'cbc:RegistrationName': {'_text': commercial_partner.name},
                'cbc:CompanyID': {'_text': commercial_partner.vat},
                'cac:RegistrationAddress': cls._get_address_node({**vals, 'partner': commercial_partner}),
                'cac:TaxScheme': {
                    'cbc:ID': {
                        '_text': (
                            'NOT_EU_VAT'
                            if commercial_partner.country_id
                            and commercial_partner.vat
                            and not commercial_partner.vat[:2].isalpha()
                            else 'VAT'
                        )
                    }
                },
            }
        return party_node

    @classmethod
    def _get_financial_account_node(cls, vals):
        """ Generic helper to generate the FinancialAccount node for a res.partner.bank """
        partner_bank = vals['partner_bank']
        bank = partner_bank.bank_id
        financial_institution_branch = None
        if bank:
            financial_institution_branch = {
                'cbc:ID': {
                    '_text': bank.bic,
                    'schemeID': 'BIC'
                },
                'cac:FinancialInstitution': {
                    'cbc:ID': {
                        '_text': bank.bic,
                        'schemeID': 'BIC'
                    },
                    'cbc:Name': {'_text': bank.name},
                    'cac:Address': cls._get_address_node({**vals, 'partner': bank})
                }
            }
        return {
            'cbc:ID': {'_text': partner_bank.acc_number.replace(' ', '')},
            'cac:FinancialInstitutionBranch': financial_institution_branch
        }

    # -------------------------------------------------------------------------
    # EXPORT: Generic templates for tax-related nodes
    # -------------------------------------------------------------------------

    @classmethod
    def _add_document_tax_total_nodes(cls, document_node, vals):
        """≙ ``_add_document_tax_total_nodes`` (odoo19c: :708-713) — **bloqueado**: la envoltura de base-lines de account.tax no se porta (0 hits)."""
        _blocked("_add_document_tax_total_nodes", "la envoltura de base-lines de account.tax no se porta (0 hits)")

    @classmethod
    def _add_tax_total_node_in_company_currency(cls, document_node, vals):
        """≙ ``_add_tax_total_node_in_company_currency`` (odoo19c: :715-728) — **bloqueado**: la envoltura de base-lines de account.tax no se porta (0 hits)."""
        _blocked("_add_tax_total_node_in_company_currency", "la envoltura de base-lines de account.tax no se porta (0 hits)")

    @classmethod
    def _get_tax_total_node(cls, vals):
        """ Generic helper to generate a TaxTotal node given a dict of aggregated tax details. """
        aggregated_tax_details = vals['aggregated_tax_details']
        currency_suffix = vals['currency_suffix']
        sign = vals.get('sign', 1)
        total_tax_amount = sum(
            values[f'tax_amount{currency_suffix}']
            for grouping_key, values in aggregated_tax_details.items()
            if grouping_key
        )
        return {
            'cbc:TaxAmount': {
                '_text': cls.format_float(sign * total_tax_amount, vals['currency_dp']),
                'currencyID': vals['currency_name']
            },
            'cac:TaxSubtotal': [
                cls._get_tax_subtotal_node({
                    **vals,
                    'tax_details': tax_details,
                    'grouping_key': grouping_key,
                })
                for grouping_key, tax_details in aggregated_tax_details.items()
                if grouping_key
            ]
        }

    @classmethod
    def _get_tax_subtotal_node(cls, vals):
        """ Generic helper to generate a TaxSubtotal node given a tax grouping key dict and associated tax values. """
        tax_details = vals['tax_details']
        grouping_key = vals['grouping_key']
        sign = vals.get('sign', 1)
        currency_suffix = vals['currency_suffix']
        return {
            'cbc:TaxableAmount': {
                '_text': cls.format_float(tax_details[f'base_amount{currency_suffix}'], vals['currency_dp']),
                'currencyID': vals['currency_name']
            },
            'cbc:TaxAmount': {
                '_text': cls.format_float(sign * tax_details[f'tax_amount{currency_suffix}'], vals['currency_dp']),
                'currencyID': vals['currency_name']
            },
            'cbc:Percent': {'_text': grouping_key['amount']} if grouping_key['amount_type'] == 'percent' else None,
            'cac:TaxCategory': cls._get_tax_category_node({**vals, 'grouping_key': grouping_key})
        }

    @classmethod
    def _get_tax_category_node(cls, vals):
        """ Generic helper to generate a TaxCategory node given a tax grouping key dict. """
        grouping_key = vals['grouping_key']
        return {
            'cbc:ID': {'_text': grouping_key['tax_category_code']},
            'cbc:Name': {'_text': grouping_key.get('name')},
            'cbc:Percent': {'_text': grouping_key['amount']} if grouping_key['amount_type'] == 'percent' else None,
            'cbc:TaxExemptionReasonCode': {'_text': grouping_key.get('tax_exemption_reason_code')},
            'cbc:TaxExemptionReason': {'_text': grouping_key.get('tax_exemption_reason')},
            'cac:TaxScheme': {
                'cbc:ID': {'_text': 'VAT'},
            }
        }

    @classmethod
    def _add_document_monetary_total_nodes(cls, document_node, vals):
        """ Generic helper to fill the MonetaryTotal node for a document given a list of base_lines. """
        monetary_total_tag = cls._get_tags_for_document_type(vals)['monetary_total']
        currency_suffix = vals['currency_suffix']

        document_node[monetary_total_tag] = {
            'cbc:LineExtensionAmount': {
                '_text': cls.format_float(vals[f'total_lines{currency_suffix}'], vals['currency_dp']),
                'currencyID': vals['currency_name'],
            },
            'cbc:TaxExclusiveAmount': {
                '_text': cls.format_float(vals[f'tax_exclusive_amount{currency_suffix}'], vals['currency_dp']),
                'currencyID': vals['currency_name'],
            },
            'cbc:TaxInclusiveAmount': {
                '_text': cls.format_float(vals[f'tax_inclusive_amount{currency_suffix}'], vals['currency_dp']),
                'currencyID': vals['currency_name'],
            },
            'cbc:AllowanceTotalAmount': {
                '_text': cls.format_float(vals[f'total_allowance{currency_suffix}'], vals['currency_dp']),
                'currencyID': vals['currency_name'],
            } if vals[f'total_allowance{currency_suffix}'] else None,
            'cbc:ChargeTotalAmount': {
                '_text': cls.format_float(vals[f'total_charge{currency_suffix}'], vals['currency_dp']),
                'currencyID': vals['currency_name'],
            } if vals[f'total_charge{currency_suffix}'] else None,
            'cbc:PrepaidAmount': {
                '_text': cls.format_float(0.0, vals['currency_dp']),
                'currencyID': vals['currency_name'],
            },
            'cbc:PayableRoundingAmount': {
                '_text': cls.format_float(vals[f'cash_rounding_base_amount{currency_suffix}'], vals['currency_dp']),
                'currencyID': vals['currency_name'],
            } if vals[f'cash_rounding_base_amount{currency_suffix}'] else None,
            'cbc:PayableAmount': {
                '_text': cls.format_float(vals[f'tax_inclusive_amount{currency_suffix}'], vals['currency_dp']),
                'currencyID': vals['currency_name'],
            },
        }

    @classmethod
    def _get_document_line_node(cls, vals):
        cls._add_document_line_vals(vals)

        line_node = {}
        cls._add_document_line_id_nodes(line_node, vals)
        cls._add_document_line_note_nodes(line_node, vals)
        cls._add_document_line_amount_nodes(line_node, vals)
        cls._add_document_line_period_nodes(line_node, vals)
        cls._add_document_line_allowance_charge_nodes(line_node, vals)
        cls._add_document_line_tax_total_nodes(line_node, vals)
        cls._add_document_line_item_nodes(line_node, vals)
        cls._add_document_line_tax_category_nodes(line_node, vals)
        cls._add_document_line_price_nodes(line_node, vals)
        cls._add_document_line_pricing_reference_nodes(line_node, vals)
        return line_node

    @classmethod
    def _add_document_line_nodes(cls, document_node, vals):
        line_idx = 1

        line_tag = cls._get_tags_for_document_type(vals)['document_line']
        document_node[line_tag] = line_nodes = []
        for base_line in vals['base_lines']:
            if not cls._is_document_allowance_charge(base_line):
                line_vals = {
                    **vals,
                    'line_idx': line_idx,
                    'base_line': base_line,
                }
                line_node = cls._get_document_line_node(line_vals)
                line_nodes.append(line_node)
                line_idx += 1

    # -------------------------------------------------------------------------
    # EXPORT: Templates for document-level allowance charge nodes
    # -------------------------------------------------------------------------

    @classmethod
    def _add_document_allowance_charge_nodes(cls, document_node, vals):
        """ Generic helper to fill the AllowanceCharge nodes for a document given a list of base_lines. """
        # AllowanceCharge doesn't exist in debit notes in UBL 2.0
        if vals['document_type'] != 'debit_note':
            document_node['cac:AllowanceCharge'] = []
            for base_line in vals['base_lines']:
                if cls._is_document_allowance_charge(base_line):
                    document_node['cac:AllowanceCharge'].append(
                        cls._get_document_allowance_charge_node({**vals, 'base_line': base_line})
                    )

    @classmethod
    def _get_document_allowance_charge_node(cls, vals):
        """≙ ``_get_document_allowance_charge_node`` (odoo19c: :876-895) — **bloqueado**: la envoltura de base-lines de account.tax no se porta (0 hits)."""
        _blocked("_get_document_allowance_charge_node", "la envoltura de base-lines de account.tax no se porta (0 hits)")

    # -------------------------------------------------------------------------
    # EXPORT: Templates for line nodes
    # -------------------------------------------------------------------------

    @classmethod
    def _add_document_line_vals(cls, vals):
        """ Generic helper to calculate the amounts for a document line. """
        cls._add_document_line_total_vals(vals)
        cls._add_document_line_gross_subtotal_and_discount_vals(vals)

    @classmethod
    def _add_document_line_total_vals(cls, vals):
        """≙ ``_add_document_line_total_vals`` (odoo19c: :906-925) — **bloqueado**: la envoltura de base-lines de account.tax no se porta (0 hits)."""
        _blocked("_add_document_line_total_vals", "la envoltura de base-lines de account.tax no se porta (0 hits)")

    @classmethod
    def _add_document_line_gross_subtotal_and_discount_vals(cls, vals):
        base_line = vals['base_line']
        company_currency = vals['company_currency_id']

        raw_total_excluded_currency = base_line['tax_details']['raw_total_excluded_currency']
        raw_total_excluded = base_line['tax_details']['raw_total_excluded']
        total_excluded_currency = base_line['tax_details']['total_excluded_currency']
        total_excluded = base_line['tax_details']['total_excluded']
        for recycling_contribution_tax_data in base_line.get('_ubl_values', {}).get('recycling_contribution_taxes_data', []):
            tax_data = recycling_contribution_tax_data['tax_data']
            raw_total_excluded_currency -= tax_data['raw_tax_amount_currency']
            raw_total_excluded -= tax_data['raw_tax_amount']
            total_excluded_currency -= tax_data['tax_amount_currency']
            total_excluded -= tax_data['tax_amount']

        discount_factor = 1 - (base_line['discount'] / 100.0)

        if discount_factor != 0.0:
            gross_subtotal_currency = base_line['currency_id'].round(raw_total_excluded_currency / discount_factor)
            gross_subtotal = company_currency.round(raw_total_excluded / discount_factor)
        else:
            gross_subtotal_currency = base_line['currency_id'].round(base_line['price_unit'] * base_line['quantity'])
            gross_subtotal = company_currency.round(gross_subtotal_currency / base_line['rate'])

        if base_line['quantity'] == 0.0 or discount_factor == 0.0:
            gross_price_unit_currency = base_line['price_unit']
            gross_price_unit = company_currency.round(base_line['price_unit'] / base_line['rate'])
        else:
            gross_price_unit_currency = gross_subtotal_currency / base_line['quantity']
            gross_price_unit = gross_subtotal / base_line['quantity']

        discount_amount_currency = gross_subtotal_currency - total_excluded_currency
        discount_amount = gross_subtotal - total_excluded

        vals.update({
            'discount_amount_currency': discount_amount_currency,
            'discount_amount': discount_amount,
            'gross_subtotal_currency': gross_subtotal_currency,
            'gross_subtotal': gross_subtotal,
            'gross_price_unit_currency': gross_price_unit_currency,
            'gross_price_unit': gross_price_unit,
        })

    @classmethod
    def _add_document_line_id_nodes(cls, line_node, vals):
        line_node['cbc:ID'] = {'_text': vals['line_idx']}

    @classmethod
    def _add_document_line_note_nodes(cls, line_node, vals):
        pass

    @classmethod
    def _add_document_line_amount_nodes(cls, line_node, vals):
        currency_suffix = vals['currency_suffix']
        base_line = vals['base_line']

        quantity_tag = cls._get_tags_for_document_type(vals)['line_quantity']

        line_node.update({
            quantity_tag: {
                '_text': base_line['quantity'],
                'unitCode': cls._get_uom_unece_code(base_line['product_uom_id']),
            },
            'cbc:LineExtensionAmount': {
                '_text': cls.format_float(vals[f'total_excluded{currency_suffix}'], vals['currency_dp']),
                'currencyID': vals['currency_name'],
            },
        })

    @classmethod
    def _add_document_line_period_nodes(cls, line_node, vals):
        pass

    @classmethod
    def _add_document_line_item_nodes(cls, line_node, vals):
        product = vals['base_line']['product_id']

        line_node['cac:Item'] = {
            'cbc:Description': {'_text': product.description_sale},
            'cbc:Name': {'_text': product.name},
            'cac:SellersItemIdentification': {
                'cbc:ID': {'_text': product.default_code},
            },
            'cac:StandardItemIdentification': {
                'cbc:ID': {
                    '_text': product.barcode,
                    'schemeID': '0160',  # GTIN
                } if product.barcode else None,
            },
            'cac:AdditionalItemProperty': [
                {
                    'cbc:Name': {'_text': value.attribute_id.name},
                    'cbc:Value': {'_text': value.name},
                } for value in product.product_template_attribute_value_ids
            ],
        }

    @classmethod
    def _add_document_line_allowance_charge_nodes(cls, line_node, vals):
        if vals['document_type'] not in {'credit_note', 'debit_note'}:
            line_node['cac:AllowanceCharge'] = []
            if node := cls._get_line_discount_allowance_charge_node(vals):
                line_node['cac:AllowanceCharge'].append(node)
            line_node['cac:AllowanceCharge'].extend(cls._get_line_fixed_tax_allowance_charge_nodes(vals))

    @classmethod
    def _get_line_discount_allowance_charge_node(cls, vals):
        currency_suffix = vals['currency_suffix']
        if float_is_zero(vals[f'discount_amount{currency_suffix}'], precision_digits=vals['currency_dp']):
            return None

        return {
            'cbc:ChargeIndicator': {'_text': 'false' if vals[f'discount_amount{currency_suffix}'] > 0 else 'true'},
            'cbc:AllowanceChargeReasonCode': {'_text': '95'},
            'cbc:Amount': {
                '_text': cls.format_float(
                    abs(vals[f'discount_amount{currency_suffix}']),
                    vals['currency_dp'],
                ),
                'currencyID': vals['currency_name'],
            },
        }

    @classmethod
    def _get_line_fixed_tax_allowance_charge_nodes(cls, vals):
        base_line = vals['base_line']
        currency_suffix = vals['currency_suffix']

        allowance_charge_nodes = []
        for recycling_contribution_tax_data in base_line.get('_ubl_values', {}).get('recycling_contribution_taxes_data', []):
            tax_data = recycling_contribution_tax_data['tax_data']
            tax = tax_data['tax']
            allowance_charge_nodes.append({
                'cbc:ChargeIndicator': {'_text': 'true' if tax_data[f'tax_amount{currency_suffix}'] > 0 else 'false'},
                'cbc:AllowanceChargeReasonCode': {'_text': 'AEO' if tax_data[f'tax_amount{currency_suffix}'] > 0 else '100'},
                'cbc:AllowanceChargeReason': {'_text': tax.name},
                'cbc:Amount': {
                    '_text': cls.format_float(
                        abs(tax_data[f'tax_amount{currency_suffix}']),
                        vals['currency_dp'],
                    ),
                    'currencyID': vals['currency_name'],
                },
            })
        return allowance_charge_nodes

    @classmethod
    def _add_document_line_tax_category_nodes(cls, line_node, vals):
        """≙ ``_add_document_line_tax_category_nodes`` (odoo19c: :1065-1072) — **bloqueado**: la envoltura de base-lines de account.tax no se porta (0 hits)."""
        _blocked("_add_document_line_tax_category_nodes", "la envoltura de base-lines de account.tax no se porta (0 hits)")

    @classmethod
    def _add_document_line_tax_total_nodes(cls, line_node, vals):
        """≙ ``_add_document_line_tax_total_nodes`` (odoo19c: :1074-1077) — **bloqueado**: la envoltura de base-lines de account.tax no se porta (0 hits)."""
        _blocked("_add_document_line_tax_total_nodes", "la envoltura de base-lines de account.tax no se porta (0 hits)")

    @classmethod
    def _add_document_line_price_nodes(cls, line_node, vals):
        """≙ ``_add_document_line_price_nodes`` (odoo19c: :1079-1091) — **bloqueado**: decimal.precision.precision_get() no existe (0 hits)."""
        _blocked("_add_document_line_price_nodes", "decimal.precision.precision_get() no existe (0 hits)")

    @classmethod
    def _add_document_line_pricing_reference_nodes(cls, line_node, vals):
        pass

    # -------------------------------------------------------------------------
    # EXPORT: Constraints
    # -------------------------------------------------------------------------

    @classmethod
    def _export_invoice_constraints(cls, invoice, vals):
        constraints = cls._invoice_constraints_common(invoice)
        constraints.update({
            'ubl20_supplier_name_required': cls._check_required_fields(vals['supplier'], 'name'),
            'ubl20_customer_name_required': cls._check_required_fields(vals['customer'].commercial_partner_id, 'name'),
            'ubl20_invoice_name_required': cls._check_required_fields(invoice, 'name'),
            'ubl20_invoice_date_required': cls._check_required_fields(invoice, 'invoice_date'),
        })
        return constraints

    # -------------------------------------------------------------------------
    # IMPORT
    # -------------------------------------------------------------------------

    @classmethod
    def _import_retrieve_partner_vals(cls, tree, role):
        """ Returns a dict of values that will be used to retrieve the partner """
        vat = cls._find_value(f'.//cac:{role}Party//cbc:CompanyID[string-length(text()) > 5]', tree)
        country_code = cls._find_value(f'.//cac:{role}Party//cac:PostalAddress/cac:Country/cbc:IdentificationCode', tree)
        if not vat and country_code:
            for scheme_id, field in EAS_MAPPING.get(country_code, {}).items():
                if field == 'vat' and (vat := cls._find_value(f".//cac:{role}Party//cac:PartyIdentification/cbc:ID[@schemeID='{scheme_id}']", tree)):
                    break
        return {
            'vat': vat,
            'phone': cls._find_value(f'.//cac:{role}Party//cac:Contact/cbc:Telephone', tree),
            'email': cls._find_value(f'.//cac:{role}Party//cac:Contact/cbc:ElectronicMail', tree),
            'name': cls._find_value(f'.//cac:{role}Party//cac:PartyTaxScheme/cbc:RegistrationName', tree) or
                    cls._find_value(f'.//cac:{role}Party//cac:PartyLegalEntity/cbc:RegistrationName', tree) or
                    cls._find_value(f'.//cac:{role}Party//cac:PartyName/cbc:Name', tree) or
                    cls._find_value(f'.//cac:{role}Party//cac:Contact/cbc:Name', tree),
            'postal_address': cls._get_postal_address(tree, role),
        }

    @classmethod
    def _get_postal_address(cls, tree, role):
        return {
            'country_code': cls._find_value(f'.//cac:{role}Party//cac:PostalAddress/cac:Country/cbc:IdentificationCode', tree),
            'street': cls._find_value(f'.//cac:{role}Party//cac:PostalAddress/cbc:StreetName', tree),
            'additional_street': cls._find_value(f'.//cac:{role}Party//cac:PostalAddress/cbc:AdditionalStreetName', tree),
            'city': cls._find_value(f'.//cac:{role}Party//cac:PostalAddress/cbc:CityName', tree),
            'zip': cls._find_value(f'.//cac:{role}Party//cac:PostalAddress/cbc:PostalZone', tree),
            'state_code': cls._find_value(f'.//cac:{role}Party//cac:PostalAddress/cbc:CountrySubentityCode', tree),
        }

    @classmethod
    def _import_fill_invoice(cls, invoice, tree, qty_factor):
        """≙ ``_import_fill_invoice`` (odoo19c: :1143-1204) — **bloqueado**: account.incoterms y los idiomas Command/fields.Date del ORM de la referencia no existen (0 hits)."""
        _blocked("_import_fill_invoice", "account.incoterms y los idiomas Command/fields.Date del ORM de la referencia no existen (0 hits)")

    @classmethod
    def _get_tax_nodes(cls, tree):
        tax_nodes = tree.findall('.//{*}Item/{*}ClassifiedTaxCategory/{*}Percent')
        if not tax_nodes:
            for elem in tree.findall('.//{*}TaxTotal'):
                percentage_nodes = elem.findall('.//{*}TaxSubtotal/{*}TaxCategory/{*}Percent')
                if not percentage_nodes:
                    percentage_nodes = elem.findall('.//{*}TaxSubtotal/{*}Percent')
                tax_nodes += percentage_nodes
        return tax_nodes

    @classmethod
    def _get_document_allowance_charge_xpaths(cls):
        return {
            'root': './{*}AllowanceCharge',
            'charge_indicator': './{*}ChargeIndicator',
            'base_amount': './{*}BaseAmount',
            'amount': './{*}Amount',
            'reason': './{*}AllowanceChargeReason',
            'percentage': './{*}MultiplierFactorNumeric',
            'tax_percentage': './{*}TaxCategory/{*}Percent',
        }

    @classmethod
    def _get_invoice_line_xpaths(cls, document_type=False, qty_factor=1):
        return {
            'deferred_start_date': './{*}InvoicePeriod/{*}StartDate',
            'deferred_end_date': './{*}InvoicePeriod/{*}EndDate',
            'date_format': '%Y-%m-%d',
        }

    @classmethod
    def _get_line_xpaths(cls, document_type=False, qty_factor=1):
        results = {
            'basis_qty': './cac:Price/cbc:BaseQuantity',
            'gross_price_unit': './{*}Price/{*}AllowanceCharge/{*}BaseAmount',
            'rebate': './{*}Price/{*}AllowanceCharge/{*}Amount',
            'net_price_unit': './{*}Price/{*}PriceAmount',
            'allowance_charge': './/{*}AllowanceCharge',
            'allowance_charge_indicator': './{*}ChargeIndicator',
            'allowance_charge_amount': './{*}Amount',
            'allowance_charge_reason': './{*}AllowanceChargeReason',
            'allowance_charge_reason_code': './{*}AllowanceChargeReasonCode',
            'line_total_amount': './{*}LineExtensionAmount',
            'name': [
                './cac:Item/cbc:Description',
                './cac:Item/cbc:Name',
            ],
            'product': cls._get_product_xpaths(),
        }

        if document_type == 'order':
            results['delivered_qty'] = './{*}Quantity'
        elif document_type and document_type in ('in_invoice', 'out_invoice') or qty_factor == -1:
            results['delivered_qty'] = './{*}InvoicedQuantity'
        else:
            results['delivered_qty'] = './{*}CreditedQuantity'

        return results

    @classmethod
    def _get_product_xpaths(cls):
        return {
            'default_code': './cac:Item/cac:SellersItemIdentification/cbc:ID',
            'name': './cac:Item/cbc:Name',
            'barcode': './cac:Item/cac:StandardItemIdentification/cbc:ID',
        }

    @classmethod
    def _correct_invoice_tax_amount(cls, tree, invoice):
        """ The tax total may have been modified for rounding purpose, if so we should use the imported tax and not
         the computed one """
        currency = invoice.currency_id
        # For each tax in our tax total, get the amount as well as the total in the xml.
        # Negative tax amounts may appear in invoices; they have to be inverted (since they are credit notes).
        document_amount_sign = cls._get_import_document_amount_sign(tree)[1] or 1
        # We only search for `TaxTotal/TaxSubtotal` in the "root" element (i.e. not in `InvoiceLine` elements).
        for elem in tree.findall('./{*}TaxTotal/{*}TaxSubtotal'):
            percentage = elem.find('.//{*}TaxCategory/{*}Percent')
            if percentage is None:
                percentage = elem.find('.//{*}Percent')
            amount = elem.find('.//{*}TaxAmount')
            # When multi-currency invoices have TaxSubtotal in multiple TaxTotal nodes (e.g. JP PINT),
            # only correct using the document currency's TaxTotal to avoid overwriting with the wrong amount.
            if amount is not None and amount.get('currencyID') != currency.name:
                continue
            if (percentage is not None and percentage.text is not None) and (amount is not None and amount.text is not None):
                tax_percent = float(percentage.text)
                # Compare the result with our tax total on the invoice, and apply correction if needed.
                # First look for taxes matching the percentage in the xml.
                taxes = invoice.line_ids.tax_line_id.filtered(lambda tax: tax.amount == tax_percent)
                # If we found taxes with the correct amount, look for a tax line using it, and correct it as needed.
                if taxes:
                    tax_total = document_amount_sign * float(amount.text)
                    # Sometimes we have multiple lines for the same tax.
                    tax_lines = invoice.line_ids.filtered(lambda line: line.tax_line_id in taxes)
                    if tax_lines:
                        sign = -1 if invoice.is_inbound(include_receipts=True) else 1
                        tax_lines_total = currency.round(sign * sum(tax_lines.mapped('amount_currency')))
                        difference = currency.round(tax_total - tax_lines_total)
                        if not currency.is_zero(difference):
                            tax_lines[0].amount_currency += sign * difference
    # -------------------------------------------------------------------------
    # IMPORT : helpers
    # -------------------------------------------------------------------------

    @classmethod
    def _get_import_document_amount_sign(cls, tree):
        """
        In UBL, an invoice has tag 'Invoice' and a credit note has tag 'CreditNote'. However, a credit note can be
        expressed as an invoice with negative amounts. For this case, we need a factor to take the opposite
        of each quantity in the invoice.
        """
        if tree.tag == '{urn:oasis:names:specification:ubl:schema:xsd:Invoice-2}Invoice':
            amount_node = tree.find('.//{*}LegalMonetaryTotal/{*}TaxExclusiveAmount')
            if amount_node is not None and float(amount_node.text) < 0:
                return 'refund', -1
            return 'invoice', 1
        if tree.tag == '{urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2}CreditNote':
            return 'refund', 1
        return None, None
