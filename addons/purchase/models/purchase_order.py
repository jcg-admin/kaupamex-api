"""Modelo ``PurchaseOrder`` — addon ``purchase``.

Adaptación fiel de Odoo ``purchase.order``
(``purchase/models/purchase_order.py``,
idéntico en 18 y 19): orden de compra a un proveedor. Núcleo verificado en
ambas
versiones — ``name``/``partner_id`` (proveedor)/``date_order``/``state``
(``draft``/``sent``/``purchase``/``cancel``)/``order_line``/``note`` +
``amount_untaxed``/``amount_tax``/``amount_total``. Espeja al addon ``sale``
(``SaleOrder``) para consistencia interna: mismos montos IVA-incluido (MX) y
misma máquina de estados de confirmación/cancelación.

Cabecera — ``company_id``/``currency_id``/``currency_rate`` (tarea #266)
==========================================================================

Los tres cerraban el bloqueo que ``purchase_requisition/models/purchase.py``
medía en su Causa D: ``price_total_cc``/``company_currency_id`` de
``purchase.order.line`` dividen entre ``order_id.currency_rate``, y ese campo
no existía aquí (``grep -c currency_rate`` daba **0**). El mecanismo —
``ResCurrency._get_conversion_rate``— ya estaba portado
(``src/addons/base/models/res_currency.py:462``); faltaba la cabecera.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Símbolo de la referencia
     - Forma aquí
   * - ``company_id`` (``odoo19c: :161``)
     - campo homónimo. **Nullable, sin default** — mismo patrón «L3 rollout,
       NULL pre-backfill» de ``sale.order.company``
       (``api: addons/sale/models/sale_order.py:425-431``); la fuente lo
       declara ``required=True`` con ``default=lambda self:
       self.env.company.id``, que aquí no existe (no hay ``env.company`` de
       sesión — el operador de plataforma es Kaupamex, L0, y la empresa la
       fija quien crea la orden).
   * - ``currency_id`` (``odoo19c: :96-101``)
     - ``compute='_compute_currency_id'``, ``store=True``, ``precompute=True``,
       ``readonly=False`` — recomputado en ``save()`` (este ORM no dispara
       ``@api.depends``, tarea #191), mismo patrón que
       ``SaleOrder._compute_validity_date``
       (``api: addons/sale/models/sale_order.py:1007-1046``).
       **Degradación declarada:** ``partner_id`` aquí es ``AUTH_USER_MODEL``,
       no ``res.partner`` (divergencia documentada, sin cambiar en este
       pase), y ``property_purchase_currency_id`` **no existe en este árbol**
       (medido: ``grep -rn "property_purchase_currency_id" addons/ src/`` →
       0) — la rama del proveedor de la fuente nunca se toma y la moneda
       sale siempre de la empresa. Mismo criterio que
       ``purchase_requisition.PurchaseRequisition._compute_currency_id``
       (``addons/purchase_requisition/models/purchase_requisition.py:271-284``).
   * - ``currency_rate`` (``odoo19c: :164-170``)
     - ``compute='_compute_currency_rate'``, ``store=True``,
       ``precompute=True`` — recomputado en ``save()``. **Divergencia de
       tipo:** la fuente lo declara ``fields.Float(digits=0)``; aquí es
       ``fields.Monetary`` (``DecimalField``), porque
       ``PurchaseOrderLine._compute_price_total_cc`` divide
       ``price_subtotal()`` (``Decimal``) entre esta tasa —
       ``Decimal / float`` levanta ``TypeError`` en Python. Mismo criterio
       que ``res.currency.rate.rate``
       (``src/addons/base/models/res_currency.py:827``, que porta el
       ``fields.Float`` de la fuente como ``Monetary`` por la misma razón).
"""

from contextlib import nullcontext
from decimal import Decimal

import pytz
from django.core.exceptions import ValidationError
from django.db import transaction
import api
import fields
import models
from django.utils import timezone
from exceptions import UserError
from orm.environments import (
    company_scope, get_current_company, get_current_uid, get_current_user,
    sudo)
from tools.translate import _

from addons.account.models.account_document_import_mixin import (
    AccountDocumentImportMixin)
from addons.account.models.account_fiscal_position import (
    AccountFiscalPosition)
from addons.base.models import (
    IrSequence, ResCompany, ResCurrency, TimeStampedModel)
from addons.mail.models import MailActivityMixin, MailThread
from addons.portal.models.portal_mixin import PortalMixin
from addons.product.models.product_catalog_mixin import ProductCatalogMixin

#: Centinela de «todavía no se cargó ninguna fila» — distinto de
#: ``company_id is None`` (fila cargada, sin empresa). El mismo patrón que
#: ``SaleOrder._loaded_company_id``
#: (``api: addons/sale/models/sale_order.py:855-861``).
_SIN_CARGAR = object()


def _next_purchase_name(company_id, sequence_date):
    """El siguiente nombre de ``purchase.order``, o ``None``.

    ≙ ``next_by_code('purchase.order', sequence_date=...)`` (``:404``). La
    secuencia ``seq_purchase_order`` de la fuente (``purchase_data.xml:
    21-27``: prefijo ``P``, relleno 5, sin empresa) se siembra en el punto de
    uso, como la de ``sale.order`` (``api: addons/sale/models/
    sale_order.py:44-60``): los datos XML no se cargan aquí (H-API-22).
    """
    with transaction.atomic():
        exists = IrSequence.objects.select_for_update().filter(
            code='purchase.order').exists()
        if not exists:
            IrSequence.objects.create(
                name='Purchase Order', code='purchase.order', prefix='P',
                padding=5)
        return IrSequence.next_by_code(
            'purchase.order', company=company_id,
            sequence_date=sequence_date)


def _default_buyer():
    """≙ ``default=lambda self: self.env.user`` (``odoo19c: :159``)."""
    return get_current_uid()


class PurchaseOrder(models.BaseModel, PortalMixin, ProductCatalogMixin,
                    MailThread, MailActivityMixin, AccountDocumentImportMixin,
                    TimeStampedModel):
    """``purchase.order`` — orden de compra a un proveedor.

    ``_inherit`` de la fuente (``:23``) completo, en su orden:
    ``portal.mixin``, ``product.catalog.mixin``, ``mail.thread``,
    ``mail.activity.mixin`` y ``account.document.import.mixin``; la misma
    composición que ``sale.order``.
    """

    _name = 'purchase.order'
    _description = "Purchase Order"
    _rec_names_search = ['name', 'partner_ref']
    _order = 'priority desc, id desc'

    STATE_DRAFT = 'draft'
    STATE_SENT = 'sent'
    STATE_TO_APPROVE = 'to approve'
    STATE_PURCHASE = 'purchase'
    STATE_CANCEL = 'cancel'
    STATE_CHOICES = [
        (STATE_DRAFT, 'Solicitud de cotización'),
        (STATE_SENT, 'Cotización enviada'),
        (STATE_TO_APPROVE, 'Por aprobar'),
        (STATE_PURCHASE, 'Orden de compra'),
        (STATE_CANCEL, 'Cancelada'),
    ]

    # Odoo purchase.order.name (default 'New'; create lo toma de la secuencia).
    name = fields.Char(
        max_length=32,
        blank=True,
        default='New',
        help_text='Referencia de la orden (Odoo purchase.order.name).',
    )
    #: ≙ ``partner_id`` (``odoo19c: :91-94``): el proveedor es un contacto.
    #: ``null=True`` mientras haya órdenes sin proveedor; la fuente lo exige.
    partner_id = fields.Many2one(
        'base.ResPartner',
        verbose_name='Vendor',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='purchase_orders',
        db_index=True,
        help_text=(
            'You can find a vendor by its Name, TIN, Email or Internal '
            'Reference.'),
        db_column='partner_id',
    )
    #: ≙ ``priority`` (``odoo19c: :78-79``).
    priority = fields.Selection(
        [('0', 'Normal'), ('1', 'Urgent')], 'Priority', default='0',
        max_length=1, db_index=True)
    #: ≙ ``partner_ref`` (``odoo19c: :83-87``).
    partner_ref = fields.Char(
        'Vendor Reference', max_length=255, blank=True, default='',
        copy=False,
        help_text=(
            "Reference of the sales order or bid sent by the vendor. It's "
            "used to do the matching when you receive the products as this "
            "reference is usually written on the delivery order sent by "
            "your vendor."))
    # Odoo purchase.order.date_order.
    #: ≙ ``date_order`` (``odoo19c: :88-89``, ``default=Datetime.now``).
    date_order = fields.Datetime(
        null=True,
        blank=True,
        default=timezone.now,
        copy=False,
        help_text='Fecha de la orden (Odoo date_order).',
    )
    # Odoo purchase.order.state.
    state = fields.Selection(
        max_length=16,
        choices=STATE_CHOICES,
        default=STATE_DRAFT,
        help_text='Estado (Odoo purchase.order.state).',
        db_index=True,
        copy=False,
    )
    #: ≙ ``date_approve`` (``odoo19c: :90``).
    date_approve = fields.Datetime(
        'Confirmation Date', null=True, blank=True, db_index=True,
        copy=False)
    #: ≙ ``locked`` (``odoo19c: :112-116``).
    locked = fields.Boolean(
        default=False, copy=False,
        help_text='Locked Purchase Orders cannot be modified.')
    #: ≙ ``lock_confirmed_po`` (``odoo19c: :117``).
    lock_confirmed_po = fields.Selection(
        related='company_id.po_lock', store=False)
    #: ≙ ``user_id`` (``odoo19c: :157-159``): el comprador, por defecto el
    #: usuario que actúa.
    #: ≙ ``invoice_ids`` e ``invoice_count`` (``odoo19c: :125-126``): las
    #: facturas de las líneas, calculadas y almacenadas.
    invoice_ids = fields.Many2many(
        'account.AccountMove', compute='_compute_invoice', store=True,
        copy=False, blank=True, related_name='+', verbose_name='Bills')
    invoice_count = fields.Integer(
        compute='_compute_invoice', store=True, copy=False, default=0,
        verbose_name='Bill Count')
    user_id = fields.Many2one(
        'base.ResUsers', verbose_name='Buyer', null=True, blank=True,
        default=_default_buyer, on_delete=models.SET_NULL,
        related_name='purchase_orders_as_buyer', db_index=True,
        db_column='user_id')
    # Odoo purchase.order.note.
    note = fields.Text(
        blank=True,
        default='',
        help_text='Términos y condiciones (Odoo note).',
    )
    # Odoo purchase.order.company_id — ver docstring del módulo (tarea #266).
    company_id = fields.Many2one(
        'base.ResCompany',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='purchase_orders',
        db_index=True,
        db_column='company_id',
        help_text=(
            'Empresa dueña de la orden (Odoo company_id, required, '
            'default=env.company). NULL pre-backfill — mismo patrón '
            'que sale.order.company_id.'
        ),
    )
    # Odoo purchase.order.currency_id — compute+store+precompute (ver
    # docstring).
    currency_id = fields.Many2one(
        'base.ResCurrency',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='+',
        db_column='currency_id',
        help_text=(
            'Odoo currency_id (compute, store=True, precompute, '
            'readonly=False, ondelete=\'restrict\' ≙ PROTECT). Sale de '
            'la empresa — la rama del proveedor está degradada, ver '
            'docstring del módulo.'
        ),
    )
    # Odoo purchase.order.currency_rate — compute+store+precompute (ver
    # docstring).
    currency_rate = fields.Monetary(
        null=True,
        blank=True,
        max_digits=24,
        decimal_places=12,
        help_text=(
            'Odoo currency_rate ("Currency Rate", compute, store=True, '
            'precompute, digits=0 en la fuente = precisión plena). '
            'Monetary/Decimal en vez de Float — ver docstring del '
            'módulo.'
        ),
    )

    #: Ver ``_SIN_CARGAR`` — mismo patrón que ``SaleOrder``.
    _loaded_company_id = _SIN_CARGAR
    _loaded_currency_id = _SIN_CARGAR
    _loaded_date_order = _SIN_CARGAR

    class Meta:
        db_table = 'purchase_order'
        ordering = ['-priority', '-id']
        verbose_name = 'Orden de compra'
        verbose_name_plural = 'Órdenes de compra'

    def __str__(self) -> str:
        return self.name or f'{self.state}:{self.pk}'

    @classmethod
    def from_db(cls, db, field_names, values):
        """Recuerda con qué empresa/moneda/fecha se cargó la fila.

        ≙ ``SaleOrder.from_db`` (``api: addons/sale/models/sale_order.py:
        985-996``) — es lo que permite a ``save()`` distinguir «cambió
        ``company_id``» de «se guardó cualquier otra cosa», que es la
        diferencia entre reproducir ``@api.depends`` y recalcular a ciegas.
        """
        order = super().from_db(db, field_names, values)
        if 'company_id' in field_names:
            order._loaded_company_id = order.company_id_id
        if 'currency_id' in field_names:
            order._loaded_currency_id = order.currency_id_id
        if 'date_order' in field_names:
            order._loaded_date_order = order.date_order
        return order

    def _compute_currency_id(self):
        """≙ ``_compute_currency_id`` (``odoo19c: purchase_order.py:459-466``).

        La moneda del proveedor manda sobre la de la empresa en la fuente.
        Degradación declarada en el docstring del módulo: aquí sale siempre
        de la empresa.
        """
        self.currency_id = (
            self.company_id.currency if self.company_id_id else None
        )

    def _compute_currency_rate(self):
        """≙ ``_compute_currency_rate`` (``odoo19c: purchase_order.py:
        211-218``). ``ResCurrency._get_conversion_rate`` ya está portado
        (``src/addons/base/models/res_currency.py:462``)."""
        company = self.company_id
        currency = self.currency_id
        if (
            not self.company_id_id
            or not self.currency_id_id
            or company.currency is None
        ):
            self.currency_rate = Decimal('1.0')
            return
        rate_date = (self.date_order or timezone.now()).date()
        self.currency_rate = ResCurrency._get_conversion_rate(
            from_currency=company.currency,
            to_currency=currency,
            company=company,
            date=rate_date,
        )

    def save(self, *args, **kwargs):
        """Recompila ``currency_id``/``currency_rate`` — este ORM no dispara
        ``@api.depends`` (tarea #191), así que el único disparo real es este
        ``save()``. Mismo patrón que ``SaleOrder.save()``
        (``api: addons/sale/models/sale_order.py:1007-1046``): reproduce los
        DOS disparos de la fuente —``precompute=True`` al crear, y
        ``@api.depends`` al cambiar la dependencia—, no uno solo.
        """
        update_fields = kwargs.get('update_fields')
        creating = self._state.adding
        company_changed = (
            self._loaded_company_id is not _SIN_CARGAR
            and self._loaded_company_id != self.company_id_id
        )
        # precompute=True: al crear, sólo si quien llama no dio valor —un
        # currency_id explícito en la creación sobrevive, no lo pisa el
        # cómputo (mismo criterio que SaleOrder.validity_date).
        recompute_currency = (
            creating and self.currency_id_id is None
        ) or company_changed
        if recompute_currency:
            self._compute_currency_id()

        currency_changed = (
            self._loaded_currency_id is not _SIN_CARGAR
            and self._loaded_currency_id != self.currency_id_id
        )
        date_changed = (
            self._loaded_date_order is not _SIN_CARGAR
            and self._loaded_date_order != self.date_order
        )
        recompute_rate = (
            (creating and self.currency_rate is None)
            or company_changed
            or currency_changed
            or date_changed
        )
        if recompute_rate:
            self._compute_currency_rate()

        if update_fields is not None and (
            recompute_currency or recompute_rate
        ):
            extra = [
                f
                for f in ('currency_id', 'currency_rate')
                if f not in update_fields
            ]
            if extra:
                kwargs['update_fields'] = [*update_fields, *extra]

        super().save(*args, **kwargs)
        self._loaded_company_id = self.company_id_id
        self._loaded_currency_id = self.currency_id_id
        self._loaded_date_order = self.date_order

    def _sum_lines(self, attr: str) -> Decimal:
        """Suma una columna de importe de las líneas contables.

        ``_amount_all`` de la fuente (``odoo19c: purchase_order.py:29-44``)
        agrega con ``_get_tax_totals_summary``, que aquí no existe: sucesores
        ``account-tax-totals-summary-0121`` y ``purchase-order-amounts-0122``.
        Mientras, se suman las columnas que ``_compute_amount`` de la línea
        ya almacena, sin las líneas de sección o nota (``:32``).
        """
        return sum(
            (getattr(line, attr) or Decimal('0.00')
             for line in self.order_line.filtered(
                 lambda line: not line.display_type)),
            Decimal('0.00'),
        ).quantize(Decimal('0.01'))

    def amount_untaxed(self) -> Decimal:
        return self._sum_lines('price_subtotal')

    def amount_tax(self) -> Decimal:
        return self._sum_lines('price_tax')

    def amount_total(self) -> Decimal:
        return self._sum_lines('price_total')

    @api.depends('order_line.invoice_lines.move')
    def _compute_invoice(self):
        """≙ ``_compute_invoice`` (``odoo19c: :70-75``).

        ``mapped('order_line.invoice_lines.move_id')`` de la fuente:
        ``invoice_lines`` es el inverso de una FK de ``account.move.line``,
        un modelo de Django, y ``mapped`` no recorre su gestor; las facturas
        se leen por la relación.
        """
        move_model = type(self).invoice_ids.field.related_model
        for order in self:
            invoice_ids = list(move_model.objects.filter(
                line_ids__purchase_line_id__order_id=order.id).distinct(
            ).values_list('pk', flat=True))
            order.invoice_ids = invoice_ids
            order.invoice_count = len(invoice_ids)

    @classmethod
    def create(cls, vals_list):
        """≙ ``create`` (``odoo19c: :393-406``).

        Un nombre ``'New'`` se cambia por el siguiente de la secuencia
        ``purchase.order``, con la empresa de los valores y la fecha de
        ``date_order``; sin secuencia, ``'/'``.
        """
        for vals in vals_list:
            company_id = vals.get('company_id') or get_current_company()
            if vals.get('name', 'New') == 'New':
                seq_date = None
                if vals.get('date_order'):
                    seq_date = timezone.localtime(vals['date_order'])
                vals['name'] = _next_purchase_name(company_id, seq_date) or '/'
        return super().create(vals_list)

    def button_approve(self, force=False):
        """≙ ``button_approve`` (``odoo19c: :615-619``)."""
        self = self.filtered(lambda order: order._approval_allowed())
        self.write({'state': self.STATE_PURCHASE,
                    'date_approve': timezone.now()})
        self.filtered(lambda order: order.lock_confirmed_po == 'lock').write(
            {'locked': True})
        return {}

    def button_draft(self):
        """≙ ``button_draft`` (``odoo19c: :621-623``)."""
        self.write({'state': self.STATE_DRAFT})
        return {}

    def button_confirm(self):
        """≙ ``button_confirm`` (``odoo19c: :625-639``).

        Una orden que no está en ``draft``/``sent`` se salta, no se rehúsa.

        Una llamada de la fuente queda pendiente, con su fila en el plan
        (diseño ``purchase-order-state-machine.md``):

        * pendiente: ``order.order_line._validate_analytic_distribution()``
          (``:631``). ``_validate_distribution`` depende de
          ``get_relevant_plans`` (``analytic_mixin.py:53``); unidad
          ``purchase-analytic-validation-0397``.
        """
        for order in self:
            if order.state not in (self.STATE_DRAFT, self.STATE_SENT):
                continue
            error_msg = order._confirmation_error_message()
            if error_msg:
                raise UserError(error_msg)
            order._add_supplier_to_product()
            if order._approval_allowed():
                order.button_approve()
            else:
                order.write({'state': self.STATE_TO_APPROVE})
        return True

    def _prepare_supplier_info(self, partner, line, price, currency):
        """≙ ``_prepare_supplier_info`` (``odoo19c: :670-680``).

        Las claves son los nombres de ``product.supplierinfo`` en este
        árbol: ``partner_id`` como en la fuente, y ``currency``, una FK que
        aún no lleva el sufijo ``_id``.
        """
        sellers = list(line.product_id.product_tmpl_id.seller_ids.all())
        return {
            'partner_id': partner,
            'sequence': (max(seller.sequence for seller in sellers) + 1
                         if sellers else 1),
            'min_qty': 1.0,
            'price': price,
            'currency_id': currency,
            'discount': line.discount,
            'delay': 0,
        }

    def _add_supplier_to_product(self):
        """≙ ``_add_supplier_to_product`` (``odoo19c: :682-707``).

        Añade el proveedor a ``seller_ids`` de la plantilla si no lo tiene y
        si tiene 10 proveedores o menos. Un contacto no se añade: se añade su
        empresa. La escritura va con elevación, como el ``sudo()`` de la
        fuente.
        """
        vendor = self.partner_id
        if not vendor:
            return
        partner = vendor.parent if vendor.parent_id else vendor
        for line in self.order_line:
            product = line.product_id
            if not product:
                continue
            template = product.product_tmpl_id
            sellers = list(template.seller_ids.all())
            seller_partners = {seller.partner_id_id for seller in sellers}
            if seller_partners & {partner.pk, vendor.pk} or len(sellers) > 10:
                continue
            price = line.price_unit
            # El precio pasa a la unidad de la plantilla, que es la de la
            # tarifa del proveedor.
            default_uom = template.uom
            if line.product_uom_id and line.product_uom_id != default_uom:
                price = Decimal(str(line.product_uom_id._compute_price(
                    float(price), default_uom)))
            supplierinfo = self._prepare_supplier_info(
                partner, line, price, line.currency_id)
            # Si la orden va a un contacto, la tarifa nueva se crea sobre la
            # empresa y conserva el nombre y el código del producto.
            selected = line.selected_seller_id
            if selected:
                supplierinfo['product_name'] = selected.product_name
                supplierinfo['product_code'] = selected.product_code
                supplierinfo['product_uom_id'] = line.product_uom_id
            with sudo():
                template.write(
                    {'seller_ids': [fields.Command.create(supplierinfo)]})

    def button_cancel(self):
        """≙ ``button_cancel`` (``odoo19c: :641-649``)."""
        locked_orders = self.filtered(lambda order: order.locked)
        if locked_orders:
            raise UserError(_(
                'Unable to cancel purchase order(s): %s. You must first '
                'unlock them.', locked_orders.mapped('display_name')))
        orders_with_invoices = self.filtered(lambda order: any(
            invoice.state not in ('cancel', 'draft')
            for invoice in order.invoice_ids))
        if orders_with_invoices:
            raise UserError(_(
                'Unable to cancel purchase order(s): %s. You must first '
                'cancel their related vendor bills.',
                orders_with_invoices.mapped('display_name')))
        self.write({'state': self.STATE_CANCEL})

    def button_lock(self):
        """≙ ``button_lock`` (``odoo19c: :651-652``)."""
        self.locked = True

    def button_unlock(self):
        """≙ ``button_unlock`` (``odoo19c: :654-655``)."""
        self.locked = False

    def _confirmation_error_message(self):
        """≙ ``_confirmation_error_message`` (``odoo19c: :657-668``)."""
        self.ensure_one()
        if any(
            not line.display_type
            and not line.is_downpayment
            and not line.product_id
            for line in self.order_line
        ):
            return _('Some order lines are missing a product, you need to '
                     'correct them before going further.')
        return False

    def _approval_allowed(self):
        """≙ ``_approval_allowed`` (``odoo19c: :1251-1260``).

        ``env.company`` es la empresa activada en contexto; sin empresa en
        contexto (cron, migraciones, pruebas) se usa la de la orden. Una
        orden sin empresa —la columna admite NULL hasta su relleno, igual que
        ``sale.order``— toma la política por defecto de ``res.company``.

        ``purchase.group_purchase_manager`` todavía no está sembrado: hasta
        que lo esté, ``has_group`` devuelve ``False``, el mismo resultado
        que para un usuario sin el grupo.
        """
        self.ensure_one()
        current = get_current_company()
        env_company = (ResCompany.objects.get(pk=current) if current
                       else None)
        company = self.company_id or env_company
        policy = (company.po_double_validation if company else
                  ResCompany._meta.get_field('po_double_validation').default)
        if policy == 'one_step':
            return True
        if policy == 'two_step':
            threshold = (env_company or company).currency._convert(
                company.po_double_validation_amount, self.currency_id,
                company, self.date_order or timezone.now().date())
            if self.amount_total() < threshold:
                return True
        user = get_current_user()
        return bool(user) and user.has_group(
            'purchase.group_purchase_manager')

    # --- Cabecera fiscal (TASK-GEN-0535) ---------------------------------
    #
    # Al final del cuerpo de la clase y no junto a los demás campos: la
    # admisión de estilo fecha cada infracción heredada por su posición en
    # el contenedor, y un campo intercalado la desplaza.
    #
    # El ``domain`` de la fuente en ``fiscal_position_id`` y
    # ``payment_term_id`` (``['|', ('company_id', '=', False), ('company_id',
    # '=', company_id)]``) sólo acota el selector del formulario: la fuente no
    # declara ``check_company`` en ninguno de los dos, así que no hay
    # restricción de registro que portar. Divergencia declarada.

    #: ≙ ``origin`` (``odoo19c: purchase_order.py:80-82``).
    origin = fields.Char(
        'Source', max_length=255, blank=True, default='', copy=False,
        help_text=(
            'Reference of the document that generated this purchase order '
            'request (e.g. a sales order)'))
    #: ≙ ``fiscal_position_id`` (``odoo19c: purchase_order.py:143``).
    fiscal_position_id = fields.Many2one(
        'account.AccountFiscalPosition', verbose_name='Fiscal Position',
        null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
        db_column='fiscal_position_id')
    #: ≙ ``payment_term_id`` (``odoo19c: purchase_order.py:153``).
    payment_term_id = fields.Many2one(
        'account.AccountPaymentTerm', verbose_name='Payment Terms',
        null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
        db_column='payment_term_id')

    @api.onchange('partner_id', 'company_id')
    def onchange_partner_id(self):
        """≙ ``onchange_partner_id`` (``odoo19c: purchase_order.py:444-457``).

        Comentario de la fuente, verbatim: *"Ensures all properties and
        fiscal positions are taken with the company of the order; if not
        defined, with_company doesn't change anything."* Su
        ``self.with_company(self.company_id)`` es aquí ``company_scope``, y
        una orden sin empresa deja el contexto como estaba.

        ``_get_fiscal_position`` devuelve el registro vacío cuando ninguna
        posición aplica (≙ el recordset vacío de la fuente); se asigna
        ``None``, que es lo que aquí vale «sin posición».
        """
        scope = (company_scope(self.company_id_id) if self.company_id_id
                 else nullcontext())
        with scope:
            if not self.partner_id:
                self.fiscal_position_id = None
            else:
                position = AccountFiscalPosition._get_fiscal_position(
                    self.partner_id)
                self.fiscal_position_id = position if position.pk else None
                self.payment_term_id = (
                    self.partner_id.property_supplier_payment_term_id)
                if self.partner_id.buyer_id:
                    self.user_id = self.partner_id.buyer_id
        return {}

    def get_order_timezone(self):
        """ Returns the timezone of the order's user or the company's
        partner or UTC if none of them are set.

        ≙ ``get_order_timezone`` (``odoo19c: purchase_order.py:1274-1278``).
        El ``partner_id`` de la empresa es aquí la FK ``partner``.
        """
        self.ensure_one()
        return pytz.timezone(
            (self.user_id.tz if self.user_id else None)
            or (self.company_id.partner.tz
                if self.company_id and self.company_id.partner else None)
            or 'UTC')
