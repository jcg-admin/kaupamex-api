"""
Tests unitarios del modelo de credencial — kaupamex-api (party, T-201).

``base.ResUsers`` (Odoo ``res.users``) es la credencial de acceso (login +
password); el nombre humano y el resto de la identidad viven en
``base.ResPartner`` (Odoo ``res.partner``), al que ``ResUsers`` delega por
``partner`` (el ``_inherits`` de la referencia — ver
``addons.base.models.res_users``). ``login`` es el identificador
(``USERNAME_FIELD``).

BD: kaupamex_core_qa
"""
import pytest
from django.contrib.auth import get_user_model

pytestmark = pytest.mark.unit

User = get_user_model()


class TestCredentialCreation:
    """La credencial se crea con login + password (sin username nativo)."""

    def test_create_user_requires_login(self, db):
        with pytest.raises(ValueError):
            User.objects.create_user(login='', password='Pass1234!')

    def test_create_user_with_login(self, db):
        user = User.objects.create_user(
            login='nestor@practicayoruba.mx', password='Pass1234!',
        )
        assert user.pk is not None
        assert user.login == 'nestor@practicayoruba.mx'
        assert user.active is True

    def test_username_field_is_login(self, db):
        assert User.USERNAME_FIELD == 'login'

    def test_create_user_stores_hashed_password(self, db):
        user = User.objects.create_user(
            login='a@practicayoruba.mx', password='Pass1234!',
        )
        assert user.password != 'Pass1234!'
        assert user.check_password('Pass1234!') is True

    def test_str_returns_login(self, db):
        user = User.objects.create_user(
            login='str@practicayoruba.mx', password='Pass1234!',
        )
        assert str(user) == 'str@practicayoruba.mx'

    def test_create_user_creates_partner_when_missing(self, db):
        """El manager crea el partner minimo cuando no se pasa uno
        (Odoo res.users.create, replicado en ResUsersManager._create_user)."""
        user = User.objects.create_user(
            login='sinpartner@practicayoruba.mx', password='Pass1234!',
        )
        assert user.partner_id is not None
        assert user.partner.email == 'sinpartner@practicayoruba.mx'


class TestPartnerDelegation:
    """name/email/phone son propiedades que delegan al partner (_inherits)."""

    def test_name_delegates_to_partner(self, db):
        user = User.objects.create_user(
            login='wp@practicayoruba.mx', password='Pass1234!',
            name='Nestor Garcia',
        )
        assert user.name == 'Nestor Garcia'
        assert user.get_full_name() == 'Nestor Garcia'

    def test_phone_delegates_to_partner(self, db):
        user = User.objects.create_user(
            login='ph@practicayoruba.mx', password='Pass1234!',
        )
        user.partner.phone = '5512345678'
        user.partner.save(update_fields=['phone'])
        assert user.phone == '5512345678'

    def test_email_falls_back_to_login_without_partner_email(self, db):
        """La referencia relaciona ``email`` al del partner (res_users.py:253);
        aqui el login sirve de fallback cuando el partner no trae uno."""
        user = User.objects.create_user(
            login='fallback@practicayoruba.mx', password='Pass1234!',
        )
        user.partner.email = ''
        user.partner.save(update_fields=['email'])
        assert user.email == 'fallback@practicayoruba.mx'

    def test_get_short_name_returns_first_word(self, db):
        user = User.objects.create_user(
            login='short@practicayoruba.mx', password='Pass1234!',
            name='Nestor Garcia',
        )
        assert user.get_short_name() == 'Nestor'


class TestDeactivation:
    """``deactivate(reason)`` — UC-AUTH-13/16, sin homologo en la referencia
    (alli ``active`` es un booleano sin motivo; aqui se conserva la causa)."""

    def test_deactivate_sets_active_false_and_reason(self, db):
        user = User.objects.create_user(
            login='deact@practicayoruba.mx', password='Pass1234!',
        )
        user.deactivate(User.DEACTIVATION_SUSPENDED)
        user.refresh_from_db()
        assert user.active is False
        assert user.deactivated_reason == User.DEACTIVATION_SUSPENDED
        assert user.deactivated_at is not None


class TestModelClassAttributes:
    """Los cinco atributos de clase de ``res.users`` (``odoo19c: :163-167``).

    ``atributos-de-clase-de-modelo.md``: si la clase de la referencia los
    declara, se portan **todos**. Este bloque los lee uno a uno contra la
    fuente y verifica que la forma Django derivada no los contradice.
    """

    def test_the_model_declares_its_name(self):
        """``_name = 'res.users'`` — lo que hace resoluble ``extend_model``."""
        assert User._name == 'res.users'

    def test_the_informal_name_matches_the_source(self):
        """``_description = 'User'`` — convive con ``verbose_name``."""
        assert User._description == 'User'

    def test_the_delegation_to_the_partner_is_declared(self):
        """``_inherits = {'res.partner': 'partner_id'}``.

        El mecanismo ya estaba cableado en ``BaseConfig.ready()``; lo que
        faltaba era la **declaración**, que es de donde el cableado debe leer
        su destino.
        """
        assert User._inherits == {'res.partner': 'partner'}

    def test_the_source_order_is_declared_verbatim(self):
        """``_order = 'name, login'`` — el nombre viene del partner delegado."""
        assert User._order == 'name, login'

    def test_the_model_refuses_privileged_commands(self):
        """``_allow_sudo_commands = False`` — la fuente lo declara explícito."""
        assert User._allow_sudo_commands is False

    def test_the_django_ordering_derives_from_the_source_order(self):
        """``Meta.ordering`` traduce ``'name, login'`` al lookup del delegado.

        ``name`` no es columna de ``res_users``: la fuente lo obtiene del
        partner por ``_inherits``. Aquí eso es ``partner__name``.
        """
        assert User._meta.ordering == ['partner__name', 'login']

    def test_the_table_name_matches_what_the_source_derives_from_name(self):
        """``_table = _name.replace('.', '_')`` (``model_classes.py:266``)."""
        assert User._meta.db_table == 'res_users'
