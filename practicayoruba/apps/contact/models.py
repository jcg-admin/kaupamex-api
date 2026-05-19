"""
Models — apps.contact (UC-COM-01..03).

Identifiers + field names in English per DEC-DOC-005.

ContactMessage — mensaje enviado a traves del formulario publico de
contacto. El admin puede marcarlo como leido y responder; la respuesta
se envia por email y se registra en el propio modelo.
"""
from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class ContactMessage(TimeStampedModel):
    """Mensaje recibido por el formulario publico de contacto."""

    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True, default='')
    subject = models.CharField(max_length=200)
    body = models.TextField()

    read = models.BooleanField(default=False)
    replied = models.BooleanField(default=False)

    reply_body = models.TextField(blank=True, default='')
    reply_sent_at = models.DateTimeField(null=True, blank=True)
    reply_sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contact_replies_sent',
    )

    class Meta:
        db_table = 'contact_message'
        ordering = ['-created_at']
        verbose_name = 'Mensaje de contacto'
        verbose_name_plural = 'Mensajes de contacto'
        indexes = [
            models.Index(fields=['read']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f'#{self.pk} {self.subject} ({self.email})'
