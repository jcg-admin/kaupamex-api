"""``_assert_can_auth`` / ``_on_login_cooldown`` — el enfriamiento de acceso.

Porta el contrato de ``odoo19c: odoo/addons/base/models/res_users.py:1214-1306``:
tras N fallos consecutivos desde el mismo origen, los intentos se **ignoran**
durante un plazo, y un acierto borra la cuenta.

La suite cubre los dos metodos por separado porque la fuente los separa a
proposito: ``_on_login_cooldown`` es el **criterio** (se sobrescribe para
cambiar la política) y ``_assert_can_auth`` es el **almacen** mas el gesto de
envolver (se sobrescribe para llevar la cuenta a otra parte).

El control que puede fallar
---------------------------

Medido neutralizando la guarda —``_on_login_cooldown`` devolviendo ``False``
siempre— el subconjunto pasa de **13 passed** a **4 failed, 9 passed**. Caen
exactamente los cuatro que afirman que el enfriamiento **ocurre**:

- ``test_at_threshold_within_window_means_cooldown``
- ``test_on_cooldown_the_body_does_not_run``
- ``test_cooldown_does_not_increment_the_count``
- ``test_a_rate_limited_private_ip_warns_about_the_proxy``

Sobreviven nueve, y no es un defecto: miden las ramas **negativas** del
criterio (por debajo del umbral, pasado el plazo, ``after=0``), el contador y
su clave, y el paso libre fuera de peticion. Ninguno de esos nueve seria una
red si la guarda desapareciera — saberlo es exactamente el punto del control.

Prediccion contra medicion: antes de correrlo se escribio aqui «ocho caen,
cuatro sobreviven». La cifra real es 4/9. Se deja anotado porque es el motivo
de que el control exista: la intuicion sobre que mide cada caso no vale como
evidencia. Ver ``metrica-decide-la-conclusion.md`` sub-patron D.
"""
import datetime

import pytest
from django.test import RequestFactory

from addons.base.models import res_users as mod
from addons.base.models.ir_http import set_current_request
from addons.base.models.res_users import ResUsers
from addons.base.models.ir_config_parameter import SystemParameter
from exceptions import AccessDenied

PUBLIC_IP = '203.0.113.7'
PRIVATE_IP = '10.0.0.4'


@pytest.fixture
def counter():
    """El contador es de modulo: cada caso arranca y termina con el vacio."""
    mod._LOGIN_FAILURES.clear()
    yield mod._LOGIN_FAILURES
    mod._LOGIN_FAILURES.clear()


@pytest.fixture
def make_request():
    """Fija la peticion en la ``ContextVar`` y la retira al salir."""
    def _set(ip=PUBLIC_IP):
        request = RequestFactory().get('/', REMOTE_ADDR=ip)
        set_current_request(request)
        return request
    yield _set
    set_current_request(None)


@pytest.fixture
def policy(db):
    """Fija ``base.login_cooldown_after`` / ``_duration`` para el caso."""
    def _set(after=2, duration=60):
        SystemParameter.set_param('base.login_cooldown_after', after)
        SystemParameter.set_param('base.login_cooldown_duration', duration)
    return _set


# --------------------------------------------------------------------------
# _on_login_cooldown — el criterio
# --------------------------------------------------------------------------

def test_no_failures_means_no_cooldown(policy):
    policy(after=2, duration=60)
    assert ResUsers._on_login_cooldown(0, datetime.datetime.min) is False


def test_below_threshold_means_no_cooldown(policy):
    policy(after=3, duration=60)
    ahora = datetime.datetime.now()
    assert ResUsers._on_login_cooldown(2, ahora) is False


def test_at_threshold_within_window_means_cooldown(policy):
    policy(after=3, duration=60)
    ahora = datetime.datetime.now()
    assert ResUsers._on_login_cooldown(3, ahora) is True


def test_cooldown_expires_past_the_window(policy):
    policy(after=3, duration=60)
    viejo = datetime.datetime.now() - datetime.timedelta(seconds=61)
    assert ResUsers._on_login_cooldown(9, viejo) is False


def test_after_zero_disables_the_mechanism(policy):
    """La via documentada por la fuente para apagarlo entero."""
    policy(after=0, duration=60)
    ahora = datetime.datetime.now()
    assert ResUsers._on_login_cooldown(999, ahora) is False


# --------------------------------------------------------------------------
# _assert_can_auth — el almacen y el gesto de envolver
# --------------------------------------------------------------------------

def test_outside_a_request_it_yields(counter):
    """Sin peticion no hay origen que contar: cron y arranque quedan fuera."""
    set_current_request(None)
    entered = False
    with ResUsers._assert_can_auth(user='quien'):
        entered = True
    assert entered is True
    assert counter == {}


def test_a_failure_increments_the_count(counter, make_request, policy):
    policy(after=5, duration=60)
    make_request()
    with pytest.raises(AccessDenied):
        with ResUsers._assert_can_auth(user='quien'):
            raise AccessDenied('credencial invalida')
    failures, at = counter[PUBLIC_IP]
    assert failures == 1
    assert isinstance(at, datetime.datetime)


def test_a_success_clears_the_count(counter, make_request, policy):
    policy(after=5, duration=60)
    make_request()
    counter[PUBLIC_IP] = (3, datetime.datetime.now())
    with ResUsers._assert_can_auth(user='quien'):
        pass
    assert PUBLIC_IP not in counter


def test_on_cooldown_the_body_does_not_run(counter, make_request, policy):
    """Lo que la fuente llama *ignorar* el intento: ni siquiera se evalua."""
    policy(after=2, duration=60)
    make_request()
    counter[PUBLIC_IP] = (2, datetime.datetime.now())
    entered = False
    with pytest.raises(AccessDenied):
        with ResUsers._assert_can_auth(user='quien'):
            entered = True
    assert entered is False


def test_cooldown_does_not_increment_the_count(counter, make_request, policy):
    """Un intento ignorado no cuenta como fallo — si contara, el plazo no
    expiraria nunca mientras alguien siguiera intentando."""
    policy(after=2, duration=60)
    make_request()
    at = datetime.datetime.now()
    counter[PUBLIC_IP] = (2, at)
    with pytest.raises(AccessDenied):
        with ResUsers._assert_can_auth(user='quien'):
            pass
    assert counter[PUBLIC_IP] == (2, at)


def test_the_count_is_per_source(counter, make_request, policy):
    policy(after=2, duration=60)
    make_request(ip=PUBLIC_IP)
    with pytest.raises(AccessDenied):
        with ResUsers._assert_can_auth():
            raise AccessDenied()
    make_request(ip='198.51.100.9')
    with ResUsers._assert_can_auth():
        pass
    assert counter[PUBLIC_IP][0] == 1
    assert '198.51.100.9' not in counter


def test_the_reverse_proxy_wins_over_remote_addr(counter, make_request, policy):
    """``_client_ip`` lee ``X-Forwarded-For`` primero — el contador cuenta al
    cliente, no al proxy."""
    policy(after=5, duration=60)
    request = RequestFactory().get(
        '/', REMOTE_ADDR=PRIVATE_IP, HTTP_X_FORWARDED_FOR=f'{PUBLIC_IP}, 10.0.0.1')
    set_current_request(request)
    with pytest.raises(AccessDenied):
        with ResUsers._assert_can_auth():
            raise AccessDenied()
    assert PUBLIC_IP in counter
    assert PRIVATE_IP not in counter


def test_a_rate_limited_private_ip_warns_about_the_proxy(counter, make_request, policy, caplog):
    """El aviso de la fuente: si la IP limitada es privada, lo mas probable es
    que se este contando al proxy y el limitador castigue a todo el mundo."""
    policy(after=2, duration=60)
    make_request(ip=PRIVATE_IP)
    counter[PRIVATE_IP] = (2, datetime.datetime.now())
    with caplog.at_level('WARNING'):
        with pytest.raises(AccessDenied):
            with ResUsers._assert_can_auth():
                pass
    assert any('privada' in r.message or 'privada' in r.getMessage()
               for r in caplog.records)
