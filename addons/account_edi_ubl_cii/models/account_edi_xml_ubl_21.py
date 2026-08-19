r"""``account.edi.xml.ubl_21`` — la capa UBL 2.1 sobre UBL 2.0.

Adaptación de ``odoo19c: addons/account_edi_ubl_cii/models/account_edi_xml_ubl_21.py``
(``odoo-tools@622ddc2a``, LGPL-3, 75 líneas, 6 métodos) — atribución y aviso de
licencia preservados (DEC-KX-03).

Cobertura: **6 de 6 portados, 0 bloqueados.**

Familia ``account_edi_ubl_cii``: clase Python plana con ``@classmethod`` en vez
de ``AbstractModel``, y ``_inherit`` materializado como herencia de Python. La
convención, sus dos consecuencias y la tabla de piezas ausentes que bloquean el
lado de registros están declaradas una sola vez en
``account_edi_common.py`` — no se repiten aquí.
"""
from .account_edi_xml_ubl_20 import AccountEdiXmlUBL20


class AccountEdiXmlUbl_21(AccountEdiXmlUBL20):
    _name = 'account.edi.xml.ubl_21'
    _inherit = ['account.edi.xml.ubl_20']
    _description = "UBL 2.1"

    # -------------------------------------------------------------------------
    # EXPORT
    # -------------------------------------------------------------------------

    @classmethod
    def _export_invoice_filename(cls, invoice):
        return f"{invoice.name.replace('/', '_')}_ubl_21.xml"

    # -------------------------------------------------------------------------
    # EXPORT: Templates
    # -------------------------------------------------------------------------

    @classmethod
    def _get_invoice_node(cls, vals):
        document_node = super()._get_invoice_node(vals)

        if vals['document_type'] != 'invoice':
            # In UBL 2.1, Delivery, PaymentMeans, PaymentTerms exist also in DebitNote and CreditNote
            cls._add_invoice_delivery_nodes(document_node, vals)
            cls._add_invoice_payment_means_nodes(document_node, vals)
            cls._add_invoice_payment_terms_nodes(document_node, vals)

        return document_node

    @classmethod
    def _add_invoice_header_nodes(cls, document_node, vals):
        super()._add_invoice_header_nodes(document_node, vals)

        invoice = vals['invoice']
        document_node.update({
            'cbc:UBLVersionID': {'_text': '2.1'},
            'cbc:DueDate': {'_text': invoice.invoice_date_due} if vals['document_type'] == 'invoice' else None,
            'cbc:CreditNoteTypeCode': {'_text': 261 if vals['process_type'] == 'selfbilling' else 381} if vals['document_type'] == 'credit_note' else None,
            'cbc:BuyerReference': {'_text': invoice.commercial_partner_id.ref},
        })

    @classmethod
    def _add_document_allowance_charge_nodes(cls, document_node, vals):
        super()._add_document_allowance_charge_nodes(document_node, vals)

        # AllowanceCharge exists in debit notes only in UBL 2.1
        if vals['document_type'] == 'debit_note':
            document_node['cac:AllowanceCharge'] = []
            for base_line in vals['base_lines']:
                if cls._is_document_allowance_charge(base_line):
                    document_node['cac:AllowanceCharge'].append(
                        cls._get_document_allowance_charge_node({
                            **vals,
                            'base_line': base_line,
                        })
                    )

    @classmethod
    def _add_invoice_line_period_nodes(cls, line_node, vals):
        base_line = vals['base_line']

        # deferred_start_date & deferred_end_date are enterprise-only fields
        if (
            vals['document_type'] in {'invoice', 'credit_note'}
            and (base_line.get('deferred_start_date') or base_line.get('deferred_end_date'))
        ):
            line_node['cac:InvoicePeriod'] = {
                'cbc:StartDate': {'_text': base_line['deferred_start_date']},
                'cbc:EndDate': {'_text': base_line['deferred_end_date']},
            }

    @classmethod
    def _add_document_line_allowance_charge_nodes(cls, line_node, vals):
        line_node['cac:AllowanceCharge'] = []
        if node := cls._get_line_discount_allowance_charge_node(vals):
            line_node['cac:AllowanceCharge'].append(node)
        if vals['fixed_taxes_as_allowance_charges']:
            line_node['cac:AllowanceCharge'].extend(cls._get_line_fixed_tax_allowance_charge_nodes(vals))
