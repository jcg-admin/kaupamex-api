"""Consumidores del remitente no-reply transaccional L1 (#199,
:ref:`hallazgos-implementar-systemparameter-l2` H-CFG-IMPL-13).

Antes leían ``settings.DEFAULT_FROM_EMAIL`` (``default=`` global cableado a
``noreply@practicayoruba.com``); ahora leen
``CompanySetting.get_setting('notifications.from_email', <neutral>)``:

- ``addons.mail.models.notification_emails._from_email()`` usa la empresa **ambiente**
  (``CompanyContextMiddleware`` la fija desde ``request.user.company_id``);
  bajo N=1 los correos de órdenes/envíos disparan en requests autenticados,
  así que resuelve al founder (PracticaYoruba).
- ``addons.users.tokens_email`` pasa ``company=user.company_id`` explícito
  (los correos de auth disparan PRE-login → sin empresa ambiente).

El fallback (sin empresa resoluble) es **neutral de plataforma** (Kaupamex,
``*@kaupamex.com``), NO el valor del founder — PracticaYoruba es solo un
tenant entre potencialmente varios (mismo criterio que contacto/newsletter,
SOL-090 slice 3).
"""
import pytest
from django.core import mail

from addons.platform.context import company_scope
from addons.platform.models import Company, CompanySetting, FOUNDER_L1_SETTINGS
from addons.mail.models.notification_emails import (
    NOTIFICATIONS_FROM_EMAIL_DEFAULT,
    _from_email,
)
from addons.users import tokens_email
from addons.users.models import IdentityUser

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _reseed_founder_settings(db):
    # Reseed idempotente (== migraciones 0006/0007): un test
    # ``transaction=True`` previo (aislamiento multi-DB SOL-091,
    # tests/integration/platform/test_multidb_isolation.py) hace ``flush`` de
    # 'default' sin re-correr la data-migration, dejando ausentes las filas
    # del founder para los tests que corren después — mismo patrón
    # order-dependent que H-CFG-IMPL-09. Restaura el estado que la migración
    # garantiza en producción, sin depender del orden de ejecución.
    founder = Company.get_founder()
    for key, value in FOUNDER_L1_SETTINGS.items():
        CompanySetting.set_setting(key, value, founder)


class TestNotificationsFromEmail:
    """``addons.mail.models.notification_emails._from_email()`` — empresa ambiente."""

    def test_ambient_founder_resolves_seeded_value(self):
        founder = Company.get_founder()
        with company_scope(founder.pk):
            assert _from_email() == 'noreply@practicayoruba.com'

    def test_no_ambient_company_falls_to_neutral_platform_default(self):
        # Sin ``company_scope`` activo -> get_setting cae al default neutral.
        assert _from_email() == NOTIFICATIONS_FROM_EMAIL_DEFAULT
        assert NOTIFICATIONS_FROM_EMAIL_DEFAULT.endswith('@kaupamex.com')
        assert 'practicayoruba' not in NOTIFICATIONS_FROM_EMAIL_DEFAULT


class TestAuthEmailFromEmail:
    """``addons.users.tokens_email`` — ``company=user.company_id`` explícito
    (auth dispara pre-login, sin empresa ambiente)."""

    def _user(self, email, company):
        return IdentityUser.objects.create_user(
            login=email, password='x-Passw0rd', company=company,
        )

    def test_reset_email_from_founder_user_uses_seeded_value(self):
        founder = Company.get_founder()
        user = self._user('reset-l1@practicayoruba.mx', founder)
        mail.outbox = []
        tokens_email.send_password_reset_email(user, 'TOK')
        assert len(mail.outbox) == 1
        assert mail.outbox[0].from_email == 'noreply@practicayoruba.com'

    def test_verify_email_from_founder_user_uses_seeded_value(self):
        founder = Company.get_founder()
        user = self._user('verify-l1@practicayoruba.mx', founder)
        mail.outbox = []
        tokens_email.send_verification_email(user, 'TOK')
        assert len(mail.outbox) == 1
        assert mail.outbox[0].from_email == 'noreply@practicayoruba.com'

    def test_companyless_user_falls_to_neutral_platform_default(self):
        # Usuario sin empresa (pre resolutor subdominio→company) -> fallback
        # neutral de plataforma, no el valor del founder.
        user = self._user('verify-neutral@practicayoruba.mx', None)
        mail.outbox = []
        tokens_email.send_verification_email(user, 'TOK')
        assert len(mail.outbox) == 1
        assert mail.outbox[0].from_email == NOTIFICATIONS_FROM_EMAIL_DEFAULT
