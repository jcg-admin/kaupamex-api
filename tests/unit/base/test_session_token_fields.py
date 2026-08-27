"""De que campos depende una sesion viva — ``:829-896``.

Porta ``odoo19c: odoo/addons/base/models/res_users.py`` (LGPL-3):
``_get_session_token_fields``, ``_session_token_get_values`` y
``_session_token_hash_compute``.

El hueco que cierra
-------------------

``get_session_auth_hash`` hmaqueaba **solo** ``self.password`` — el default de
``AbstractBaseUser``. Con eso, archivar una cuenta o renombrar su login dejaba
**vivas** las sesiones abiertas. La referencia las cierra: su token depende de
``{'id', 'login', 'password', 'active'}`` (``:829-830``).

El control que puede fallar
---------------------------

Devolviendo ``{'password'}`` en ``_get_session_token_fields`` —el conjunto de
antes de este pase— la suite pasa de **13 passed** a **6 failed, 7 passed**.
Caen los tres que inspeccionan el conjunto y su forma, y los tres que afirman
que ``active``, ``login`` e ``id`` cierran la sesion. Sobreviven los siete
que miden el calculo —determinismo, filtro de ``None``, secreto alterno— y el
que afirma que un campo de fuera no invalida: ninguno depende de que campos
haya dentro.

Prediccion contra medicion
--------------------------

Este docstring decia «3 caen de 12» y la cifra real fue 5 de 12, con una
sorpresa que valia la pena: ``test_two_users_do_not_share_a_hash`` **no**
discriminaba el ``id``. Django saltea cada hash de contrasena, asi que dos
usuarios con la misma clave ya difieren en ``password`` y el caso pasaba con
el conjunto reducido. La red del ``id`` es
``test_the_id_separates_two_otherwise_identical_users``, escrito despues de
medir, y por eso la cifra final es 6 de 13.
"""
import pytest

from addons.base.models import ResPartner, ResUsers

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

PASSWORD = 'una-clave-larga-y-valida-2026'


def _make_user(login):
    partner = ResPartner.objects.create(name=login, email='')
    user = ResUsers.objects.create(login=login, partner=partner)
    user.set_password(PASSWORD)
    user.save(update_fields=['password'])
    return user


@pytest.fixture
def user(db):
    return _make_user('sesion-uno')


# --------------------------------------------------------------------------
# El conjunto — ≙ :829-830
# --------------------------------------------------------------------------

def test_the_field_set_is_the_reference_one(db):
    """≙ ``_get_session_token_fields`` (``:829-830``) verbatim."""
    assert ResUsers._get_session_token_fields() == {
        'id', 'login', 'password', 'active'}


def test_the_values_come_out_sorted_by_name(user):
    """El ``sorted()`` de la fuente (``:836``) no es cosmetico.

    Sin orden estable el mismo usuario daria hashes distintos entre procesos
    y toda sesion moriria al primer salto de worker.
    """
    nombres = [k for k, __ in user._session_token_get_values()]
    assert nombres == sorted(nombres)
    assert nombres == ['active', 'id', 'login', 'password']


def test_the_id_reads_the_primary_key(user):
    """``id`` es el nombre de la referencia; aqui la columna es ``pk``."""
    valores = dict(user._session_token_get_values())
    assert valores['id'] == user.pk


# --------------------------------------------------------------------------
# Que invalida una sesion — el punto entero del bloque
# --------------------------------------------------------------------------

def test_changing_the_password_invalidates_the_session(user):
    """Lo unico que el default de Django ya cubria."""
    antes = user.get_session_auth_hash()
    user.set_password('otra-clave-igual-de-larga-2026')
    assert user.get_session_auth_hash() != antes


def test_archiving_the_user_invalidates_the_session(user):
    """``active`` esta en el conjunto de la fuente, y por esto.

    Antes de este pase archivar una cuenta dejaba vivas sus sesiones: el hash
    solo miraba la contrasena.
    """
    antes = user.get_session_auth_hash()
    user.active = False
    assert user.get_session_auth_hash() != antes


def test_renaming_the_login_invalidates_the_session(user):
    """``login`` esta en el conjunto: la identidad renombrada no continua."""
    antes = user.get_session_auth_hash()
    user.login = 'sesion-uno-renombrada'
    assert user.get_session_auth_hash() != antes


def test_two_users_do_not_share_a_hash(user):
    """Dos cuentas distintas no comparten hash.

    CAVEAT medido: este caso **no** discrimina la presencia de ``id`` en el
    conjunto. Django saltea cada hash de contrasena, asi que dos usuarios con
    la misma clave en claro ya tienen ``password`` distinto y el caso pasa
    aunque el conjunto sea solo ``{'password'}``. La red del ``id`` la pone
    el caso siguiente, escrito **despues** de medirlo.
    """
    otro = _make_user('sesion-dos')
    otro.set_password(PASSWORD)
    assert user.get_session_auth_hash() != otro.get_session_auth_hash()


def test_the_id_separates_two_otherwise_identical_users(user):
    """``id`` esta en el conjunto, y esto es lo que prueba que hace falta.

    Se igualan los otros tres campos a proposito —mismo hash almacenado,
    mismo login, mismo estado— para que lo unico que quede distinto sea la
    clave primaria. Sin ``id`` en el conjunto, los dos hashes coinciden y una
    sesion valdria para la otra cuenta.
    """
    otro = _make_user('sesion-tres')
    otro.password = user.password
    otro.login = user.login
    otro.active = user.active
    assert user.get_session_auth_hash() != otro.get_session_auth_hash()


def test_an_unrelated_field_does_not_invalidate_the_session(user):
    """El conjunto es cerrado: lo que no esta dentro no cierra sesiones.

    Es la otra mitad del contrato, y la que hace util al punto de extension:
    si cualquier escritura invalidara, extenderlo no significaria nada.
    """
    antes = user.get_session_auth_hash()
    user.partner.name = 'Otro Nombre'
    assert user.get_session_auth_hash() == antes


# --------------------------------------------------------------------------
# El calculo — ≙ :871-884
# --------------------------------------------------------------------------

def test_a_none_value_is_dropped_from_the_key(user):
    """≙ ``:876-878`` — *"To avoid invalidating sessions when installing a new
    feature modifying the session token computation while not still being
    used"*: un campo nuevo y vacio no cierra las sesiones de todo el mundo.
    """
    base = user._session_token_get_values()
    with_new_field = base + (('campo_nuevo', None),)
    assert (ResUsers._session_token_hash_compute(base)
            == ResUsers._session_token_hash_compute(with_new_field))


def test_a_present_value_does_change_the_key(user):
    """La contraparte: en cuanto el campo nuevo tiene valor, si cuenta."""
    base = user._session_token_get_values()
    with_a_value = base + (('campo_nuevo', 'x'),)
    assert (ResUsers._session_token_hash_compute(base)
            != ResUsers._session_token_hash_compute(with_a_value))


def test_the_computation_is_deterministic(user):
    """Dos llamadas seguidas dan el mismo hash — si no, nadie mantiene sesion."""
    assert user.get_session_auth_hash() == user.get_session_auth_hash()


def test_a_different_secret_gives_a_different_hash(user):
    """El eje del legado aqui es el secreto, no la formula.

    Es lo que ``get_session_auth_fallback_hash`` recorre durante una rotacion
    de ``SECRET_KEY``.
    """
    assert (ResUsers._session_token_hash_compute(
                user._session_token_get_values(), secret='otro-secreto')
            != user.get_session_auth_hash())
