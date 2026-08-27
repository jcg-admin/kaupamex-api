"""``account.chart.template`` (demo) — los datos de demostración contables.

Adaptación de Odoo ``addons/account/demo/account_demo.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3 —
atribución y aviso de licencia preservados, DEC-KX-03).

La referencia es un ``_inherit`` de ``account.chart.template`` (el
``AbstractModel`` cargador de planes). Aquí el cargador ya está portado
como clase de classmethods (``models/chart_template.py``) — esta clase lo
extiende por herencia normal de Python, mismo criterio que
``wizard/base_document_layout.py``. La empresa que allá viaja implícita en
``self.env`` aquí es el parámetro ``company`` que ``ref``/``company_xmlid``
del cargador ya reciben.

Los datos de demo NUNCA nombran una empresa real — es la premisa que
``.claude/CLAUDE.md`` fija sobre esta misma fuente (``ProBike Inc`` es
ficticia; aquí ni eso: sólo partners "Demo Partner N", verbatim).

Dieciocho defs de la referencia — el desglose
==============================================

=========================================  ================================
Símbolo de la referencia                    Qué pasa aquí
=========================================  ================================
``_get_demo_data``                          PORTADO
``_get_demo_exception_product_template_xml_ids``  PORTADO — verbatim
``_get_demo_exception_product_variant_xml_ids``   PORTADO — verbatim
``_get_demo_data_products``                 PORTADO (parcial declarado, ver
                                             su docstring)
``_post_load_demo_data``                    PORTADO
``_get_demo_data_bank``                     PORTADO (parcial declarado:
                                             ``company.root_id`` — árbol de
                                             empresas — se colapsa a la
                                             empresa misma)
``_get_demo_data_partner``                  PORTADO
``_get_demo_data_user``                     PORTADO
``_get_demo_data_product``                  PORTADO
``_get_demo_data_journal``                  PORTADO (parcial declarado:
                                             ``journal.bank_account_id`` no
                                             está portado — devuelve ``{}``
                                             y lo declara)
``_get_demo_data_move``                     PORTADO (parcial declarado, ver
                                             su docstring)
``_get_demo_data_statement``                PORTADO
``_get_demo_data_transactions``             PORTADO
``_get_demo_data_reconcile_model``          PORTADO
``_get_demo_data_attachment``               PORTADO (parcial declarado: el
                                             ``raw`` sale de ``file_open``
                                             sobre PDFs de
                                             ``account/static/demo/`` que
                                             este árbol no porta — las
                                             entradas conservan su
                                             metadata y omiten ``raw``)
``_get_demo_data_mail_message``             PORTADO
``_get_demo_data_mail_activity``            PORTADO
``_get_demo_account``                       PORTADO
=========================================  ================================

Divergencias transversales declaradas:

- ``Command.create({...})``/``Command.set([...])`` en los datos: allá son
  literales de comando del ORM ((0,0,vals)/(6,0,ids)); el ``Command`` de
  este árbol (``orm/commands.py``) es un ejecutor sobre managers, no un
  literal. Las líneas viajan como **listas de dicts** y las referencias
  x2m como **listas de xmlids** — el consumidor (``load_model_data`` del
  cargador) las materializa.
- ``formatLang`` (locale) → f-string; campos aún no portados en los
  modelos destino (``delivery_date``, ``invoice_payment_term_id``,
  ``invoice_user_id``, ``message_main_attachment_id``,
  ``balance_end_real``…) se conservan como claves de dato: los datos de
  demo describen la fila de la referencia y el cargador ignora lo que el
  modelo local aún no declare — el dato no se recorta para no perder la
  fila cuando el campo aterrice.
"""
import logging
import time
from datetime import date, datetime, timedelta

from addons.account.models.account_account import AccountAccount
from addons.account.models.account_journal import AccountJournal
from addons.account.models.chart_template import ChartTemplate
from addons.base.models import IrModelData
from exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


def _months_ago(when, months):
    """``relativedelta(months=-n)`` sin dependencia externa — retrocede mes
    a mes conservando el día (recortado al 28 para no desbordar)."""
    year, month = when.year, when.month - months
    while month <= 0:
        month += 12
        year -= 1
    return when.replace(year=year, month=month, day=min(when.day, 28))


class AccountChartTemplate(ChartTemplate):
    """≙ el ``_inherit = "account.chart.template"`` de ``account/demo`` —
    los generadores de datos de demostración."""

    _inherit = 'account.chart.template'

    @classmethod
    def _get_demo_data(cls, company=False):
        """Generate the demo data related to accounting.

        (Docstring verbatim de la referencia.)"""
        return {
            **cls._get_demo_data_products(company),
            'account.move': cls._get_demo_data_move(company),
            'account.bank.statement': cls._get_demo_data_statement(company),
            'account.bank.statement.line':
                cls._get_demo_data_transactions(company),
            'account.reconcile.model':
                cls._get_demo_data_reconcile_model(company),
            'ir.attachment': cls._get_demo_data_attachment(company),
            'mail.message': cls._get_demo_data_mail_message(company),
            'mail.activity': cls._get_demo_data_mail_activity(company),
            'product.product': cls._get_demo_data_product(),
            'res.partner.bank': cls._get_demo_data_bank(company),
            'res.partner': cls._get_demo_data_partner(),
            'res.users': cls._get_demo_data_user(),
            'account.journal': cls._get_demo_data_journal(company),
        }

    @classmethod
    def _get_demo_exception_product_template_xml_ids(cls):
        """ Return demo product template xml ids to not put taxes on"""
        return []

    @classmethod
    def _get_demo_exception_product_variant_xml_ids(cls):
        """ Return demo product variant xml ids to not put taxes on"""
        return ['product.office_combo']

    @classmethod
    def _get_demo_data_products(cls, company):
        """≙ ``_get_demo_data_products`` (parcial declarado) — impuestos por
        defecto de la empresa sobre todos los productos de demo.

        La referencia barre ``ir.model.data`` por ``complete_name``; aquí
        igual, sobre el ``IrModelData`` portado. El guard "sólo la primera
        empresa" de allá compara contra ``base.main_company`` (xmlid de
        data XML de ``base`` no portada) — se usa la ausencia de impuestos
        como el no-op equivalente: sin ``account_sale_tax`` ni
        ``account_purchase_tax`` en la empresa, ``{}``.
        """
        taxes = {}
        sale_tax = getattr(company, 'account_sale_tax', None)
        purchase_tax = getattr(company, 'account_purchase_tax', None)
        if sale_tax is not None:
            taxes.update({'taxes_id': [sale_tax.pk]})
        if purchase_tax is not None:
            taxes.update({'supplier_taxes_id': [purchase_tax.pk]})
        if not taxes:
            return {}
        product_templates = sorted(
            {row.complete_name for row in IrModelData.objects.filter(
                model='product.template')}
            - set(cls._get_demo_exception_product_template_xml_ids())
        )
        product_variants = sorted(
            {row.complete_name for row in IrModelData.objects.filter(
                model='product.product')}
            - set(cls._get_demo_exception_product_variant_xml_ids())
        )
        return {
            'product.template': {d: taxes for d in product_templates},
            'product.product': {d: taxes for d in product_variants},
        }

    @classmethod
    def _post_load_demo_data(cls, company=False):
        """≙ ``_post_load_demo_data`` — publica las facturas de demo,
        tragando (con log) las que no puedan postearse."""
        xmlids = [
            'demo_invoice_1', 'demo_invoice_2', 'demo_invoice_3',
            'demo_invoice_followup', 'demo_invoice_5', 'demo_invoice_6',
            'demo_invoice_7', 'demo_invoice_8',
            'demo_invoice_equipment_purchase', 'demo_invoice_9',
            'demo_invoice_10', 'demo_move_auto_reconcile_1',
            'demo_move_auto_reconcile_2', 'demo_move_auto_reconcile_3',
            'demo_move_auto_reconcile_4', 'demo_move_auto_reconcile_5',
            'demo_move_auto_reconcile_6', 'demo_move_auto_reconcile_7',
        ]
        invoices = [cls.ref(xmlid, company, raise_if_not_found=False)
                    for xmlid in xmlids]
        for move in invoices:
            if move is None:
                continue
            try:
                # ``action_post`` de la referencia ≙ ``post()`` del puerto.
                move.post()
            except (UserError, ValidationError):
                _logger.exception('Error while posting demo data')

    @classmethod
    def _get_demo_data_bank(cls, company=False):
        """≙ ``_get_demo_data_bank`` (``root_id`` → la empresa misma,
        divergencia declarada en el módulo)."""
        partner = company.partner
        if partner is not None and partner.bank_accounts.exists():
            return {}
        return {
            'demo_bank_1': {
                'acc_number': f'BANK{company.pk}34567890',
                'partner_id': partner.pk if partner is not None else None,
                'journal_id': 'bank',
                'allow_out_payment': True,
            },
        }

    @classmethod
    def _get_demo_data_partner(cls):
        """≙ ``_get_demo_data_partner`` — verbatim (partners ficticios)."""
        if IrModelData.ref('base.res_partner_2',
                           raise_if_not_found=False) is not None:
            return {}
        return {
            'base.res_partner_2': {'name': 'Demo Partner 2'},
            'base.res_partner_3': {'name': 'Demo Partner 3'},
            'base.res_partner_4': {'name': 'Demo Partner 4'},
            'base.res_partner_5': {'name': 'Demo Partner 5'},
            'base.res_partner_6': {'name': 'Demo Partner 6'},
            'base.res_partner_12': {'name': 'Demo Partner 12'},
            'base.partner_demo': {'name': 'Marc Demo'},
        }

    @classmethod
    def _get_demo_data_user(cls):
        """≙ ``_get_demo_data_user`` — verbatim."""
        if IrModelData.ref('base.user_demo',
                           raise_if_not_found=False) is not None:
            return {}
        return {
            'base.user_demo': {'name': 'Marc Demo', 'login': 'demo'}
        }

    @classmethod
    def _get_demo_data_product(cls):
        """≙ ``_get_demo_data_product`` — verbatim."""
        if IrModelData.ref('product.product_delivery_01',
                           raise_if_not_found=False) is not None:
            return {}
        return {
            'product.product_delivery_01': {
                'name': 'product_delivery_01', 'type': 'consu'},
            'product.product_delivery_02': {
                'name': 'product_delivery_02', 'type': 'consu'},
            'product.consu_delivery_01': {
                'name': 'consu_delivery_01', 'type': 'consu'},
            'product.consu_delivery_02': {
                'name': 'consu_delivery_02', 'type': 'consu'},
            'product.consu_delivery_03': {
                'name': 'consu_delivery_03', 'type': 'consu'},
            'product.product_order_01': {
                'name': 'product_order_01', 'type': 'consu'},
        }

    @classmethod
    def _get_demo_data_journal(cls, company=False):
        """≙ ``_get_demo_data_journal`` — enlaza la cuenta bancaria del
        partner al diario. Bloqueado por ``journal.bank_account_id`` (el
        diario del puerto no declara la FK a ``res.partner.bank`` — misma
        pieza que declara ``wizard/setup_wizards.py``): mientras no exista,
        no hay clave que escribir y se devuelve ``{}`` en ambas ramas."""
        return {}

    @classmethod
    def _get_demo_data_move(cls, company=False):
        """≙ ``_get_demo_data_move`` (parcial declarado).

        Los dicts conservan xmlids, tipos, fechas relativas, partners y
        líneas verbatim. Adaptaciones declaradas (además de las
        transversales del módulo): ``default_receivable`` allá sale de
        ``partner.property_account_receivable_id`` (property de partner no
        portada) — aquí, la primera cuenta ``asset_receivable`` de la
        empresa (mismo fallback que ``_get_demo_account``); el descarte de
        la cuenta de descuento por pronto pago usa el campo ya portado
        ``account_journal_early_pay_discount_gain_account``.
        """
        today = time.strftime('%Y-%m-%d')
        today_date = date.today()
        one_month_ago = _months_ago(today_date, 1)
        misc_journal = AccountJournal.objects.filter(
            company=company, type='general').first()
        bank_journal = AccountJournal.objects.filter(
            company=company, type='bank').first()
        default_receivable = AccountAccount.objects.filter(
            company=company, account_type='asset_receivable').first()
        gain_account = getattr(
            company, 'account_journal_early_pay_discount_gain_account', None)
        income_qs = AccountAccount.objects.filter(
            company=company, account_type='income')
        if gain_account is not None:
            income_qs = income_qs.exclude(pk=gain_account.pk)
        income_account = income_qs.first()

        def days_ago(days, fmt='%Y-%m-%d'):
            return (today_date + timedelta(days=-days)).strftime(fmt)

        return {
            cls.company_xmlid('demo_invoice_1', company): {
                'move_type': 'out_invoice',
                'partner_id': 'base.res_partner_12',
                'invoice_user_id': 'base.user_demo',
                'invoice_payment_term_id':
                    'account.account_payment_term_end_following_month',
                'invoice_date': time.strftime('%Y-%m-01'),
                'delivery_date': time.strftime('%Y-%m-01'),
                'invoice_line_ids': [
                    {'product_id': 'product.consu_delivery_02', 'quantity': 5},
                    {'product_id': 'product.consu_delivery_03', 'quantity': 5},
                ],
            },
            cls.company_xmlid('demo_invoice_2', company): {
                'move_type': 'out_invoice',
                'partner_id': 'base.res_partner_2',
                'invoice_user_id': False,
                'invoice_date': days_ago(2),
                'delivery_date': days_ago(2),
                'invoice_line_ids': [
                    {'product_id': 'product.consu_delivery_03', 'quantity': 5},
                    {'product_id': 'product.consu_delivery_01', 'quantity': 20},
                ],
            },
            cls.company_xmlid('demo_invoice_3', company): {
                'move_type': 'out_invoice',
                'partner_id': 'base.res_partner_2',
                'invoice_user_id': False,
                'invoice_date': days_ago(3),
                'delivery_date': days_ago(3),
                'invoice_line_ids': [
                    {'product_id': 'product.consu_delivery_01', 'quantity': 5},
                    {'product_id': 'product.consu_delivery_03', 'quantity': 5},
                ],
            },
            cls.company_xmlid('demo_invoice_followup', company): {
                'move_type': 'out_invoice',
                'partner_id': 'base.res_partner_2',
                'invoice_user_id': 'base.user_demo',
                'invoice_payment_term_id':
                    'account.account_payment_term_immediate',
                'invoice_date': days_ago(15),
                'delivery_date': days_ago(15),
                'invoice_line_ids': [
                    {'product_id': 'product.consu_delivery_02', 'quantity': 5},
                    {'product_id': 'product.consu_delivery_03', 'quantity': 5},
                ],
            },
            cls.company_xmlid('demo_invoice_5', company): {
                'move_type': 'out_invoice',
                'partner_id': 'base.res_partner_5',
                'invoice_user_id': 'base.user_demo',
                'invoice_payment_term_id':
                    'account.account_payment_term_end_following_month',
                'invoice_date': days_ago(40),
                'delivery_date': days_ago(40),
                'invoice_line_ids': [
                    {'product_id': 'product.product_order_01',
                     'price_unit': 200, 'quantity': 10},
                ],
            },
            cls.company_xmlid('demo_invoice_6', company): {
                'move_type': 'out_invoice',
                'partner_id': 'base.res_partner_5',
                'invoice_user_id': 'base.user_demo',
                'invoice_payment_term_id':
                    'account.account_payment_term_end_following_month',
                'invoice_date': days_ago(35),
                'delivery_date': days_ago(35),
                'invoice_line_ids': [
                    {'product_id': 'product.product_order_01',
                     'price_unit': 100.0, 'quantity': 10},
                ],
            },
            cls.company_xmlid('demo_invoice_7', company): {
                'move_type': 'out_invoice',
                'partner_id': 'base.res_partner_5',
                'invoice_user_id': 'base.user_demo',
                'invoice_payment_term_id':
                    'account.account_payment_term_end_following_month',
                'invoice_date': one_month_ago.strftime('%Y-%m-%d'),
                'delivery_date': one_month_ago.strftime('%Y-%m-%d'),
                'invoice_line_ids': [
                    {'product_id': 'product.product_order_01',
                     'price_unit': 275, 'quantity': 1},
                ],
            },
            cls.company_xmlid('demo_invoice_8', company): {
                'move_type': 'in_invoice',
                'partner_id': 'base.res_partner_4',
                'invoice_payment_term_id':
                    'account.account_payment_term_end_following_month',
                'invoice_date': time.strftime('%Y-%m-01'),
                'delivery_date': time.strftime('%Y-%m-01'),
                'invoice_line_ids': [
                    {'product_id': 'product.product_order_01',
                     'price_unit': 10.0, 'quantity': 1},
                    {'product_id': 'product.product_delivery_01',
                     'price_unit': 4, 'quantity': 5},
                ],
                'message_main_attachment_id': 'ir_attachment_in_invoice_1',
            },
            cls.company_xmlid('demo_invoice_equipment_purchase', company): {
                'move_type': 'in_invoice',
                'ref': f'INV/{(today_date + timedelta(days=-20)).year}/0057',
                'partner_id': 'base.res_partner_3',
                'invoice_user_id': False,
                'invoice_date': days_ago(20),
                'delivery_date': days_ago(20),
                'invoice_line_ids': [
                    {'name': 'Redeem Reference Number: PO02529',
                     'quantity': 1, 'price_unit': 622.27},
                ],
                'message_main_attachment_id': 'ir_attachment_in_invoice_2',
            },
            cls.company_xmlid('demo_invoice_9', company): {
                'move_type': 'out_invoice',
                'partner_id': 'base.res_partner_6',
                'invoice_user_id': False,
                'invoice_date': today,
                'delivery_date': today,
                'invoice_line_ids': [
                    {'product_id': 'product.product_delivery_02',
                     'price_unit': 50.00, 'quantity': 15},
                ],
            },
            cls.company_xmlid('demo_invoice_10', company): {
                'move_type': 'out_invoice',
                'partner_id': 'base.res_partner_5',
                'invoice_user_id': False,
                'invoice_date': days_ago(5),
                'delivery_date': days_ago(5),
                'invoice_line_ids': [
                    {'product_id': 'product.consu_delivery_03',
                     'price_unit': 1799, 'quantity': 1},
                ],
            },
            cls.company_xmlid('demo_move_auto_reconcile_1', company): {
                'move_type': 'out_refund',
                'partner_id': 'base.res_partner_12',
                'invoice_date': one_month_ago.strftime('%Y-%m-02'),
                'delivery_date': one_month_ago.strftime('%Y-%m-02'),
                'invoice_line_ids': [
                    {'product_id': 'product.consu_delivery_03', 'quantity': 5},
                ],
            },
            cls.company_xmlid('demo_move_auto_reconcile_2', company): {
                'move_type': 'out_refund',
                'partner_id': 'base.res_partner_12',
                'invoice_date': one_month_ago.strftime('%Y-%m-03'),
                'delivery_date': one_month_ago.strftime('%Y-%m-03'),
                'invoice_line_ids': [
                    {'product_id': 'product.consu_delivery_02', 'quantity': 5},
                ],
            },
            cls.company_xmlid('demo_move_auto_reconcile_3', company): {
                'move_type': 'in_refund',
                'partner_id': 'base.res_partner_4',
                'invoice_date': time.strftime('%Y-%m-01'),
                'delivery_date': time.strftime('%Y-%m-01'),
                'invoice_line_ids': [
                    {'product_id': 'product.product_delivery_01',
                     'price_unit': 10.0, 'quantity': 1},
                    {'product_id': 'product.product_order_01',
                     'price_unit': 4.0, 'quantity': 5},
                ],
                'message_main_attachment_id': 'ir_attachment_in_invoice_1',
            },
            cls.company_xmlid('demo_move_auto_reconcile_4', company): {
                'move_type': 'out_refund',
                'partner_id': 'base.res_partner_2',
                'invoice_date': days_ago(10),
                'delivery_date': days_ago(10),
                'invoice_line_ids': [
                    {'product_id': 'product.consu_delivery_02', 'quantity': 5},
                    {'product_id': 'product.consu_delivery_03', 'quantity': 5},
                ],
            },
            cls.company_xmlid('demo_move_auto_reconcile_5', company): {
                'move_type': 'out_refund',
                'partner_id': 'base.res_partner_2',
                'invoice_date': days_ago(2),
                'delivery_date': days_ago(2),
                'invoice_line_ids': [
                    {'product_id': 'product.consu_delivery_01', 'quantity': 5},
                    {'product_id': 'product.consu_delivery_03', 'quantity': 5},
                ],
            },
            cls.company_xmlid('demo_move_auto_reconcile_6', company): {
                'move_type': 'entry',
                'partner_id': 'base.res_partner_2',
                'date': days_ago(20),
                'journal_id': misc_journal.pk if misc_journal else None,
                'line_ids': [
                    {'debit': 0.0, 'credit': 2500.0,
                     'account_id': default_receivable.pk
                     if default_receivable else None},
                    {'debit': 2500.0, 'credit': 0.0,
                     'account_id': bank_journal.default_account_id
                     if bank_journal else None},
                ],
            },
            cls.company_xmlid('demo_move_auto_reconcile_7', company): {
                'move_type': 'entry',
                'partner_id': 'base.res_partner_2',
                'date': days_ago(20),
                'journal_id': misc_journal.pk if misc_journal else None,
                'line_ids': [
                    {'debit': 2500.0, 'credit': 0.0,
                     'account_id': default_receivable.pk
                     if default_receivable else None},
                    {'debit': 0.0, 'credit': 2500.0,
                     'account_id': income_account.pk
                     if income_account else None},
                ],
            },
        }

    @classmethod
    def _get_demo_data_statement(cls, company=False):
        """≙ ``_get_demo_data_statement`` — los dos extractos de demo."""
        today_date = date.today()
        bnk_journal = AccountJournal.objects.filter(
            company=company, type='bank').first()
        bnk_journal_name = bnk_journal.name if bnk_journal else 'Bank'
        two_months_ago = _months_ago(today_date, 2)
        one_month_ago = _months_ago(today_date, 1)
        return {
            'demo_bank_statement_1': {
                'name': "Opening Statement: First Synchronization",
                'balance_end_real': 4253.0,
                'balance_start': 5103.0,
                'attachment_ids': ['ir_attachment_bank_statement_1'],
                'line_ids': [
                    {
                        'journal_id': bnk_journal.pk if bnk_journal else None,
                        'payment_ref': 'Office rent',
                        'amount': -850.0,
                        'date': two_months_ago.strftime('%Y-%m-%d'),
                    },
                ],
            },
            'demo_bank_statement_2': {
                'name': f'{bnk_journal_name} - '
                        f'{one_month_ago.strftime("%Y-%m-%d")}',
                'balance_end_real': 6678.0,
                'balance_start': 4253.0,
                'attachment_ids': ['ir_attachment_bank_statement_2'],
                'line_ids': [
                    {
                        'journal_id': bnk_journal.pk if bnk_journal else None,
                        'payment_ref': 'Office rent',
                        'amount': -850.0,
                        'date': one_month_ago.strftime('%Y-%m-%d'),
                    },
                    {
                        'journal_id': bnk_journal.pk if bnk_journal else None,
                        'payment_ref': time.strftime(
                            'INV/%Y/00006 and INV/%Y/00007'),
                        'amount': 1275.0,
                        'date': one_month_ago.strftime('%Y-%m-%d'),
                        'partner_name': 'Open Wood Inc.',
                    },
                    {
                        'journal_id': bnk_journal.pk if bnk_journal else None,
                        'payment_ref': 'Payment of your invoice #5',
                        'amount': 2000.0,
                        'date': (today_date + timedelta(days=-40))
                                .strftime('%Y-%m-%d'),
                        'partner_name': 'Open Wood Inc.',
                    },
                ],
            },
        }

    @classmethod
    def _get_demo_data_transactions(cls, company=False):
        """≙ ``_get_demo_data_transactions`` — las líneas de extracto
        sueltas (``formatLang`` → f-string, divergencia del módulo)."""
        bnk_journal = AccountJournal.objects.filter(
            company=company, type='bank').first()
        journal_pk = bnk_journal.pk if bnk_journal else None
        return {
            'demo_bank_statement_line_0': {
                'journal_id': journal_pk,
                'payment_ref': 'BILL/2024/01/0001',
                'amount': -622.27,
                'partner_id': 'base.res_partner_3',
            },
            'demo_bank_statement_line_1': {
                'journal_id': journal_pk,
                'payment_ref': 'Office rent',
                'amount': -850.0,
            },
            'demo_bank_statement_line_2': {
                'journal_id': journal_pk,
                'payment_ref': 'Prepayment for invoice #9',
                'amount': 650.0,
                'partner_name': 'Open Wood Inc.',
            },
            'demo_bank_statement_line_3': {
                'journal_id': journal_pk,
                'payment_ref': 'Last Year Interests',
                'amount': 102.78,
            },
            'demo_bank_statement_line_4': {
                'journal_id': journal_pk,
                'payment_ref': time.strftime('INV/%Y/00008'),
                'amount': 738.75,
                'partner_id': 'base.res_partner_6',
            },
            'demo_bank_statement_line_5': {
                'journal_id': journal_pk,
                'payment_ref': f'R:9772938  10/07 AX 9415116318 T:5 BRT: '
                               f'{100.0:.2f} C/ croip',
                'amount': 96.67,
            },
        }

    @classmethod
    def _get_demo_data_reconcile_model(cls, company=False):
        """≙ ``_get_demo_data_reconcile_model`` — los dos modelos de
        conciliación de demo."""
        return {
            'reconcile_from_label': {
                'name': 'Line with Bank Fees',
                'match_label': 'contains',
                'match_label_param': 'BRT',
                'line_ids': [
                    {
                        'label': 'Due amount',
                        'account_id': cls._get_demo_account(
                            'income', 'income', company).pk,
                        'amount_type': 'regex',
                        'amount_string': r'BRT: ([\d,.]+)',
                    },
                    {
                        'label': 'Bank Fees',
                        'account_id': cls._get_demo_account(
                            'expense_finance', 'expense', company).pk,
                        'amount_type': 'percentage',
                        'amount_string': '100',
                    },
                ],
            },
            'owner_current_account_model': {
                'name': "Owner's Current Account",
                'line_ids': [
                    {
                        'label': "Owner's Current Account",
                        'account_id': cls._get_demo_account(
                            'owner_current_account', 'asset_receivable',
                            company).pk,
                        'amount_type': 'percentage',
                        'amount_string': '100',
                    },
                ],
            },
        }

    @classmethod
    def _get_demo_data_attachment(cls, company=False):
        """≙ ``_get_demo_data_attachment`` (parcial declarado — ver la tabla
        del módulo: los PDFs de ``account/static/demo/`` no están portados,
        así que las entradas conservan su metadata y omiten ``raw``)."""
        return {
            'ir_attachment_in_invoice_1': {
                'type': 'binary',
                'name': 'in_invoice_yourcompany_demo.pdf',
                'res_model': 'account.move',
                'res_id': 'demo_invoice_8',
                'res_field': 'invoice_pdf_report_file',
            },
            'ir_attachment_in_invoice_2': {
                'type': 'binary',
                'name': 'in_invoice_yourcompany_demo.pdf',
                'res_model': 'account.move',
                'res_id': 'demo_invoice_equipment_purchase',
                'res_field': 'invoice_pdf_report_file',
            },
            'ir_attachment_bank_statement_1': {
                'type': 'binary',
                'name': 'bank_opening_statement.pdf',
                'res_model': 'account.bank.statement',
                'res_id': 'demo_bank_statement_1',
            },
            'ir_attachment_bank_statement_2': {
                'type': 'binary',
                'name': 'bank_statement_one_month_old.pdf',
                'res_model': 'account.bank.statement',
                'res_id': 'demo_bank_statement_2',
            },
        }

    @classmethod
    def _get_demo_data_mail_message(cls, company=False):
        """≙ ``_get_demo_data_mail_message`` — verbatim (los adjuntos por
        xmlid, forma de lista — divergencia ``Command`` del módulo)."""
        return {
            'mail_message_in_invoice_1': {
                'model': 'account.move',
                'res_id': 'demo_invoice_8',
                'body': 'Vendor Bill attachment',
                'message_type': 'comment',
                'author_id': 'base.partner_demo',
                'attachment_ids': ['ir_attachment_in_invoice_1'],
            },
            'mail_message_in_invoice_2': {
                'model': 'account.move',
                'res_id': 'demo_invoice_equipment_purchase',
                'body': 'Vendor Bill attachment',
                'message_type': 'comment',
                'author_id': 'base.partner_demo',
                'attachment_ids': ['ir_attachment_in_invoice_2'],
            },
            'mail_message_bank_statement_1': {
                'model': 'account.bank.statement',
                'res_id': 'demo_bank_statement_1',
                'body': 'Bank Statement attachment',
                'message_type': 'comment',
                'author_id': 'base.partner_demo',
                'attachment_ids': ['ir_attachment_bank_statement_1'],
            },
            'mail_message_bank_statement_2': {
                'model': 'account.bank.statement',
                'res_id': 'demo_bank_statement_2',
                'body': 'Bank Statement attachment',
                'message_type': 'comment',
                'author_id': 'base.partner_demo',
                'attachment_ids': ['ir_attachment_bank_statement_2'],
            },
        }

    @classmethod
    def _get_demo_data_mail_activity(cls, company=False):
        """≙ ``_get_demo_data_mail_activity`` — verbatim (fechas relativas
        calculadas aquí)."""
        now = datetime.now()
        in_five_days = (now + timedelta(days=5)).strftime('%Y-%m-%d %H:%M')
        today_stamp = now.strftime('%Y-%m-%d %H:%M')
        return {
            'invoice_activity_1': {
                'res_id': 'demo_invoice_3',
                'res_model_id': 'account.model_account_move',
                'activity_type_id': 'mail.mail_activity_data_todo',
                'date_deadline': in_five_days,
                'summary': 'Follow-up on payment',
                'create_uid': 'base.user_admin',
                'user_id': 'base.user_admin',
            },
            'invoice_activity_2': {
                'res_id': 'demo_invoice_2',
                'res_model_id': 'account.model_account_move',
                'activity_type_id': 'mail.mail_activity_data_call',
                'date_deadline': today_stamp,
                'summary': 'Follow up on missed call',
                'create_uid': 'base.user_admin',
                'user_id': 'base.user_admin',
            },
            'invoice_activity_3': {
                'res_id': 'demo_invoice_1',
                'res_model_id': 'account.model_account_move',
                'activity_type_id': 'mail.mail_activity_data_todo',
                'date_deadline': in_five_days,
                'summary': 'Include upsell',
                'create_uid': 'base.user_admin',
                'user_id': 'base.user_admin',
            },
            'invoice_activity_4': {
                'res_id': 'demo_invoice_8',
                'res_model_id': 'account.model_account_move',
                'activity_type_id': 'mail.mail_activity_data_todo',
                'date_deadline': in_five_days,
                'summary': 'Update address',
                'create_uid': 'base.user_admin',
                'user_id': 'base.user_admin',
            },
        }

    @classmethod
    def _get_demo_account(cls, xml_id, account_type, company):
        """Find the most appropriate account possible for demo data creation.

        :param str xml_id: the xml_id of the account template in the generic coa
        :param str account_type: the full xml_id of the account type wanted
        :param company: the company for which we search the account
        :return: the most appropriate ``account.account`` record found

        (Docstring verbatim de la referencia.) Mismos tres escalones: el
        xmlid por-empresa en ``ir.model.data``, luego la primera cuenta del
        tipo, luego cualquier cuenta de la empresa.
        """
        row = IrModelData.objects.filter(
            name=f'{company.pk}_{xml_id}',
            model='account.account',
        ).first()
        if row is not None:
            account = AccountAccount.objects.filter(pk=row.res_id).first()
            if account is not None:
                return account
        return (
            AccountAccount.objects.filter(
                company=company, account_type=account_type).first()
            or AccountAccount.objects.filter(company=company).first()
        )
