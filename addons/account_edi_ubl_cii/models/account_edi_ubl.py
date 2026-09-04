r"""``account.edi.ubl`` — los ayudantes base de UBL (el archivo grande del addon).

Adaptación de ``odoo19c: addons/account_edi_ubl_cii/models/account_edi_ubl.py``
(``odoo-tools@622ddc2a``, LGPL-3, **4038 líneas, 224 métodos**) — atribución y
aviso de licencia preservados (DEC-KX-03).

Cobertura: 224 de 224 símbolos presentes
=========================================

**157 portados** (cuerpo verbatim de la referencia, con la conversión a
``@classmethod`` que ``account_edi_common.py`` declara para toda la familia) y
**67 bloqueados por pieza nombrada**, cada uno con su ``_blocked(...)``.

Los 67 bloqueados son exactamente dos familias, no una lista arbitraria:

.. list-table::
   :header-rows: 1
   :widths: 8 32 60

   * - N
     - Familia
     - Pieza ausente que la bloquea (medida, 0 hits)
   * - 53
     - ``_import_ubl_*`` + ``_import_attachments`` + ``_ubl_import_invoice``
     - la API de importación de registros: ``AccountMove._get_edi_creation``,
       ``_get_line_vals_list``, ``AccountMove._fields``,
       ``ResPartner._retrieve_partner``, ``ProductProduct._retrieve_product``,
       ``AccountJournal._check_company_domain``,
       ``AccountMoveLine._predict_specific_account``, ``Command``/``fields.Date``
       (idiomas del ORM de la referencia), ``odoo.tools.pdf`` (``pypdf``: 0 en
       ``uv.lock``)
   * - 13
     - los ``_ubl_add_*`` que agregan importes
     - **la envoltura de base-lines de** ``account.tax``:
       ``_aggregate_base_lines_tax_details``,
       ``_aggregate_base_line_tax_details``,
       ``_aggregate_base_lines_aggregated_values``,
       ``_get_price_unit_without_tax``, ``_get_gross_total_without_tax``.
       ``account/models/account_tax.py:82-90`` declara explícitamente que esa
       envoltura **no se porta** en este árbol
   * - 1
     - ``_init_invoice_export_values``
     - ``AccountMove._get_rounded_base_and_tax_lines()`` (misma envoltura) más
       ``partner_shipping_id``/``child_ids``/``with_context``

**La puerta está bloqueada, las habitaciones no.** Los 157 portados operan
sobre ``dict`` —``vals``, ``document_node``, ``base_line``— y son
transformaciones puras: siguen siendo correctos y siguen siendo el valor de
este porte. Ningún camino de ejecución llega a ellos sin pasar antes por una
puerta bloqueada, que levanta ``UserError`` nombrando su causa. Sucesor
declarado: portar la envoltura de base-lines de ``account.tax`` + la mitad
*factura* de ``account.move`` (ver la tabla de piezas de
``account_edi_common.py``); ninguna de las dos cae en el write-set de este
pase.

Sustituciones de import (medidas)
==================================

.. list-table::
   :header-rows: 1
   :widths: 32 68

   * - Import de la fuente
     - Qué se usa aquí
   * - ``stdnum.be.vat``
     - **0 hits en ``uv.lock``**. Su único consumidor
       (``_ubl_add_party_legal_entity_nodes_iso_6523_icd``, dos llamadas a
       ``compact``) es un método **portado**, así que se vendoriza
       :func:`_be_vat_compact` con el algoritmo verbatim de ``stdnum``
   * - ``odoo.tools.frozendict`` · ``unique``
     - **no se traen**: sus únicos consumidores (``_ubl_add_values_tax_totals``,
       ``_ubl_add_tax_totals_nodes``, ``_import_ubl_invoice_add_payment_reference``)
       están bloqueados, y vendorizar código sin consumidor vivo es dejar
       código muerto. Se re-traen el día que se desbloqueen
   * - ``markupsafe.Markup`` · ``odoo.tools.pdf`` · ``str2bool`` · ``io`` · ``re``
     - ídem — sus consumidores viven en los 53 métodos de importación
   * - ``Command`` · ``fields`` · ``formatLang`` · ``UserError``
     - ídem. Los cuatro ``PEPPOL_*_OPTIONAL_*`` y
       ``EAS_MAPPING``/``UOM_TO_UNECE_CODE`` tampoco se importan aquí por la
       misma razón; siguen declarados en ``account_edi_common.py`` y en
       ``tools/ubl_20_optional_fields.py``, que es donde viven
   * - ``odoo.tools.html_escape`` / ``html2plaintext``
     - existen en ``src/tools`` y se usan tal cual

Los seis ``_logger.warning("DEPRECATED")`` de la referencia se conservan
verbatim: son parte del contrato de los métodos que la propia fuente marca
obsoletos, y borrarlos silenciaría un aviso que ella emite.
"""
import logging

from tools.mail import html2plaintext
from tools.misc import html_escape
from tools.translate import _

from ..tools import CreditNote, DebitNote, Invoice
from .account_edi_common import AccountEdiCommon, FloatFmt, GST_COUNTRY_CODES, _blocked

_logger = logging.getLogger(__name__)


def _be_vat_compact(number):
    """≙ ``stdnum.be.vat.compact`` — vendorizado.

    Se vendorizó cuando ``stdnum`` no era dependencia de este árbol. **Ya lo
    es** (``python-stdnum>=2.0`` en ``pyproject.toml``, ``api@414b286f``), así
    que esta copia dejó de ser necesaria y pasó a ser una segunda fuente de
    verdad: delegar en ``stdnum.be.vat.compact`` es la tarea **#292**.

    El algoritmo que replica: quitar espacios, puntos y guiones, mayúsculas,
    retirar el prefijo de país ``BE`` y rellenar con un cero a la izquierda el
    número de nueve dígitos (los NIF belgas anteriores a 2008 tenían nueve; el
    formato vigente tiene diez).
    """
    if not number:
        return number
    compacted = ''.join(
        char for char in str(number) if char not in ' -.').upper()
    if compacted.startswith('BE'):
        compacted = compacted[2:]
    if len(compacted) == 9:
        compacted = '0' + compacted
    return compacted

_logger = logging.getLogger(__name__)


class AccountEdiUBL(AccountEdiCommon):
    _name = "account.edi.ubl"
    _inherit = 'account.edi.common'
    _description = "Base helpers for UBL"

    # -------------------------------------------------------------------------
    # BASE LINES HELPERS
    # -------------------------------------------------------------------------

    @classmethod
    def _ubl_is_recycling_contribution_tax(cls, tax_data):
        """ Indicate if the 'tax_data' passed as parameter is a recycling contribution tax.

        :param tax_data:    One of the tax data in base_line['tax_details']['taxes_data'].
        :return:            True if tax_data['tax'] is a recycling contribution tax, False otherwise.
        """
        if not tax_data:
            return False

        tax = tax_data['tax']
        return tax.amount_type == 'fixed' and tax.include_base_amount

    @classmethod
    def _ubl_is_excise_tax(cls, tax_data):
        """ Indicate if the 'tax_data' passed as parameter is an excise tax.

        :param tax_data:    One of the tax data in base_line['tax_details']['taxes_data'].
        :return:            True if tax_data['tax'] is an excise tax, False otherwise.
        """
        if not tax_data:
            return False

        tax = tax_data['tax']
        return tax.amount_type == 'code' and tax.include_base_amount

    @classmethod
    def _ubl_is_reverse_charge_tax(cls, tax_data):
        """ Indicate if the 'tax_data' passed as parameter is an intracommunity reverse charge purchase tax.

        :param tax_data:    One of the tax data in base_line['tax_details']['taxes_data'].
        :return:            True if tax_data['tax'] is an intracommunity reverse charge purchase tax, False otherwise.
        """
        if not tax_data:
            return False

        tax = tax_data['tax']
        return tax.amount_type == 'percent' and tax.has_negative_factor

    @classmethod
    def _ubl_is_early_payment_base_line(cls, base_line):
        """ Indicate if the 'base_line' passed as parameter has been generated by an 'mixed' early payment.

        :param      base_line: A base line (see '_prepare_base_line_for_taxes_computation').
        :return:    True if the 'base_line' is a 'mixed' early payment line, False otherwise.
        """
        return base_line['special_type'] == 'early_payment'

    @classmethod
    def _ubl_is_global_discount_base_line(cls, base_line):
        """ Indicate if the 'base_line' passed as parameter is a global discount line.

        :param      base_line: A base line (see '_prepare_base_line_for_taxes_computation').
        :return:    True if the 'base_line' is a global discount line, False otherwise.
        """
        return base_line['special_type'] == 'global_discount'

    @classmethod
    def _ubl_is_cash_rounding_base_line(cls, base_line):
        """ Indicate if the 'base_line' passed as parameter has been generated by a cash rounding method.

        :param      base_line: A base line (see '_prepare_base_line_for_taxes_computation').
        :return:    True if the 'base_line' is a cash rounding line, False otherwise.
        """
        return base_line['special_type'] == 'cash_rounding'

    @classmethod
    def _ubl_default_tax_category_grouping_key(cls, base_line, tax_data, vals, currency):
        """≙ ``_ubl_default_tax_category_grouping_key`` (odoo19c: :92-157) — **bloqueado**: la envoltura de base-lines de account.tax no se porta (account/models/account_tax.py:82-90) — 0 hits."""
        _blocked('_ubl_default_tax_category_grouping_key', 'la envoltura de base-lines de account.tax no se porta (account/models/account_tax.py:82-90) — 0 hits')

    @classmethod
    def _ubl_default_tax_subtotal_tax_category_grouping_key(cls, tax_grouping_key, vals):
        """ Give the values about how taxes are grouped together in TaxTotal -> TaxSubtotal -> TaxCategory
        (or WithholdingTaxTotal depending on 'is_withholding').

        :param tax_grouping_key:            The grouping key returned by '_ubl_default_tax_category_grouping_key'.
        :param vals:                        Some custom data.
        :return:                            A dictionary that could be used as a grouping key for the taxes helpers.
        """
        return dict(tax_grouping_key)

    @classmethod
    def _ubl_default_tax_subtotal_grouping_key(cls, tax_category_grouping_key, vals):
        """ Give the values about how taxes are grouped together in TaxTotal -> TaxSubtotal
        (or WithholdingTaxTotal depending on 'is_withholding').

        :param tax_category_grouping_key:   The grouping key returned by '_ubl_default_tax_subtotal_tax_category_grouping_key'.
        :param vals:                        Some custom data.
        :return:                            A dictionary that could be used as a grouping key for the taxes helpers.
        """
        return dict(tax_category_grouping_key)

    @classmethod
    def _ubl_default_tax_total_grouping_key(cls, tax_subtotal_grouping_key, vals):
        """ Give the values about how taxes are grouped together in TaxTotal
        (or WithholdingTaxTotal depending on 'is_withholding').

        :param tax_subtotal_grouping_key:   The grouping key returned by '_ubl_default_tax_subtotal_grouping_key'.
        :param vals:                        Some custom data.
        :return:                            A dictionary that could be used as a grouping key for the taxes helpers.
        """
        return {
            'is_withholding': tax_subtotal_grouping_key['is_withholding'],
            'currency': tax_subtotal_grouping_key['currency'],
        }

    @classmethod
    def _ubl_default_allowance_charge_early_payment_grouping_key(cls, base_line, tax_data, vals, currency):
        """ Give the grouping key when generating the allowance/charge from an early payment discount.

        :param base_line:   A base line (see '_prepare_base_line_for_taxes_computation').
        :param tax_data:    One of the tax data in base_line['tax_details']['taxes_data'].
        :param vals:        Some custom data.
        :param currency:    The currency for which the grouping key is expressed.
        :return:            A dictionary that could be used as a grouping key for the taxes helpers.
        """
        if not cls._ubl_is_early_payment_base_line(base_line):
            return

        tax_grouping_key = cls._ubl_default_tax_category_grouping_key(base_line, tax_data, vals, currency)
        if not tax_grouping_key or tax_grouping_key['is_withholding']:
            return

        # We do not want to group the positive and negative lines together;
        # the following changes the grouping key to be like in 18.0 to 18.3.
        if tax_grouping_key['tax_category_code'] == 'E' and tax_data and tax_data['tax']:
            tax_grouping_key['tax_exemption_reason'] = None

        return tax_grouping_key

    @classmethod
    def _ubl_default_allowance_charge_global_discount_grouping_key(cls, base_line, tax_data, vals, currency):
        """ Give the grouping key when generating the allowance/charge from a global discount line.

        :param base_line:   A base line (see '_prepare_base_line_for_taxes_computation').
        :param tax_data:    One of the tax data in base_line['tax_details']['taxes_data'].
        :param vals:        Some custom data.
        :param currency:    The currency for which the grouping key is expressed.
        :return:            A dictionary that could be used as a grouping key for the taxes helpers.
        """
        if not cls._ubl_is_global_discount_base_line(base_line):
            return

        tax_grouping_key = cls._ubl_default_tax_category_grouping_key(base_line, tax_data, vals, currency)
        if not tax_grouping_key or tax_grouping_key['is_withholding']:
            return
        return tax_grouping_key

    @classmethod
    def _ubl_default_payable_amount_tax_withholding_grouping_key(cls, base_line, tax_data, vals, currency):
        """ Give the grouping key when moving the tax withholding amounts to PrepaidAmount.

        :param base_line:   A base line (see '_prepare_base_line_for_taxes_computation').
        :param tax_data:    One of the tax data in base_line['tax_details']['taxes_data'].
        :param vals:        Some custom data.
        :param currency:    The currency for which the grouping key is expressed.
        :return:            A dictionary that could be used as a grouping key for the taxes helpers.
        """
        if not tax_data:
            return
        tax_grouping_key = cls._ubl_default_tax_category_grouping_key(base_line, tax_data, vals, currency)
        if not tax_grouping_key:
            return
        return tax_grouping_key['is_withholding']

    @classmethod
    def _ubl_default_base_line_item_classified_tax_category_grouping_key(cls, base_line, tax_data, vals, currency):
        """ Give the grouping key when computing taxes for Item -> ClassifiedTaxCategory.

        :param base_line:   A base line (see '_prepare_base_line_for_taxes_computation').
        :param tax_data:    One of the tax data in base_line['tax_details']['taxes_data'].
        :param vals:        Some custom data.
        :param currency:    The currency for which the grouping key is expressed.
        :return:            A dictionary that could be used as a grouping key for the taxes helpers.
        """
        tax_grouping_key = cls._ubl_default_tax_category_grouping_key(base_line, tax_data, vals, currency)
        if not tax_grouping_key or tax_grouping_key['is_withholding']:
            return
        return tax_grouping_key

    @classmethod
    def _ubl_turn_base_lines_price_unit_as_always_positive(cls, vals):
        """ Helper to make sure the base_lines don't contain any negative price_unit.

        :param vals: Some custom data.
        """
        for base_line in vals['base_lines']:
            if base_line['price_unit'] < 0.0:
                base_line['quantity'] *= -1
                base_line['price_unit'] *= -1

    @classmethod
    def _ubl_turn_emptying_taxes_as_new_base_lines(cls, base_lines, company, vals):
        """≙ ``_ubl_turn_emptying_taxes_as_new_base_lines`` (odoo19c: :272-312) — **bloqueado**: la envoltura de base-lines de account.tax no se porta (account/models/account_tax.py:82-90) — 0 hits."""
        _blocked('_ubl_turn_emptying_taxes_as_new_base_lines', 'la envoltura de base-lines de account.tax no se porta (account/models/account_tax.py:82-90) — 0 hits')

    # -------------------------------------------------------------------------
    # EXPORT: Collecting data
    # -------------------------------------------------------------------------

    @classmethod
    def _ubl_add_values_company(cls, vals, company):
        vals['company'] = company

    @classmethod
    def _ubl_add_values_currency(cls, vals, currency):
        vals['currency'] = currency
        # TODO: For retro-compatibility with previous code
        vals['currency_id'] = currency

    @classmethod
    def _ubl_add_values_supplier(cls, vals, supplier):
        vals['supplier'] = supplier

    @classmethod
    def _ubl_add_values_customer(cls, vals, customer):
        vals['customer'] = customer

    @classmethod
    def _ubl_add_values_delivery(cls, vals, delivery):
        vals['delivery'] = delivery

    @classmethod
    def _ubl_add_base_line_ubl_values_allowance_charges_recycling_contribution(cls, vals):
        """ Extract recycling contribution taxes such as RECUPEL, AUVIBEL, etc from the current base lines.
        Instead, add them under 'base_line' -> '_ubl_values' -> 'allowance_charges_recycling_contribution'
        to be reported as allowances/charges.

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

        TO BE REMOVED IN MASTER

        :param vals:        Some custom data.
        """
        base_lines = vals['base_lines']
        company = vals['company']
        company_currency = company.currency_id
        currency = vals['currency_id']

        for base_line in base_lines:
            ubl_values = base_line['_ubl_values']
            tax_details = base_line['tax_details']
            taxes_data = tax_details['taxes_data']

            allowance_charges_recycling_contribution = ubl_values['allowance_charges_recycling_contribution'] = []
            allowance_charges_recycling_contribution_currency = ubl_values['allowance_charges_recycling_contribution_currency'] = []
            for tax_data in taxes_data:
                if cls._ubl_is_recycling_contribution_tax(tax_data):
                    allowance_charges_recycling_contribution.append({
                        'tax': tax_data['tax'],
                        'is_charge': tax_data['tax_amount'] > 0.0,
                        'amount': tax_data['tax_amount'],
                        'currency': company_currency,
                    })
                    allowance_charges_recycling_contribution_currency.append({
                        'tax': tax_data['tax'],
                        'is_charge': tax_data['tax_amount_currency'] > 0.0,
                        'amount': tax_data['tax_amount_currency'],
                        'currency': currency,
                    })

    @classmethod
    def _ubl_add_base_line_ubl_values_allowance_charges_excise(cls, vals):
        """ Extract excise taxes from the current base lines.
        Instead, add them under 'base_line' -> '_ubl_values' -> 'allowance_charges_excise'
        to be reported as allowances/charges.

        From a 'base_line' having
            price_unit = 99
            tax_ids = EXCISE of 1 + 21% tax
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

        TO BE REMOVED IN MASTER

        :param vals:        Some custom data.
        """
        base_lines = vals['base_lines']
        company = vals['company']
        company_currency = company.currency_id
        currency = vals['currency_id']

        for base_line in base_lines:
            ubl_values = base_line['_ubl_values']
            tax_details = base_line['tax_details']
            taxes_data = tax_details['taxes_data']

            allowance_charges_excise = ubl_values['allowance_charges_excise'] = []
            allowance_charges_excise_currency = ubl_values['allowance_charges_excise_currency'] = []
            for tax_data in taxes_data:
                if cls._ubl_is_excise_tax(tax_data):
                    allowance_charges_excise.append({
                        'tax': tax_data['tax'],
                        'is_charge': tax_data['tax_amount'] > 0.0,
                        'amount': tax_data['tax_amount'],
                        'currency': company_currency,
                    })
                    allowance_charges_excise_currency.append({
                        'tax': tax_data['tax'],
                        'is_charge': tax_data['tax_amount_currency'] > 0.0,
                        'amount': tax_data['tax_amount_currency'],
                        'currency': currency,
                    })

    @classmethod
    def _ubl_add_base_line_ubl_values_allowance_charges_discount(cls, vals):
        """ Extract the amount implies by a discount. This amount will be turned into an allowances/charge
        into 'base_line' -> '_ubl_values' -> 'allowance_charge_discount'.

        From a 'base_line' having
            price_unit = 100
            quantity = 5
            discount = 20
            total_excluded_currency = (5 * 100) * 0.8 = 400
        ... compute an 'allowance_charge_discount' or (5 * 100) - 400 = 100:

        TO BE REMOVED IN MASTER

        :param vals:        Some custom data.
        """
        base_lines = vals['base_lines']
        company = vals['company']
        company_currency = company.currency_id
        currency = vals['currency_id']

        for base_line in base_lines:
            ubl_values = base_line['_ubl_values']
            tax_details = base_line['tax_details']
            raw_discount_amount_currency = tax_details['raw_discount_amount_currency']
            raw_discount_amount = tax_details['raw_discount_amount']

            if (
                base_line['currency_id'].is_zero(raw_discount_amount_currency)
                and company.currency_id.is_zero(raw_discount_amount)
            ):
                ubl_values['allowance_charge_discount'] = None
                ubl_values['allowance_charge_discount_currency'] = None
            else:
                ubl_values['allowance_charge_discount'] = {
                    'currency': company_currency,
                    'percent': base_line['discount'],
                    'is_charge': raw_discount_amount < 0.0,
                    'amount': raw_discount_amount,
                    'base_amount': tax_details['raw_gross_total_excluded'],
                }
                ubl_values['allowance_charge_discount_currency'] = {
                    'currency': currency,
                    'percent': base_line['discount'],
                    'amount': raw_discount_amount_currency,
                    'is_charge': raw_discount_amount_currency < 0.0,
                    'base_amount': tax_details['raw_gross_total_excluded_currency'],
                }

    @classmethod
    def _ubl_add_base_line_ubl_values_line_extension_amount(cls, vals, use_company_currency=False):
        """ Add 'base_line' -> '_ubl_values' -> 'line_extension_amount[_currency]'.

        'line_extension_amount' is the subtotal of the line but without tax plus charges.

        TO BE REMOVED IN MASTER

        :param vals:                    Some custom data.
        :param use_company_currency:    Express the amount in company currency.
        """
        base_lines = vals['base_lines']
        suffix = '' if use_company_currency else '_currency'

        for base_line in base_lines:
            tax_details = base_line['tax_details']
            ubl_values = base_line['_ubl_values']
            amount = (
                tax_details[f'total_excluded{suffix}']
                + tax_details[f'delta_total_excluded{suffix}']
                + sum(
                    (1 if allowance_charge_values['is_charge'] else -1) * allowance_charge_values['amount']
                    for allowance_charge_values in ubl_values[f'allowance_charges_recycling_contribution{suffix}']
                )
                + sum(
                    (1 if allowance_charge_values['is_charge'] else -1) * allowance_charge_values['amount']
                    for allowance_charge_values in ubl_values[f'allowance_charges_excise{suffix}']
                )
            )
            ubl_values[f'line_extension_amount{suffix}'] = amount

    @classmethod
    def _ubl_add_base_line_ubl_values_item(cls, vals):
        """≙ ``_ubl_add_base_line_ubl_values_item`` (odoo19c: :515-551) — **bloqueado**: la envoltura de base-lines de account.tax no se porta (account/models/account_tax.py:82-90) — 0 hits."""
        _blocked('_ubl_add_base_line_ubl_values_item', 'la envoltura de base-lines de account.tax no se porta (account/models/account_tax.py:82-90) — 0 hits')

    @classmethod
    def _ubl_add_base_line_ubl_values_price(cls, vals):
        """ Add 'price_amount' under 'base_line' -> '_ubl_values' -> 'price_amount[_currency]'.

        'price_amount' is price unit of a single unit of the product.

        DEPRECATED: TO BE REMOVED IN MASTER

        :param vals:        Some custom data.
        """
        _logger.warning("DEPRECATED")
        base_lines = vals['base_lines']

        for base_line in base_lines:
            tax_details = base_line['tax_details']
            ubl_values = base_line['_ubl_values']
            for currency_suffix in ('_currency', ''):
                ubl_values[f'price_amount{currency_suffix}'] = tax_details[f'raw_gross_price_unit{currency_suffix}']

    @classmethod
    def _ubl_add_values_tax_currency_code_company_currency_if_foreign_currency(cls, vals):
        """ Add 'vals' -> '_ubl_values' -> 'tax_currency_code'

        The value is set only at the company currency when there is a foreign currency.

        DEPRECATED: TO BE REMOVED IN MASTER

        :param vals:    Some custom data.
        """
        _logger.warning("DEPRECATED")
        company = vals['company']
        currency = vals['currency_id']
        vals['tax_currency_code'] = None if currency == company.currency_id else company.currency_id.name

    @classmethod
    def _ubl_add_values_tax_currency_code_company_currency(cls, vals):
        """ Add 'vals' -> '_ubl_values' -> 'tax_currency_code'

        The company currency will always be set on it.

        DEPRECATED: TO BE REMOVED IN MASTER

        :param vals:    Some custom data.
        """
        _logger.warning("DEPRECATED")
        vals['tax_currency_code'] = vals['company'].currency_id.name

    @classmethod
    def _ubl_add_values_tax_currency_code_empty(cls, vals):
        """ Add 'vals' -> '_ubl_values' -> 'tax_currency_code'

        The value is empty.

        DEPRECATED: TO BE REMOVED IN MASTER

        :param vals:    Some custom data.
        """
        _logger.warning("DEPRECATED")
        vals['tax_currency_code'] = None

    @classmethod
    def _ubl_add_values_tax_currency_code(cls, vals):
        """ Add 'vals' -> '_ubl_values' -> 'tax_currency_code'

        DEPRECATED: TO BE REMOVED IN MASTER

        :param vals:    Some custom data.
        """
        _logger.warning("DEPRECATED")
        cls._ubl_add_values_tax_currency_code_company_currency_if_foreign_currency(vals)

    @classmethod
    def _ubl_add_values_tax_totals(cls, vals):
        """≙ ``_ubl_add_values_tax_totals`` (odoo19c: :619-756) — **bloqueado**: la envoltura de base-lines de account.tax no se porta (account/models/account_tax.py:82-90) — 0 hits."""
        _blocked('_ubl_add_values_tax_totals', 'la envoltura de base-lines de account.tax no se porta (account/models/account_tax.py:82-90) — 0 hits')

    @classmethod
    def _ubl_add_values_payable_amount_tax_withholding(cls, vals):
        # DEPRECATED: TO BE REMOVED IN MASTER
        """≙ ``_ubl_add_values_payable_amount_tax_withholding`` (odoo19c: :758-786) — **bloqueado**: la envoltura de base-lines de account.tax no se porta (account/models/account_tax.py:82-90) — 0 hits."""
        _blocked('_ubl_add_values_payable_amount_tax_withholding', 'la envoltura de base-lines de account.tax no se porta (account/models/account_tax.py:82-90) — 0 hits')

    @classmethod
    def _ubl_add_values_payable_rounding_amount(cls, vals):
        """≙ ``_ubl_add_values_payable_rounding_amount`` (odoo19c: :788-820) — **bloqueado**: la envoltura de base-lines de account.tax no se porta (account/models/account_tax.py:82-90) — 0 hits."""
        _blocked('_ubl_add_values_payable_rounding_amount', 'la envoltura de base-lines de account.tax no se porta (account/models/account_tax.py:82-90) — 0 hits')

    @classmethod
    def _ubl_add_values_allowance_charge_early_payment(cls, vals):
        """≙ ``_ubl_add_values_allowance_charge_early_payment`` (odoo19c: :822-881) — **bloqueado**: la envoltura de base-lines de account.tax no se porta (account/models/account_tax.py:82-90) — 0 hits."""
        _blocked('_ubl_add_values_allowance_charge_early_payment', 'la envoltura de base-lines de account.tax no se porta (account/models/account_tax.py:82-90) — 0 hits')

    # -------------------------------------------------------------------------
    # EXPORT: Building nodes
    # -------------------------------------------------------------------------

    @classmethod
    def _ubl_add_line_id_node(cls, vals):
        vals['line_node']['cbc:ID'] = {'_text': vals['line_vals']['index']}

    @classmethod
    def _ubl_add_line_note_nodes(cls, vals):
        vals['line_node']['cbc:Note'] = []

    @classmethod
    def _ubl_add_line_quantity_node(cls, vals):
        base_line = vals['line_vals']['base_line']
        vals['line_node']['cbc:Quantity'] = {
            '_text': base_line['quantity'],
            'unitCode': cls._get_uom_unece_code(base_line['product_uom_id']),
        }

    @classmethod
    def _ubl_add_line_invoiced_quantity_node(cls, vals):
        base_line = vals['line_vals']['base_line']
        vals['line_node']['cbc:InvoicedQuantity'] = {
            '_text': base_line['quantity'],
            'unitCode': cls._get_uom_unece_code(base_line['product_uom_id']),
        }

    @classmethod
    def _ubl_add_line_credited_quantity_node(cls, vals):
        base_line = vals['line_vals']['base_line']
        vals['line_node']['cbc:CreditedQuantity'] = {
            '_text': base_line['quantity'],
            'unitCode': cls._get_uom_unece_code(base_line['product_uom_id']),
        }

    @classmethod
    def _ubl_add_line_debited_quantity_node(cls, vals):
        base_line = vals['line_vals']['base_line']
        vals['line_node']['cbc:DebitedQuantity'] = {
            '_text': base_line['quantity'],
            'unitCode': cls._get_uom_unece_code(base_line['product_uom_id']),
        }

    @classmethod
    def _ubl_add_line_item_name_description_nodes(cls, vals):
        item_node = vals['item_node']
        base_line = vals['line_vals']['base_line']

        line_name = name = base_line.get('name') or ''  # Regular business line.
        description = None
        if product := base_line['product_id']:
            name = product.display_name
            description = line_name.replace(name, '').strip()  # Remove the redundant product's name from the description.
        elif base_line.get('_removed_tax_data'):
            # Emptying tax extra line.
            name = base_line['_removed_tax_data']['tax'].name

        if description:
            item_node['cbc:Description'] = {'_text': description}
        else:
            item_node['cbc:Description'] = None

        if name:
            item_node['cbc:Name'] = {'_text': name}
        else:
            item_node['cbc:Name'] = None

    @classmethod
    def _ubl_add_line_item_identification_nodes(cls, vals):
        item_node = vals['item_node']
        base_line = vals['line_vals']['base_line']
        product = base_line['product_id']

        if product.default_code:
            item_node['cac:SellersItemIdentification'] = {
                'cbc:ID': {'_text': product.default_code},
            }
        else:
            item_node['cac:SellersItemIdentification'] = None
        if product.barcode:
            item_node['cac:StandardItemIdentification'] = {
                'cbc:ID': {
                    '_text': product.barcode,
                    'schemeID': '0160',  # GTIN
                },
            }
        else:
            item_node['cac:StandardItemIdentification'] = None

    @classmethod
    def _ubl_add_line_item_additional_item_property_nodes(cls, vals):
        item_node = vals['item_node']
        base_line = vals['line_vals']['base_line']
        product = base_line['product_id']

        item_node['cac:AdditionalItemProperty'] = [
            {
                'cbc:Name': {'_text': value.attribute_id.name},
                'cbc:Value': {'_text': value.name},
            }
            for value in product.product_template_attribute_value_ids
        ]

    @classmethod
    def _ubl_get_line_item_commodity_classification_node_from_intrastat_code(cls, vals, intrastat_code):
        return {
            'cbc:ItemClassificationCode': {
                '_text': intrastat_code.code,
                'listID': 'HS',
                'listVersionID': None,
            }
        }

    @classmethod
    def _ubl_get_line_item_commodity_classification_node_from_unspsc_code(cls, vals, unspsc_code):
        return {
            'cbc:ItemClassificationCode': {
                '_text': unspsc_code.code,
                'listID': 'TST',
                'listVersionID': None,
            }
        }

    @classmethod
    def _ubl_get_line_item_commodity_classification_node_from_cpv_code(cls, vals, cpv_code):
        return {
            'cbc:ItemClassificationCode': {
                '_text': cpv_code.code,
                'listID': 'STI',
                'listVersionID': None,
            }
        }

    @classmethod
    def _ubl_get_line_item_commodity_classification_node_from_cg_code(cls, vals, cg_code):
        return {
            'cbc:ItemClassificationCode': {
                '_text': cg_code.name,
                'listID': 'CG',
                'listVersionID': None,
            }
        }

    @classmethod
    def _ubl_add_line_item_commodity_classification_nodes(cls, vals):
        item_node = vals['item_node']
        base_line = vals['line_vals']['base_line']
        product = base_line['product_id']
        nodes = item_node['cac:CommodityClassification'] = []

        if cls.module_installed('account_intrastat'):
            intrastat_code = product.intrastat_code_id
            if intrastat_code.code:
                nodes.append(cls._ubl_get_line_item_commodity_classification_node_from_intrastat_code(vals, intrastat_code))

        if cls.module_installed('product_unspsc'):
            unspsc_code = product.unspsc_code_id
            if unspsc_code.code:
                nodes.append(cls._ubl_get_line_item_commodity_classification_node_from_unspsc_code(vals, unspsc_code))

        if cls.module_installed('l10n_ro_cpv_code'):
            cpv_code = product.cpv_code_id
            if cpv_code.code:
                nodes.append(cls._ubl_get_line_item_commodity_classification_node_from_cpv_code(vals, cpv_code))

        if cls.module_installed('l10n_hr_edi'):
            cg_code = base_line.get('cg_item_classification_code') or product.l10n_hr_kpd_category_id
            if cg_code.name:
                nodes.append(cls._ubl_get_line_item_commodity_classification_node_from_cg_code(vals, cg_code))

        return nodes

    @classmethod
    def _ubl_get_line_item_node_classified_tax_category_node(cls, vals, tax_category):
        """ Generate the node 'cac:ClassifiedTaxCategory' in 'cac:Item'.

        :param vals:            Some custom data.
        :param tax_category:    An entry of vals['_ubl_values']['item_classified_tax_categories']
                                containing all the necessary data to build the node.
        :return:                A new node in 'cac:Item' -> 'cac:ClassifiedTaxCategory'.
        """
        return {
            '_currency': tax_category['currency'],
            'cbc:ID': {'_text': tax_category['tax_category_code']},
            'cbc:Name': {'_text': None},
            'cbc:Percent': {'_text': tax_category['percent']},
            'cbc:TaxExemptionReasonCode': {'_text': None},
            'cbc:TaxExemptionReason': {'_text': None},
            'cac:TaxScheme': {
                'cbc:ID': {'_text': tax_category['scheme_id']},
            }
        }

    @classmethod
    def _ubl_add_line_item_classified_tax_category_nodes(cls, vals, in_foreign_currency=True):
        """≙ ``_ubl_add_line_item_classified_tax_category_nodes`` (odoo19c: :1062-1087) — **bloqueado**: la envoltura de base-lines de account.tax no se porta (account/models/account_tax.py:82-90) — 0 hits."""
        _blocked('_ubl_add_line_item_classified_tax_category_nodes', 'la envoltura de base-lines de account.tax no se porta (account/models/account_tax.py:82-90) — 0 hits')

    @classmethod
    def _ubl_add_line_item_node(cls, vals):
        node = vals['line_node']['cac:Item'] = {}
        sub_vals = {**vals, 'item_node': node}
        cls._ubl_add_line_item_name_description_nodes(sub_vals)
        cls._ubl_add_line_item_identification_nodes(sub_vals)
        cls._ubl_add_line_item_additional_item_property_nodes(sub_vals)
        cls._ubl_add_line_item_commodity_classification_nodes(sub_vals)
        cls._ubl_add_line_item_classified_tax_category_nodes(sub_vals)

    @classmethod
    def _ubl_add_line_price_node(cls, vals, in_foreign_currency=True):
        """≙ ``_ubl_add_line_price_node`` (odoo19c: :1098-1120) — **bloqueado**: la envoltura de base-lines de account.tax no se porta (account/models/account_tax.py:82-90) — 0 hits."""
        _blocked('_ubl_add_line_price_node', 'la envoltura de base-lines de account.tax no se porta (account/models/account_tax.py:82-90) — 0 hits')

    @classmethod
    def _ubl_get_line_item_node(cls, vals, item_values):
        # TO BE REMOVED IN MASTER
        _logger.warning("DEPRECATED")
        item_node = {}
        base_line = item_values['base_line']
        product = base_line['product_id']

        if product.default_code:
            item_node['cac:SellersItemIdentification'] = {
                'cbc:ID': {'_text': product.default_code},
            }
        else:
            item_node['cac:SellersItemIdentification'] = None
        if product.barcode:
            item_node['cac:StandardItemIdentification'] = {
                'cbc:ID': {
                    '_text': product.barcode,
                    'schemeID': '0160',  # GTIN
                },
            }
        else:
            item_node['cac:StandardItemIdentification'] = None
        item_node['cac:AdditionalItemProperty'] = [
            {
                'cbc:Name': {'_text': value.attribute_id.name},
                'cbc:Value': {'_text': value.name},
            }
            for value in product.product_template_attribute_value_ids
        ]

        if base_line.get('_removed_tax_data'):
            # Emptying tax extra line.
            name = description = base_line['_removed_tax_data']['tax'].name
        else:
            name = product.name or ''
            if line_name := base_line.get('name'):
                # Regular business line.
                description = line_name
                if not name:
                    name = line_name
            else:
                # Undefined line.
                description = product.description_sale or ''

        if description:
            item_node['cbc:Description'] = {'_text': description}
        else:
            item_node['cbc:Description'] = None

        if name:
            item_node['cbc:Name'] = {'_text': name}
        else:
            item_node['cbc:Name'] = None

        item_node['cac:ClassifiedTaxCategory'] = [
            cls._ubl_get_line_item_node_classified_tax_category_node(vals, tax_category)
            for tax_category in item_values['classified_tax_categories'].values()
        ]
        return item_node

    @classmethod
    def _ubl_get_line_allowance_charge_recycling_contribution_node(cls, vals, recycling_contribution_values):
        currency = recycling_contribution_values['currency']
        amount = recycling_contribution_values['amount']
        tax = recycling_contribution_values['tax']
        if 'bebat' in tax.name.lower():
            charge_reason_code = 'CAV'
        else:
            charge_reason_code = 'AEO'
        is_charge = recycling_contribution_values['is_charge']
        return {
            '_currency': currency,
            'cbc:ChargeIndicator': {'_text': 'true' if is_charge else 'false'},
            'cbc:AllowanceChargeReasonCode': {'_text': charge_reason_code if is_charge else '100'},
            'cbc:AllowanceChargeReason': {'_text': tax.name},
            'cbc:Amount': {
                '_text': FloatFmt(abs(amount), max_dp=currency.decimal_places),
                'currencyID': currency.name,
            },
        }

    @classmethod
    def _ubl_get_line_allowance_charge_excise_node(cls, vals, excise_values):
        currency = excise_values['currency']
        amount = excise_values['amount']
        tax = excise_values['tax']
        is_charge = excise_values['is_charge']
        return {
            '_currency': currency,
            'cbc:ChargeIndicator': {'_text': 'true' if is_charge else 'false'},
            'cbc:AllowanceChargeReason': {'_text': tax.name},
            'cbc:Amount': {
                '_text': FloatFmt(abs(amount), max_dp=currency.decimal_places),
                'currencyID': currency.name,
            },
        }

    @classmethod
    def _ubl_get_line_allowance_charge_discount_node(cls, vals, discount_values):
        currency = discount_values['currency']
        amount = discount_values['amount']
        base_amount = discount_values['base_amount']
        percent = discount_values['percent']
        is_charge = discount_values['is_charge']
        return {
            '_currency': currency,
            'cbc:ChargeIndicator': {'_text': 'true' if is_charge else 'false'},
            'cbc:MultiplierFactorNumeric': {'_text': abs(percent)},
            'cbc:AllowanceChargeReasonCode': {'_text': 'ADK' if is_charge else '95'},
            'cbc:AllowanceChargeReason': {'_text': _("Discount")},
            'cbc:Amount': {
                '_text': FloatFmt(abs(amount), max_dp=currency.decimal_places),
                'currencyID': currency.name,
            },
            'cbc:BaseAmount': {
                '_text': FloatFmt(abs(base_amount), max_dp=currency.decimal_places),
                'currencyID': currency.name,
            },
        }

    @classmethod
    def _ubl_add_line_allowance_charge_nodes_for_discount(cls, vals, in_foreign_currency=True):
        line_node = vals['line_node']
        base_line = vals['line_vals']['base_line']
        currency = base_line['currency_id'] if in_foreign_currency else vals['company_currency']
        suffix = '_currency' if in_foreign_currency else ''
        tax_details = base_line['tax_details']

        raw_discount_amount = tax_details[f'discount_amount{suffix}']
        if currency.is_zero(raw_discount_amount):
            return

        allowance_charges_nodes = line_node['cac:AllowanceCharge']
        allowance_charges_nodes.append(cls._ubl_get_line_allowance_charge_discount_node(vals, {
            'currency': currency,
            'percent': base_line['discount'],
            'is_charge': raw_discount_amount < 0.0,
            'amount': raw_discount_amount,
            'base_amount': tax_details[f'gross_total_excluded{suffix}'],
        }))

    @classmethod
    def _ubl_add_line_allowance_charge_nodes_for_recycling_contribution_taxes(cls, vals, in_foreign_currency=True):
        line_node = vals['line_node']
        base_line = vals['line_vals']['base_line']
        currency = base_line['currency_id'] if in_foreign_currency else vals['company_currency']
        suffix = '_currency' if in_foreign_currency else ''

        allowance_charges_nodes = line_node['cac:AllowanceCharge']
        for tax_data in base_line['tax_details']['taxes_data']:
            if not cls._ubl_is_recycling_contribution_tax(tax_data):
                continue

            allowance_charges_nodes.append(cls._ubl_get_line_allowance_charge_recycling_contribution_node(vals, {
                'tax': tax_data['tax'],
                'is_charge': tax_data['tax_amount'] > 0.0,
                'amount': tax_data[f'tax_amount{suffix}'],
                'currency': currency,
            }))

    @classmethod
    def _ubl_add_line_allowance_charge_nodes_for_excise_taxes(cls, vals, in_foreign_currency=True):
        line_node = vals['line_node']
        base_line = vals['line_vals']['base_line']
        currency = base_line['currency_id'] if in_foreign_currency else vals['company_currency']
        suffix = '_currency' if in_foreign_currency else ''

        allowance_charges_nodes = line_node['cac:AllowanceCharge']
        for tax_data in base_line['tax_details']['taxes_data']:
            if not cls._ubl_is_excise_tax(tax_data):
                continue

            allowance_charges_nodes.append(cls._ubl_get_line_allowance_charge_excise_node(vals, {
                'tax': tax_data['tax'],
                'is_charge': tax_data['tax_amount'] > 0.0,
                'amount': tax_data[f'tax_amount{suffix}'],
                'currency': currency,
            }))

    @classmethod
    def _ubl_add_line_allowance_charge_nodes(cls, vals):
        vals['line_node']['cac:AllowanceCharge'] = []

    @classmethod
    def _ubl_add_line_extension_amount_node(cls, vals, in_foreign_currency=True):
        line_node = vals['line_node']
        base_line = vals['line_vals']['base_line']
        currency = base_line['currency_id'] if in_foreign_currency else vals['company_currency']
        suffix = '_currency' if in_foreign_currency else ''
        tax_details = base_line['tax_details']

        gross_total_excluded = currency.round(tax_details[f'raw_gross_total_excluded{suffix}'])
        for allowance_charge_node in line_node['cac:AllowanceCharge']:
            sign = 1 if allowance_charge_node['cbc:ChargeIndicator']['_text'] == 'true' else -1
            gross_total_excluded += sign * allowance_charge_node['cbc:Amount']['_text']

        line_node['cbc:LineExtensionAmount'] = {
            '_text': FloatFmt(gross_total_excluded, min_dp=currency.decimal_places),
            'currencyID': currency.name,
        }

    @classmethod
    def _ubl_add_line_period_nodes(cls, vals):
        nodes = vals['line_node']['cac:InvoicePeriod'] = []

        if cls._is_document(vals, 'invoice', 'credit_note', 'self_invoice', 'self_credit_note'):
            base_line = vals['line_vals']['base_line']
            if base_line.get('deferred_start_date') or base_line.get('deferred_end_date'):
                nodes.append({
                    'cbc:StartDate': {'_text': base_line['deferred_start_date']},
                    'cbc:EndDate': {'_text': base_line['deferred_end_date']},
                })

    @classmethod
    def _ubl_add_line_pricing_reference_node(cls, vals):
        vals['line_node']['cac:PricingReference'] = {}

    @classmethod
    def _ubl_add_line_tax_totals_nodes(cls, vals):
        vals['line_node']['cac:TaxTotal'] = []

    @classmethod
    def _line_nodes_filter_base_lines(cls, vals, filter_function=None):
        index = 1
        for base_line in vals['base_lines']:
            if not filter_function or filter_function(base_line):
                line_vals = {'base_line': base_line, 'index': index}
                line_node = {}
                index += 1
                yield {**vals, 'line_vals': line_vals, 'line_node': line_node}

    @classmethod
    def _ubl_add_party_endpoint_id_node(cls, vals):
        vals['party_node']['cbc:EndpointID'] = {
            '_text': None,
            'schemeID': None,
        }

    @classmethod
    def _ubl_add_party_identification_nodes_iso_6523_icd(cls, vals):
        nodes = vals['party_node']['cac:PartyIdentification']
        partner = vals['party_vals']['partner']
        commercial_partner = partner.commercial_partner_id
        country_code = commercial_partner.country_code

        if country_code == 'BE' and commercial_partner.company_registry:
            nodes.append({
                'cbc:ID': {
                    '_text': _be_vat_compact(commercial_partner.company_registry),
                    'schemeID': '0208',
                },
            })

    @classmethod
    def _ubl_add_party_identification_nodes(cls, vals):
        vals['party_node']['cac:PartyIdentification'] = []

    @classmethod
    def _ubl_add_party_name_node(cls, vals):
        partner = vals['party_vals']['partner']

        # When the selected partner is a contact or an invoice address, there is nothing ensuring the partner's name is set.
        # In that case, fallback on the commercial partner's name.
        if partner.name:
            name = partner.display_name
        else:
            name = partner.commercial_partner_id.display_name

        vals['party_node']['cac:PartyName'] = {
            'cbc:Name': {'_text': name},
        }

    @classmethod
    def _ubl_get_partner_address_node(cls, vals, partner):
        return {
            'cbc:StreetName': {'_text': partner.street},
            'cbc:AdditionalStreetName': {'_text': partner.street2},
            'cbc:CityName': {'_text': partner.city},
            'cbc:PostalZone': {'_text': partner.zip},
            'cbc:CountrySubentity': {'_text': partner.state_id.name},
            'cbc:CountrySubentityCode': {'_text': partner.state_id.code},
            'cac:Country': {
                'cbc:IdentificationCode': {'_text': partner.country_id.code},
                'cbc:Name': {'_text': partner.country_id.name},
            },
        }

    @classmethod
    def _ubl_add_party_postal_address_node(cls, vals):
        partner = vals['party_vals']['partner']
        vals['party_node']['cac:PostalAddress'] = cls._ubl_get_partner_address_node(vals, partner)

    @classmethod
    def _ubl_add_party_tax_scheme_nodes_vat_gst(cls, vals):
        nodes = vals['party_node']['cac:PartyTaxScheme']
        partner = vals['party_vals']['partner']
        commercial_partner = partner.commercial_partner_id
        country_code = commercial_partner.country_code
        if not country_code:
            return

        if commercial_partner.vat and commercial_partner.vat != '/':
            vat = commercial_partner.vat
            country_code = commercial_partner.country_id.code
            if country_code in GST_COUNTRY_CODES:
                tax_scheme_id = 'GST'
            else:
                tax_scheme_id = 'VAT'

            if country_code == 'HU' and not vat.upper().startswith('HU'):
                vat = 'HU' + vat[:8]
            elif country_code == 'DK' and not vat.upper().startswith('DK'):
                vat = 'DK' + vat

            nodes.append({
                'cbc:CompanyID': {'_text': vat},
                'cac:TaxScheme': {
                    'cbc:ID': {'_text': tax_scheme_id},
                },
            })

    @classmethod
    def _ubl_add_party_tax_scheme_nodes(cls, vals):
        vals['party_node']['cac:PartyTaxScheme'] = []

    @classmethod
    def _ubl_add_party_legal_entity_nodes_iso_6523_icd(cls, vals):
        nodes = vals['party_node']['cac:PartyLegalEntity']
        partner = vals['party_vals']['partner']
        commercial_partner = partner.commercial_partner_id
        vat = commercial_partner.vat != '/' and commercial_partner.vat

        if commercial_partner.peppol_eas in ('0106', '0190'):
            nl_id = commercial_partner.peppol_endpoint
        else:
            nl_id = commercial_partner.company_registry

        if commercial_partner.country_code == 'NL' and nl_id:
            # For NL, VAT can be used as a Peppol endpoint, but KVK/OIN has to be used as PartyLegalEntity/CompanyID
            # To implement a workaround on stable, company_registry field is used without recording whether
            # the number is a KVK or OIN, and the length of the number (8 = KVK, 20 = OIN) is used to determine the type
            nodes.append({
                'cbc:RegistrationName': {'_text': commercial_partner.name},
                'cbc:CompanyID': {
                    '_text': nl_id,
                    'schemeID': '0190' if len(nl_id) == 20 else '0106',
                },
            })
        elif commercial_partner.country_code == 'LU' and commercial_partner.company_registry:
            nodes.append({
                'cbc:RegistrationName': {'_text': commercial_partner.name},
                'cbc:CompanyID': {
                    '_text': commercial_partner.company_registry,
                    'schemeID': None,
                },
            })
        elif commercial_partner.country_code == 'SE' and commercial_partner.company_registry:
            nodes.append({
                'cbc:RegistrationName': {'_text': commercial_partner.name},
                'cbc:CompanyID': {
                    '_text': ''.join(char for char in commercial_partner.company_registry if char.isdigit()),
                },
            })
        elif commercial_partner.country_code == 'BE' and commercial_partner.company_registry:
            nodes.append({
                'cbc:RegistrationName': {'_text': commercial_partner.name},
                'cbc:CompanyID': {
                    '_text': _be_vat_compact(commercial_partner.company_registry),
                    'schemeID': '0208',
                },
            })
        elif (
            commercial_partner.country_code == 'DK'
            and commercial_partner.peppol_eas == '0184'
            and commercial_partner.peppol_endpoint
        ):
            nodes.append({
                'cbc:RegistrationName': {'_text': commercial_partner.name},
                'cbc:CompanyID': {
                    '_text': commercial_partner.peppol_endpoint,
                    'schemeID': '0184',
                },
            })
        elif commercial_partner.country_code == 'AU' and vat:
            nodes.append({
                'cbc:RegistrationName': {'_text': commercial_partner.name},
                'cbc:CompanyID': {
                    '_text': commercial_partner.vat,
                    'schemeID': '0151',
                },
            })
        elif commercial_partner.country_code == 'NZ' and vat:
            nodes.append({
                'cbc:RegistrationName': {'_text': commercial_partner.name},
                'cbc:CompanyID': {
                    '_text': commercial_partner.vat,
                    'schemeID': '0088',
                },
            })
        elif commercial_partner.vat and commercial_partner.vat != '/':
            nodes.append({
                'cbc:RegistrationName': {'_text': commercial_partner.name},
                'cbc:CompanyID': {
                    '_text': commercial_partner.vat,
                    'schemeID': None,
                },
            })
        elif commercial_partner.peppol_endpoint:
            nodes.append({
                'cbc:RegistrationName': {'_text': commercial_partner.name},
                'cbc:CompanyID': {
                    '_text': commercial_partner.peppol_endpoint,
                    'schemeID': None,
                },
            })

    @classmethod
    def _ubl_add_party_legal_entity_nodes(cls, vals):
        vals['party_node']['cac:PartyLegalEntity'] = []

    @classmethod
    def _ubl_add_party_contact_node(cls, vals):
        partner = vals['party_vals']['partner']
        vals['party_node']['cac:Contact'] = {
            'cbc:ID': {'_text': None},
            'cbc:Name': {'_text': partner.name},
            'cbc:Telephone': {'_text': partner.phone},
            'cbc:ElectronicMail': {'_text': partner.email},
        }

    @classmethod
    def _ubl_add_accounting_supplier_party_endpoint_id_node(cls, vals):
        cls._ubl_add_party_endpoint_id_node(vals)

    @classmethod
    def _ubl_add_accounting_supplier_party_identification_nodes(cls, vals):
        cls._ubl_add_party_identification_nodes(vals)

    @classmethod
    def _ubl_add_accounting_supplier_party_name_node(cls, vals):
        cls._ubl_add_party_name_node(vals)

    @classmethod
    def _ubl_add_accounting_supplier_party_postal_address_node(cls, vals):
        cls._ubl_add_party_postal_address_node(vals)

    @classmethod
    def _ubl_add_accounting_supplier_party_tax_scheme_nodes(cls, vals):
        cls._ubl_add_party_tax_scheme_nodes(vals)

    @classmethod
    def _ubl_add_accounting_supplier_party_legal_entity_nodes(cls, vals):
        cls._ubl_add_party_legal_entity_nodes(vals)

    @classmethod
    def _ubl_add_accounting_supplier_party_contact_node(cls, vals):
        cls._ubl_add_party_contact_node(vals)

    @classmethod
    def _ubl_add_accounting_supplier_party_node(cls, vals):
        node = vals['document_node']['cac:AccountingSupplierParty'] = {'cac:Party': {}}
        party_node = node['cac:Party']
        sub_vals = {
            **vals,
            'party_vals': {'partner': vals['supplier']},
            'party_node': party_node,
        }
        cls._ubl_add_accounting_supplier_party_endpoint_id_node(sub_vals)
        cls._ubl_add_accounting_supplier_party_identification_nodes(sub_vals)
        cls._ubl_add_accounting_supplier_party_name_node(sub_vals)
        cls._ubl_add_accounting_supplier_party_postal_address_node(sub_vals)
        cls._ubl_add_accounting_supplier_party_tax_scheme_nodes(sub_vals)
        cls._ubl_add_accounting_supplier_party_legal_entity_nodes(sub_vals)
        cls._ubl_add_accounting_supplier_party_contact_node(sub_vals)

    @classmethod
    def _ubl_add_accounting_customer_party_endpoint_id_node(cls, vals):
        cls._ubl_add_party_endpoint_id_node(vals)

    @classmethod
    def _ubl_add_accounting_customer_party_identification_nodes(cls, vals):
        cls._ubl_add_party_identification_nodes(vals)

    @classmethod
    def _ubl_add_accounting_customer_party_name_node(cls, vals):
        cls._ubl_add_party_name_node(vals)

    @classmethod
    def _ubl_add_accounting_customer_party_postal_address_node(cls, vals):
        cls._ubl_add_party_postal_address_node(vals)

    @classmethod
    def _ubl_add_accounting_customer_party_tax_scheme_nodes(cls, vals):
        cls._ubl_add_party_tax_scheme_nodes(vals)

    @classmethod
    def _ubl_add_accounting_customer_party_legal_entity_nodes(cls, vals):
        cls._ubl_add_party_legal_entity_nodes(vals)

    @classmethod
    def _ubl_add_accounting_customer_party_contact_node(cls, vals):
        cls._ubl_add_party_contact_node(vals)

    @classmethod
    def _ubl_add_accounting_customer_party_node(cls, vals):
        node = vals['document_node']['cac:AccountingCustomerParty'] = {'cac:Party': {}}
        party_node = node['cac:Party']
        sub_vals = {
            **vals,
            'party_vals': {'partner': vals['customer']},
            'party_node': party_node,
        }
        cls._ubl_add_accounting_customer_party_endpoint_id_node(sub_vals)
        cls._ubl_add_accounting_customer_party_identification_nodes(sub_vals)
        cls._ubl_add_accounting_customer_party_name_node(sub_vals)
        cls._ubl_add_accounting_customer_party_postal_address_node(sub_vals)
        cls._ubl_add_accounting_customer_party_tax_scheme_nodes(sub_vals)
        cls._ubl_add_accounting_customer_party_legal_entity_nodes(sub_vals)
        cls._ubl_add_accounting_customer_party_contact_node(sub_vals)

    @classmethod
    def _ubl_add_seller_supplier_party_node(cls, vals):
        node = vals['document_node']['cac:SellerSupplierParty'] = {'cac:Party': {}}
        party_node = node['cac:Party']
        sub_vals = {
            **vals,
            'party_vals': {'partner': vals['supplier']},
            'party_node': party_node,
        }
        cls._ubl_add_accounting_supplier_party_endpoint_id_node(sub_vals)
        cls._ubl_add_accounting_supplier_party_identification_nodes(sub_vals)
        cls._ubl_add_accounting_supplier_party_name_node(sub_vals)
        cls._ubl_add_accounting_supplier_party_postal_address_node(sub_vals)
        cls._ubl_add_accounting_supplier_party_tax_scheme_nodes(sub_vals)
        cls._ubl_add_accounting_supplier_party_legal_entity_nodes(sub_vals)
        cls._ubl_add_accounting_supplier_party_contact_node(sub_vals)

    @classmethod
    def _ubl_add_buyer_customer_party_node(cls, vals):
        node = vals['document_node']['cac:BuyerCustomerParty'] = {'cac:Party': {}}
        party_node = node['cac:Party']
        sub_vals = {
            **vals,
            'party_vals': {'partner': vals['customer']},
            'party_node': party_node,
        }
        cls._ubl_add_accounting_customer_party_endpoint_id_node(sub_vals)
        cls._ubl_add_accounting_customer_party_identification_nodes(sub_vals)
        cls._ubl_add_accounting_customer_party_name_node(sub_vals)
        cls._ubl_add_accounting_customer_party_postal_address_node(sub_vals)
        cls._ubl_add_accounting_customer_party_tax_scheme_nodes(sub_vals)
        cls._ubl_add_accounting_customer_party_legal_entity_nodes(sub_vals)
        cls._ubl_add_accounting_customer_party_contact_node(sub_vals)

    @classmethod
    def _ubl_add_delivery_party_endpoint_id_node(cls, vals):
        cls._ubl_add_party_endpoint_id_node(vals)

    @classmethod
    def _ubl_add_delivery_party_identification_nodes(cls, vals):
        cls._ubl_add_party_identification_nodes(vals)

    @classmethod
    def _ubl_add_delivery_party_name_node(cls, vals):
        cls._ubl_add_party_name_node(vals)

    @classmethod
    def _ubl_add_delivery_party_postal_address_node(cls, vals):
        cls._ubl_add_party_postal_address_node(vals)

    @classmethod
    def _ubl_add_delivery_party_tax_scheme_nodes(cls, vals):
        cls._ubl_add_party_tax_scheme_nodes(vals)

    @classmethod
    def _ubl_add_delivery_party_legal_entity_nodes(cls, vals):
        cls._ubl_add_party_legal_entity_nodes(vals)

    @classmethod
    def _ubl_add_delivery_party_contact_node(cls, vals):
        cls._ubl_add_party_contact_node(vals)

    @classmethod
    def _ubl_get_delivery_node_from_delivery_address(cls, vals):
        delivery_partner = vals['delivery']
        node = {
            'cbc:ActualDeliveryDate': {'_text': None},
            'cac:DeliveryLocation': {
                'cbc:ID': {
                    'schemeID': None,
                    '_text': None,
                },
                'cac:Address': cls._ubl_get_partner_address_node(vals, delivery_partner),
            },
        }

        if cls.module_installed('account_add_gln') and delivery_partner.global_location_number:
            node['cac:DeliveryLocation']['cbc:ID']['schemeID'] = '0088'
            node['cac:DeliveryLocation']['cbc:ID']['_text'] = delivery_partner.global_location_number

        if cls._is_document(vals, 'invoice', 'credit_note', 'self_invoice', 'self_credit_note'):
            invoice = vals['invoice']
            if invoice.delivery_date:
                node['cbc:ActualDeliveryDate']['_text'] = invoice.delivery_date

        party_node = node['cac:DeliveryParty'] = {}

        sub_vals = {
            **vals,
            'party_vals': {'partner': vals['delivery']},
            'party_node': party_node,
        }
        cls._ubl_add_delivery_party_endpoint_id_node(sub_vals)
        cls._ubl_add_delivery_party_identification_nodes(sub_vals)
        cls._ubl_add_delivery_party_name_node(sub_vals)
        cls._ubl_add_delivery_party_postal_address_node(sub_vals)
        cls._ubl_add_delivery_party_tax_scheme_nodes(sub_vals)
        cls._ubl_add_delivery_party_legal_entity_nodes(sub_vals)
        cls._ubl_add_delivery_party_contact_node(sub_vals)

        return node

    @classmethod
    def _ubl_add_delivery_nodes(cls, vals):
        nodes = vals['document_node']['cac:Delivery'] = []

        if vals.get('delivery'):
            nodes.append(cls._ubl_get_delivery_node_from_delivery_address(vals))

    @classmethod
    def _ubl_add_invoice_line_node(cls, vals):
        cls._ubl_add_line_id_node(vals)
        cls._ubl_add_line_note_nodes(vals)
        cls._ubl_add_line_invoiced_quantity_node(vals)
        cls._ubl_add_line_allowance_charge_nodes(vals)
        cls._ubl_add_line_extension_amount_node(vals)
        cls._ubl_add_line_period_nodes(vals)
        cls._ubl_add_line_pricing_reference_node(vals)
        cls._ubl_add_line_tax_totals_nodes(vals)
        cls._ubl_add_line_item_node(vals)
        cls._ubl_add_line_price_node(vals)

    @classmethod
    def _ubl_add_invoice_line_nodes(cls, vals, filter_function=None):
        nodes = vals['document_node']['cac:InvoiceLine'] = []
        for sub_vals in cls._line_nodes_filter_base_lines(vals, filter_function=filter_function):
            cls._ubl_add_invoice_line_node(sub_vals)
            nodes.append(sub_vals['line_node'])

    @classmethod
    def _ubl_add_credit_note_line_node(cls, vals):
        cls._ubl_add_line_id_node(vals)
        cls._ubl_add_line_note_nodes(vals)
        cls._ubl_add_line_credited_quantity_node(vals)
        cls._ubl_add_line_allowance_charge_nodes(vals)
        cls._ubl_add_line_extension_amount_node(vals)
        cls._ubl_add_line_period_nodes(vals)
        cls._ubl_add_line_pricing_reference_node(vals)
        cls._ubl_add_line_tax_totals_nodes(vals)
        cls._ubl_add_line_item_node(vals)
        cls._ubl_add_line_price_node(vals)

    @classmethod
    def _ubl_add_credit_note_line_nodes(cls, vals, filter_function=None):
        nodes = vals['document_node']['cac:CreditNoteLine'] = []
        for sub_vals in cls._line_nodes_filter_base_lines(vals, filter_function=filter_function):
            cls._ubl_add_credit_note_line_node(sub_vals)
            nodes.append(sub_vals['line_node'])

    @classmethod
    def _ubl_add_debit_note_line_node(cls, vals):
        cls._ubl_add_line_id_node(vals)
        cls._ubl_add_line_note_nodes(vals)
        cls._ubl_add_line_debited_quantity_node(vals)
        cls._ubl_add_line_allowance_charge_nodes(vals)
        cls._ubl_add_line_extension_amount_node(vals)
        cls._ubl_add_line_period_nodes(vals)
        cls._ubl_add_line_pricing_reference_node(vals)
        cls._ubl_add_line_tax_totals_nodes(vals)
        cls._ubl_add_line_item_node(vals)
        cls._ubl_add_line_price_node(vals)

    @classmethod
    def _ubl_add_debit_note_line_nodes(cls, vals, filter_function=None):
        nodes = vals['document_node']['cac:DebitNoteLine'] = []
        for sub_vals in cls._line_nodes_filter_base_lines(vals, filter_function=filter_function):
            cls._ubl_add_debit_note_line_node(sub_vals)
            nodes.append(sub_vals['line_node'])

    @classmethod
    def _ubl_add_version_id_node(cls, vals):
        vals['document_node']['cbc:UBLVersionID'] = {'_text': None}

    @classmethod
    def _ubl_add_customization_id_node(cls, vals):
        vals['document_node']['cbc:CustomizationID'] = {'_text': None}

    @classmethod
    def _ubl_add_profile_id_node(cls, vals):
        vals['document_node']['cbc:ProfileID'] = {'_text': None}

    @classmethod
    def _ubl_add_id_node(cls, vals):
        vals['document_node']['cbc:ID'] = {'_text': None}

        if cls._is_document(vals, 'invoice', 'credit_note', 'self_invoice', 'self_credit_note'):
            vals['document_node']['cbc:ID']['_text'] = vals['invoice'].name

    @classmethod
    def _ubl_add_copy_indicator_node(cls, vals):
        vals['document_node']['cbc:CopyIndicator'] = {'_text': None}

    @classmethod
    def _ubl_add_issue_date_node(cls, vals):
        issue_date_node = vals['document_node']['cbc:IssueDate'] = {'_text': None}
        vals['document_node']['cbc:IssueTime'] = {'_text': None}

        if cls._is_document(vals, 'invoice', 'credit_note', 'self_invoice', 'self_credit_note'):
            issue_date_node['_text'] = vals['invoice'].invoice_date

    @classmethod
    def _ubl_add_due_date_node(cls, vals):
        due_date_node = vals['document_node']['cbc:DueDate'] = {'_text': None}

        if cls._is_document(vals, 'invoice', 'credit_note', 'self_invoice', 'self_credit_note'):
            due_date_node['_text'] = vals['invoice'].invoice_date_due

    @classmethod
    def _ubl_add_invoice_type_code_node(cls, vals):
        vals['document_node']['cbc:InvoiceTypeCode'] = {'_text': None}

    @classmethod
    def _ubl_add_credit_note_type_code_node(cls, vals):
        vals['document_node']['cbc:CreditNoteTypeCode'] = {'_text': None}

    @classmethod
    def _ubl_add_order_type_code_node(cls, vals):
        vals['document_node']['cbc:OrderTypeCode'] = {'_text': None}

    @classmethod
    def _ubl_add_notes_nodes(cls, vals):
        vals['document_node']['cbc:Note'] = []

    @classmethod
    def _ubl_add_document_currency_code_node_foreign_currency(cls, vals):
        vals['document_node']['cbc:DocumentCurrencyCode'] = {'_text': vals['currency'].name}

    @classmethod
    def _ubl_add_document_currency_code_node_company_currency(cls, vals):
        vals['document_node']['cbc:DocumentCurrencyCode'] = {'_text': vals['company'].currency_id.name}

    @classmethod
    def _ubl_add_document_currency_code_node(cls, vals):
        vals['document_node']['cbc:DocumentCurrencyCode'] = {'_text': None}

    @classmethod
    def _ubl_add_tax_currency_code_node_company_currency_if_foreign_currency(cls, vals):
        company = vals['company']
        currency = vals['currency_id']
        vals['document_node']['cbc:TaxCurrencyCode'] = {'_text': None if currency == company.currency_id else company.currency_id.name}

    @classmethod
    def _ubl_add_tax_currency_code_node_company_currency(cls, vals):
        vals['document_node']['cbc:TaxCurrencyCode'] = {'_text': vals['company'].currency_id.name}

    @classmethod
    def _ubl_add_tax_currency_code_node_empty(cls, vals):
        vals['document_node']['cbc:TaxCurrencyCode'] = {'_text': None}

    @classmethod
    def _ubl_add_tax_currency_code_node(cls, vals):
        vals['document_node']['cbc:TaxCurrencyCode'] = {'_text': None}

    @classmethod
    def _ubl_add_buyer_reference_node(cls, vals):
        vals['document_node']['cbc:BuyerReference'] = {'_text': None}

    @classmethod
    def _ubl_add_invoice_period_nodes(cls, vals):
        vals['document_node']['cac:InvoicePeriod'] = {}

    @classmethod
    def _ubl_add_order_reference_node(cls, vals):
        order_ref_node = vals['document_node']['cac:OrderReference'] = {
            'cbc:ID': {'_text': None},
            'cbc:SalesOrderID': {
                '_text': None,
            },
        }

        if cls._is_document(vals, 'invoice', 'credit_note', 'self_invoice', 'self_credit_note'):
            invoice = vals['invoice']

            # Purchase order reference
            # An identifier of a referenced purchase order, issued by the Buyer.
            # Suppose the following case:
            # - Buyer does a RFQ to the Seller.
            # - Seller confirms with a SO.
            # - Buyer converts the RFQ to a PO.
            # => There is no automatic tracking of this information.
            # Instead, the user can encode this information on 'Customer Reference' a.k.a the 'ref' field.
            # Since ID is required, the fallback is also fine and avoid to force the encoding of this
            # manual information.
            order_ref_node['cbc:ID']['_text'] = invoice.ref or invoice.name

            # Sales order reference
            # An identifier of a referenced sales order issued by the Seller.
            if cls.module_installed('sale'):
                so_names = set(invoice.invoice_line_ids.sale_line_ids.order_id.mapped('name'))
                if so_names:
                    order_ref_node['cbc:SalesOrderID']['_text'] = ",".join(so_names)

    @classmethod
    def _ubl_add_billing_reference_nodes(cls, vals):
        vals['document_node']['cac:BillingReference'] = []

    @classmethod
    def _ubl_get_partner_bank_address_node(cls, vals, bank):
        return {
            'cbc:StreetName': {'_text': bank.street},
            'cbc:AdditionalStreetName': {'_text': bank.street2},
            'cbc:CityName': {'_text': bank.city},
            'cbc:PostalZone': {'_text': bank.zip},
            'cbc:CountrySubentity': {'_text': bank.state.name},
            'cbc:CountrySubentityCode': {'_text': bank.state.code},
            'cac:Country': {
                'cbc:IdentificationCode': {'_text': bank.country.code},
                'cbc:Name': {'_text': bank.country.name},
            },
        }

    @classmethod
    def _ubl_get_payment_means_payee_financial_account_institution_branch_node_from_partner_bank(cls, vals, partner_bank):
        bank = partner_bank.bank_id
        if not bank:
            return None

        return {
            'cbc:ID': {
                '_text': bank.bic,
                'schemeID': 'BIC',
            },
            'cac:FinancialInstitution': {
                'cbc:ID': {
                    '_text': bank.bic,
                    'schemeID': 'BIC',
                },
                'cbc:Name': {'_text': bank.name},
                'cac:Address': cls._ubl_get_partner_bank_address_node(vals, bank)
            }
        }

    @classmethod
    def _ubl_get_payment_means_payee_financial_account_node_from_partner_bank(cls, vals, partner_bank):
        return {
            'cbc:ID': {'_text': partner_bank.sanitized_acc_number},
            'cac:FinancialInstitutionBranch': cls._ubl_get_payment_means_payee_financial_account_institution_branch_node_from_partner_bank(vals, partner_bank),
        }

    @classmethod
    def _ubl_add_payment_means_nodes(cls, vals):
        vals['document_node']['cac:PaymentMeans'] = []

    @classmethod
    def _ubl_get_payment_terms_node_from_payment_term(cls, vals, payment_term):
        note = payment_term.note and html2plaintext(payment_term.note) or None
        if not note:
            return

        return {
            'cbc:Note': {'_text': note}
        }

    @classmethod
    def _ubl_add_payment_terms_nodes(cls, vals):
        nodes = vals['document_node']['cac:PaymentTerms'] = []

        if cls._is_document(vals, 'invoice', 'credit_note', 'self_invoice', 'self_credit_note'):
            invoice = vals['invoice']
            if payment_terms_node := cls._ubl_get_payment_terms_node_from_payment_term(vals, invoice.invoice_payment_term_id):
                nodes.append(payment_terms_node)

    @classmethod
    def _ubl_get_allowance_charge_early_payment_tax_category_node(cls, vals, tax_category):
        return {
            '_currency': tax_category['currency'],
            'cbc:ID': {'_text': tax_category['tax_category_code']},
            'cbc:Percent': {'_text': tax_category['percent']},
            'cac:TaxScheme': {
                'cbc:ID': {'_text': tax_category['scheme_id']},
            }
        }

    @classmethod
    def _ubl_get_allowance_charge_global_discount_tax_category_node(cls, vals, tax_category):
        return {
            '_currency': tax_category['currency'],
            'cbc:ID': {'_text': tax_category['tax_category_code']},
            'cbc:Percent': {'_text': tax_category['percent']},
            'cac:TaxScheme': {
                'cbc:ID': {'_text': tax_category['scheme_id']},
            },
        }

    @classmethod
    def _ubl_get_allowance_charge_early_payment_node(cls, vals, early_payment_values):
        currency = early_payment_values['currency']
        amount = early_payment_values['amount']
        is_charge = early_payment_values['is_charge']
        return {
            '_currency': currency,
            'cbc:ChargeIndicator': {'_text': 'true' if is_charge else 'false'},
            'cbc:AllowanceChargeReasonCode': {'_text': 'ZZZ' if is_charge else '64'},
            'cbc:AllowanceChargeReason': {'_text': _("Conditional cash/payment discount")},
            'cbc:Amount': {
                '_text': currency.round(abs(amount)),
                'currencyID': currency.name,
            },
            'cac:TaxCategory': [
                cls._ubl_get_allowance_charge_early_payment_tax_category_node(vals, tax_category)
                for tax_category in early_payment_values['tax_categories'].values()
            ],
        }

    @classmethod
    def _ubl_get_allowance_charge_global_discount_node(cls, vals, global_discount_values):
        currency = global_discount_values['currency']
        amount = global_discount_values['amount']
        is_charge = global_discount_values['is_charge']
        return {
            '_currency': currency,
            'cbc:ChargeIndicator': {'_text': 'true' if is_charge else 'false'},
            'cbc:AllowanceChargeReasonCode': {'_text': 'ADK' if is_charge else '95'},
            'cbc:AllowanceChargeReason': {'_text': _("General upsell") if is_charge else _("General discount")},
            'cbc:Amount': {
                '_text': FloatFmt(abs(amount), max_dp=currency.decimal_places),
                'currencyID': currency.name,
            },
            'cac:TaxCategory': [
                cls._ubl_get_allowance_charge_global_discount_tax_category_node(vals, tax_category)
                for tax_category in global_discount_values['tax_categories'].values()
            ],
        }

    @classmethod
    def _ubl_get_allowance_charge_early_payment(cls, vals, early_payment_values):
        # DEPRECATED: TO BE REMOVED IN MASTER
        _logger.warning("DEPRECATED")
        return cls._ubl_get_allowance_charge_early_payment_node(vals, early_payment_values)

    @classmethod
    def _ubl_add_allowance_charge_nodes_early_payment_discount(cls, vals, in_foreign_currency=True):
        """≙ ``_ubl_add_allowance_charge_nodes_early_payment_discount`` (odoo19c: :1983-2014) — **bloqueado**: la envoltura de base-lines de account.tax no se porta (account/models/account_tax.py:82-90) — 0 hits."""
        _blocked('_ubl_add_allowance_charge_nodes_early_payment_discount', 'la envoltura de base-lines de account.tax no se porta (account/models/account_tax.py:82-90) — 0 hits')

    @classmethod
    def _ubl_add_allowance_charge_nodes_global_discount(cls, vals, in_foreign_currency=True):
        """≙ ``_ubl_add_allowance_charge_nodes_global_discount`` (odoo19c: :2016-2049) — **bloqueado**: la envoltura de base-lines de account.tax no se porta (account/models/account_tax.py:82-90) — 0 hits."""
        _blocked('_ubl_add_allowance_charge_nodes_global_discount', 'la envoltura de base-lines de account.tax no se porta (account/models/account_tax.py:82-90) — 0 hits')

    @classmethod
    def _ubl_add_allowance_charge_nodes(cls, vals):
        vals['document_node']['cac:AllowanceCharge'] = []

    @classmethod
    def _ubl_get_tax_category_node(cls, vals, tax_category):
        """ Generate the node 'cac:TaxCategory' in 'cac:SubTotal'.

        :param vals:            Some custom data.
        :param tax_category:    An entry of vals['_ubl_values'](['tax_totals']|['withholding_tax_totals'])['tax_subtotals']
                                containing all the necessary data to build the node.
        :return:                A new node in 'cac:TaxTotal'.
        """
        return {
            '_currency': tax_category['currency'],
            'cbc:ID': {'_text': tax_category['tax_category_code']},
            'cbc:Name': {'_text': None},
            'cbc:Percent': {'_text': tax_category['percent']},
            'cbc:TaxExemptionReasonCode': {'_text': tax_category.get('tax_exemption_reason_code')},
            'cbc:TaxExemptionReason': {'_text': tax_category.get('tax_exemption_reason')},
            'cac:TaxScheme': {
                'cbc:ID': {'_text': tax_category['scheme_id']},
            }
        }

    @classmethod
    def _ubl_get_tax_subtotal_node(cls, vals, tax_subtotal):
        """ Generate the node 'cac:SubTotal' in 'cac:TaxTotal'/'cac:WithholdingTaxTotal'.

        Note: 'cac:TaxCategory' is managed by '_ubl_get_tax_category_node'.

        :param vals:            Some custom data.
        :param tax_subtotal:    An entry of vals['_ubl_values'](['tax_totals']|['withholding_tax_totals'])['tax_subtotals']
                                containing all the necessary data to build the node.
        :return:                A new node in 'cac:TaxTotal'.
        """
        currency = tax_subtotal['currency']
        return {
            '_currency': currency,
            'cbc:TaxableAmount': {
                '_text': FloatFmt(tax_subtotal['base_amount'], min_dp=currency.decimal_places),
                'currencyID': currency.name
            },
            'cbc:TaxAmount': {
                '_text': FloatFmt(tax_subtotal['tax_amount'], min_dp=currency.decimal_places),
                'currencyID': currency.name
            },
            'cbc:Percent': {
                '_text': (
                    tax_subtotal['percent']
                    if tax_subtotal.get('percent') is not None
                    else None
                ),
            },
            'cac:TaxCategory': [
                cls._ubl_get_tax_category_node(vals, tax_category)
                for tax_category in tax_subtotal['tax_categories'].values()
            ],
        }

    @classmethod
    def _ubl_get_tax_total_node(cls, vals, tax_total):
        """ Generate the node 'cac:TaxTotal'.

        Note: 'cac:Subtotal' is managed by '_ubl_get_tax_subtotal_node'.

        :param vals:            Some custom data.
        :param tax_total:       An entry of vals['_ubl_values']['tax_totals'] containing all the necessary data to build the node.
        :return:                A new node in 'cac:TaxTotal'.
        """
        currency = tax_total['currency']
        return {
            '_currency': currency,
            'cbc:TaxAmount': {
                '_text': FloatFmt(tax_total['amount'], min_dp=currency.decimal_places),
                'currencyID': currency.name
            },
            'cac:TaxSubtotal': [
                cls._ubl_get_tax_subtotal_node(vals, subtotal)
                for subtotal in tax_total['subtotals'].values()
            ],
        }

    @classmethod
    def _ubl_get_withholding_tax_total_node(cls, vals, tax_total):
        """ Generate the node 'cac:WithholdingTaxTotal'.

        Note: 'cac:Subtotal' is managed by '_ubl_get_tax_subtotal_node'.

        :param vals:            Some custom data.
        :param tax_total:       An entry of vals['_ubl_values']['withholding_tax_totals'] containing all the necessary data to build the node.
        :return:                A new node in 'cac:WithholdingTaxTotal'.
        """
        return cls._ubl_get_tax_total_node(vals, tax_total)

    @classmethod
    def _ubl_tax_totals_node_grouping_key(cls, base_line, tax_data, vals, currency):
        tax_category_key = cls._ubl_default_tax_category_grouping_key(base_line, tax_data, vals, currency)
        if tax_category_key:
            tax_subtotal_key = {
                'currency': tax_category_key['currency'],
                'is_withholding': tax_category_key['is_withholding'],
                'tax_category_code': tax_category_key['tax_category_code'],
                'scheme_id': tax_category_key['scheme_id'],
                'percent': tax_category_key['percent'],
            }
        else:
            tax_subtotal_key = None
        if tax_category_key:
            tax_total_key = {
                'is_withholding': tax_category_key['is_withholding'],
                'currency': currency,
            }
        else:
            tax_total_key = None
        return {
            'tax_category_key': tax_category_key,
            'tax_subtotal_key': tax_subtotal_key,
            'tax_total_key': tax_total_key
        }

    @classmethod
    def _ubl_add_tax_totals_nodes(cls, vals):
        """≙ ``_ubl_add_tax_totals_nodes`` (odoo19c: :2166-2290) — **bloqueado**: la envoltura de base-lines de account.tax no se porta (account/models/account_tax.py:82-90) — 0 hits."""
        _blocked('_ubl_add_tax_totals_nodes', 'la envoltura de base-lines de account.tax no se porta (account/models/account_tax.py:82-90) — 0 hits')

    @classmethod
    def _ubl_add_legal_monetary_total_line_extension_amount_node(cls, vals, in_foreign_currency=True):
        currency = vals['currency_id'] if in_foreign_currency else vals['company_currency']

        line_extension_amount = sum(
            line_node['cbc:LineExtensionAmount']['_text']
            for line_key in ('cac:InvoiceLine', 'cac:CreditNoteLine', 'cac:DebitNoteLine')
            for line_node in vals['document_node'].get(line_key, [])
        )
        vals['legal_monetary_total_node']['cbc:LineExtensionAmount'] = {
            '_text': FloatFmt(line_extension_amount, min_dp=currency.decimal_places),
            'currencyID': currency.name,
        }

    @classmethod
    def _ubl_add_legal_monetary_total_tax_exclusive_amount_node(cls, vals, in_foreign_currency=True):
        """ The total amount of the document without TAX including all line net amounts
            minus sum of allowance amount on document level
            plus sum of charges on document level.
        """
        currency = vals['currency_id'] if in_foreign_currency else vals['company_currency']
        node = vals['legal_monetary_total_node']

        tax_exlusive_amount = node['cbc:LineExtensionAmount']['_text']
        document_node = vals['document_node']
        for allowance_charge_node in document_node['cac:AllowanceCharge']:
            sign = 1 if allowance_charge_node['cbc:ChargeIndicator']['_text'] == 'true' else -1
            tax_exlusive_amount += sign * allowance_charge_node['cbc:Amount']['_text']

        node['cbc:TaxExclusiveAmount'] = {
            '_text': FloatFmt(
                tax_exlusive_amount,
                min_dp=currency.decimal_places,
            ),
            'currencyID': currency.name,
        }

    @classmethod
    def _ubl_add_legal_monetary_total_tax_inclusive_amount_node(cls, vals, in_foreign_currency=True):
        currency = vals['currency_id'] if in_foreign_currency else vals['company_currency']
        document_node = vals['document_node']
        node = vals['legal_monetary_total_node']

        tax_amount = sum(
            tax_total_node['cbc:TaxAmount']['_text']
                for tax_total_node in document_node['cac:TaxTotal']
                if tax_total_node['_currency'] == currency
        ) + sum(
            -tax_total_node['cbc:TaxAmount']['_text']
                for tax_total_node in document_node['cac:WithholdingTaxTotal']
                if tax_total_node['_currency'] == currency
        )

        node['cbc:TaxInclusiveAmount'] = {
            '_text': FloatFmt(
                node['cbc:TaxExclusiveAmount']['_text'] + tax_amount,
                min_dp=currency.decimal_places,
            ),
            'currencyID': currency.name,
        }

    @classmethod
    def _ubl_add_legal_monetary_total_allowance_charge_total_amount_node(cls, vals, in_foreign_currency=True):
        currency = vals['currency_id'] if in_foreign_currency else vals['company_currency']
        node = vals['legal_monetary_total_node']

        total_allowance = sum(
            allowance_node['cbc:Amount']['_text']
                for allowance_node in vals['document_node']['cac:AllowanceCharge']
                if allowance_node['cbc:ChargeIndicator']['_text'] == 'false'
        )
        total_charge = sum(
            charge_node['cbc:Amount']['_text']
                for charge_node in vals['document_node']['cac:AllowanceCharge']
                if charge_node['cbc:ChargeIndicator']['_text'] == 'true'
        )

        node.update({
            'cbc:AllowanceTotalAmount': {
                '_text': FloatFmt(total_allowance, min_dp=currency.decimal_places),
                'currencyID': currency.name,
            } if total_allowance else None,
            'cbc:ChargeTotalAmount': {
                '_text': FloatFmt(total_charge, min_dp=currency.decimal_places),
                'currencyID': currency.name,
            } if total_charge else None,
        })

    @classmethod
    def _ubl_add_legal_monetary_total_prepaid_payable_amount_node(cls, vals, in_foreign_currency=True):
        currency = vals['currency_id'] if in_foreign_currency else vals['company_currency']
        node = vals['legal_monetary_total_node']

        payable_rounding_amount = (node['cbc:PayableRoundingAmount'] or {}).get('_text') or 0.0
        node['cbc:PrepaidAmount'] = {
            '_text': FloatFmt(0.0, min_dp=currency.decimal_places),
            'currencyID': currency.name,
        }
        node['cbc:PayableAmount'] = {
            '_text': FloatFmt(
                node['cbc:TaxInclusiveAmount']['_text']
                + payable_rounding_amount,
                min_dp=currency.decimal_places,
            ),
            'currencyID': currency.name,
        }

        if cls._is_document(vals, 'invoice', 'credit_note', 'self_invoice', 'self_credit_note'):
            invoice = vals['invoice']

            if in_foreign_currency:
                amount_total = invoice.amount_total
                amount_residual = invoice.amount_residual
            else:
                amount_total = invoice.amount_total_signed * -invoice.direction_sign
                amount_residual = invoice.amount_residual_signed * -invoice.direction_sign

            node['cbc:PayableAmount']['_text'] = FloatFmt(
                amount_residual,
                min_dp=currency.decimal_places,
            )
            node['cbc:PrepaidAmount']['_text'] = FloatFmt(
                amount_total - amount_residual,
                min_dp=currency.decimal_places,
            )

    @classmethod
    def _ubl_add_legal_monetary_total_payable_rounding_amount_node_from_cash_rounding(cls, vals, in_foreign_currency=True):
        # DEPRECATED: TO BE REMOVED
        pass

    @classmethod
    def _ubl_add_legal_monetary_total_payable_rounding_amount_node(cls, vals):
        """≙ ``_ubl_add_legal_monetary_total_payable_rounding_amount_node`` (odoo19c: :2417-2444) — **bloqueado**: la envoltura de base-lines de account.tax no se porta (account/models/account_tax.py:82-90) — 0 hits."""
        _blocked('_ubl_add_legal_monetary_total_payable_rounding_amount_node', 'la envoltura de base-lines de account.tax no se porta (account/models/account_tax.py:82-90) — 0 hits')

    @classmethod
    def _ubl_add_legal_monetary_total_node(cls, vals):
        node = vals['document_node']['cac:LegalMonetaryTotal'] = {}
        sub_vals = {**vals, 'legal_monetary_total_node': node}
        cls._ubl_add_legal_monetary_total_line_extension_amount_node(sub_vals)
        cls._ubl_add_legal_monetary_total_tax_exclusive_amount_node(sub_vals)
        cls._ubl_add_legal_monetary_total_tax_inclusive_amount_node(sub_vals)
        cls._ubl_add_legal_monetary_total_allowance_charge_total_amount_node(sub_vals)
        cls._ubl_add_legal_monetary_total_payable_rounding_amount_node(sub_vals)
        cls._ubl_add_legal_monetary_total_prepaid_payable_amount_node(sub_vals)

    @classmethod
    def _ubl_add_requested_monetary_total_node(cls, vals):
        node = vals['document_node']['cac:RequestedMonetaryTotal'] = {}
        sub_vals = {**vals, 'legal_monetary_total_node': node}
        cls._ubl_add_legal_monetary_total_line_extension_amount_node(sub_vals)
        cls._ubl_add_legal_monetary_total_tax_exclusive_amount_node(sub_vals)
        cls._ubl_add_legal_monetary_total_tax_inclusive_amount_node(sub_vals)
        cls._ubl_add_legal_monetary_total_allowance_charge_total_amount_node(sub_vals)
        cls._ubl_add_legal_monetary_total_payable_rounding_amount_node(sub_vals)
        cls._ubl_add_legal_monetary_total_prepaid_payable_amount_node(sub_vals)

    @classmethod
    def _fill_document_values_invoice(cls, vals):
        document_node = vals['document_node']
        document_node['_template'] = Invoice
        document_node['_nsmap'][None] = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
        cls._ubl_add_version_id_node(vals)
        cls._ubl_add_customization_id_node(vals)
        cls._ubl_add_profile_id_node(vals)
        cls._ubl_add_invoice_period_nodes(vals)
        cls._ubl_add_id_node(vals)
        cls._ubl_add_issue_date_node(vals)
        cls._ubl_add_due_date_node(vals)
        cls._ubl_add_invoice_type_code_node(vals)
        cls._ubl_add_notes_nodes(vals)
        cls._ubl_add_document_currency_code_node(vals)
        cls._ubl_add_tax_currency_code_node(vals)
        cls._ubl_add_buyer_reference_node(vals)
        cls._ubl_add_order_reference_node(vals)
        cls._ubl_add_accounting_supplier_party_node(vals)
        cls._ubl_add_accounting_customer_party_node(vals)
        cls._ubl_add_delivery_nodes(vals)
        cls._ubl_add_payment_means_nodes(vals)
        cls._ubl_add_payment_terms_nodes(vals)
        cls._ubl_add_allowance_charge_nodes(vals)
        cls._ubl_add_invoice_line_nodes(vals)
        cls._ubl_add_tax_totals_nodes(vals)
        cls._ubl_add_legal_monetary_total_node(vals)

    @classmethod
    def _fill_document_values_credit_note(cls, vals):
        document_node = vals['document_node']
        document_node['_template'] = CreditNote
        document_node['_nsmap'][None] = "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2"
        cls._ubl_add_version_id_node(vals)
        cls._ubl_add_customization_id_node(vals)
        cls._ubl_add_profile_id_node(vals)
        cls._ubl_add_invoice_period_nodes(vals)
        cls._ubl_add_id_node(vals)
        cls._ubl_add_issue_date_node(vals)
        cls._ubl_add_credit_note_type_code_node(vals)
        cls._ubl_add_notes_nodes(vals)
        cls._ubl_add_document_currency_code_node(vals)
        cls._ubl_add_tax_currency_code_node(vals)
        cls._ubl_add_buyer_reference_node(vals)
        cls._ubl_add_order_reference_node(vals)
        cls._ubl_add_accounting_supplier_party_node(vals)
        cls._ubl_add_accounting_customer_party_node(vals)
        cls._ubl_add_delivery_nodes(vals)
        cls._ubl_add_payment_means_nodes(vals)
        cls._ubl_add_payment_terms_nodes(vals)
        cls._ubl_add_allowance_charge_nodes(vals)
        cls._ubl_add_credit_note_line_nodes(vals)
        cls._ubl_add_tax_totals_nodes(vals)
        cls._ubl_add_legal_monetary_total_node(vals)

    @classmethod
    def _fill_document_values_debit_note(cls, vals):
        document_node = vals['document_node']
        document_node['_template'] = DebitNote
        document_node['_nsmap'][None] = "urn:oasis:names:specification:ubl:schema:xsd:DebitNote-2"
        cls._ubl_add_version_id_node(vals)
        cls._ubl_add_customization_id_node(vals)
        cls._ubl_add_profile_id_node(vals)
        cls._ubl_add_invoice_period_nodes(vals)
        cls._ubl_add_id_node(vals)
        cls._ubl_add_issue_date_node(vals)
        cls._ubl_add_notes_nodes(vals)
        cls._ubl_add_document_currency_code_node(vals)
        cls._ubl_add_tax_currency_code_node(vals)
        cls._ubl_add_buyer_reference_node(vals)
        cls._ubl_add_order_reference_node(vals)
        cls._ubl_add_accounting_supplier_party_node(vals)
        cls._ubl_add_accounting_customer_party_node(vals)
        cls._ubl_add_delivery_nodes(vals)
        cls._ubl_add_payment_means_nodes(vals)
        cls._ubl_add_payment_terms_nodes(vals)
        cls._ubl_add_allowance_charge_nodes(vals)
        cls._ubl_add_debit_note_line_nodes(vals)
        cls._ubl_add_tax_totals_nodes(vals)
        cls._ubl_add_requested_monetary_total_node(vals)

    @classmethod
    def _fill_document_values(cls, vals):
        document_node = vals['document_node']
        document_node['_nsmap']['cac'] = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
        document_node['_nsmap']['cbc'] = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
        document_node['_nsmap']['ext'] = "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"

        if cls._is_document(vals, 'invoice', 'self_invoice'):
            cls._fill_document_values_invoice(vals)
        elif cls._is_document(vals, 'credit_note', 'self_credit_note'):
            cls._fill_document_values_credit_note(vals)
        elif cls._is_document(vals, 'debit_note'):
            cls._fill_document_values_debit_note(vals)

    @classmethod
    def _export_document_node_constraints(cls, vals):
        return {}

    @classmethod
    def _export_document(cls, vals):
        vals['document_node'] = {
            '_nsmap': {},
            '_template': Invoice,
        }
        cls._fill_document_values(vals)

        vals['constraints'] = {
            k: v
            for k, v in cls._export_document_node_constraints(vals).items()
            if v
        }
        return vals

    @classmethod
    def _ubl_add_values_document_type(cls, vals):
        invoice = vals['invoice']

        if invoice.move_type == 'out_invoice':
            document_type = 'invoice'
        elif invoice.move_type == 'out_refund':
            document_type = 'credit_note'
        elif invoice.move_type == 'in_invoice':
            document_type = 'self_invoice'
        elif invoice.move_type == 'in_refund':
            document_type = 'self_credit_note'

        cls._define_document_type(vals, document_type)

    @classmethod
    def _init_invoice_export_values(cls, invoice):
        """≙ ``_init_invoice_export_values`` (odoo19c: :2588-2608) — **bloqueado**: AccountMove._get_rounded_base_and_tax_lines/partner_shipping_id/child_ids/with_context no existen (0 hits)."""
        _blocked('_init_invoice_export_values', 'AccountMove._get_rounded_base_and_tax_lines/partner_shipping_id/child_ids/with_context no existen (0 hits)')

    @classmethod
    def _export_invoice(cls, invoice):
        vals = cls._init_invoice_export_values(invoice)
        return cls._export_document(vals)

    # -------------------------------------------------------------------------
    # IMPORT: INVOICE
    # -------------------------------------------------------------------------

    @classmethod
    def _import_ubl_invoice_document_sign(cls, collected_values):
        """≙ ``_import_ubl_invoice_document_sign`` (odoo19c: :2618-2622) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_document_sign', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_update_move_type(cls, collected_values):
        """≙ ``_import_ubl_invoice_update_move_type`` (odoo19c: :2624-2637) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_update_move_type', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_add_customer_values(cls, collected_values):
        """≙ ``_import_ubl_invoice_add_customer_values`` (odoo19c: :2639-2678) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_add_customer_values', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_retrieve_customer_search_plan(cls, collected_values):
        """≙ ``_import_ubl_retrieve_customer_search_plan`` (odoo19c: :2680-2689) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_retrieve_customer_search_plan', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_retrieve_customer(cls, collected_values):
        """≙ ``_import_ubl_retrieve_customer`` (odoo19c: :2691-2701) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_retrieve_customer', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_get_country(cls, collected_values):
        """≙ ``_import_ubl_get_country`` (odoo19c: :2703-2712) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_get_country', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_prepare_missing_customer_create_values(cls, collected_values):
        """≙ ``_import_ubl_prepare_missing_customer_create_values`` (odoo19c: :2714-2732) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_prepare_missing_customer_create_values', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_create_missing_customer(cls, collected_values):
        """≙ ``_import_ubl_create_missing_customer`` (odoo19c: :2734-2761) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_create_missing_customer', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_add_currency_values(cls, collected_values):
        """≙ ``_import_ubl_invoice_add_currency_values`` (odoo19c: :2763-2766) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_add_currency_values', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_add_currency(cls, collected_values):
        """≙ ``_import_ubl_invoice_add_currency`` (odoo19c: :2768-2797) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_add_currency', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_add_issue_date(cls, collected_values):
        """≙ ``_import_ubl_invoice_add_issue_date`` (odoo19c: :2799-2803) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_add_issue_date', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_add_due_date(cls, collected_values):
        """≙ ``_import_ubl_invoice_add_due_date`` (odoo19c: :2805-2811) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_add_due_date', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_add_partner_bank_values(cls, collected_values):
        """≙ ``_import_ubl_invoice_add_partner_bank_values`` (odoo19c: :2813-2817) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_add_partner_bank_values', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_retrieve_partner_bank(cls, collected_values):
        """≙ ``_import_ubl_retrieve_partner_bank`` (odoo19c: :2819-2847) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_retrieve_partner_bank', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_add_ref(cls, collected_values):
        """≙ ``_import_ubl_invoice_add_ref`` (odoo19c: :2849-2856) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_add_ref', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_add_invoice_origin(cls, collected_values):
        """≙ ``_import_ubl_invoice_add_invoice_origin`` (odoo19c: :2858-2873) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_add_invoice_origin', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_add_narration(cls, collected_values):
        """≙ ``_import_ubl_invoice_add_narration`` (odoo19c: :2875-2877) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_add_narration', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _get_notes(cls, collected_values):
        tree = collected_values["tree"]
        nodes = tree.findall("./{*}Note") + tree.findall("./{*}PaymentTerms/{*}Note")
        return [html_escape(node.text) for node in nodes if node.text]

    @classmethod
    def _import_ubl_invoice_add_payment_reference(cls, collected_values):
        """≙ ``_import_ubl_invoice_add_payment_reference`` (odoo19c: :2885-2893) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_add_payment_reference', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_add_delivery(cls, collected_values):
        """≙ ``_import_ubl_invoice_add_delivery`` (odoo19c: :2895-2899) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_add_delivery', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_add_incoterm_values(cls, collected_values):
        """≙ ``_import_ubl_invoice_add_incoterm_values`` (odoo19c: :2901-2907) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_add_incoterm_values', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_add_incoterm(cls, collected_values):
        """≙ ``_import_ubl_invoice_add_incoterm`` (odoo19c: :2909-2920) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_add_incoterm', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_add_prepaid_amount(cls, collected_values):
        """≙ ``_import_ubl_invoice_add_prepaid_amount`` (odoo19c: :2922-2933) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_add_prepaid_amount', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_add_tax_total_values(cls, collected_values):
        """≙ ``_import_ubl_invoice_add_tax_total_values`` (odoo19c: :2935-2972) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_add_tax_total_values', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_add_allowances_charges_values(cls, collected_values):
        """≙ ``_import_ubl_invoice_add_allowances_charges_values`` (odoo19c: :2974-3024) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_add_allowances_charges_values', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_line_add_name(cls, collected_values):
        """≙ ``_import_ubl_invoice_line_add_name`` (odoo19c: :3026-3048) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_line_add_name', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_line_add_allowance_charges_values(cls, collected_values):
        """≙ ``_import_ubl_invoice_line_add_allowance_charges_values`` (odoo19c: :3050-3097) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_line_add_allowance_charges_values', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_line_add_price_unit_quantity_discount(cls, collected_values):
        """≙ ``_import_ubl_invoice_line_add_price_unit_quantity_discount`` (odoo19c: :3099-3216) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_line_add_price_unit_quantity_discount', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_line_add_product_values(cls, collected_values):
        """≙ ``_import_ubl_invoice_line_add_product_values`` (odoo19c: :3218-3248) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_line_add_product_values', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_line_add_product_uom_values(cls, collected_values):
        """≙ ``_import_ubl_invoice_line_add_product_uom_values`` (odoo19c: :3250-3259) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_line_add_product_uom_values', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_line_add_account_values(cls, collected_values):
        """≙ ``_import_ubl_invoice_line_add_account_values`` (odoo19c: :3261-3269) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_line_add_account_values', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_line_add_deferred_dates(cls, collected_values):
        """≙ ``_import_ubl_invoice_line_add_deferred_dates`` (odoo19c: :3271-3281) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_line_add_deferred_dates', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_line_prepare_classified_tax_category_tax_values(cls, collected_values, tax_category_tree):
        """≙ ``_import_ubl_invoice_line_prepare_classified_tax_category_tax_values`` (odoo19c: :3283-3314) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_line_prepare_classified_tax_category_tax_values', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_line_prepare_charge_tax_values(cls, collected_values, charge):
        """≙ ``_import_ubl_invoice_line_prepare_charge_tax_values`` (odoo19c: :3316-3337) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_line_prepare_charge_tax_values', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_line_add_taxes_values(cls, collected_values):
        """≙ ``_import_ubl_invoice_line_add_taxes_values`` (odoo19c: :3339-3356) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_line_add_taxes_values', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_line_add_optional_fields(cls, collected_values):
        """≙ ``_import_ubl_invoice_line_add_optional_fields`` (odoo19c: :3358-3382) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_line_add_optional_fields', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_add_invoice_line_values(cls, collected_values):
        """≙ ``_import_ubl_invoice_add_invoice_line_values`` (odoo19c: :3384-3409) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_add_invoice_line_values', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_retrieve_taxes_search_plan(cls, collected_values):
        """≙ ``_import_ubl_retrieve_taxes_search_plan`` (odoo19c: :3411-3416) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_retrieve_taxes_search_plan', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_retrieve_taxes(cls, collected_values):
        """≙ ``_import_ubl_invoice_retrieve_taxes`` (odoo19c: :3418-3478) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_retrieve_taxes', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_get_default_base_line_kwargs(cls, collected_values):
        """≙ ``_import_ubl_invoice_get_default_base_line_kwargs`` (odoo19c: :3480-3499) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_get_default_base_line_kwargs', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_line_get_product_base_line_kwargs(cls, collected_values):
        """≙ ``_import_ubl_invoice_line_get_product_base_line_kwargs`` (odoo19c: :3501-3537) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_line_get_product_base_line_kwargs', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_get_allowance_charge_line_kwargs(cls, collected_values):
        """≙ ``_import_ubl_invoice_get_allowance_charge_line_kwargs`` (odoo19c: :3539-3567) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_get_allowance_charge_line_kwargs', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_retrieve_products_search_plan(cls, collected_values):
        """≙ ``_import_ubl_retrieve_products_search_plan`` (odoo19c: :3569-3574) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_retrieve_products_search_plan', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_retrieve_products(cls, collected_values):
        """≙ ``_import_ubl_invoice_retrieve_products`` (odoo19c: :3576-3595) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_retrieve_products', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_retrieve_product_uoms(cls, collected_values):
        """≙ ``_import_ubl_invoice_retrieve_product_uoms`` (odoo19c: :3597-3631) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_retrieve_product_uoms', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_retrieve_accounts(cls, collected_values):
        """≙ ``_import_ubl_invoice_retrieve_accounts`` (odoo19c: :3633-3649) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_retrieve_accounts', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_add_base_lines(cls, collected_values):
        """≙ ``_import_ubl_invoice_add_base_lines`` (odoo19c: :3651-3716) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_add_base_lines', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_optional_fields(cls, collected_values):
        """≙ ``_import_ubl_invoice_optional_fields`` (odoo19c: :3718-3740) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_optional_fields', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_write_collected_values(cls, collected_values):
        """≙ ``_import_ubl_invoice_write_collected_values`` (odoo19c: :3742-3771) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_write_collected_values', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_fix_taxes_amounts(cls, collected_values):
        """≙ ``_import_ubl_invoice_fix_taxes_amounts`` (odoo19c: :3773-3851) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_fix_taxes_amounts', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_fix_untaxed_amount(cls, collected_values):
        """≙ ``_import_ubl_invoice_fix_untaxed_amount`` (odoo19c: :3853-3892) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_fix_untaxed_amount', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_attachments(cls, invoice, tree):
        """≙ ``_import_attachments`` (odoo19c: :3894-3942) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_attachments', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _import_ubl_invoice_post_processing(cls, collected_values):
        # During the import, fill 'ubl_cii_xml_file' to be retrieved later if necessary.
        """≙ ``_import_ubl_invoice_post_processing`` (odoo19c: :3944-3966) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_import_ubl_invoice_post_processing', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')

    @classmethod
    def _ubl_import_invoice(cls, invoice, file_data, new=False):
        """≙ ``_ubl_import_invoice`` (odoo19c: :3968-4038) — **bloqueado**: la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo."""
        _blocked('_ubl_import_invoice', 'la API de importacion de registros de account.move/res.partner/product.product no existe (0 hits) — ver la tabla del docstring del modulo')
