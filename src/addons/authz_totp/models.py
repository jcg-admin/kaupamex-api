"""Models — addons.authz_totp (2FA por TOTP, DEC-01).

Adaptación de ``auth_totp`` de Odoo, que guarda ``totp_secret`` (base32) en
``res.users`` (``groups=NO_ACCESS``). Aquí el secreto vive en su propia tabla
(app de feature opcional), OneToOne con el usuario: mientras se configura,
``confirmed=False``; al verificar el primer código, ``confirmed=True`` y el 2FA
queda activo. ``totp_enabled(user)`` == existe fila ``confirmed=True``.
"""
from django.conf import settings
import fields
import models

from addons.base.models import TimeStampedModel


class TotpSecret(TimeStampedModel):
    """Secreto TOTP de un usuario (base32). Un secreto por usuario.

    NO expuesto por la API salvo en el flujo de setup (URI de aprovisionamiento).
    Paridad con Odoo: el secreto se guarda como base32 en claro (Odoo lo marca
    ``NO_ACCESS`` pero no lo cifra por defecto). Endurecer el cifrado en reposo
    es follow-up (ver hallazgos H-API-TOTP-*).
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='totp_secret', verbose_name='Usuario',
    )
    secret = fields.Char(
        max_length=64, verbose_name='Secreto (base32)',
        help_text='Clave TOTP en base32 (RFC 4648). No se expone salvo en setup.',
    )
    confirmed = fields.Boolean(
        default=False, db_index=True, verbose_name='Confirmado',
        help_text='True cuando el usuario verificó el primer código (2FA activo).',
    )

    class Meta:
        db_table = 'authz_totp_secret'
        verbose_name = 'Secreto TOTP'
        verbose_name_plural = 'Secretos TOTP'
        ordering = ['-created_at']

    def __str__(self):
        state = 'activo' if self.confirmed else 'pendiente'
        return f'TotpSecret[{self.user_id}] ({state})'


class TotpRecoveryCode(TimeStampedModel):
    """Código de recuperación de un solo uso (backup del 2FA).

    Adaptación de los *recovery codes* de ``auth_totp`` de Odoo: al activar el
    2FA se generan N códigos que el usuario guarda; si pierde el authenticator,
    puede iniciar sesión con uno de ellos (se consume). Se guarda **hasheado**
    (SHA-256), no en claro — endurecimiento sobre el default de Odoo, sin costo
    funcional: el código plano sólo se muestra una vez al generarlo.
    """
    user = fields.Many2one(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='totp_recovery_codes', verbose_name='Usuario',
    )
    code_hash = fields.Char(
        max_length=64, verbose_name='Hash del código',
        help_text='SHA-256 hex del código de recuperación (el plano no se guarda).',
    )
    used_at = fields.Datetime(
        null=True, blank=True, db_index=True, verbose_name='Consumido en',
        help_text='Timestamp de uso; NULL = aún válido (un solo uso).',
    )

    class Meta:
        db_table = 'authz_totp_recovery_code'
        verbose_name = 'Código de recuperación TOTP'
        verbose_name_plural = 'Códigos de recuperación TOTP'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'code_hash'],
                         name='authz_totp_rec_user_hash'),
        ]

    def __str__(self):
        state = 'usado' if self.used_at else 'válido'
        return f'TotpRecoveryCode[{self.user_id}] ({state})'
