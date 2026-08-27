r"""``account.edi.xml.cii`` — Factur-X / XRechnung CII 2.2.0.

Adaptación de ``odoo19c: addons/account_edi_ubl_cii/models/account_edi_xml_cii_facturx.py``
(``odoo-tools@622ddc2a``, LGPL-3, 415 líneas, 19 métodos) — atribución y aviso
de licencia preservados (DEC-KX-03).

Cobertura: 19 de 19 presentes — **16 portados, 3 bloqueados**
=============================================================

* ``_export_invoice_vals`` — lee la mitad *factura* de ``account.move``
  (``narration``, ``invoice_date``, líneas) y ``env['account.payment']._fields``;
  ninguna existe (0 hits).
* ``_export_invoice`` — renderiza con ``env['ir.qweb']._render(...)``: este
  árbol no tiene motor QWeb (GAP ya declarado por
  ``account_edi/models/ir_actions_report.py``), y además necesita
  ``odoo.tools.cleanup_xml_node``, que ``src/tools`` no porta.
* ``_import_fill_invoice`` — la API de importación de registros más el idioma
  ``Command`` del ORM de la referencia.

Es la única rama de la familia que cuelga directamente de
``account.edi.common`` (no pasa por ``account.edi.ubl``): CII es otro
vocabulario XML, no una variante de UBL.

Familia ``account_edi_ubl_cii``: clase Python plana con ``@classmethod`` en vez
de ``AbstractModel``, y ``_inherit`` materializado como herencia de Python. La
convención, sus dos consecuencias y la tabla de piezas ausentes que bloquean el
lado de registros están declaradas una sola vez en
``account_edi_common.py`` — no se repiten aquí.
"""
import logging

from tools.mail import html2plaintext
from tools.translate import _

from .account_edi_common import AccountEdiCommon, _blocked

_logger = logging.getLogger(__name__)

DEFAULT_FACTURX_DATE_FORMAT = '%Y%m%d'
CII_NAMESPACES = {
    'ram': "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
    'rsm': "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
    'udt': "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
}

# Imcomplete, full list on https://service.unece.org/trade/untdid/d16b/tred/tred4461.htm
PAYMENT_MEAN_CODES = {
    'Payment to bank account': 42,
    'SEPA direct debit': 59
}


class AccountEdiXmlCii(AccountEdiCommon):
    _name = 'account.edi.xml.cii'
    _inherit = ['account.edi.common']
    _description = "Factur-x/XRechnung CII 2.2.0"

    @classmethod
    def _find_value(cls, xpath, tree, nsmap=False):
        # EXTENDS account.edi.common
        return super()._find_value(xpath, tree, CII_NAMESPACES)

    @classmethod
    def _export_invoice_filename(cls, invoice):
        if invoice.commercial_partner_id.country_code == 'DE':
            return f"{invoice.name.replace('/', '_')}_zugferd.xml"
        return f"{invoice.name.replace('/', '_')}_factur_x.xml"

    @classmethod
    def _export_invoice_ecosio_schematrons(cls):
        return {
            'invoice': 'de.xrechnung:cii:2.2.0',
            'credit_note': 'de.xrechnung:cii:2.2.0',
        }

    @classmethod
    def _export_invoice_constraints(cls, invoice, vals):
        constraints = cls._invoice_constraints_common(invoice)
        if invoice.move_type == 'out_invoice':
            # [BR-DE-1] An Invoice must contain information on "PAYMENT INSTRUCTIONS" (BG-16)
            # first check that a partner_bank_id exists, then check that there is an account number
            constraints.update({
                'seller_payment_instructions_1': cls._check_required_fields(
                    vals['record'], 'partner_bank_id'
                ),
                'seller_payment_instructions_2': cls._check_required_fields(
                    vals['record']['partner_bank_id'], 'sanitized_acc_number',
                    _("The field 'Sanitized Account Number' is required on the Recipient Bank.")
                ),
            })
        constraints.update({
            # [BR-08]-An Invoice shall contain the Seller postal address (BG-5).
            # [BR-09]-The Seller postal address (BG-5) shall contain a Seller country code (BT-40).
            'seller_postal_address': cls._check_required_fields(
                vals['record']['company_id']['partner_id']['commercial_partner_id'], 'country_id'
            ),
            # [BR-CO-26]-In order for the buyer to automatically identify a supplier, the Seller identifier (BT-29),
            # the Seller legal registration identifier (BT-30) and/or the Seller VAT identifier (BT-31) shall be present.
            'seller_identifier': cls._check_required_fields(
                vals['record']['company_id'], ['vat']  # 'siret'
            ),
            # [BR-DE-6] The element "Seller contact telephone number" (BT-42) must be transmitted.
            'seller_phone': cls._check_required_fields(
                vals['record']['company_id']['partner_id']['commercial_partner_id'], ['phone'],
            ),
            # [BR-DE-7] The element "Seller contact email address" (BT-43) must be transmitted.
            'seller_email': cls._check_required_fields(
                vals['record']['company_id'], 'email'
            ),
            # [BR-CO-04]-Each Invoice line (BG-25) shall be categorized with an Invoiced item VAT category code (BT-151).
            'tax_invoice_line': cls._check_required_tax(vals),
            # [BR-IC-02]-An Invoice that contains an Invoice line (BG-25) where the Invoiced item VAT category code (BT-151)
            # is "Intra-community supply" shall contain the Seller VAT Identifier (BT-31) or the Seller tax representative
            # VAT identifier (BT-63) and the Buyer VAT identifier (BT-48).
            'intracom_seller_vat': cls._check_required_fields(vals['record']['company_id'], 'vat') if vals['intracom_delivery'] else None,
            'intracom_buyer_vat': cls._check_required_fields(vals['record']['commercial_partner_id'], 'vat') if vals['intracom_delivery'] else None,
            # [BR-IG-05]-In an Invoice line (BG-25) where the Invoiced item VAT category code (BT-151) is "IGIC" the
            # invoiced item VAT rate (BT-152) shall be greater than 0 (zero).
            'igic_tax_rate': cls._check_non_0_rate_tax(vals)
                if vals['record']['partner_id']['country_id']['code'] == 'ES'
                    and vals['record']['partner_id']['zip']
                    and vals['record']['partner_id']['zip'][:2] in ['35', '38'] else None,
        })
        return constraints

    @classmethod
    def _check_required_tax(cls, vals):
        for line_vals in vals['invoice_line_vals_list']:
            line = line_vals['line']
            if not vals['tax_details']['tax_details_per_record'][line]['tax_details']:
                return _("You should include at least one tax per invoice line. [BR-CO-04]-Each Invoice line (BG-25) "
                         "shall be categorized with an Invoiced item VAT category code (BT-151).")

    @classmethod
    def _check_non_0_rate_tax(cls, vals):
        for line_vals in vals['tax_details']['tax_details_per_record']:
            tax_rate_list = line_vals.tax_ids.flatten_taxes_hierarchy().mapped("amount")
            if not any([rate > 0 for rate in tax_rate_list]):
                return _("When the Canary Island General Indirect Tax (IGIC) applies, the tax rate on "
                         "each invoice line should be greater than 0.")

    @classmethod
    def _get_scheduled_delivery_time(cls, invoice):
        # don't create a bridge only to get line.sale_line_ids.order_id.picking_ids.date_done
        # line.sale_line_ids.order_id.picking_ids.scheduled_date or line.sale_line_ids.order_id.commitment_date
        return invoice.delivery_date or invoice.invoice_date

    @classmethod
    def _get_invoicing_period(cls, invoice):
        # get the Invoicing period (BG-14): a list of dates covered by the invoice
        # don't create a bridge to get the date range from the timesheet_ids
        return [invoice.invoice_date]

    @classmethod
    def _get_exchanged_document_vals(cls, invoice):
        return {
            'id': invoice.name,
            'type_code': '380' if invoice.move_type == 'out_invoice' else '381',
            'issue_date_time': invoice.invoice_date,
            'included_note': html2plaintext(invoice.narration) if invoice.narration else "",
            'included_note_list': [],
        }

    @classmethod
    def _export_invoice_vals(cls, invoice):
        """≙ ``_export_invoice_vals`` (odoo19c: :127-256) — **bloqueado**: la mitad factura de account.move y env['account.payment']._fields no existen (0 hits)."""
        _blocked("_export_invoice_vals", "la mitad factura de account.move y env['account.payment']._fields no existen (0 hits)")

    @classmethod
    def _export_invoice(cls, invoice):
        """≙ ``_export_invoice`` (odoo19c: :258-262) — **bloqueado**: no hay motor QWeb (env[ir.qweb]) ni cleanup_xml_node en src/tools (0 hits)."""
        _blocked("_export_invoice", "no hay motor QWeb (env[ir.qweb]) ni cleanup_xml_node en src/tools (0 hits)")

    # -------------------------------------------------------------------------
    # IMPORT
    # -------------------------------------------------------------------------

    @classmethod
    def _import_retrieve_partner_vals(cls, tree, role):
        return {
            'vat': cls._find_value(f".//ram:{role}/ram:SpecifiedTaxRegistration/ram:ID[string-length(text()) > 5]", tree),
            'name': cls._find_value(f".//ram:{role}/ram:Name", tree),
            'phone': cls._find_value(f".//ram:{role}/ram:DefinedTradeContact/ram:TelephoneUniversalCommunication/ram:CompleteNumber", tree),
            'email': cls._find_value(f".//ram:{role}//ram:EmailURIUniversalCommunication/ram:URIID", tree),
            'postal_address': cls._get_postal_address(tree, role),
        }

    @classmethod
    def _get_postal_address(cls, tree, role):
        return {
            'country_code': cls._find_value(f'.//ram:{role}/ram:PostalTradeAddress//ram:CountryID', tree),
            'street': cls._find_value(f'.//ram:{role}/ram:PostalTradeAddress//ram:LineOne', tree),
            'additional_street': cls._find_value(f'.//ram:{role}/ram:PostalTradeAddress//ram:LineTwo', tree),
            'city': cls._find_value(f'.//ram:{role}/ram:PostalTradeAddress//ram:CityName', tree),
            'zip': cls._find_value(f'.//ram:{role}/ram:PostalTradeAddress//ram:PostcodeCode', tree),
        }

    @classmethod
    def _import_fill_invoice(cls, invoice, tree, qty_factor):
        """≙ ``_import_fill_invoice`` (odoo19c: :286-345) — **bloqueado**: la API de importacion de registros y el idioma Command no existen (0 hits)."""
        _blocked("_import_fill_invoice", "la API de importacion de registros y el idioma Command no existen (0 hits)")

    @classmethod
    def _get_tax_nodes(cls, tree):
        return tree.findall('.//{*}ApplicableTradeTax/{*}RateApplicablePercent')

    @classmethod
    def _get_document_allowance_charge_xpaths(cls):
        return {
            'root': './{*}SupplyChainTradeTransaction/{*}ApplicableHeaderTradeSettlement/{*}SpecifiedTradeAllowanceCharge',
            'charge_indicator': './{*}ChargeIndicator/{*}Indicator',
            'base_amount': './{*}BasisAmount',
            'amount': './{*}ActualAmount',
            'reason': './{*}Reason',
            'percentage': './{*}CalculationPercent',
            'tax_percentage': './{*}CategoryTradeTax/{*}RateApplicablePercent',
        }

    @classmethod
    def _get_invoice_line_xpaths(cls, document_type=False, qty_factor=1):
        return {
            'deferred_start_date': './{*}SpecifiedLineTradeSettlement/{*}BillingSpecifiedPeriod/{*}StartDateTime/{*}DateTimeString',
            'deferred_end_date': './{*}SpecifiedLineTradeSettlement/{*}BillingSpecifiedPeriod/{*}EndDateTime/{*}DateTimeString',
            'date_format': DEFAULT_FACTURX_DATE_FORMAT,
        }

    @classmethod
    def _get_line_xpaths(cls, document_type=False, qty_factor=1):
        return {
            'basis_qty': (
                './ram:SpecifiedLineTradeAgreement/ram:GrossPriceProductTradePrice/ram:BasisQuantity',
                './ram:SpecifiedLineTradeAgreement/ram:NetPriceProductTradePrice/ram:BasisQuantity',
            ),
            'gross_price_unit': './{*}SpecifiedLineTradeAgreement/{*}GrossPriceProductTradePrice/{*}ChargeAmount',
            'rebate': './{*}SpecifiedLineTradeAgreement/{*}GrossPriceProductTradePrice/{*}AppliedTradeAllowanceCharge/{*}ActualAmount',
            'net_price_unit': './{*}SpecifiedLineTradeAgreement/{*}NetPriceProductTradePrice/{*}ChargeAmount',
            'delivered_qty': './{*}SpecifiedLineTradeDelivery/{*}BilledQuantity',
            'allowance_charge': './/{*}SpecifiedLineTradeSettlement/{*}SpecifiedTradeAllowanceCharge',
            'allowance_charge_indicator': './{*}ChargeIndicator/{*}Indicator',
            'allowance_charge_amount': './{*}ActualAmount',
            'allowance_charge_reason': './{*}Reason',
            'allowance_charge_reason_code': './{*}ReasonCode',
            'line_total_amount': './{*}SpecifiedLineTradeSettlement/{*}SpecifiedTradeSettlementLineMonetarySummation/{*}LineTotalAmount',
            'name': [
                './ram:SpecifiedTradeProduct/ram:Description',
                './ram:SpecifiedTradeProduct/ram:Name',
            ],
            'product': {
                'default_code': './ram:SpecifiedTradeProduct/ram:SellerAssignedID',
                'name': './ram:SpecifiedTradeProduct/ram:Name',
                'barcode': './ram:SpecifiedTradeProduct/ram:GlobalID',
            },
        }

    # -------------------------------------------------------------------------
    # IMPORT : helpers
    # -------------------------------------------------------------------------

    @classmethod
    def _get_import_document_amount_sign(cls, tree):
        """
        In factur-x, an invoice has code 380 and a credit note has code 381. However, a credit note can be expressed
        as an invoice with negative amounts. For this case, we need a factor to take the opposite of each quantity
        in the invoice.
        """
        move_type_code = tree.find('.//{*}ExchangedDocument/{*}TypeCode')
        if move_type_code is None:
            return None, None
        if move_type_code.text == '381':
            return 'refund', 1
        if move_type_code.text == '380':
            amount_node = tree.find('.//{*}SpecifiedTradeSettlementHeaderMonetarySummation/{*}TaxBasisTotalAmount')
            if amount_node is not None and float(amount_node.text) < 0:
                return 'refund', -1
            return 'invoice', 1
        return None, None
