r"""``account.edi.xml.ubl_bis3`` — Peppol BIS Billing 3.0.12.

Adaptación de ``odoo19c: addons/account_edi_ubl_cii/models/account_edi_xml_ubl_bis3.py``
(``odoo-tools@622ddc2a``, LGPL-3, 400 líneas, 37 métodos) — atribución y aviso
de licencia preservados (DEC-KX-03).

Cobertura: 37 de 37 presentes — **33 portados, 4 bloqueados**
=============================================================

* ``_invoice_constraints_peppol_en16931_ubl`` — **LIBRE, pendiente de
  portar**. Estuvo bloqueado por ``stdnum``, que no era dependencia; su
  sucesor era declararla y **ya está declarada**
  (``python-stdnum>=2.0``, ``api@414b286f``). Valida NIF belga
  (``be_vat.is_valid``) y noruego (``mva.is_valid``), y ambos son **dígitos de
  control**, no normalizaciones — por eso no se vendorizaron: ``compact``
  normaliza y su resultado es verificable a ojo, mientras que una checksum mal
  transcrita produce **falsos errores de validación en silencio**. Portarlo
  contra la librería es la tarea **#292**.
* ``_import_order_payment_terms_id`` — ``AccountPaymentTerm._check_company_domain``
  no existe (0 hits).
* ``_import_order_ubl`` — ``markupsafe.Markup`` (0 en ``uv.lock``) más la API
  de importación de registros.
* ``_import_invoice_ubl_cii`` — la misma API de importación.

Herencia múltiple en el orden de la fuente
(``['account.edi.xml.ubl_21', 'account.edi.ubl_pint_eu']``); la linearización
C3 se verificó al escribir el archivo.

Familia ``account_edi_ubl_cii``: clase Python plana con ``@classmethod`` en vez
de ``AbstractModel``, y ``_inherit`` materializado como herencia de Python. La
convención, sus dos consecuencias y la tabla de piezas ausentes que bloquean el
lado de registros están declaradas una sola vez en
``account_edi_common.py`` — no se repiten aquí.
"""
from typing import Literal

from .account_edi_common import _blocked
from .account_edi_ubl_pint_eu import AccountEdiUBLPintEU
from .account_edi_xml_ubl_21 import AccountEdiXmlUbl_21
CHORUS_PRO_PEPPOL_ID = "0009:11000201100044"


class AccountEdiXmlUBLBIS3(AccountEdiXmlUbl_21, AccountEdiUBLPintEU):
    _name = "account.edi.xml.ubl_bis3"
    _inherit = ['account.edi.xml.ubl_21', 'account.edi.ubl_pint_eu']
    _description = "UBL BIS Billing 3.0.12"

    """
    * Documentation of EHF Billing 3.0: https://anskaffelser.dev/postaward/g3/
    * EHF 2.0 is no longer used:
      https://anskaffelser.dev/postaward/g2/announcement/2019-11-14-removal-old-invoicing-specifications/
    * Official doc for EHF Billing 3.0 is the OpenPeppol BIS 3 doc +
      https://anskaffelser.dev/postaward/g3/spec/current/billing-3.0/norway/

        "Based on work done in PEPPOL BIS Billing 3.0, Difi has included Norwegian rules in PEPPOL BIS Billing 3.0 and
        does not see a need to implement a different CIUS targeting the Norwegian market. Implementation of EHF Billing
        3.0 is therefore done by implementing PEPPOL BIS Billing 3.0 without extensions or extra rules."

    Thus, EHF 3 and Bis 3 are actually the same format. The specific rules for NO defined in Bis 3 are added in Bis 3.

    To avoid multi-parental inheritance in case of UBL 4.0, we're adding the sale/purchase logic here.
    * Documentation for Peppol Order transaction 3.5: https://docs.peppol.eu/poacc/upgrade-3/syntax/Order/tree/
    """

    @classmethod
    def _is_customer_behind_chorus_pro(cls, customer):
        return customer.peppol_eas and customer.peppol_endpoint and f"{customer.peppol_eas}:{customer.peppol_endpoint}" == CHORUS_PRO_PEPPOL_ID

    # -------------------------------------------------------------------------
    # EXPORT
    # -------------------------------------------------------------------------

    @classmethod
    def _export_invoice_filename(cls, invoice):
        return f"{invoice.name.replace('/', '_')}_ubl_bis3.xml"

    # -------------------------------------------------------------------------
    # EXPORT: BIS3 LAYER
    # -------------------------------------------------------------------------
    @classmethod
    def _can_export_selfbilling(cls):
        return bool(cls._get_customization_id(process_type='selfbilling'))

    @classmethod
    def _get_customization_id(cls, process_type: Literal['billing', 'selfbilling'] = 'billing'):
        if process_type == 'billing':
            return 'urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0'
        else:
            return 'urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:selfbilling:3.0'

    @classmethod
    def _add_invoice_accounting_supplier_party_nodes(cls, document_node, vals):
        # OVERRIDE
        sub_vals = {
            **vals,
            'document_node': document_node,
        }
        cls._ubl_add_accounting_supplier_party_node(sub_vals)

    @classmethod
    def _add_invoice_accounting_customer_party_nodes(cls, document_node, vals):
        # OVERRIDE
        sub_vals = {
            **vals,
            'document_node': document_node,
        }
        cls._ubl_add_accounting_customer_party_node(sub_vals)

    @classmethod
    def _add_invoice_delivery_nodes(cls, document_node, vals):
        # OVERRIDE
        sub_vals = {
            **vals,
            'document_node': document_node,
        }
        cls._ubl_add_delivery_nodes(sub_vals)

    @classmethod
    def _add_invoice_allowance_charge_nodes(cls, document_node, vals):
        # OVERRIDE
        sub_vals = {
            **vals,
            'document_node': document_node,
            'currency': vals['currency_id'],
        }
        cls._ubl_add_allowance_charge_nodes(sub_vals)

    @classmethod
    def _add_invoice_monetary_total_nodes(cls, document_node, vals):
        # OVERRIDE
        invoice = vals.get('invoice')
        if not invoice:
            return

        sub_vals = {
            **vals,
            'document_node': document_node,
            'currency': vals['currency_id'],
        }
        cls._ubl_add_legal_monetary_total_node(sub_vals)

    @classmethod
    def _add_invoice_payment_means_nodes(cls, document_node, vals):
        # OVERRIDE
        sub_vals = {
            **vals,
            'document_node': document_node,
            'currency': vals['currency_id'],
        }
        cls._ubl_add_payment_means_nodes(sub_vals)

    @classmethod
    def _add_invoice_payment_terms_nodes(cls, document_node, vals):
        # OVERRIDE
        sub_vals = {
            **vals,
            'document_node': document_node,
            'currency': vals['currency_id'],
        }

        cls._ubl_add_payment_terms_nodes(sub_vals)

    @classmethod
    def _add_invoice_tax_total_nodes(cls, document_node, vals):
        # OVERRIDE
        sub_vals = {
            **vals,
            'document_node': document_node,
            'currency': vals['currency_id'],
        }
        cls._ubl_add_tax_totals_nodes(sub_vals)

    @classmethod
    def _add_invoice_monetary_total_vals(cls, vals):
        # OVERRIDE
        pass

    @classmethod
    def _add_invoice_line_id_nodes(cls, line_node, vals):
        # OVERRIDE
        sub_vals = {
            **vals,
            'line_node': line_node,
            'base_line': vals['line_vals']['base_line'],
        }
        cls._ubl_add_line_id_node(sub_vals)

    @classmethod
    def _add_invoice_line_allowance_charge_nodes(cls, line_node, vals):
        # OVERRIDE
        sub_vals = {
            **vals,
            'line_node': line_node,
            'base_line': vals['line_vals']['base_line'],
        }
        cls._ubl_add_line_allowance_charge_nodes(sub_vals)

    @classmethod
    def _add_invoice_line_amount_nodes(cls, line_node, vals):
        # OVERRIDE
        sub_vals = {
            **vals,
            'line_node': line_node,
            'base_line': vals['line_vals']['base_line'],
        }

        if vals['document_type'] == 'credit_note':
            cls._ubl_add_line_credited_quantity_node(sub_vals)
        else:
            cls._ubl_add_line_invoiced_quantity_node(sub_vals)

        cls._ubl_add_line_extension_amount_node(sub_vals)

    @classmethod
    def _add_invoice_line_period_nodes(cls, line_node, vals):
        # OVERRIDE
        sub_vals = {
            **vals,
            'line_node': line_node,
            'base_line': vals['line_vals']['base_line'],
        }
        cls._ubl_add_line_period_nodes(sub_vals)

    @classmethod
    def _add_invoice_line_pricing_reference_nodes(cls, line_node, vals):
        # OVERRIDE
        sub_vals = {
            **vals,
            'line_node': line_node,
            'base_line': vals['line_vals']['base_line'],
        }
        cls._ubl_add_line_pricing_reference_node(sub_vals)

    @classmethod
    def _add_invoice_line_tax_total_nodes(cls, line_node, vals):
        # OVERRIDE
        sub_vals = {
            **vals,
            'line_node': line_node,
            'base_line': vals['line_vals']['base_line'],
        }
        cls._ubl_add_line_tax_totals_nodes(sub_vals)

    @classmethod
    def _add_invoice_line_tax_category_nodes(cls, line_node, vals):
        # OVERRIDE
        pass

    @classmethod
    def _add_invoice_line_item_nodes(cls, line_node, vals):
        # OVERRIDE
        sub_vals = {
            **vals,
            'line_node': line_node,
            'base_line': vals['line_vals']['base_line'],
        }
        cls._ubl_add_line_item_node(sub_vals)

    @classmethod
    def _add_invoice_line_price_nodes(cls, line_node, vals):
        # OVERRIDE
        sub_vals = {
            **vals,
            'line_node': line_node,
            'base_line': vals['line_vals']['base_line'],
        }
        cls._ubl_add_line_price_node(sub_vals)

    @classmethod
    def _ubl_add_invoice_line_node(cls, vals):
        # OVERRIDE. For retro-compatibility, ensure '_get_invoice_line_node' is called.
        sub_vals = {
            **vals,
            'base_line': vals['line_vals']['base_line'],
        }
        vals['line_node'].update(cls._get_invoice_line_node(sub_vals))

    @classmethod
    def _ubl_add_credit_note_line_node(cls, vals):
        # OVERRIDE. For retro-compatbility, ensure '_get_invoice_line_node' is called.
        sub_vals = {
            **vals,
            'base_line': vals['line_vals']['base_line'],
        }
        vals['line_node'].update(cls._get_invoice_line_node(sub_vals))

    @classmethod
    def _add_invoice_line_nodes(cls, document_node, vals):
        # OVERRIDE
        sub_vals = {
            **vals,
            'document_node': document_node,
            'currency': vals['currency_id'],
        }
        if vals['document_type'] == 'invoice':
            cls._ubl_add_invoice_line_nodes(sub_vals)
        elif vals['document_type'] == 'credit_note':
            cls._ubl_add_credit_note_line_nodes(sub_vals)

    @classmethod
    def _add_invoice_header_nodes(cls, document_node, vals):
        # OVERRIDE
        sub_vals = {
            **vals,
            'document_node': document_node,
            'currency': vals['currency_id'],
        }
        cls._ubl_add_version_id_node(sub_vals)
        cls._ubl_add_customization_id_node(sub_vals)
        cls._ubl_add_profile_id_node(sub_vals)
        cls._ubl_add_id_node(sub_vals)
        cls._ubl_add_copy_indicator_node(sub_vals)
        cls._ubl_add_issue_date_node(sub_vals)
        if vals['document_type'] == 'invoice':
            cls._ubl_add_due_date_node(sub_vals)
            cls._ubl_add_invoice_type_code_node(sub_vals)
        elif vals['document_type'] == 'credit_note':
            cls._ubl_add_credit_note_type_code_node(sub_vals)
        cls._ubl_add_notes_nodes(sub_vals)
        cls._ubl_add_document_currency_code_node(sub_vals)
        cls._ubl_add_tax_currency_code_node(sub_vals)
        cls._ubl_add_buyer_reference_node(sub_vals)
        cls._ubl_add_invoice_period_nodes(sub_vals)
        cls._ubl_add_order_reference_node(sub_vals)
        cls._ubl_add_billing_reference_nodes(sub_vals)

    @classmethod
    def _add_invoice_config_vals(cls, vals):
        super()._add_invoice_config_vals(vals)

        # There is no specifications for debit notes in BIS3, we'll concider them as invoices
        if vals['document_type'] == 'debit_note':
            vals['document_type'] = 'invoice'

        invoice = vals['invoice']
        vals.update(cls._init_invoice_export_values(invoice))

    @classmethod
    def _setup_base_lines(cls, vals):
        # OVERRIDE
        pass

    @classmethod
    def _add_invoice_base_lines_vals(cls, vals):
        # OVERRIDE
        pass

    @classmethod
    def _add_invoice_line_vals(cls, vals):
        # OVERRIDE
        pass

    # -------------------------------------------------------------------------
    # EXPORT: Constraints
    # -------------------------------------------------------------------------

    @classmethod
    def _export_invoice_constraints(cls, invoice, vals):
        constraints = super()._export_invoice_constraints(invoice, vals)
        constraints.update(cls._export_document_node_constraints(vals))

        constraints.update(
            cls._invoice_constraints_peppol_en16931_ubl(invoice, vals)
        )
        constraints.update(
            cls._invoice_constraints_cen_en16931_ubl(invoice, vals)
        )

        return constraints

    @classmethod
    def _invoice_constraints_cen_en16931_ubl(cls, invoice, vals):
        return {}

    @classmethod
    def _invoice_constraints_peppol_en16931_ubl(cls, invoice, vals):
        """≙ ``_invoice_constraints_peppol_en16931_ubl`` (odoo19c: :312-345) — **bloqueado**: stdnum no es dependencia de este arbol (0 hits en uv.lock): be_vat.is_valid/mva.is_valid son digitos de control, no se transcriben a mano."""
        _blocked("_invoice_constraints_peppol_en16931_ubl", "stdnum no es dependencia de este arbol (0 hits en uv.lock): be_vat.is_valid/mva.is_valid son digitos de control, no se transcriben a mano")

    # -------------------------------------------------------------------------
    # Sale/Purchase Order: Import
    # -------------------------------------------------------------------------

    @classmethod
    def _import_order_payment_terms_id(cls, company_id, tree, xpath):
        """≙ ``_import_order_payment_terms_id`` (odoo19c: :351-358) — **bloqueado**: AccountPaymentTerm._check_company_domain() no existe (0 hits)."""
        _blocked("_import_order_payment_terms_id", "AccountPaymentTerm._check_company_domain() no existe (0 hits)")

    @classmethod
    def _retrieve_order_vals(cls, order, tree):
        order_vals = {}
        logs = []

        order_vals['date_order'] = tree.findtext('.//{*}EndDate') or tree.findtext('.//{*}IssueDate')
        order_vals['note'] = cls._import_description(tree, xpaths=['./{*}Note'])
        order_vals['payment_term_id'] = cls._import_order_payment_terms_id(order.company_id, tree, './/cac:PaymentTerms/cbc:Note')
        order_vals['currency_id'], currency_logs = cls._import_currency(tree, './/{*}DocumentCurrencyCode')

        logs += currency_logs
        return order_vals, logs

    @classmethod
    def _import_order_ubl(cls, order, file_data, new):
        """≙ ``_import_order_ubl`` (odoo19c: :372-387) — **bloqueado**: markupsafe (0 en uv.lock) y la API de importacion de registros no existen."""
        _blocked("_import_order_ubl", "markupsafe (0 en uv.lock) y la API de importacion de registros no existen")

    @classmethod
    def _import_invoice_ubl_cii(cls, invoice, file_data, new=False):
        """≙ ``_import_invoice_ubl_cii`` (odoo19c: :389-400) — **bloqueado**: la API de importacion de registros no existe (0 hits)."""
        _blocked("_import_invoice_ubl_cii", "la API de importacion de registros no existe (0 hits)")
