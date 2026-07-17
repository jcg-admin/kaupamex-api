"""
Models — addons.newsletter (UC-NEW-01..04).

Identifiers + field names in English per DEC-DOC-005.

NewsletterSubscriber — suscriptor a la newsletter publica. Estados:
    PENDING       — alta enviada, falta confirmar (doble opt-in).
    CONFIRMED     — confirmado, recibe campanas.
    UNSUBSCRIBED  — opt-out (auto o forzado por admin).

NewsletterCampaign — campana enviada por admin a una audiencia
                     filtrada (status=CONFIRMED por defecto).
"""
import secrets

from django.core import signing
from django.conf import settings
from django.db import models
from core.models import SoftDeleteModel, TimeStampedModel



def _generate_unsubscribe_token():
    """Genera token HMAC firmado con TTL para opt-out (DEC-NEW-02 T-117)."""
    return signing.dumps(secrets.token_urlsafe(16), salt='newsletter-unsub')


class SubscriberStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pendiente'
    CONFIRMED = 'CONFIRMED', 'Confirmado'
    UNSUBSCRIBED = 'UNSUBSCRIBED', 'Dado de baja'


class NewsletterSubscriber(TimeStampedModel, SoftDeleteModel):
    """Suscriptor de la newsletter publica.

    Coexisten dos semánticas de "borrado":

    - ``status=UNSUBSCRIBED`` / ``unsubscribed_at``: opt-out de NEGOCIO
      (el usuario o el admin marca la baja de la newsletter). La fila
      sigue listada y se conserva el token para casos de re-suscripcion.
    - ``is_deleted`` / ``deleted_at`` (heredados de SoftDeleteModel,
      DEC-DOC-007): borrado LOGICO de SISTEMA. El admin descarta la
      fila del listado operativo; queda disponible en
      ``NewsletterSubscriber.all_objects`` para auditoria (PII +
      compliance LOPD).

    Ambos son ortogonales: un suscriptor confirmado puede ser borrado
    logicamente sin pasar antes por UNSUBSCRIBED.
    """

    email = models.EmailField(unique=True)
    status = models.CharField(
        max_length=16,
        choices=SubscriberStatus.choices,
        default=SubscriberStatus.PENDING,
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    confirmation_token = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        default=None,
    )
    unsubscribe_token = models.CharField(
        max_length=200,
        unique=True,
        default=_generate_unsubscribe_token,
    )

    class Meta:
        db_table = 'newsletter_subscriber'
        ordering = ['-created_at']
        verbose_name = 'Suscriptor de newsletter'
        verbose_name_plural = 'Suscriptores de newsletter'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f'{self.email} ({self.status})'


class NewsletterCampaign(TimeStampedModel):
    """Campana enviada por admin a una audiencia filtrada."""

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='newsletter_campaigns_sent',
    )
    subject = models.CharField(max_length=200)
    body = models.TextField()
    audience_filter = models.CharField(
        max_length=32,
        default=SubscriberStatus.CONFIRMED,
        help_text='Status objetivo (default: CONFIRMED).',
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    recipients_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'newsletter_campaign'
        ordering = ['-created_at']
        verbose_name = 'Campana de newsletter'
        verbose_name_plural = 'Campanas de newsletter'

    def __str__(self):
        return f'Campaign#{self.pk} {self.subject} ({self.recipients_count})'
