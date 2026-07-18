"""Models — addons.authz_audit (auditoría de autorización, DEC-07).

``AuthzEvent`` extraído de ``addons.authz`` a su propio módulo (SOL-094 frente B,
DEC-01) manteniendo la tabla física ``authz_event`` (migración
``SeparateDatabaseAndState``). Patrón Odoo: la auditoría es un módulo de feature
separado (``account_audit_trail``), no parte del core.
"""
from django.conf import settings
from django.db import models

from core.models import AppendOnlyModel


class AuthzEvent(AppendOnlyModel):
    """Auditoría append-only de autorización (DEC-07): se emite en denegación
    (403) y en uso exitoso de una ``Capability.is_sensitive=True``. Mismo patrón
    que ``BusinessEvent``. PII-safe: no guarda tokens ni passwords."""
    ACTION_DENY = 'DENY'
    ACTION_SENSITIVE_USE = 'SENSITIVE_USE'
    ACTION_CHOICES = [
        (ACTION_DENY, 'Denegación (403)'),
        (ACTION_SENSITIVE_USE, 'Uso de capacidad sensible'),
    ]

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='authz_events', verbose_name='Actor',
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, db_index=True, verbose_name='Acción')
    capability_code = models.CharField(max_length=100, blank=True, default='', verbose_name='Capacidad')
    ip_addr = models.GenericIPAddressField(null=True, blank=True)
    correlation_id = models.CharField(max_length=32, blank=True, default='', db_index=True)
    extra_json = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = 'authz_event'
        verbose_name = 'Evento de autorización'
        verbose_name_plural = 'Eventos de autorización'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['action', '-created_at']),
            models.Index(fields=['actor', 'action', '-created_at']),
        ]

    def __str__(self):
        a = self.actor_id or 'anon'
        return f'AuthzEvent[{a}] {self.action} {self.capability_code}'
