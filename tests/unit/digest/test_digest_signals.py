"""Auto-suscripción al digest por defecto de los usuarios internos
(``addons/digest/models/signals.py``, adaptación de
``digest/models/res_users.py`` — odoo-tools@622ddc2a, odoo19c:, LGPL-3).

El disparo es ``base.models.signals.res_users_created``, emitida por
``_create_user`` **después** de aplicar los grupos — el mismo instante en que
``super().create()`` retorna en la referencia. Ver H-API-304.
"""
import pytest

from addons.base.models import ResCompany, ResGroups, ResUsers, SystemParameter
from addons.digest.models import DigestDigest

pytestmark = pytest.mark.django_db


@pytest.fixture
def company():
    return ResCompany.objects.create(code='signals-digest', name='ACME')


@pytest.fixture
def digest(company):
    return DigestDigest.objects.create(name='Digest por defecto', company=company)


@pytest.fixture
def grupo_interno():
    return ResGroups.objects.create(name='Empleado digest', user_type='internal')


@pytest.fixture
def grupo_portal():
    return ResGroups.objects.create(name='Portal digest', user_type='portal')


@pytest.fixture(autouse=True)
def _clear_default_digest_params():
    """Cada test parte sin ``digest.default_digest_*`` fijado — evita que un
    valor sembrado por un test anterior (misma clave en ``SystemParameter``,
    tabla compartida) se filtre entre pruebas."""
    SystemParameter.set_param('digest.default_digest_emails', None)
    SystemParameter.set_param('digest.default_digest_id', None)
    yield
    SystemParameter.set_param('digest.default_digest_emails', None)
    SystemParameter.set_param('digest.default_digest_id', None)


def _configurar(digest):
    SystemParameter.set_param('digest.default_digest_emails', '1')
    SystemParameter.set_param('digest.default_digest_id', str(digest.pk))


class TestAutoSubscribeNewUser:
    def test_noop_when_param_disabled(self, digest, grupo_interno):
        user = ResUsers.objects.create_user(
            login='sin-digest@practicayoruba.mx', group_ids=[grupo_interno])
        assert not digest.user_ids.filter(pk=user.pk).exists()

    def test_noop_when_no_default_digest_configured(self, grupo_interno):
        SystemParameter.set_param('digest.default_digest_emails', '1')
        user = ResUsers.objects.create_user(
            login='sin-default@practicayoruba.mx', group_ids=[grupo_interno])
        # Sin excepción y sin efecto observable — no hay digest a suscribir.
        assert user.pk is not None

    def test_subscribes_internal_user_on_create(self, digest, grupo_interno):
        """El caso de la referencia: el usuario llega con su grupo puesto, y
        la suscripción ocurre **en la creación**, no en un paso posterior."""
        _configurar(digest)
        user = ResUsers.objects.create_user(
            login='nueva@practicayoruba.mx', group_ids=[grupo_interno])

        assert user.share is False, 'con grupo interno el usuario NO es share'
        assert digest.user_ids.filter(pk=user.pk).exists()

    def test_skips_portal_user(self, digest, grupo_portal):
        _configurar(digest)
        user = ResUsers.objects.create_user(
            login='portal@practicayoruba.mx', group_ids=[grupo_portal])

        assert user.share is True
        assert not digest.user_ids.filter(pk=user.pk).exists()

    def test_skips_user_without_groups(self, digest):
        """Sin grupos el usuario es share — la referencia tampoco lo
        suscribiría (``filtered_domain([('share','=',False)])``)."""
        _configurar(digest)
        user = ResUsers.objects.create_user(login='sin-grupo@practicayoruba.mx')

        assert user.share is True
        assert not digest.user_ids.filter(pk=user.pk).exists()


class TestCreateUserAppliesGroups:
    """El contrato que hace posible lo anterior: ``_create_user`` devuelve la
    credencial con sus grupos ya escritos, como ``super().create()`` en la
    referencia (``res_users.py:257`` declara ``group_ids`` como campo)."""

    def test_groups_are_set_when_create_returns(self, grupo_interno):
        user = ResUsers.objects.create_user(
            login='conmigrupo@practicayoruba.mx', group_ids=[grupo_interno])
        assert list(user.group_ids.all()) == [grupo_interno]
        assert user._is_internal() is True

    def test_without_group_ids_user_has_none(self):
        user = ResUsers.objects.create_user(login='pelado@practicayoruba.mx')
        assert list(user.group_ids.all()) == []
