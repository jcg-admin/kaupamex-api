"""Models — addons.authz_reauth (step-up / re-autenticación, DEC-12 shape A).

App de feature opcional separada del core ``addons.authz`` (SOL-094 frente B,
DEC-01), al estilo ``auth_totp`` de Odoo. La tabla física ``authz_reauth_session``
NO cambia: la mudanza entre app labels se hace con ``SeparateDatabaseAndState``
(migración ``authz.0011`` la borra del *state* de ``authz``; ``0001`` de esta app
la re-declara en el *state*, sin tocar la tabla).
"""
from api import autovacuum
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
    apertura/cierre se auditan en ``AuthzEvent`` (DEC-07).

    **Divergencia declarada frente a la referencia** (:ref:`h-api-767`). El
    equivalente de este mecanismo es ``check_identity``
    (``odoo19c: odoo/addons/base/models/res_users.py:87-127``), que guarda la
    marca en la **sesión** —``session['identity-check-last']``— y no en una
    tabla. Aquí es una tabla porque la ventana debe sobrevivir a un canal de
    autenticación **sin sesión**: ``base.py:401-403`` declara que reañadir
    ``JWTAuthentication`` es el camino de la app móvil, y con JWT
    ``request.session`` nace vacía en cada petición — la marca en sesión no se
    encontraría nunca y la acción sensible quedaría en 403 permanente.

    Lo que **sí** se adopta de la referencia es su higiene: las filas vencidas
    se barren con ``@api.autovacuum`` (abajo). La redacción anterior decía que
    *"el barrido de expiradas lo hace la propia consulta"* — y no lo hace:
    ``expires_at__gt=now`` **ignora** la fila vencida, no la borra. Filtrar no
    es barrer, y sin barrido la tabla sólo crecía.
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

    @classmethod
    @autovacuum
    def _gc_reauth_sessions(cls) -> int:
        """Purga las ventanas vencidas — ≙ ``_gc_user_logs``
        (``odoo19c: odoo/addons/base/models/res_users.py:143``).

        Una fila vencida no eleva nada: ``has_active_reauth_session`` filtra
        por ``expires_at__gt=now``. Pero **filtrar no es barrer**, y la clave
        natural ``(user, session_key)`` rota en cada login —Django cicla el
        ``session_key`` al autenticar—, así que sin este barrido la tabla gana
        una fila muerta por cada sesión que alguna vez se elevó.

        Devuelve cuántas borró, que es lo que el colector reencola por lotes.
        """
        deleted, _ = cls.objects.filter(expires_at__lte=timezone.now()).delete()
        return deleted

    def __str__(self):
        return f'ReauthSession[{self.user_id}] → {self.expires_at:%Y-%m-%dT%H:%M}'
