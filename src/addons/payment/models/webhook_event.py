"""Modelo ``WebhookEvent`` — addon ``payment`` (dedup de webhooks entrantes)."""
from django.db import models


class WebhookEvent(models.Model):
    """
    Registro dedup para idempotencia de webhooks entrantes. DEC-BC-04.
    UNIQUE(gateway, event_id, transmission_id) previene doble procesamiento.
    INSERT falla con IntegrityError si el evento ya fue procesado.
    """
    gateway         = models.CharField(max_length=20)
    event_id        = models.CharField(max_length=100)
    transmission_id = models.CharField(max_length=100, blank=True, default='')
    raw_body        = models.TextField()
    processed_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table     = 'payments_webhook_event'
        constraints  = [
            models.UniqueConstraint(
                fields=['gateway', 'event_id', 'transmission_id'],
                name='unique_webhook_event',
            )
        ]
        verbose_name = 'Webhook event'

    def __str__(self):
        return f'{self.gateway}/{self.event_id}'
