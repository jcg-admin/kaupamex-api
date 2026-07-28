"""
Models — addons.delivery (P-13 / UC-LOG-01..09).

Entities:
  - Courier: catalogue of shipping providers (Estafeta, DHL, FedEx, ...).
  - ShipmentGuide: one-to-one with Order (an order has at most one
    active shipment). Hereda SoftDeleteModel para conservar historial
    de guias canceladas.
  - ShipmentEvent: append-only audit log of guide status transitions
    (DEC-DOC-007 explicit exception for audit tables).

English identifiers per DEC-DOC-005. Business codes Spanish per
DEC-DOC-006 (raised in views, not in models).
"""
import base64
import hashlib
import hmac
import logging
from decimal import Decimal
from cryptography.fernet import Fernet
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from addons.base.models import SoftDeleteModel, TimeStampedModel
from addons.delivery.offers import RateCard
from addons.delivery.models.shipping_zone import ShippingZone

logger = logging.getLogger('apps')


class Courier(TimeStampedModel):
    """Shipping provider catalogue."""
    name        = models.CharField(max_length=80, unique=True)
    code        = models.CharField(max_length=20, unique=True, db_index=True)
    tracking_url_template = models.CharField(
        max_length=255, blank=True, default='',
        help_text='URL template with {tracking_number} placeholder.',
    )
    is_active   = models.BooleanField(default=True, db_index=True)
    # LOG-04 (US-1.2 / DEC-LOOP-05): shared secret used to verify the HMAC
    # signature of courier status webhooks. Stored Fernet-encrypted (same
    # pattern as addons.settings_app.PaymentGateway.credentials, DEC-DOC-008) —
    # never in plaintext. Empty/unset means the courier cannot send webhooks
    # and any incoming webhook for it is rejected fail-closed.
    webhook_secret = models.BinaryField(
        null=True, blank=True,
        help_text='Per-courier webhook secret, Fernet-encrypted (LOG-04).',
    )

    class Meta:
        db_table     = 'logistics_courier'
        ordering     = ['name']
        verbose_name = 'Paqueteria'

    def __str__(self):
        return self.name

    @staticmethod
    def _fernet_key() -> bytes:
        raw = settings.SECRET_KEY.encode()
        digest = hashlib.sha256(raw).digest()
        return base64.urlsafe_b64encode(digest)

    def set_webhook_secret(self, plaintext: str) -> None:
        """Encrypt and store the shared webhook secret for this courier."""
        if not plaintext:
            self.webhook_secret = None
            return
        f = Fernet(self._fernet_key())
        self.webhook_secret = f.encrypt(plaintext.encode())

    def get_webhook_secret(self) -> str | None:
        """Decrypt and return the webhook secret, or None if unset/invalid."""
        if not self.webhook_secret:
            return None
        try:
            f = Fernet(self._fernet_key())
            return f.decrypt(bytes(self.webhook_secret)).decode()
        except Exception:
            # Loud-log: secret no descifrable (SECRET_KEY rotada o blob
            # corrupto). Sin secret legible, los webhooks de este courier
            # se rechazan fail-closed. Operaciones debe verlo. DEC-DOC-008.
            logger.warning(
                'Courier.get_webhook_secret: decrypt failed code=%s',
                getattr(self, 'code', '?'), exc_info=True,
            )
            return None

    def verify_webhook_signature(self, raw_body: bytes, signature: str) -> bool:
        """Verify an HMAC-SHA256 hex signature over raw_body (LOG-04).

        Fail-closed: missing signature or missing/unreadable secret -> False.
        Constant-time comparison to prevent timing attacks.
        """
        if not signature:
            return False
        secret = self.get_webhook_secret()
        if not secret:
            logger.error(
                'Courier webhook: secret no configurado code=%s — rechazando',
                getattr(self, 'code', '?'),
            )
            return False
        expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)


class ShipmentGuide(TimeStampedModel, SoftDeleteModel):
    """Shipment guide linked to an order. UC-LOG-01..09."""
    STATUS_CREATED    = 'CREATED'
    STATUS_PICKED_UP  = 'PICKED_UP'
    STATUS_IN_TRANSIT = 'IN_TRANSIT'
    STATUS_DELIVERED  = 'DELIVERED'
    STATUS_INCIDENT   = 'INCIDENT'
    STATUS_CANCELLED  = 'CANCELLED'
    STATUSES = [
        (STATUS_CREATED,    'Creada'),
        (STATUS_PICKED_UP,  'Recolectada'),
        (STATUS_IN_TRANSIT, 'En transito'),
        (STATUS_DELIVERED,  'Entregada'),
        (STATUS_INCIDENT,   'Incidente'),
        (STATUS_CANCELLED,  'Cancelada'),
    ]

    # E4-pre (H-API-26): anclaje invertido. El eje de fulfillment es la
    # adaptación de stock.picking y en Odoo cuelga de la sale.order — la
    # canónica manda (NOT NULL, PROTECT); la FK al espejo queda
    # nullable/SET_NULL hasta su retiro en E5.
    order           = models.OneToOneField(
        'orders.Order', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='shipment_guide',
    )
    sale_order      = models.OneToOneField(
        'sale.SaleOrder', on_delete=models.PROTECT, related_name='shipment_guide',
    )
    courier         = models.ForeignKey(
        Courier, on_delete=models.PROTECT, related_name='guides',
    )
    # H-CICLO78-10: tracking_number must be unique per courier, not globally.
    # Different couriers (DHL, Estafeta, FedEx) independently generate tracking
    # numbers and may issue the same number string. A global UNIQUE constraint
    # would reject the second guide as a duplicate even though
    # (DHL, "12345") and (Estafeta, "12345") are distinct shipments.
    # Uniqueness is enforced via unique_together = ('courier', 'tracking_number')
    # in Meta, and a db_index on tracking_number alone is retained for fast lookups.
    tracking_number = models.CharField(max_length=80, db_index=True)
    # UC-LOG-02 PARTE 7.1 / Alt B: optional direct tracking URL provided by the
    # courier. When set, takes precedence over the courier's URL template so the
    # buyer (UC-LOG-03) sees the exact link the courier supplied.
    tracking_url    = models.URLField(max_length=500, blank=True, default='')
    status          = models.CharField(
        max_length=20, choices=STATUSES,
        default=STATUS_CREATED, db_index=True,
    )
    delivered_at    = models.DateTimeField(null=True, blank=True)
    estimated_delivery = models.DateTimeField(null=True, blank=True)
    notes           = models.TextField(blank=True, default='')

    class Meta:
        db_table     = 'logistics_shipment_guide'
        ordering     = ['-created_at']
        verbose_name = 'Guia de envio'
        # H-CICLO78-10: uniqueness per courier — same tracking number is valid
        # for different carriers (each carrier has its own numbering space).
        constraints = [
            models.UniqueConstraint(
                fields=['courier', 'tracking_number'],
                name='unique_tracking_per_courier',
            ),
        ]

    def __str__(self):
        return f'{self.tracking_number} ({self.courier.code})'


class ShipmentEvent(TimeStampedModel):
    """
    Append-only audit log of guide status transitions.

    DEC-DOC-007 exception: tablas append-only (auditoria) NO heredan
    SoftDeleteModel. La integridad del historial depende de que las
    filas sean inmutables.
    """
    guide        = models.ForeignKey(
        ShipmentGuide, on_delete=models.CASCADE, related_name='events',
    )
    status       = models.CharField(max_length=20)
    description  = models.CharField(max_length=255, blank=True, default='')
    occurred_at  = models.DateTimeField()
    recorded_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
    )

    class Meta:
        db_table     = 'logistics_shipment_event'
        ordering     = ['-occurred_at', '-created_at']
        verbose_name = 'Evento de envio'

    def __str__(self):
        return f'{self.guide.tracking_number}: {self.status} @ {self.occurred_at:%Y-%m-%d %H:%M}'


class CarrierRateCard(TimeStampedModel):
    """Catálogo de tarifas + reglas de una paquetería para el motor de
    cotización (addons.delivery.offers). Separado de ``Courier`` (que modela
    tracking/webhooks) por responsabilidad única: aquí vive el pricing y las
    reglas de elegibilidad. Un ``Courier`` sin rate card no se cotiza.

    Reglas ``null`` = sin límite. Dimensiones por eje (para "cualquier dimensión
    ≤ N" se fija el mismo N en los tres). Costo = base + por_kg × peso_total.
    """
    ENV_LOW    = 'low'
    ENV_MEDIUM = 'medium'
    ENV_HIGH   = 'high'
    ENV_CHOICES = [(ENV_LOW, 'Baja'), (ENV_MEDIUM, 'Media'), (ENV_HIGH, 'Alta')]

    courier = models.OneToOneField(
        Courier, on_delete=models.CASCADE, related_name='rate_card')
    base_cost   = models.DecimalField(max_digits=10, decimal_places=2)
    cost_per_kg = models.DecimalField(max_digits=10, decimal_places=2)
    transit_days = models.PositiveSmallIntegerField()
    environmental = models.CharField(
        max_length=6, choices=ENV_CHOICES, default=ENV_MEDIUM,
        help_text='Rating ambiental (mayor es mejor en el ranking).')

    max_package_weight_kg = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True)
    max_length_cm = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True)
    max_width_cm  = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True)
    max_height_cm = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True)
    max_total_value = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    max_total_weight_kg = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    allows_hazardous = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table     = 'logistics_carrier_rate_card'
        verbose_name = 'Tarifa de paqueteria'

    def __str__(self):
        return f'RateCard({self.courier.name})'

    def to_rate_card(self):
        """Proyección al dataclass puro ``offers.RateCard``."""
        return RateCard(
            carrier=self.courier.name,
            base_cost=self.base_cost,
            cost_per_kg=self.cost_per_kg,
            transit_days=self.transit_days,
            environmental=self.environmental,
            max_package_weight_kg=self.max_package_weight_kg,
            max_length_cm=self.max_length_cm,
            max_width_cm=self.max_width_cm,
            max_height_cm=self.max_height_cm,
            max_total_value=self.max_total_value,
            max_total_weight_kg=self.max_total_weight_kg,
            allows_hazardous=self.allows_hazardous,
        )


class ShippingMethod(TimeStampedModel):
    """Método de envío disponible. UC-CFG-02.

    Contraparte de ``delivery.carrier`` (Odoo ``delivery``): el método de
    envío que el comprador elige en el checkout, con costo y umbral de
    gratuidad. Movido state-only desde el addon no-Odoo ``settings_app``;
    la tabla física ``settings_shipping_method`` no cambia.
    """
    name           = models.CharField(max_length=100)
    cost           = models.DecimalField(
                       max_digits=10, decimal_places=2,
                       validators=[MinValueValidator(Decimal('0'))],
                       help_text='Costo de envío. 0 = gratis.')
    estimated_days = models.PositiveSmallIntegerField()
    is_active      = models.BooleanField(default=True, db_index=True)
    free_threshold = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    zones          = models.JSONField(default=list, blank=True)
    # E1-bis (H-API-24): producto de servicio que representa este método como
    # LÍNEA de la venta. Contraparte de Odoo ``delivery.carrier.product_id``
    # (``delivery/models/delivery_carrier.py:56``), que allí es
    # ``required=True`` porque ``sale.order.line.product_id`` es obligatorio —
    # igual que aquí (``SaleOrderLine.product`` es PROTECT NOT NULL).
    #
    # Aquí es **opcional** a propósito: el comprador ya no elige transportista
    # (``orders/services.py:update_shipping_method`` DEPRECADO 2026-07-07 — el
    # envío se deriva por zona), así que un método sin producto sigue siendo
    # utilizable para cotizar; sólo no puede facturarse como concepto. La FK se
    # puebla por método vía ``ensure_service_product`` y el gate de la línea
    # vive en el servicio, no en el esquema.
    product        = models.ForeignKey(
                       'catalogue.Product', null=True, blank=True,
                       on_delete=models.PROTECT, related_name='shipping_methods',
                       help_text='Producto de servicio para la línea de envío '
                                 '(Odoo delivery.carrier.product_id).')

    class Meta:
        db_table     = 'settings_shipping_method'
        ordering     = ['cost', 'name']
        verbose_name = 'Método de envío'

    def __str__(self):
        return f'{self.name} (${self.cost})'

    # E1-bis: sembrado del producto de servicio (≙ delivery_data.xml de Odoo,
    # que trae ``product_product_delivery`` como dato maestro editable con
    # ``type=service`` y ``sale_ok=False`` — no un artefacto de runtime).
    #
    # Equivalencias de la semilla:
    #   Odoo ``type='service'``  → nuestro producto sin stock relevante.
    #   Odoo ``sale_ok=False``   → ``is_published=False`` (fuera del storefront:
    #                              el comprador nunca lo ve en el catálogo).
    SERVICE_SKU_PREFIX = 'SRV-ENVIO-'

    def ensure_service_product(self):
        """Devuelve el producto de servicio de este método, creándolo si falta.

        Idempotente: dos llamadas devuelven la misma fila. El precio del
        producto es informativo — el importe que va a la línea lo fija el
        servicio de venta con el costo calculado para la orden (por zona), no
        este campo.
        """
        if self.product_id is not None:
            return self.product
        product_model = self._meta.get_field('product').related_model
        sku = f'{self.SERVICE_SKU_PREFIX}{self.pk}'
        product, _ = product_model.objects.get_or_create(
            sku=sku,
            defaults={
                'name': f'Envío — {self.name}',
                'slug': f'servicio-envio-{self.pk}',
                'price': self.cost,
                'is_active': True,
                'is_published': False,
                'short_description': 'Concepto de envío para facturación.',
            },
        )
        self.product = product
        self.save(update_fields=['product', 'updated_at'])
        return product
