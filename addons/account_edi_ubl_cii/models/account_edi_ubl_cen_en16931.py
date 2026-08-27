r"""``account.edi.ubl_cen_en16931`` — la capa CEN EN 16931 sobre UBL.

Adaptación de ``odoo19c: addons/account_edi_ubl_cii/models/account_edi_ubl_cen_en16931.py``
(``odoo-tools@622ddc2a``, LGPL-3, 201 líneas, 8 métodos) — atribución y aviso
de licencia preservados (DEC-KX-03).

Cobertura: 8 de 8 presentes — **6 portados, 2 bloqueados**
==========================================================

* ``_ubl_add_party_tax_scheme_nodes`` — bloqueado: lee
  ``env['account.tax']._fields`` (introspección del ORM de la referencia; este
  árbol usa ``Meta`` de Django, y el campo que consulta pertenece a la mitad
  *factura* de ``account.move`` que no está portada).
* ``_export_document_node_constraints`` — bloqueado: resuelve
  ``env.ref('base.europe')``, y no hay registro de xmlid en este árbol (GAP ya
  declarado por varios archivos de ``account``).

Familia ``account_edi_ubl_cii``: clase Python plana con ``@classmethod`` en vez
de ``AbstractModel``, y ``_inherit`` materializado como herencia de Python. La
convención, sus dos consecuencias y la tabla de piezas ausentes que bloquean el
lado de registros están declaradas una sola vez en
``account_edi_common.py`` — no se repiten aquí.
"""
from tools.translate import _

from .account_edi_common import _blocked
from .account_edi_ubl import AccountEdiUBL


class AccountEdiUBLCenEn16931(AccountEdiUBL):
    _name = "account.edi.ubl_cen_en16931"
    _inherit = 'account.edi.ubl'
    _description = "UBL CEN-EN16931"

    # -------------------------------------------------------------------------
    # EXPORT: NODES
    # -------------------------------------------------------------------------

    @classmethod
    def _ubl_add_line_allowance_charge_nodes(cls, vals):
        super()._ubl_add_line_allowance_charge_nodes(vals)

        # Discount.
        cls._ubl_add_line_allowance_charge_nodes_for_discount(vals)

        # Recycling contribution taxes.
        cls._ubl_add_line_allowance_charge_nodes_for_recycling_contribution_taxes(vals)

        # Excise taxes.
        cls._ubl_add_line_allowance_charge_nodes_for_excise_taxes(vals)

    @classmethod
    def _line_nodes_filter_base_lines(cls, vals, filter_function=None):
        # Early payment discount lines should not appear as lines but as allowances/charges.
        # Cash rounding lines should not appear as lines but in PayableRoundingAmount.
        def new_filter_function(base_line):
            if any([
                cls._ubl_is_early_payment_base_line(base_line),
                cls._ubl_is_global_discount_base_line(base_line),
                cls._ubl_is_cash_rounding_base_line(base_line),
            ]):
                return False
            return not filter_function or filter_function(base_line)

        return super()._line_nodes_filter_base_lines(vals, filter_function=new_filter_function)

    @classmethod
    def _ubl_add_party_tax_scheme_nodes(cls, vals):
        """≙ ``_ubl_add_party_tax_scheme_nodes`` (odoo19c: :41-53) — **bloqueado**: env['account.tax']._fields (introspeccion del ORM de la referencia) no tiene analogo."""
        _blocked("_ubl_add_party_tax_scheme_nodes", "env['account.tax']._fields (introspeccion del ORM de la referencia) no tiene analogo")

    @classmethod
    def _ubl_add_allowance_charge_nodes(cls, vals):
        super()._ubl_add_allowance_charge_nodes(vals)

        if cls._is_document(vals, 'invoice', 'credit_note', 'self_invoice', 'self_credit_note'):
            # Early payment discount lines are treated as allowances/charges.
            cls._ubl_add_allowance_charge_nodes_early_payment_discount(vals)
            # Global discount lines are treated as allowances/charges.
            cls._ubl_add_allowance_charge_nodes_global_discount(vals)

    @classmethod
    def _ubl_default_tax_category_grouping_key(cls, base_line, tax_data, vals, currency):
        # Recycling contribution taxes / excises should not appear anywhere as taxes but as allowances/charges.
        # Cash rounding lines should not appear as lines but in PayableRoundingAmount.
        # Since this method produces a default 0% tax automatically when no tax is set on the line by default,
        # we have to do something here to avoid it.
        if (
            cls._ubl_is_cash_rounding_base_line(base_line)
            or cls._ubl_is_recycling_contribution_tax(tax_data)
            or cls._ubl_is_excise_tax(tax_data)
        ):
            return
        return super()._ubl_default_tax_category_grouping_key(base_line, tax_data, vals, currency)

    @classmethod
    def _ubl_tax_totals_node_grouping_key(cls, base_line, tax_data, vals, currency):
        tax_total_keys = super()._ubl_tax_totals_node_grouping_key(base_line, tax_data, vals, currency)

        # [BR-E-10]-A VAT breakdown (BG-23) with VAT Category code (BT-118) "Exempt from VAT" shall have
        # a VAT exemption reason code (BT-121) or a VAT exemption reason text (BT-120).
        tax_category_key = tax_total_keys['tax_category_key']
        if (
            tax_category_key
            and tax_category_key['tax_category_code'] == 'E'
            and not tax_category_key.get('tax_exemption_reason')
        ):
            tax_category_key['tax_exemption_reason'] = _("Exempt from tax")

        return tax_total_keys

    @classmethod
    def _export_document_node_constraints(cls, vals):
        """≙ ``_export_document_node_constraints`` (odoo19c: :92-193) — **bloqueado**: env.ref('base.europe'): no hay registro de xmlid (0 hits)."""
        _blocked("_export_document_node_constraints", "env.ref('base.europe'): no hay registro de xmlid (0 hits)")

    @classmethod
    def _init_invoice_export_values(cls, invoice):
        vals = super()._init_invoice_export_values(invoice)

        # [BR-27]-The Item net price (BT-146) shall NOT be negative.
        cls._ubl_turn_base_lines_price_unit_as_always_positive(vals)

        return vals
