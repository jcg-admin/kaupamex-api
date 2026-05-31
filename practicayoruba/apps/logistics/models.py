"""
Models — apps.logistics (P-13 / UC-LOG-01..09).

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
from django.conf import settings
from django.db import models
from apps.core.models import SoftDeleteModel, TimeStampedModel



class Courier(TimeStampedModel):
    """Shipping provider catalogue."""
    name        = models.CharField(max_length=80, unique=True)
    code        = models.CharField(max_length=20, unique=True, db_index=True)
    tracking_url_template = models.CharField(
        max_length=255, blank=True, default='',
        help_text='URL template with {tracking_number} placeholder.',
    )
    is_active   = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table     = 'logistics_courier'
        ordering     = ['name']
        verbose_name = 'Paqueteria'

    def __str__(self):
        return self.name


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

    order           = models.OneToOneField(
        'orders.Order', on_delete=models.PROTECT, related_name='shipment_guide',
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
