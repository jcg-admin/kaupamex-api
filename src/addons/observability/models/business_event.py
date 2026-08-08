"""``BusinessEvent`` — bitácora append-only de eventos de negocio (SOL-011).

**Sin análogo en la referencia.** ``odoo19c`` no declara un modelo de auditoría
de negocio transversal: registra la actividad por documento vía ``mail.thread``
(``message_ids`` / ``mail.tracking.value``), no en una tabla plana de eventos.
Por eso vive en ``observability`` — el único addon net-new sancionado
(DEC-12) — y no en un addon de dominio: es telemetría de infraestructura, no un
modelo Odoo.

**Procedencia.** Declarado antes en ``users/models.py:594-644``. El commit
``api@6cf8120`` disolvió ``users`` en ``base`` (``res.users`` / ``res.partner``)
y ``BusinessEvent`` **murió sin destino**: no tiene homólogo ``res.*``, así que
no viajó con la identidad. :ref:`analisis-users-no-es-un-addon-en-la-referencia`
ya lo había nombrado como *"candidato a observability, el único net-new
sancionado"*; esto lo ejecuta. Ver H-API-211.

Cambios respecto del original, ambos consecuencia del traslado:

- ``db_table`` ``users_business_event`` → ``observability_business_event``.
- ``actor`` apunta a ``settings.AUTH_USER_MODEL``, que ahora resuelve a
  ``base.ResUsers``; ``__str__`` usa ``login`` (el ``USERNAME_FIELD`` de
  ``res.users``) en vez del ``email`` de la credencial difunta.
"""
from django.conf import settings
from django.db import models

from addons.base.models import AppendOnlyModel
from tools.logging_context import get_correlation_id


class BusinessEvent(AppendOnlyModel):
    """Audit trail de eventos business cross-cutting (append-only, PII safe)."""

    ACTION_ORDER_CREATED          = 'ORDER_CREATED'
    ACTION_ORDER_CANCELLED        = 'ORDER_CANCELLED'
    ACTION_RETURN_REQUESTED       = 'RETURN_REQUESTED'
    ACTION_RETURN_RESOLVED        = 'RETURN_RESOLVED'
    ACTION_STOCK_ADJUSTED_TO_ZERO = 'STOCK_ADJUSTED_TO_ZERO'
    ACTION_RECEIPT_PDF_GENERATED  = 'RECEIPT_PDF_GENERATED'
    ACTION_CHOICES = [
        (ACTION_ORDER_CREATED,          'Order creada'),
        (ACTION_ORDER_CANCELLED,        'Order cancelada'),
        (ACTION_RETURN_REQUESTED,       'Return solicitada'),
        (ACTION_RETURN_RESOLVED,        'Return resuelta'),
        (ACTION_STOCK_ADJUSTED_TO_ZERO, 'Stock ajustado a cero'),
        (ACTION_RECEIPT_PDF_GENERATED,  'Receipt PDF generado'),
    ]

    TARGET_ORDER   = 'order'
    TARGET_RETURN  = 'return'
    TARGET_VARIANT = 'variant'
    TARGET_PAYMENT = 'payment'

    actor       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='business_events',
    )
    action      = models.CharField(
        max_length=30, choices=ACTION_CHOICES, db_index=True)
    target_type = models.CharField(max_length=20, blank=True, default='')
    target_id   = models.PositiveIntegerField(null=True, blank=True)
    ip_addr     = models.GenericIPAddressField(null=True, blank=True)
    extra_json  = models.JSONField(null=True, blank=True)
    correlation_id = models.CharField(
        max_length=32, db_index=True, blank=True, default='')

    class Meta:
        db_table = 'observability_business_event'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['action', '-created_at']),
            models.Index(fields=['target_type', 'target_id']),
        ]

    def save(self, *args, **kwargs):
        # DEC-LOG-07: sella el correlation_id de la request en curso si el
        # llamador no lo fijó explícitamente. No pisa un valor ya provisto.
        if not self.correlation_id:
            self.correlation_id = get_correlation_id() or ''
        super().save(*args, **kwargs)

    def __str__(self):
        a = self.actor.login if self.actor_id else 'system'
        return f'BusinessEvent[{a}] {self.action} {self.target_type}#{self.target_id}'
