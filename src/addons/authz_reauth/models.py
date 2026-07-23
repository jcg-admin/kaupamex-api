"""Models — addons.authz_reauth (step-up / re-autenticación, DEC-12 shape A).

App de feature opcional separada del core ``addons.authz`` (SOL-094 frente B,
DEC-01), al estilo ``auth_totp`` de Odoo. La tabla física ``authz_reauth_session``
NO cambia: la mudanza entre app labels se hace con ``SeparateDatabaseAndState``
(migración ``authz.0011`` la borra del *state* de ``authz``; ``0001`` de esta app
la re-declara en el *state*, sin tocar la tabla).
"""
from django.conf import settings
from django.db import models
from django.utils import timezone

from addons.base.models import TimeStampedModel


class ReauthSession(TimeStampedModel):
    """Sesión reautenticada — DEC-12 shape A.

    Ventana temporal, con TTL, abierta tras **re-autenticación**, dentro de la
    cual las acciones **sensibles** del usuario pasan sin re-teclear
    credenciales. **NO es una elevación de privilegios** (no se llama "sudo" a
    propósito): la elegibilidad es por **capacidad/Role** —nunca ``is_staff``,
    invariante SoD— y confirmar identidad **no otorga poderes nuevos**; sólo
    ratifica intención para las acciones sensibles que el Role del usuario ya
    autoriza (:ref:`analisis-diseno-reauth-sensibles-dec12`).

    Se ata a la **sesión** Django (``session_key``): una fila activa por
    ``(user, session_key)``. El gate vive en el permission class
    ``HasCapability`` (``assert_session_fresh``), no en un middleware. La
    apertura/cierre se auditan en ``AuthzEvent`` (DEC-07). Un cierre de sesión
    la deja huérfana; el barrido de expiradas lo hace la propia consulta
    (``expires_at__gt=now``).
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='reauth_sessions', verbose_name='Usuario',
    )
    session_key = models.CharField(
        max_length=40, blank=True, default='', db_index=True,
        verbose_name='Clave de sesión',
        help_text='Sesión Django a la que se ata la reautenticación.',
    )
    started_at = models.DateTimeField(verbose_name='Iniciada')
    expires_at = models.DateTimeField(db_index=True, verbose_name='Expira')
    ip_addr = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP')

    class Meta:
        db_table = 'authz_reauth_session'
        verbose_name = 'Sesión reautenticada'
        verbose_name_plural = 'Sesiones reautenticadas'
        ordering = ['-started_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'session_key'], name='uq_authz_reauth_session',
            ),
        ]
        indexes = [
            models.Index(fields=['user', 'session_key', 'expires_at']),
        ]

    def is_active(self, now=None):
        return self.expires_at > (now or timezone.now())

    def __str__(self):
        return f'ReauthSession[{self.user_id}] → {self.expires_at:%Y-%m-%dT%H:%M}'
