"""Tests — addons.authz_totp_mail (2FA por correo e invitación).

Porta la intención de ``odoo19c: auth_totp_mail/tests/``: el código emitido
por ``totp_mail_code`` verifica contra ``verify_totp_mail_code`` (ida y
vuelta del TOTP con timestep 3600), la invitación omite a quienes ya tienen
2FA activo, y la política ``authz_totp.policy`` decide quién queda obligado.
El transporte de correo corre síncrono en testing (DISPATCH_EMAIL_SYNC) y se
asserta sobre ``mail.outbox``.
"""
import pytest
from django.contrib.auth import get_user_model
from django.core import mail as django_mail
from django.core.management import call_command

from exceptions import AccessDenied

from addons.authz.bootstrap import assign_buyer_role
from addons.authz.models import Capability, Role, RoleAssignment, RoleCapability
from addons.authz.services import invalidate_capabilities
from addons.authz_totp.models import TotpSecret
from addons.authz_totp_mail.data import seed as seed_totp_mail
from addons.authz_totp_mail.models.res_users import (
    totp_mail_code,
    verify_totp_mail_code,
)
from addons.base.models import SystemParameter

User = get_user_model()

SEND_URL = '/api/v2/authz/totp-mail/send-code/'
VERIFY_URL = '/api/v2/authz/totp-mail/verify-code/'
INVITE_URL = '/api/v2/authz/totp-mail/invite/'


@pytest.fixture
def user(db):
    seed_totp_mail()
    return User.objects.create_user(
        login='totpmail@kaupamex.mx', password='x')


class TestTotpMailCode:

    def test_codigo_emitido_verifica(self, user):
        code, expiration = totp_mail_code(user)
        assert len(code) == 6
        assert expiration == 3600
        assert verify_totp_mail_code(user, code) is True

    def test_codigo_incorrecto_access_denied(self, user):
        with pytest.raises(AccessDenied):
            verify_totp_mail_code(user, '000001')

    def test_codigo_de_otro_usuario_no_verifica(self, user, db):
        otro = User.objects.create_user(login='otro@kaupamex.mx')
        code, _ = totp_mail_code(otro)
        with pytest.raises(AccessDenied):
            verify_totp_mail_code(user, code)

    def test_endpoint_send_y_verify(self, api_client, user):
        # account.security viaja en los roles sembrados (DEC-ENF-01): el
        # usuario necesita el rol comprador del bootstrap real.
        call_command('seed_authz')
        assign_buyer_role(user)
        invalidate_capabilities(user.id)
        api_client.force_authenticate(user)
        assert len(django_mail.outbox) == 0
        resp = api_client.post(SEND_URL)
        assert resp.status_code == 202, getattr(resp, 'data', resp)
        assert len(django_mail.outbox) == 1
        assert django_mail.outbox[0].to == [user.login]

        code, _ = totp_mail_code(user)
        resp = api_client.post(VERIFY_URL, {'code': code}, format='json')
        assert resp.status_code == 200, resp.data
        resp = api_client.post(VERIFY_URL, {'code': '999999'}, format='json')
        assert resp.status_code == 403
        assert resp.data['codigo_error'] == 'TOTP_MAIL_CODE_INVALID'


class TestPolicy:
    """La política se lee por ``_mfa_type()``, la forma de la fuente.

    Los tres casos medían antes un predicado propio, ``totp_mail_required``,
    retirado en #719 por redundante: su conjunción *"la política lo exige **y**
    no tiene TOTP de app"* es exactamente lo que el ``combine=keep_previous``
    de la cadena calcula. Preguntado así, cada caso ejercita **el mecanismo**
    —los tres eslabones y su precedencia— en vez de una función paralela que
    ningún camino de producción consultaba.
    """

    def test_policy_all_required(self, user):
        SystemParameter.objects.update_or_create(
            key='authz_totp.policy', defaults={'value': 'all_required'})
        assert user._mfa_type() == 'totp_mail'

    def test_policy_apagada(self, user):
        SystemParameter.objects.update_or_create(
            key='authz_totp.policy', defaults={'value': ''})
        assert user._mfa_type() is None

    def test_con_totp_de_app_no_exige_mail(self, user):
        """CONTROL de precedencia — el eslabón interno gana al externo.

        Qué lo haría fallar: encadenar el eslabón de correo sin
        ``keep_previous``. Con el relevo por defecto ganaría el último en
        registrarse, y un usuario con app activa recibiría códigos por correo.
        """
        SystemParameter.objects.update_or_create(
            key='authz_totp.policy', defaults={'value': 'all_required'})
        TotpSecret.objects.create(user=user, secret='S3CRET', confirmed=True)
        assert user._mfa_type() == 'totp'


class TestInvite:

    def test_invita_solo_a_quienes_no_tienen_2fa(self, api_client, user, db):
        call_command('seed_authz')
        admin = User.objects.create_user(
            login='admin-invite@kaupamex.mx', password='x')
        cap = Capability.objects.get(code='permissions.totp_invite')
        role = Role.objects.create(code='r-invite', name='Invita 2FA')
        RoleCapability.objects.create(role=role, capability=cap)
        RoleAssignment.objects.create(user=admin, role=role)
        invalidate_capabilities(admin.id)

        con_2fa = User.objects.create_user(login='ya2fa@kaupamex.mx')
        TotpSecret.objects.create(
            user=con_2fa, secret='S3CRET', confirmed=True)
        # El create anterior dispara la notificación "2FA Activated" (la
        # señal de este addon) — se limpia para asertar solo la invitación.
        assert len(django_mail.outbox) == 1
        assert 'Activated' in django_mail.outbox[0].subject
        django_mail.outbox.clear()

        api_client.force_authenticate(admin)
        resp = api_client.post(INVITE_URL, {
            'user_ids': [user.id, con_2fa.id],
        }, format='json')
        assert resp.status_code == 200, resp.data
        assert len(resp.data['invited']) == 1
        assert len(django_mail.outbox) == 1
        assert django_mail.outbox[0].to == [user.login]

    def test_sin_capacidad_403(self, api_client, user, db):
        call_command('seed_authz')
        alguien = User.objects.create_user(
            login='sin-invite@kaupamex.mx', password='x')
        api_client.force_authenticate(alguien)
        resp = api_client.post(INVITE_URL, {
            'user_ids': [user.id],
        }, format='json')
        assert resp.status_code == 403
