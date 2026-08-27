"""El procedimiento de acceso de ``res.users`` — ``:742-827`` y ``:1177-1191``.

Porta ``odoo19c: odoo/addons/base/models/res_users.py`` (LGPL-3): la familia
``_login`` / ``authenticate`` / ``_check_uid_passwd`` con sus cuatro ayudantes
de busqueda, el barrido de ``res.users.log``, y los tres predicados de
identidad que la fuente resuelve por grupo.

Lo que este pase cierra, y no era divergencia sino hueco
--------------------------------------------------------

``_assert_can_auth`` se porto con la familia de claves de API y hasta hoy solo
tenia consumidor **ahi**: el acceso por contrasena —el que la fuente protege
en ``_login`` (``:766``) y en ``_check_uid_passwd`` (``:822``)— pasaba sin
contar fallos. Es la tarea **#26**, registrada cuando se porto el limitador.

Y ``res.users.log`` existia como tabla sin nadie que escribiera en ella: la
fuente crea una fila por acceso (``_update_last_login``, ``:742-746``) y
recorta el exceso (``_gc_user_logs``, ``:143-152``). Sin las dos mitades, la
tabla era un modelo portado sin mecanismo.

Los controles que pueden fallar
-------------------------------

Cada uno se probo anulando la guarda que dice medir, no leyendo el codigo:

1. **El limitador envuelve el acceso.** Con ``_assert_can_auth`` sustituido
   por un gestor que solo cede el paso, cae
   ``test_repeated_failures_put_the_source_on_cooldown``.
2. **El acceso deja rastro.** Sin la llamada a ``_update_last_login`` cae
   ``test_a_successful_login_records_one_log_row``.
3. **El barrido conserva la ultima.** Sin el ``exclude(pk=Subquery(...))``
   —borrando todo— caen ``test_the_gc_keeps_the_newest_row_per_user`` y
   ``test_the_gc_does_not_touch_another_users_rows``.
4. **El correo se compara entero.** Con ``__icontains`` en vez de
   ``__iexact`` caen ``test_the_email_domain_is_exact_not_a_substring`` y
   ``test_the_email_domain_of_none_matches_nobody``.

Medido: con las cuatro anuladas a la vez la suite pasa de **28 passed** a
**7 failed, 21 passed**. Los que caen son esos siete; los veintiuno que
sobreviven miden otra cosa —los ayudantes de busqueda, los predicados de
identidad, las ramas de rechazo de ``_check_uid_passwd``, las tres de zona
horaria— y saber cuales son es el punto del control.

Prediccion contra medicion, y son dos correcciones
---------------------------------------------------

Antes de correrlo esta cabecera decia «5 caen de 21». Las dos diferencias:

- El limitador hace caer **dos** casos, no uno: sin el, tambien cae
  ``test_a_successful_login_clears_the_failure_count``, porque el ``else``
  que borra la cuenta vive en el mismo gestor de contexto que la cuenta.
- ``test_the_email_domain_does_not_read_wildcards`` **NO discrimina**
  ``__iexact`` de ``__icontains``: ninguno de los dos interpreta ``%``, asi
  que sobrevive a la anulacion. Documenta por que la fuente escapa el valor
  antes de su ``=ilike`` —eso sigue valiendo— pero no es una red para este
  cambio. La red la puso el caso del sufijo, escrito **despues** de medir.
"""
import datetime

import pytest
from django.test import RequestFactory

from addons.base.models import ResPartner, ResUsers
from addons.base.models import res_users as mod
from addons.base.models.ir_http import set_current_request
from addons.base.models.res_users import ResUsersLog
from exceptions import AccessDenied
from orm.utils import SUPERUSER_ID

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

PASSWORD = 'una-clave-larga-y-valida-2026'
PUBLIC_IP = '203.0.113.9'


def _make_user(login, email='', active=True):
    partner = ResPartner.objects.create(name=login, email=email)
    user = ResUsers.objects.create(login=login, partner=partner, active=active)
    user.set_password(PASSWORD)
    user.save(update_fields=['password'])
    return user


@pytest.fixture
def user(db):
    return _make_user('acceso-uno', email='acceso-uno@ejemplo.mx')


@pytest.fixture
def counter():
    mod._LOGIN_FAILURES.clear()
    yield mod._LOGIN_FAILURES
    mod._LOGIN_FAILURES.clear()


@pytest.fixture
def request_in_context():
    def _set(ip=PUBLIC_IP, cookies=None):
        request = RequestFactory().get('/', REMOTE_ADDR=ip)
        request.COOKIES.update(cookies or {})
        set_current_request(request)
        return request
    yield _set
    set_current_request(None)


# --------------------------------------------------------------------------
# Los cuatro ayudantes de busqueda — ≙ :748-758
# --------------------------------------------------------------------------

def test_the_login_domain_finds_the_user_by_its_login(user):
    """≙ ``_get_login_domain`` (``:748-750``)."""
    found = ResUsers.objects.filter(ResUsers._get_login_domain('acceso-uno'))
    assert list(found) == [user]


def test_the_login_domain_is_case_sensitive(user):
    """La fuente usa ``'='``, no ``'=ilike'``: el login distingue mayusculas.

    Es la diferencia deliberada con ``_get_email_domain``, que si es
    insensible. Confundirlas dejaria entrar con ``ACCESO-UNO``.
    """
    assert not ResUsers.objects.filter(
        ResUsers._get_login_domain('ACCESO-UNO')).exists()


def test_the_email_domain_ignores_case(user):
    """≙ ``_get_email_domain`` (``:752-754``) — ``=ilike`` es ``__iexact``."""
    found = ResUsers.objects.filter(
        ResUsers._get_email_domain('ACCESO-UNO@EJEMPLO.MX'))
    assert list(found) == [user]


def test_the_email_domain_does_not_read_wildcards(db):
    """Por que la fuente llama a ``escape_psql`` antes de su ``=ilike``.

    ``ilike`` interpreta ``%`` y ``_``, y un correo puede llevarlos. El
    equivalente exacto es ``__iexact``, que no los interpreta: buscar
    ``a%b@x.mx`` **no** debe encontrar ``azzb@x.mx``.
    """
    _make_user('comodin', email='azzb@ejemplo.mx')
    found = ResUsers.objects.filter(
        ResUsers._get_email_domain('a%b@ejemplo.mx'))
    assert not found.exists()


def test_the_email_domain_of_none_matches_nobody(user):
    """La fuente escribe ``email or ''``: sin correo, no hay a quien buscar."""
    assert not ResUsers.objects.filter(
        ResUsers._get_email_domain(None)).exists()


def test_the_email_domain_is_exact_not_a_substring(user):
    """``=ilike`` compara la cadena **entera**, no un fragmento.

    Este es el caso que discrimina de verdad: el de los comodines de arriba
    sobrevive tanto a ``__iexact`` como a ``__icontains`` —medido— porque
    ninguno de los dos interpreta ``%``. Un sufijo del correo real si separa
    los dos: con ``__iexact`` no encuentra a nadie, con ``__icontains`` si.
    """
    assert not ResUsers.objects.filter(
        ResUsers._get_email_domain('uno@ejemplo.mx')).exists()


def test_the_login_order_is_the_declared_ordering(db):
    """≙ ``_get_login_order`` (``:756-758``) — su ``self._order``.

    Decide **cual** fila autentica cuando el dominio devuelve mas de una.
    """
    assert ResUsers._get_login_order() == ('partner__name', 'login')


# --------------------------------------------------------------------------
# El rastro del acceso — ≙ :742-746 y :143-152
# --------------------------------------------------------------------------

def test_update_last_login_creates_one_row(user):
    """≙ ``_update_last_login`` (``:742-746``) — crea, no actualiza."""
    user._update_last_login()
    user._update_last_login()
    assert ResUsersLog.objects.filter(user=user).count() == 2


def test_the_gc_keeps_the_newest_row_per_user(user):
    """≙ ``_gc_user_logs`` (``:143-152``) — conserva la ultima de cada uno."""
    for __ in range(3):
        user._update_last_login()
    ultima = ResUsersLog.objects.filter(user=user).order_by(
        '-created_at', '-id').first()

    ResUsersLog._gc_user_logs()

    quedan = list(ResUsersLog.objects.filter(user=user))
    assert quedan == [ultima]


def test_the_gc_does_not_touch_another_users_rows(user):
    """El ``EXISTS`` de la fuente esta correlacionado **por usuario**.

    Sin la correlacion el barrido dejaria una sola fila en toda la tabla, no
    una por usuario.
    """
    otro = _make_user('acceso-dos')
    for __ in range(2):
        user._update_last_login()
        otro._update_last_login()

    ResUsersLog._gc_user_logs()

    assert ResUsersLog.objects.filter(user=user).count() == 1
    assert ResUsersLog.objects.filter(user=otro).count() == 1


# --------------------------------------------------------------------------
# _login — ≙ :760-781
# --------------------------------------------------------------------------

def test_a_successful_login_returns_the_uid(user, counter, request_in_context):
    request_in_context()
    auth_info = ResUsers._login(
        {'type': 'password', 'login': 'acceso-uno', 'password': PASSWORD},
        {'interactive': True})
    assert auth_info['uid'] == user.pk
    assert auth_info['user'] == user


def test_a_successful_login_records_one_log_row(user, counter,
                                                request_in_context):
    """El acceso deja rastro: es la mitad de ``res.users.log`` que faltaba."""
    request_in_context()
    ResUsers._login(
        {'type': 'password', 'login': 'acceso-uno', 'password': PASSWORD},
        {'interactive': True})
    assert ResUsersLog.objects.filter(user=user).count() == 1


def test_an_unknown_login_is_denied(db, counter, request_in_context):
    """El usuario inexistente y la credencial mala son el mismo rechazo.

    Separarlos revelaria que logins existen — la fuente levanta el mismo
    ``AccessDenied`` en las dos ramas (``:768`` y el de ``_check_credentials``).
    """
    request_in_context()
    with pytest.raises(AccessDenied):
        ResUsers._login(
            {'type': 'password', 'login': 'no-existe', 'password': PASSWORD},
            {'interactive': True})


def test_a_wrong_password_is_denied(user, counter, request_in_context):
    request_in_context()
    with pytest.raises(AccessDenied):
        ResUsers._login(
            {'type': 'password', 'login': 'acceso-uno', 'password': 'mala'},
            {'interactive': True})


def test_a_failed_login_leaves_no_log_row(user, counter, request_in_context):
    """La fuente registra **despues** de verificar: un fallo no es un acceso."""
    request_in_context()
    with pytest.raises(AccessDenied):
        ResUsers._login(
            {'type': 'password', 'login': 'acceso-uno', 'password': 'mala'},
            {'interactive': True})
    assert not ResUsersLog.objects.filter(user=user).exists()


def test_repeated_failures_put_the_source_on_cooldown(user, counter,
                                                      request_in_context):
    """Cierra la tarea #26: ``_assert_can_auth`` envuelve el acceso.

    Al quinto fallo —el umbral por defecto de ``base.login_cooldown_after``—
    el sexto intento se rechaza **sin llegar a la credencial**, y el mensaje
    lo dice.
    """
    request_in_context()
    credencial = {'type': 'password', 'login': 'acceso-uno',
                  'password': 'mala'}
    for __ in range(5):
        with pytest.raises(AccessDenied):
            ResUsers._login(credencial, {'interactive': True})

    assert counter[PUBLIC_IP][0] == 5
    with pytest.raises(AccessDenied, match='Demasiados intentos'):
        ResUsers._login(
            {'type': 'password', 'login': 'acceso-uno', 'password': PASSWORD},
            {'interactive': True})


def test_a_successful_login_clears_the_failure_count(user, counter,
                                                     request_in_context):
    """El ``else`` de ``_assert_can_auth``: el acierto borra la cuenta."""
    request_in_context()
    with pytest.raises(AccessDenied):
        ResUsers._login(
            {'type': 'password', 'login': 'acceso-uno', 'password': 'mala'},
            {'interactive': True})
    assert PUBLIC_IP in counter

    ResUsers._login(
        {'type': 'password', 'login': 'acceso-uno', 'password': PASSWORD},
        {'interactive': True})
    assert PUBLIC_IP not in counter


def test_the_browser_timezone_is_adopted_on_first_login(user, counter,
                                                        request_in_context):
    """≙ ``:772-775`` — *"first login or missing tz -> set tz to browser tz"*."""
    request_in_context(cookies={'tz': 'America/Mexico_City'})
    ResUsers._login(
        {'type': 'password', 'login': 'acceso-uno', 'password': PASSWORD},
        {'interactive': True})
    user.partner.refresh_from_db()
    assert user.partner.tz == 'America/Mexico_City'


def test_an_invalid_timezone_cookie_is_ignored(user, counter,
                                               request_in_context):
    """La fuente valida contra la base IANA antes de escribir."""
    request_in_context(cookies={'tz': 'Marte/Olympus'})
    ResUsers._login(
        {'type': 'password', 'login': 'acceso-uno', 'password': PASSWORD},
        {'interactive': True})
    user.partner.refresh_from_db()
    assert not user.partner.tz


def test_an_existing_timezone_survives_once_the_user_has_logged_in(
        user, counter, request_in_context):
    """La condicion de la fuente es un **o**: ``not tz or not login_date``.

    Con zona puesta **y** un acceso previo registrado, las dos mitades son
    falsas y la cookie no manda. Es el unico caso en que la zona sobrevive.
    """
    user.partner.tz = 'Europe/Madrid'
    user.partner.save(update_fields=['tz'])
    user._update_last_login()
    request_in_context(cookies={'tz': 'America/Mexico_City'})

    ResUsers._login(
        {'type': 'password', 'login': 'acceso-uno', 'password': PASSWORD},
        {'interactive': True})

    user.partner.refresh_from_db()
    assert user.partner.tz == 'Europe/Madrid'


def test_a_never_logged_user_adopts_the_browser_timezone_anyway(
        user, counter, request_in_context):
    """La otra mitad del **o**, y es facil de leer al reves.

    Con zona puesta pero **sin** acceso previo, la fuente adopta la del
    navegador igualmente: su condicion es ``not user.tz or not
    user.login_date``, no un ``and``. Una zona heredada de una siembra no
    bloquea la primera deteccion real.
    """
    user.partner.tz = 'Europe/Madrid'
    user.partner.save(update_fields=['tz'])
    request_in_context(cookies={'tz': 'America/Mexico_City'})

    ResUsers._login(
        {'type': 'password', 'login': 'acceso-uno', 'password': PASSWORD},
        {'interactive': True})

    user.partner.refresh_from_db()
    assert user.partner.tz == 'America/Mexico_City'


# --------------------------------------------------------------------------
# _check_uid_passwd — ≙ :813-827
# --------------------------------------------------------------------------

def test_an_empty_password_is_denied(user, counter, request_in_context):
    """*"empty passwords disallowed for obvious security reasons"* (``:818``)."""
    request_in_context()
    with pytest.raises(AccessDenied):
        ResUsers._check_uid_passwd(user.pk, '')


def test_an_inactive_user_is_denied(db, counter, request_in_context):
    """≙ ``:823-824`` — el usuario archivado no autentica aunque acierte."""
    inactivo = _make_user('archivado', active=False)
    request_in_context()
    with pytest.raises(AccessDenied):
        ResUsers._check_uid_passwd(inactivo.pk, PASSWORD)


def test_an_unknown_uid_is_denied(db, counter, request_in_context):
    request_in_context()
    with pytest.raises(AccessDenied):
        ResUsers._check_uid_passwd(999999, PASSWORD)


def test_the_right_password_passes(user, counter, request_in_context):
    request_in_context()
    assert ResUsers._check_uid_passwd(user.pk, PASSWORD) is None


# --------------------------------------------------------------------------
# Los tres predicados de identidad — ≙ :1177-1187
# --------------------------------------------------------------------------

def test_the_superuser_is_the_id_not_a_flag(db):
    """≙ ``_is_superuser`` (``:1185-1187``) — ``self.id == SUPERUSER_ID``.

    NO es el ``is_superuser`` de Django: ese flag no existe en este modelo.
    """
    user = _make_user('cualquiera')
    assert user._is_superuser() is False
    assert ResUsers(pk=SUPERUSER_ID)._is_superuser() is True


def test_a_plain_user_is_not_system(user):
    """≙ ``_is_system`` (``:1177-1179``) — pertenencia a ``group_system``."""
    assert user._is_system() is False


def test_the_superuser_is_admin(db):
    """≙ ``_is_admin`` (``:1181-1183``) — el super-usuario **o** el gestor.

    La fuente evalua en ese orden a proposito: ``_is_superuser`` no consulta
    la base, asi que el camino corto no paga una consulta.
    """
    assert ResUsers(pk=SUPERUSER_ID)._is_admin() is True
