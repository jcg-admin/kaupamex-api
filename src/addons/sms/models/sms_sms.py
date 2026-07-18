"""Modelo ``SmsSms`` — addon ``sms``.

Adaptación de Odoo ``sms/models/sms_sms.py`` (``sms.sms`` — "Outgoing SMS"):
registro de un SMS saliente. Se conserva el núcleo del modelo — ``number`` +
``body`` + ``state`` — y se colapsa la selección de estado de Odoo (outgoing/
process/pending/sent/error/canceled) a los estados que este stack necesita
(pendiente/enviado/error). La integración IAP de Odoo (envío real vía su API de
SMS) queda fuera de scope: aquí ``SmsSms`` es el registro de intención de envío
y su transición de estado; el transporte real lo cablea el proveedor que se
integre después (Clausula 5 anti-performativa — no se fabrica el gateway).
"""
from django.db import models

from core.models import TimeStampedModel


class SmsSms(TimeStampedModel):
    """``sms.sms`` — un SMS saliente y su estado de envío."""

    STATE_PENDING = 'pending'
    STATE_SENT    = 'sent'
    STATE_ERROR   = 'error'
    STATE_CHOICES = [
        (STATE_PENDING, 'En cola'),
        (STATE_SENT, 'Enviado'),
        (STATE_ERROR, 'Error'),
    ]

    # Odoo sms.sms.number (sms_sms.py:40).
    number     = models.CharField(
        max_length=32, help_text='Número destino (Odoo sms.sms.number).',
    )
    # Odoo sms.sms.body (sms_sms.py:41).
    body       = models.TextField(
        help_text='Cuerpo del mensaje (Odoo sms.sms.body).',
    )
    # Odoo sms.sms.state (sms_sms.py:44) — colapsado a 3 estados.
    state      = models.CharField(
        max_length=16, choices=STATE_CHOICES, default=STATE_PENDING,
        help_text='Estado de envío (Odoo sms.sms.state, colapsado).',
    )
    # Odoo sms.sms.failure_type (sms_sms.py:54) — motivo de error, texto libre.
    error_code = models.CharField(
        max_length=64, blank=True, default='',
        help_text='Motivo del fallo si state=error (Odoo failure_type).',
    )

    class Meta:
        db_table = 'sms_sms'
        ordering = ['-created_at', '-id']
        verbose_name = 'SMS saliente'
        verbose_name_plural = 'SMS salientes'

    def __str__(self) -> str:
        return f'SMS→{self.number} [{self.state}]'

    def mark_sent(self) -> None:
        """Marca el SMS como enviado (Odoo state=sent)."""
        self.state = self.STATE_SENT
        self.error_code = ''
        self.save(update_fields=['state', 'error_code', 'updated_at'])

    def mark_error(self, code: str) -> None:
        """Marca el SMS como fallido con un motivo (Odoo state=error)."""
        self.state = self.STATE_ERROR
        self.error_code = code
        self.save(update_fields=['state', 'error_code', 'updated_at'])
