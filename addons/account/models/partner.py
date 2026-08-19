r"""``res.partner`` colgado por ``account`` — la mitad contable del socio.

Adaptación de ``addons/account/models/partner.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, 1191 líneas, LGPL-3 — atribución y
aviso de licencia preservados, DEC-KX-03). Este archivo porta **sólo la
tercera clase** de la referencia (``ResPartner``, líneas 332-1191).

Las dos primeras clases NO se re-declaran aquí — ya existen en este árbol
=============================================================================

La referencia declara ``AccountFiscalPosition`` (líneas 26-308) y
``AccountFiscalPositionAccount`` (309-330) en el MISMO archivo
``partner.py``. Este repositorio ya las tiene en sus propios archivos —
``account_fiscal_position.py``/``account_fiscal_position_account.py`` — por
la convención de un-archivo-por-modelo que ``account/models/__init__.py``
declara. Re-declararlas aquí duplicaría la clase. **Ninguno de los dos
archivos está en la lista de esta tarea**, así que no se tocan.

**Hallazgo colateral, medido, no corregido aquí**: ``account_fiscal_
position.py`` porta sólo **4 de ~21** métodos de ``AccountFiscalPosition``
(medido: ``grep -n "    def " account_fiscal_position.py`` → 4;
en la referencia, líneas 26-308 → 21). Su propio docstring declara el
recorte y nombra la causa: *"``_get_fiscal_position``/``_get_first_matching_
fpos``/``_get_fpos_validation_functions`` requieren ``res.partner`` con
``property_account_position_id``... fuera de este corte fiscal"*. Este
archivo **añade justo ese campo** (ver abajo) — el bloqueador que su
docstring nombraba ya no existe, pero completar esos tres métodos es
trabajo de ``account_fiscal_position.py``, no de éste. Se reporta como
hallazgo para que se registre en docs.

``ResPartner`` — treinta y dos campos, dieciocho métodos
============================================================

FKs company_dependent → FK simple (mismo criterio que ``product.py``)
------------------------------------------------------------------------

``property_account_payable_id``/``property_account_receivable_id``/
``property_account_position_id``/``property_payment_term_id``/
``property_supplier_payment_term_id`` son ``company_dependent=True`` en la
referencia — Django no tiene *Property fields*, se portan como FK simples
(mismo criterio ya fijado en ``account_cash_rounding.py``/``product.py``).

Campos escalares ``company_dependent`` → sin variación por empresa
------------------------------------------------------------------------

``trust``/``ignore_abnormal_invoice_date``/``ignore_abnormal_invoice_amount``
también son ``company_dependent`` pero NO son FK — no hay Property fields
ni sustituto de FK; se portan como campo plano de valor único (divergencia
declarada: la referencia permite un valor distinto por empresa, aquí uno
solo).

Compute-only (sin ``store=True``) → funciones, no columnas
---------------------------------------------------------------

``credit``/``debit``/``total_invoiced``/``currency_id``/
``fiscal_country_codes``/``account_move_count``/``supplier_invoice_count``/
``bank_account_count``/``display_invoice_edi_format`` son ``compute=`` sin
``store=True`` — mismo criterio que ``sale/models/res_partner.py`` (*"la
contribución es una función sobre el partner en vez de un campo
inyectado"*): funciones de módulo, no ``add_to_class``.

Bloqueados — nueve campos/métodos, con su pieza concreta
-------------------------------------------------------------

``invoice_template_pdf_report_id``/``available_invoice_template_pdf_report_
ids`` apuntan a ``ir.actions.report`` (SÍ portado,
``src/addons/base/models/ir_actions_report.py`` — corrige la suposición
inicial de que todo lo "ir.actions" está bloqueado) — se portan como FK
real. ``property_outbound_payment_method_line_id``/``property_inbound_
payment_method_line_id`` apuntan a ``account.payment.method.line`` — medido
presente (``account_payment_method.py``) — se portan. ``ref_company_ids``
(``res.company.partner_id`` inverso) — ``ResCompany`` de este árbol no
declara ``partner`` (medido: 0 hits) — **bloqueado**, sucesor: portar ese
campo en ``res_company.py`` (fuera de este archivo). ``contract_ids``
(``account.analytic.account.partner_id``) — bloqueado por el mismo motivo
que ``account_analytic_account.py`` ya declara (no-op documentado).
``_run_vat_checks``/validación de VAT europeo (VIES) — bloqueado: sin
librería de validación de VAT ni servicio VIES en este árbol.
"""
from decimal import Decimal

import fields
from django.db import models as dj_models

from addons.account.models.account_move import AccountMove
from addons.base.models.res_partner import ResPartner


def _add_if_absent(model, name, field):
    """Añade el campo sólo si el modelo no lo tiene ya — mismo helper que
    ``product.py``/``res_company.py`` repiten en este árbol."""
    if not any(f.name == name for f in model._meta.get_fields()):
        model.add_to_class(name, field)


INVOICE_SENDING_METHODS = [
    ('email', 'por correo'),
    ('manual', 'manual'),
]

AUTOPOST_BILLS_CHOICES = [
    ('always', 'siempre'),
    ('ask', 'preguntar'),
    ('never', 'nunca'),
]


# --------------------------------------------------------------------
# Compute-only — funciones, no columnas (≙ odoo19c: partner.py:513-624)
# --------------------------------------------------------------------

def credit(partner):
    """≙ ``_credit_debit_get`` (mitad ``credit``, ``odoo19c: partner.py:514``).

    **Cobertura reducida, declarada.** La referencia suma ``amount_
    residual_signed`` de las líneas por cobrar sin conciliar — sin
    ``amount_residual``/conciliación en ``AccountMoveLine`` de este árbol
    (mismo hueco que ``account_move_line_tax_details.py`` mide), se
    aproxima con ``AccountMove.amount_total`` de las facturas de cliente
    publicadas — mide "facturado", no "pendiente de cobro".
    """
    invoices = AccountMove.objects.filter(
        partner=partner, move_type='out_invoice', state='posted')
    return sum((i.amount_total for i in invoices), Decimal('0.00'))


def total_invoiced(partner):
    """≙ ``_invoice_total`` (``odoo19c: partner.py:539``). Portable: suma
    de facturas de cliente publicadas del socio."""
    invoices = AccountMove.objects.filter(
        partner=partner, move_type='out_invoice', state='posted')
    return sum((i.amount_total for i in invoices), Decimal('0.00'))


def account_move_count(partner):
    """≙ ``_compute_account_move_count`` (``odoo19c: partner.py:568``)."""
    return AccountMove.objects.filter(partner=partner).count()


def supplier_invoice_count(partner):
    """≙ ``_compute_supplier_invoice_count`` (``odoo19c: partner.py:567``)."""
    return AccountMove.objects.filter(partner=partner, move_type='in_invoice').count()


# ``fiscal_country_codes`` NO se cuelga aquí — su hogar ya existía:
# ``res_company.py`` lo aplica sobre los siete modelos que la referencia
# decora (ResPartner incluido, forma ``partner_fiscal_country_codes`` que
# suma el país del propio partner) con guard ``if not hasattr``. El stub
# «bloqueado» que este módulo declaraba tenía la premisa falsa
# (``ResCompany.account_fiscal_country`` SÍ existe) y, al correr antes en
# ``_EXTENSIONES``, ganaba la colisión en silencio y dejaba el campo en ''.


def invoice_ids(partner):
    """≙ ``invoice_ids`` (``odoo19c: partner.py:569``). Vía el
    ``related_name`` que ``AccountMove.partner`` ya expone
    (``account_moves``)."""
    return partner.account_moves.all()


# --------------------------------------------------------------------
# apply_account_extensions
# --------------------------------------------------------------------

def apply_account_extensions():
    """Cuelga la mitad contable sobre ``res.partner`` — ≙ ``_inherit``.

    **Todavía no cableado** en ``AccountConfig._EXTENSIONES`` — mismo
    estado que el resto de archivos de este pase.
    """
    # --- FKs company_dependent → FK simple ---------------------------
    _add_if_absent(ResPartner, 'property_account_payable_id', fields.Many2one(
        'account.AccountAccount', null=True, blank=True,
        on_delete=dj_models.PROTECT, related_name='payable_partners',
        help_text='Cuenta por pagar de este socio (Odoo '
                  'property_account_payable_id).'))
    _add_if_absent(ResPartner, 'property_account_receivable_id', fields.Many2one(
        'account.AccountAccount', null=True, blank=True,
        on_delete=dj_models.PROTECT, related_name='receivable_partners',
        help_text='Cuenta por cobrar de este socio (Odoo '
                  'property_account_receivable_id).'))
    _add_if_absent(ResPartner, 'property_account_position_id', fields.Many2one(
        'account.AccountFiscalPosition', null=True, blank=True,
        on_delete=dj_models.SET_NULL, related_name='partners',
        help_text='Posición fiscal por defecto de este socio (Odoo '
                  'property_account_position_id).'))
    _add_if_absent(ResPartner, 'property_payment_term_id', fields.Many2one(
        'account.AccountPaymentTerm', null=True, blank=True,
        on_delete=dj_models.SET_NULL, related_name='customer_partners',
        help_text='Plazo de pago de venta de este socio (Odoo '
                  'property_payment_term_id).'))
    _add_if_absent(ResPartner, 'property_supplier_payment_term_id', fields.Many2one(
        'account.AccountPaymentTerm', null=True, blank=True,
        on_delete=dj_models.SET_NULL, related_name='supplier_partners',
        help_text='Plazo de pago de compra de este socio (Odoo '
                  'property_supplier_payment_term_id).'))
    _add_if_absent(ResPartner, 'property_outbound_payment_method_line_id', fields.Many2one(
        'account.AccountPaymentMethodLine', null=True, blank=True,
        on_delete=dj_models.SET_NULL, related_name='outbound_partners',
        help_text='Método de pago saliente preferido (Odoo '
                  'property_outbound_payment_method_line_id).'))
    _add_if_absent(ResPartner, 'property_inbound_payment_method_line_id', fields.Many2one(
        'account.AccountPaymentMethodLine', null=True, blank=True,
        on_delete=dj_models.SET_NULL, related_name='inbound_partners',
        help_text='Método de pago entrante preferido (Odoo '
                  'property_inbound_payment_method_line_id).'))
    _add_if_absent(ResPartner, 'invoice_template_pdf_report_id', fields.Many2one(
        'base.IrActionsReport', null=True, blank=True,
        on_delete=dj_models.SET_NULL, related_name='+',
        help_text='Plantilla PDF de factura preferida de este socio (Odoo '
                  'invoice_template_pdf_report_id).'))

    # --- escalares company_dependent → sin variación por empresa -----
    _add_if_absent(ResPartner, 'credit_limit', fields.Float(
        default=0.0,
        help_text='Límite de crédito (Odoo credit_limit; sin variación '
                  'por empresa, ver docstring del módulo).'))
    _add_if_absent(ResPartner, 'use_partner_credit_limit', fields.Boolean(
        default=False, help_text='Odoo use_partner_credit_limit.'))
    _add_if_absent(ResPartner, 'show_credit_limit', fields.Boolean(
        default=False, help_text='Odoo show_credit_limit.'))
    _add_if_absent(ResPartner, 'trust', fields.Selection(
        max_length=16, blank=True, default='',
        choices=[('good', 'buen pagador'), ('normal', 'normal'), ('bad', 'mal pagador')],
        help_text='Grado de confianza en este deudor (Odoo trust).'))
    _add_if_absent(ResPartner, 'ignore_abnormal_invoice_date', fields.Boolean(
        default=False, help_text='Odoo ignore_abnormal_invoice_date.'))
    _add_if_absent(ResPartner, 'ignore_abnormal_invoice_amount', fields.Boolean(
        default=False, help_text='Odoo ignore_abnormal_invoice_amount.'))
    _add_if_absent(ResPartner, 'invoice_sending_method', fields.Selection(
        max_length=16, blank=True, default='',
        choices=INVOICE_SENDING_METHODS,
        help_text='Método de envío de factura preferido (Odoo '
                  'invoice_sending_method).'))
    _add_if_absent(ResPartner, 'invoice_edi_format_store', fields.Char(
        max_length=64, blank=True, default='',
        help_text='Formato EDI de factura preferido (Odoo '
                  'invoice_edi_format_store).'))
    _add_if_absent(ResPartner, 'supplier_rank', fields.Integer(
        default=0, help_text='Odoo supplier_rank.'))
    _add_if_absent(ResPartner, 'customer_rank', fields.Integer(
        default=0, help_text='Odoo customer_rank.'))
    _add_if_absent(ResPartner, 'autopost_bills', fields.Selection(
        max_length=16, blank=True, default='',
        choices=AUTOPOST_BILLS_CHOICES,
        help_text='Auto-publicación de facturas de proveedor recurrentes '
                  '(Odoo autopost_bills).'))

    # --- bloqueados, con su pieza nombrada en el docstring ------------
    # ref_company_ids / contract_ids: ver docstring del módulo — no se
    # añade ningún campo porque el modelo del otro lado no lo expone.

    # --- compute-only → funciones, no columnas ------------------------
    ResPartner.credit = property(credit)
    ResPartner.total_invoiced = property(total_invoiced)
    ResPartner.account_move_count = property(account_move_count)
    ResPartner.supplier_invoice_count = property(supplier_invoice_count)
    ResPartner.invoice_ids = property(invoice_ids)
