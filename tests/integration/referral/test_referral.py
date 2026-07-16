"""
Tests — Referral program (UC-PRO-05)

Subflujo A: el referidor obtiene y comparte su codigo.
Subflujo B: el nuevo comprador usa el codigo (redeem).
Subflujo C: el referidor recibe su recompensa al primer pedido del referido.

Endpoints:
    GET  /api/v2/account/referral/         — codigo + stats del usuario autenticado
    POST /api/v2/account/referral/redeem/  — canjear un codigo referral

Convenciones del proyecto:
    - Clave de error: ``codigo_error`` (no ``error_code``).
    - Identificadores en ingles (DEC-DOC-005).
"""
import re
import pytest
from django.contrib.auth import get_user_model
from apps.modules.users.models import Person
from django.utils import timezone
from datetime import timedelta

from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.modules.orders.models import Order
from apps.modules.settings_app.models import SiteSettings
from apps.modules.referral.models import ReferralCode, Referral
from apps.modules.referral.services import complete_referral_for_order
from apps.modules.voucher.models import Voucher
from tests.factories.user_factory import make_buyer

pytestmark = pytest.mark.integration

REFERRAL_URL = '/api/v2/account/referral/'
REDEEM_URL = '/api/v2/account/referral/redemptions/'

User = get_user_model()


@pytest.fixture
def referral_enabled(db):
    s = SiteSettings.get_or_create_defaults()
    s.referral_active = True
    s.save()
    return s


@pytest.fixture
def referrer(db):
    # Party (T-201): nombre vive en Person; create_user solo toma email+password.
    user = User.objects.create_user(
        email='referrer@practicayoruba.mx',
        password='RefPass123!',
    )
    Person.objects.create(identity=user, first_name='Ref', last_name='Errer')
    # ADR-020: todo usuario validado ES comprador; el referidor accede a
    # /account/referral/ (account.referral). make_buyer refleja producción.
    return make_buyer(user)


@pytest.fixture
def referrer_client(api_client, referrer):
    api_client.force_login(referrer)
    return api_client


# ───────────────────────── Subflujo A — codigo del referidor ─────────────────

class TestReferralCodeGeneration:
    def test_get_creates_unique_code_for_authed_user(self, referrer_client, referrer, referral_enabled):
        res = referrer_client.get(REFERRAL_URL)
        assert res.status_code == 200, res.content
        code = res.data['code']
        # Formato REF-{user.id}-{6 chars en mayusculas}
        assert re.fullmatch(rf'REF-{referrer.id}-[A-Z0-9]{{6}}', code), code
        # Persistido como ReferralCode y como Voucher tipo REFERRAL
        rc = ReferralCode.objects.get(user=referrer)
        assert rc.code == code
        assert Voucher.objects.filter(code=code, voucher_type=Voucher.TYPE_REFERRAL).exists()

    def test_get_is_idempotent_returns_same_code(self, referrer_client, referrer, referral_enabled):
        first = referrer_client.get(REFERRAL_URL).data['code']
        second = referrer_client.get(REFERRAL_URL).data['code']
        assert first == second
        assert ReferralCode.objects.filter(user=referrer).count() == 1

    def test_codes_are_unique_across_users(self, db, referral_enabled):
        u1 = User.objects.create_user(email='u1@x.mx', password='P1ass123!')
        u2 = User.objects.create_user(email='u2@x.mx', password='P2ass123!')
        c1 = ReferralCode.get_or_create_for_user(u1).code
        c2 = ReferralCode.get_or_create_for_user(u2).code
        assert c1 != c2

    def test_get_returns_stats_and_share_link(self, referrer_client, referral_enabled):
        res = referrer_client.get(REFERRAL_URL)
        assert res.status_code == 200
        for key in ('code', 'share_link', 'total_referrals', 'completed_referrals', 'rewards_earned'):
            assert key in res.data, key
        assert res.data['code'] in res.data['share_link']


class TestReferralAuthAndProgramState:
    def test_get_unauthenticated_returns_401(self, api_client, referral_enabled):
        res = api_client.get(REFERRAL_URL)
        assert res.status_code == 401

    def test_get_returns_404_when_program_disabled(self, referrer_client, db):
        s = SiteSettings.get_or_create_defaults()
        s.referral_active = False
        s.save()
        res = referrer_client.get(REFERRAL_URL)
        assert res.status_code == 404
        assert res.data['codigo_error'] == 'NOT_FOUND'


# ───────────────────────── Subflujo B — redeem del referido ──────────────────

class TestReferralRedeem:
    def test_redeem_happy_path_creates_pending_referral_and_welcome_voucher(
        self, db, referral_enabled, referrer
    ):
        rc = ReferralCode.get_or_create_for_user(referrer)
        referee = make_buyer(User.objects.create_user(
            email='referee@x.mx', password='RefeePass123!'))
        client = APIClient()
        client.force_login(referee)

        res = client.post(REDEEM_URL, {'code': rc.code}, format='json')
        assert res.status_code == 201, res.content
        ref = Referral.objects.get(referee=referee)
        assert ref.referrer == referrer
        assert ref.status == Referral.STATUS_PENDING
        # Voucher de bienvenida emitido al referido
        assert Voucher.objects.filter(restricted_to_email=referee.email).exists()

    def test_redeem_self_referral_rejected(self, referrer_client, referrer, referral_enabled):
        rc = ReferralCode.get_or_create_for_user(referrer)
        res = referrer_client.post(REDEEM_URL, {'code': rc.code}, format='json')
        assert res.status_code == 422
        assert res.data['codigo_error'] == 'SELF_REFERRAL_NOT_ALLOWED'

    def test_redeem_unknown_code_returns_404(self, auth_client, referral_enabled):
        res = auth_client.post(REDEEM_URL, {'code': 'REF-9999-ZZZZZZ'}, format='json')
        assert res.status_code == 404
        assert res.data['codigo_error'] == 'NOT_FOUND'

    def test_redeem_inactive_code_rejected(self, db, referral_enabled, referrer):
        rc = ReferralCode.get_or_create_for_user(referrer)
        Voucher.objects.filter(code=rc.code).update(is_active=False)
        referee = make_buyer(User.objects.create_user(email='ref2@x.mx', password='Ref2Pass123!'))
        client = APIClient()
        client.force_login(referee)
        res = client.post(REDEEM_URL, {'code': rc.code}, format='json')
        assert res.status_code == 422
        assert res.data['codigo_error'] == 'VOUCHER_INACTIVE'

    def test_redeem_unauthenticated_returns_401(self, api_client, referral_enabled, referrer):
        rc = ReferralCode.get_or_create_for_user(referrer)
        res = api_client.post(REDEEM_URL, {'code': rc.code}, format='json')
        assert res.status_code == 401

    def test_redeem_missing_code_returns_400(self, auth_client, referral_enabled):
        res = auth_client.post(REDEEM_URL, {}, format='json')
        assert res.status_code == 400
        assert res.data['codigo_error'] == 'INVALID_PAYLOAD'

    def test_redeem_twice_rejected(self, db, referral_enabled, referrer):
        rc = ReferralCode.get_or_create_for_user(referrer)
        referee = make_buyer(User.objects.create_user(email='ref3@x.mx', password='Ref3Pass123!'))
        client = APIClient()
        client.force_login(referee)
        assert client.post(REDEEM_URL, {'code': rc.code}, format='json').status_code == 201
        res = client.post(REDEEM_URL, {'code': rc.code}, format='json')
        assert res.status_code == 409
        assert res.data['codigo_error'] == 'CONFLICT'


# ───────────────────────── Subflujo C — recompensa al referidor ──────────────

class TestReferralReward:
    def _make_referral(self, referrer, referee):
        rc = ReferralCode.get_or_create_for_user(referrer)
        return Referral.objects.create(
            referrer=referrer, referee=referee, code=rc.code,
            status=Referral.STATUS_PENDING,
        )

    def test_first_paid_order_completes_referral_and_rewards_referrer(
        self, db, referral_enabled, referrer
    ):
        referee = User.objects.create_user(email='refc@x.mx', password='RefcPass123!')
        ref = self._make_referral(referrer, referee)
        order = Order.objects.create(user=referee, status=Order.STATUS_PAID)

        complete_referral_for_order(order)

        ref.refresh_from_db()
        assert ref.status == Referral.STATUS_COMPLETED
        # Voucher de recompensa emitido al referidor
        assert Voucher.objects.filter(
            restricted_to_email=referrer.email,
            voucher_type__in=[Voucher.TYPE_FIXED, Voucher.TYPE_PERCENTAGE],
        ).exists()

    def test_unpaid_order_does_not_complete_referral(self, db, referral_enabled, referrer):
        referee = User.objects.create_user(email='refd@x.mx', password='RefdPass123!')
        ref = self._make_referral(referrer, referee)
        order = Order.objects.create(user=referee, status=Order.STATUS_PENDING)

        complete_referral_for_order(order)

        ref.refresh_from_db()
        assert ref.status == Referral.STATUS_PENDING

    def test_completion_is_idempotent(self, db, referral_enabled, referrer):
        referee = User.objects.create_user(email='refe@x.mx', password='RefePass123!')
        ref = self._make_referral(referrer, referee)
        order = Order.objects.create(user=referee, status=Order.STATUS_DELIVERED)

        complete_referral_for_order(order)
        complete_referral_for_order(order)

        ref.refresh_from_db()
        assert ref.status == Referral.STATUS_COMPLETED
        # Solo un voucher de recompensa, no dos
        assert Voucher.objects.filter(restricted_to_email=referrer.email).count() == 1


# ───────────────────── Enforcement — account.referral (DEC-ENF-01) ────────────

class TestReferralCapabilityGate:
    """El programa de referidos es buyer-only: exige ``account.referral``.
    Un usuario autenticado sin la capacidad (no-comprador) recibe 403."""

    def test_get_without_referral_capability_returns_403(self, api_client, referral_enabled):
        outsider = User.objects.create_user(
            email='no_ref@x.mx', password='NoRefPass123!')
        api_client.force_login(outsider)
        res = api_client.get(REFERRAL_URL)
        assert res.status_code == 403

    def test_redeem_without_referral_capability_returns_403(self, api_client, referral_enabled, referrer):
        rc = ReferralCode.get_or_create_for_user(referrer)
        outsider = User.objects.create_user(
            email='no_ref2@x.mx', password='NoRef2Pass123!')
        api_client.force_login(outsider)
        res = api_client.post(REDEEM_URL, {'code': rc.code}, format='json')
        assert res.status_code == 403
