"""``SignupRequest`` — el ``signup_type`` pendiente de un partner.

Adaptación de Odoo ``auth_signup/models/res_partner.py`` (LGPL-3): la
referencia cuelga ``signup_type`` de ``res.partner`` con ``_inherit`` (un Char
'signup'/'reset'/None). Django no permite inyectar campos en el modelo de otra
app, así que el estado vive en su propia tabla, OneToOne con el partner —
mismo criterio que ``authz_totp.TotpSecret``.

Es **lo único que se persiste** del flujo: el token en sí es firmado y
stateless (``../token.py``). Que exista una fila con ``signup_type`` = hay un
signup/reset pendiente para ese partner.
"""
import fields
import models

from addons.base.models import TimeStampedModel


class SignupRequest(TimeStampedModel):
    """El signup/reset pendiente de un partner. ≙ ``res.partner.signup_type``."""

    TYPE_SIGNUP = 'signup'
    TYPE_RESET = 'reset'
    # Forma propia declarada — la referencia NO tiene verificación de correo.
    # Medido sobre ``odoo-tools@622ddc2a``: en todo ``odoo19c:`` no hay una
    # ``@route`` cuyo path contenga ``verify``/``confirm`` fuera de
    # ``/shop/confirmation``, y ``signup_type`` sólo toma ``'signup'``/
    # ``'reset'`` (``odoo19c: addons/auth_signup/models/res_partner.py:113``).
    # En la referencia el alta ES la prueba del buzón: el enlace de invitación
    # llega al correo. Nuestro producto además permite alta self-service con
    # contraseña inmediata, así que la cuenta nace ``active=False`` con
    # ``deactivated_reason='unverified'`` y necesita este tercer tipo.
    # Lo que sí se hereda es el **mecanismo**: mismo token firmado stateless.
    TYPE_VERIFY = 'verify'
    TYPE_CHOICES = [
        (TYPE_SIGNUP, 'Alta invitada'),
        (TYPE_RESET, 'Restablecer contraseña'),
        (TYPE_VERIFY, 'Verificación de correo'),
    ]

    partner = models.OneToOneField(
        'base.ResPartner', on_delete=models.CASCADE,
        related_name='signup_request', verbose_name='Partner',
    )
    signup_type = fields.Char(
        max_length=16, choices=TYPE_CHOICES,
        verbose_name='Tipo de signup',
        help_text='Odoo signup_type: "signup" (alta invitada) o "reset" '
                  '(restablecer contraseña). "verify" (verificación de '
                  'correo) es forma propia: no existe en la referencia.',
    )

    class Meta:
        db_table = 'authz_signup_request'
        verbose_name = 'Signup pendiente'
        verbose_name_plural = 'Signups pendientes'

    def __str__(self):
        return f'SignupRequest[{self.partner_id}] ({self.signup_type})'
