"""Tests — el candado por tiempo llega al cuerpo de sesión que ``web`` produce.

Lo que se mide aquí NO es el cálculo del umbral (eso vive en
``test_res_groups.py``) sino el **registro**: que
``web.controllers.session.build_session_info`` pase por la extensión que
``authz_timeout`` declara al arrancar. Es la mitad que faltaba —las tres
funciones estaban portadas y nadie las llamaba, capacidad muerta.

En la fuente ese paso no existe: ``_inherit = "ir.http"`` mete el método en la
cadena de ``super()`` y corre solo
(``odoo19c: auth_timeout/models/ir_http.py:222-232``). Aquí el productor es una
**función de módulo**, así que la herencia se sustituye por un registro
explícito, y un registro se puede olvidar. Por eso tiene test.

El caso 2 es el control que exige el sub-patrón D de
``metrica-decide-la-conclusion.md``: anula el registro y comprueba que el caso 1
**cae**. Sin él, un verde del caso 1 no distingue «la extensión corre» de «el
cuerpo base ya traía la clave».
"""
import pytest

from addons.authz_timeout.models import ir_http as lock_http
from addons.authz_timeout.models import res_groups as lock_groups
from addons.base.models.res_groups import ResGroups
from addons.web.controllers import session as web_session


@pytest.fixture(autouse=True)
def clean_cache():
    """El umbral se cachea por grupo; cada caso arranca sin residuo."""
    lock_groups._clear_lock_timeouts_cache()
    yield
    lock_groups._clear_lock_timeouts_cache()


def _user_with_threshold(django_user_model, login, minutes=15):
    group = ResGroups.objects.create(
        name=f'Candado {login}', lock_timeout_inactivity=minutes)
    user = django_user_model.objects.create_user(login=login)
    user.group_ids.set([group])
    return user


# === 1. El caso positivo: el registro del addon tiene efecto =============

def test_the_session_body_carries_the_inactivity_threshold(db, django_user_model):
    """Si ``ready()`` registró la extensión, el umbral sale en el cuerpo.

    Cae si alguien retira ``_SESSION_INFO`` de ``AuthzTimeoutConfig``, si el
    bucle que lo consume desaparece de ``ready()``, o si ``build_session_info``
    deja de recorrer sus extensiones.
    """
    user = _user_with_threshold(django_user_model, 'candado@kaupamex.test', 15)

    body = web_session.build_session_info(user)

    assert body['lock_timeout_inactivity'] == 900


# === 2. El control del control — sub-patrón D ===========================

def test_with_the_registry_emptied_the_threshold_disappears(
        db, django_user_model, monkeypatch):
    """Sin extensiones registradas, el caso 1 **tiene que** fallar.

    Es lo que separa «la extensión corre» de «el cuerpo base ya traía la
    clave». Si esta aserción fallara, el caso 1 estaría midiendo otra cosa.
    """
    user = _user_with_threshold(django_user_model, 'control@kaupamex.test', 15)
    monkeypatch.setattr(web_session, '_SESSION_INFO_EXTENSIONS', [])

    body = web_session.build_session_info(user)

    assert 'lock_timeout_inactivity' not in body


# === 3. El cuerpo base sobrevive a la extensión =========================

def test_the_extension_adds_without_dropping_the_base_body(db, django_user_model):
    """Una extensión que devolviera un diccionario nuevo rompería el contrato.

    ``build_session_info`` reasigna el cuerpo con lo que la extensión devuelve,
    así que una extensión descuidada puede tirar lo que había. Las cuatro
    claves base son contrato del cliente
    (``odoo19c: web/controllers/session.py``).
    """
    user = _user_with_threshold(django_user_model, 'base@kaupamex.test', 15)

    body = web_session.build_session_info(user)

    assert body['uid'] == user.pk
    assert body['login'] == user.login
    assert body['name'] == user.partner.name
    assert 'is_system' in body


# === 4. La guarda de la propia extensión ================================

def test_a_user_without_thresholds_gets_no_key(db, django_user_model):
    """≙ ``if timeout := …`` — sin umbral no se emite la clave, no un ``None``.

    Un ``None`` explícito obligaría al cliente a distinguir dos formas de
    «no hay candado»; la fuente omite la clave y aquí igual.
    """
    group = ResGroups.objects.create(name='Sin candado')
    user = django_user_model.objects.create_user(login='sinumbral@kaupamex.test')
    user.group_ids.set([group])

    assert 'lock_timeout_inactivity' not in web_session.build_session_info(user)


# === 5. El registro es idempotente ======================================

def test_registering_twice_does_not_duplicate_the_extension(db):
    """``ready()`` se ejecuta dos veces en algunas configuraciones de Django.

    Un registro que duplicara haría correr la extensión dos veces por cuerpo:
    inocuo hoy —el añadido es idempotente— y no cuando alguien registre una
    extensión que acumule.
    """
    before = list(web_session._SESSION_INFO_EXTENSIONS)
    assert lock_http.session_info in before, (
        'el arranque de la app debe haber registrado session_info')

    lock_http.register_authz_timeout_session_info()

    assert web_session._SESSION_INFO_EXTENSIONS == before
