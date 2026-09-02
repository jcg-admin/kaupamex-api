"""Modelo ``PurchaseOrder`` — addon ``purchase``.

Adaptación fiel de Odoo ``purchase.order`` (``purchase/models/purchase_order.py``,
idéntico en 18 y 19): orden de compra a un proveedor. Núcleo verificado en ambas
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
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
import fields
import models
from django.utils import timezone

from addons.base.models import ResCurrency, TimeStampedModel

#: Centinela de «todavía no se cargó ninguna fila» — distinto de
#: ``company_id is None`` (fila cargada, sin empresa). El mismo patrón que
#: ``SaleOrder._loaded_company_id``
#: (``api: addons/sale/models/sale_order.py:855-861``).
_SIN_CARGAR = object()


class PurchaseOrder(TimeStampedModel):
    """``purchase.order`` — orden de compra a un proveedor."""

    STATE_DRAFT    = 'draft'
    STATE_SENT     = 'sent'
    STATE_PURCHASE = 'purchase'
    STATE_CANCEL   = 'cancel'
    STATE_CHOICES = [
        (STATE_DRAFT, 'Solicitud de cotización'),
        (STATE_SENT, 'Cotización enviada'),
        (STATE_PURCHASE, 'Orden de compra'),
        (STATE_CANCEL, 'Cancelada'),
    ]

    # Odoo purchase.order.name (default 'New' → aquí se asigna al confirmar).
    name       = fields.Char(
        max_length=32, blank=True, default='',
        help_text='Referencia de la orden (Odoo purchase.order.name).',
    )
    # Odoo purchase.order.partner_id — proveedor (res.partner). Aquí AUTH_USER.
    partner_id = fields.Many2one(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='purchase_orders', help_text='Proveedor (Odoo partner_id).',
        db_column='partner_id',
    )
    # Odoo purchase.order.date_order.
    date_order = fields.Datetime(
        null=True, blank=True, help_text='Fecha de la orden (Odoo date_order).',
    )
    # Odoo purchase.order.state.
    state      = fields.Selection(
        max_length=16, choices=STATE_CHOICES, default=STATE_DRAFT,
        help_text='Estado (Odoo purchase.order.state).',
    )
    # Odoo purchase.order.note.
    note       = fields.Text(
        blank=True, default='', help_text='Términos y condiciones (Odoo note).',
    )
    # Odoo purchase.order.company_id — ver docstring del módulo (tarea #266).
    company_id = fields.Many2one(
        'base.ResCompany', null=True, blank=True, on_delete=models.CASCADE,
        related_name='purchase_orders', db_index=True, db_column='company_id',
        help_text='Empresa dueña de la orden (Odoo company_id, required, '
                  'default=env.company). NULL pre-backfill — mismo patrón '
                  'que sale.order.company_id.',
    )
    # Odoo purchase.order.currency_id — compute+store+precompute (ver docstring).
    currency_id = fields.Many2one(
        'base.ResCurrency', null=True, blank=True, on_delete=models.PROTECT,
        related_name='+', db_column='currency_id',
        help_text='Odoo currency_id (compute, store=True, precompute, '
                  "readonly=False, ondelete='restrict' ≙ PROTECT). Sale de "
                  'la empresa — la rama del proveedor está degradada, ver '
                  'docstring del módulo.',
    )
    # Odoo purchase.order.currency_rate — compute+store+precompute (ver docstring).
    currency_rate = fields.Monetary(
        null=True, blank=True, max_digits=24, decimal_places=12,
        help_text='Odoo currency_rate ("Currency Rate", compute, store=True, '
                  'precompute, digits=0 en la fuente = precisión plena). '
                  'Monetary/Decimal en vez de Float — ver docstring del '
                  'módulo.',
    )

    #: Ver ``_SIN_CARGAR`` — mismo patrón que ``SaleOrder``.
    _loaded_company_id = _SIN_CARGAR
    _loaded_currency_id = _SIN_CARGAR
    _loaded_date_order = _SIN_CARGAR

    class Meta:
        db_table = 'purchase_order'
        ordering = ['-created_at', '-id']
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
        self.currency_id = self.company_id.currency if self.company_id_id else None

    def _compute_currency_rate(self):
        """≙ ``_compute_currency_rate`` (``odoo19c: purchase_order.py:
        211-218``). ``ResCurrency._get_conversion_rate`` ya está portado
        (``src/addons/base/models/res_currency.py:462``)."""
        company = self.company_id
        currency = self.currency_id
        if not self.company_id_id or not self.currency_id_id or company.currency is None:
            self.currency_rate = Decimal('1.0')
            return
        rate_date = (self.date_order or timezone.now()).date()
        self.currency_rate = ResCurrency._get_conversion_rate(
            from_currency=company.currency, to_currency=currency,
            company=company, date=rate_date,
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
            (creating and self.currency_id_id is None) or company_changed
        )
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
            or company_changed or currency_changed or date_changed
        )
        if recompute_rate:
            self._compute_currency_rate()

        if update_fields is not None and (recompute_currency or recompute_rate):
            extra = [f for f in ('currency_id', 'currency_rate')
                     if f not in update_fields]
            if extra:
                kwargs['update_fields'] = [*update_fields, *extra]

        super().save(*args, **kwargs)
        self._loaded_company_id = self.company_id_id
        self._loaded_currency_id = self.currency_id_id
        self._loaded_date_order = self.date_order

    def _sum_lines(self, attr: str) -> Decimal:
        # Odoo purchase.order._amount_all (suma de las líneas).
        return sum(
            (getattr(line, attr)() for line in self.order_line.all()),
            Decimal('0.00'),
        ).quantize(Decimal('0.01'))

    def amount_untaxed(self) -> Decimal:
        return self._sum_lines('price_subtotal')

    def amount_tax(self) -> Decimal:
        return self._sum_lines('price_tax')

    def amount_total(self) -> Decimal:
        return self._sum_lines('price_total')

    def _generate_purchase_name(self) -> str:
        # Odoo asigna la secuencia 'purchase.order' al confirmar; aquí P-<uuid>.
        return f'P-{uuid.uuid4().hex[:8].upper()}'

    def button_confirm(self):
        """Confirma la RFQ → orden de compra (Odoo purchase.order.button_confirm)."""
        if self.state not in (self.STATE_DRAFT, self.STATE_SENT):
            raise ValidationError('Solo una RFQ (draft/sent) puede confirmarse.')
        if not self.order_line.exists():
            raise ValidationError('No se puede confirmar una orden sin líneas.')
        if not self.name:
            self.name = self._generate_purchase_name()
        self.state = self.STATE_PURCHASE
        self.date_order = self.date_order or timezone.now()
        self.save(update_fields=['name', 'state', 'date_order', 'updated_at'])
        return self

    def button_cancel(self):
        """Cancela la orden (Odoo purchase.order.button_cancel)."""
        self.state = self.STATE_CANCEL
        self.save(update_fields=['state', 'updated_at'])
        return self
