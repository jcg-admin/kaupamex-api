"""Consumidores del remitente no-reply transaccional L1 (#199,
:ref:`hallazgos-implementar-systemparameter-l2` H-CFG-IMPL-13).

Antes leían ``settings.DEFAULT_FROM_EMAIL`` (``default=`` global cableado al
remitente de una empresa concreta); ahora leen
``CompanySetting.get_setting('notifications.from_email', <neutral>)``:

- ``addons.mail.models.notification_emails._from_email()`` usa la empresa
  **ambiente** (``CompanyContextMiddleware`` la fija desde
  ``request.user.company_id``), así que resuelve al remitente propio de esa
  empresa.
- Los correos de auth disparan PRE-login (sin empresa ambiente) y pasan
  ``company=`` explícito.

El fallback (sin empresa resoluble) es **neutral de plataforma** (Kaupamex, el
operador L0), NO el de una empresa concreta — cada L1 es una entre
potencialmente varias, y su remitente se siembra por bootstrap
(``company_create --setting``), no por constante de código (DEC-3).
"""
import pytest

from orm.environments import company_scope
from addons.base.models import CompanySetting, ResCompany
from addons.mail.models.notification_emails import (
    NOTIFICATIONS_FROM_EMAIL_DEFAULT,
    _from_email,
)

pytestmark = pytest.mark.django_db


class TestNotificationsFromEmail:
    """``addons.mail.models.notification_emails._from_email()`` — empresa ambiente."""

    def test_ambient_company_resolves_its_own_sender(self):
        acme = ResCompany.objects.create(code='acme-from-email', name='Acme')
        CompanySetting.set_setting(
            'notifications.from_email', 'noreply@acme.com', acme)
        with company_scope(acme.pk):
            assert _from_email() == 'noreply@acme.com'

    def test_ambient_company_without_row_falls_to_neutral_platform_default(self):
        # Una empresa sin su fila propia NO hereda la de otra: cae al neutral.
        globex = ResCompany.objects.create(code='globex-from-email', name='Globex')
        with company_scope(globex.pk):
            assert _from_email() == NOTIFICATIONS_FROM_EMAIL_DEFAULT

    def test_no_ambient_company_falls_to_neutral_platform_default(self):
        # Sin ``company_scope`` activo -> get_setting cae al default neutral.
        assert _from_email() == NOTIFICATIONS_FROM_EMAIL_DEFAULT
        assert NOTIFICATIONS_FROM_EMAIL_DEFAULT.endswith('@kaupamex.com')


# ``TestAuthEmailFromEmail`` (3 casos) se retiró aquí: ejercitaba
# ``addons.users.tokens_email.send_password_reset_email`` /
# ``send_verification_email``, que la disolución de ``users`` no portó a ningún
# addon —medido: 0 hits de ambos nombres en ``src/``— y ``IdentityUser``, que
# hoy sólo aparece en prosa (el modelo real es ``ResUsers``). El remitente
# per-company que probaban sigue cubierto por ``TestNotificationsFromEmail``
# desde el lado de ``mail``; lo que falta es el disparo pre-login de auth.
# Ver H-API-252.
