"""``account.payment`` — pago (Odoo ``account``).

Portación fiel de ``account_payment.py`` (Odoo 18/19). Campos núcleo:
``amount``, ``payment_type`` (inbound/outbound), ``partner_type``
(customer/supplier), ``state`` (draft/in_process/paid/canceled/rejected),
``journal``, ``partner``, ``currency``, ``company``, ``memo``,
``is_reconciled``.
"""

from decimal import Decimal

import api
import fields
import models
from addons.base.models import IrSequence, TimeStampedModel
from exceptions import ValidationError
from tools.translate import _


class AccountPayment(models.BaseModel, TimeStampedModel):
    """``account.payment`` — registro de un pago entrante o saliente."""

    #: Atributos de clase de ``account.payment``, verbatim
    #: (``odoo19c: account/models/account_payment.py:8-11``).
    _name = 'account.payment'
    _inherit = ['mail.thread.main.attachment', 'mail.activity.mixin']
    _description = "Payments"
    _order = "date desc, name desc"

    PAYMENT_TYPES = [
        ('outbound', 'Enviar'),
        ('inbound', 'Recibir'),
    ]
    PARTNER_TYPES = [
        ('customer', 'Cliente'),
        ('supplier', 'Proveedor'),
    ]
    STATES = [
        ('draft', 'Borrador'),
        ('in_process', 'En proceso'),
        ('paid', 'Pagado'),
        ('canceled', 'Cancelado'),
        ('rejected', 'Rechazado'),
    ]

    #: ≙ ``name`` (``odoo19c: addons/account/models/account_payment.py:15``),
    #: el número del pago; lo cita ``_order``.
    name = fields.Char(string="Number", compute='_compute_name', store=True,
                       max_length=255, null=True, blank=True)
    #: ≙ ``date`` (``odoo19c: addons/account/models/account_payment.py:16``);
    #: la cita ``_order``.
    date = fields.Date(default=fields.Date.context_today, required=True,
                       tracking=True)
    amount = fields.Monetary(
        max_digits=16,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Importe del pago (Odoo amount).',
    )
    payment_type = fields.Selection(
        max_length=8,
        choices=PAYMENT_TYPES,
        default='inbound',
        help_text='Tipo de pago (Odoo payment_type, requerido).',
    )
    partner_type = fields.Selection(
        max_length=8,
        choices=PARTNER_TYPES,
        default='customer',
        help_text='Tipo de contraparte (Odoo partner_type, requerido).',
    )
    state = fields.Selection(
        max_length=12,
        choices=STATES,
        default='draft',
        help_text='Estado del pago (Odoo state).',
    )
    journal = fields.Many2one(
        'account.AccountJournal',
        null=False, on_delete=models.PROTECT,
        related_name='payments',
        help_text='Diario (Odoo journal_id).',
    )
    #: ≙ ``partner_id``
    #: (``odoo19c: addons/account/models/account_payment.py:116``).
    partner = fields.Many2one(
        'base.ResPartner',
        string="Customer/Vendor",
        ondelete='restrict',
        domain="['|', ('parent_id','=', False), ('is_company','=', True)]",
        tracking=True,
        check_company=True,
        null=True,
        blank=True,
        related_name='account_payments',
        help_text='Cliente o proveedor (Odoo partner_id).',
    )
    #: ≙ ``payment_method_line_id``
    #: (``odoo19c: addons/account/models/account_payment.py:74``):
    #: calculado, almacenado y editable.
    payment_method_line_id = fields.Many2one(
        'account.AccountPaymentMethodLine',
        string='Payment Method',
        readonly=False, store=True, copy=False,
        compute='_compute_payment_method_line_id',
        domain="[('id', 'in', available_payment_method_line_ids)]",
        null=True, blank=True,
        related_name='payments',
        db_column='payment_method_line_id',
        help_text=(
            'Manual: Pay or Get paid by any method outside of Odoo (Odoo '
            'payment_method_line_id).'
        ),
    )
    #: ≙ ``available_payment_method_line_ids`` (``:85``): calculado sin
    #: ``store`` → sin columna ni tabla intermedia.
    available_payment_method_line_ids = fields.Many2many(
        'account.AccountPaymentMethodLine',
        compute='_compute_payment_method_line_fields',
        related_name='+',
    )
    #: ≙ ``payment_method_id`` (``:87``): relacionado almacenado.
    payment_method_id = fields.Many2one(
        'account.AccountPaymentMethod',
        related='payment_method_line_id.payment_method',
        string="Method",
        tracking=True,
        store=True,
        null=True, blank=True,
        related_name='+',
        db_column='payment_method_id',
    )
    #: ≙ ``outstanding_account_id`` (``:123``): calculado almacenado.
    outstanding_account_id = fields.Many2one(
        'account.AccountAccount',
        string="Outstanding Account",
        store=True,
        index='btree_not_null',
        compute='_compute_outstanding_account_id',
        check_company=True,
        null=True, blank=True,
        related_name='+',
        db_column='outstanding_account_id',
    )
    #: ≙ ``payment_method_code`` (``:176``): relacionado sin columna.
    payment_method_code = fields.Char(
        related='payment_method_line_id.code')
    currency = fields.Many2one(
        'base.ResCurrency',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments',
        help_text='Moneda (Odoo currency_id).',
    )
    company = fields.Many2one(
        'base.ResCompany',
        null=False, on_delete=models.PROTECT,
        related_name='payments',
        help_text='Empresa (Odoo company_id).',
    )
    memo = fields.Char(
        max_length=255,
        blank=True,
        default='',
        help_text='Concepto (Odoo memo).',
    )
    is_reconciled = fields.Boolean(
        default=False,
        help_text='Pago conciliado (Odoo is_reconciled).',
    )

    class Meta:
        db_table = 'account_payment'
        ordering = ['-id']
        verbose_name = 'Pago'
        verbose_name_plural = 'Pagos'

    @api.depends('state')
    def _compute_name(self):
        """≙ ``_compute_name``
        (``odoo19c: addons/account/models/account_payment.py:414``): el
        número se toma de la secuencia ``account.payment`` cuando el pago ya
        está en proceso o pagado, y una sola vez.
        """
        # pendiente: la rama ``payment.move_id.name`` (:417-419) y la
        # dependencia ``move_id.name`` (:414) -- el pago no tiene aquí
        # ``move_id``.
        for payment in self:
            if (payment.id and not payment.name
                    and payment.state in ('in_process', 'paid')):
                payment.name = IrSequence.next_by_code(
                    'account.payment', company=payment.company,
                    sequence_date=payment.date)

    @api.depends('available_payment_method_line_ids')
    def _compute_payment_method_line_id(self):
        """≙ ``_compute_payment_method_line_id``
        (``odoo19c: addons/account/models/account_payment.py:565``).

        This field is not computed in '_compute_payment_method_line_fields'
        because it's a stored editable one.
        """
        for pay in self:
            available_payment_method_lines = (
                pay.available_payment_method_line_ids)
            # ``res.partner`` no es aquí un recordset: sin partner no hay
            # preferida que leer, donde la fuente lee el vacío.
            partner = pay.partner
            inbound_payment_method = (
                partner.property_inbound_payment_method_line_id
                if partner else None)
            outbound_payment_method = (
                partner.property_outbound_payment_method_line_id
                if partner else None)
            available_ids = available_payment_method_lines.ids
            if (pay.payment_type == 'inbound' and inbound_payment_method
                    and inbound_payment_method.id in available_ids):
                pay.payment_method_line_id = inbound_payment_method
            elif (pay.payment_type == 'outbound' and outbound_payment_method
                    and outbound_payment_method.id in available_ids):
                pay.payment_method_line_id = outbound_payment_method
            elif pay.payment_method_line_id.id in available_ids:
                pay.payment_method_line_id = pay.payment_method_line_id
            elif available_payment_method_lines:
                pay.payment_method_line_id = (
                    available_payment_method_lines[0]._origin)
            else:
                pay.payment_method_line_id = None

    @api.depends('payment_type', 'journal', 'currency')
    def _compute_payment_method_line_fields(self):
        """≙ ``_compute_payment_method_line_fields``
        (``odoo19c: addons/account/models/account_payment.py:585``)."""
        for pay in self:
            pay.available_payment_method_line_ids = (
                pay.journal._get_available_payment_method_lines(
                    pay.payment_type))
            to_exclude = pay._get_payment_method_codes_to_exclude()
            if to_exclude:
                pay.available_payment_method_line_ids = (
                    pay.available_payment_method_line_ids.filtered(
                        lambda x: x.code not in to_exclude))

    def _get_payment_method_codes_to_exclude(self):
        """≙ ``_get_payment_method_codes_to_exclude``
        (``odoo19c: addons/account/models/account_payment.py:610``)."""
        # can be overriden to exclude payment methods based on the payment
        # characteristics
        self.ensure_one()
        return []

    @api.depends('payment_method_line_id')
    def _compute_outstanding_account_id(self):
        """≙ ``_compute_outstanding_account_id``
        (``odoo19c: addons/account/models/account_payment.py:620``)."""
        for pay in self:
            pay.outstanding_account_id = (
                pay.payment_method_line_id.payment_account)

    @api.constrains('payment_method_line_id')
    def _check_payment_method_line_id(self):
        """≙ ``_check_payment_method_line_id``
        (``odoo19c: addons/account/models/account_payment.py:863``).

        Ensure the 'payment_method_line_id' field is not null.
        Can't be done using the regular 'required=True' because the field is
        a computed editable stored one.
        """
        for pay in self:
            if not pay.payment_method_line_id:
                raise ValidationError(_(
                    "Please define a payment method line on your payment."))
            elif (pay.payment_method_line_id.journal
                    and pay.payment_method_line_id.journal != pay.journal):
                raise ValidationError(_(
                    "The selected payment method is not available for this "
                    "payment, please select the payment method again."))

    def __str__(self) -> str:
        return (
            f'{self.get_payment_type_display()} {self.amount} ({self.state})'
        )
