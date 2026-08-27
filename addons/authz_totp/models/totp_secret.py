"""``TotpSecret`` — el secreto TOTP del usuario (2FA por TOTP, DEC-01).

Adaptación de Odoo ``auth_totp`` (LGPL-3): la referencia guarda
``totp_secret`` (base32) como campo ``NO_ACCESS`` en ``res.users``
(``auth_totp/models/res_users.py``); aquí vive en su propia tabla (app de
feature opcional), OneToOne con el usuario. Mientras se configura,
``confirmed=False``; al verificar el primer código, ``confirmed=True`` y el
2FA queda activo.

Divergencia declarada — el nombre del contador
===============================================

La referencia declara ``totp_last_counter`` **junto a** ``totp_secret``, los dos
sobre ``res.users`` (``odoo19c: auth_totp/models/res_users.py:31,34``), así que
el prefijo ``totp_`` los desambigua de todo lo demás que vive en ese modelo.
Aquí los dos viven en **este** modelo, que ya se llama ``TotpSecret``: el
prefijo se cae por la misma razón por la que ``totp_secret`` es ``secret``
—precedente de este archivo, no invención de este pase— y quedan ``secret`` y
``last_counter``.
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
    last_counter = fields.Integer(
        null=True, blank=True, default=None, verbose_name='Último contador',
        help_text=(
            'Odoo totp_last_counter — el intervalo del último código aceptado. '
            'Un código sólo vale una vez: la comprobación exige que el contador '
            'del código presentado sea ESTRICTAMENTE mayor que éste.'
        ),
    )

    class Meta:
        db_table = 'authz_totp_secret'
        verbose_name = 'Secreto TOTP'
        verbose_name_plural = 'Secretos TOTP'
        ordering = ['-created_at']

    def __str__(self):
        state = 'activo' if self.confirmed else 'pendiente'
        return f'TotpSecret[{self.user_id}] ({state})'
