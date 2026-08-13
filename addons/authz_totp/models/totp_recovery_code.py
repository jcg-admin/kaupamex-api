"""``TotpRecoveryCode`` — código de recuperación de un solo uso.

SIN contraparte en la referencia (medido: 0 hits de "recovery" en
``odoo19c: auth_totp/``) — endurecimiento propio: al activar el 2FA se
generan N códigos que el usuario guarda; si pierde el authenticator, inicia
sesión con uno (se consume). Se guarda hasheado (SHA-256), no en claro.
"""
from django.conf import settings

import fields
import models

from addons.base.models import TimeStampedModel

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
