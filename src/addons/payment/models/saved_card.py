"""Modelo ``SavedCard`` — addon ``payment`` (~ ``payment.token`` de Odoo)."""
import secrets
from django.conf import settings
from django.db import models
from addons.base.models import TimeStampedModel


def _make_verification_token():
    return secrets.token_urlsafe(48)


class SavedCard(TimeStampedModel):
    """
    Tarjeta guardada por un usuario autenticado en MercadoPago Customer Cards.

    Flujo de verificación por email (seguridad interna):
    1. Usuario solicita guardar tarjeta → status=PENDING_VERIFICATION
    2. Se envía email con link que contiene verification_token
    3. Usuario hace clic → status=ACTIVE
    4. Solo tarjetas ACTIVE se muestran en el checkout

    mp_card_id es el ID de la tarjeta en el sistema de MP.
    mp_customer_id duplica el campo del User para consultas sin JOIN.
    """
    STATUS_PENDING  = 'pending_verification'
    STATUS_ACTIVE   = 'active'
    STATUS_DELETED  = 'deleted'
    STATUSES = [
        (STATUS_PENDING, 'Pendiente de verificación'),
        (STATUS_ACTIVE,  'Activa'),
        (STATUS_DELETED, 'Eliminada'),
    ]

    user               = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_cards',
    )
    mp_card_id         = models.CharField(max_length=100, db_index=True)
    mp_customer_id     = models.CharField(max_length=100, db_index=True)
    last_four_digits   = models.CharField(max_length=4)
    first_six_digits   = models.CharField(max_length=6, blank=True, default='')
    expiration_month   = models.PositiveSmallIntegerField()
    expiration_year    = models.PositiveSmallIntegerField()
    payment_method_id  = models.CharField(max_length=50, blank=True, default='')
    cardholder_name    = models.CharField(max_length=200, blank=True, default='')
    status             = models.CharField(
        max_length=30, choices=STATUSES, default=STATUS_PENDING, db_index=True,
    )
    verification_token = models.CharField(
        max_length=100, unique=True, default=_make_verification_token,
        help_text='Token de un solo uso enviado por email para activar la tarjeta.',
    )

    class Meta:
        db_table     = 'payments_saved_card'
        ordering     = ['-created_at']
        verbose_name = 'Tarjeta guardada'
        constraints  = [
            models.UniqueConstraint(
                fields=['user', 'mp_card_id'],
                name='unique_user_mp_card',
            )
        ]

    def __str__(self):
        return f'****{self.last_four_digits} ({self.payment_method_id}) — {self.status}'
