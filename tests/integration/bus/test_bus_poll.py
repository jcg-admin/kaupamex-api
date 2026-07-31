"""Integration — ``GET /api/v2/bus/poll`` (T-077, DEC-AF-06).

Verifica las tres propiedades que hacen del endpoint una sustitución válida del
transporte de la referencia:

1. Está gateado por capacidad (DEC-11, fail-closed), no por ``IsAuthenticated``.
2. El canal se deriva de la sesión — un usuario **no** puede leer el de otro,
   aunque lo intente por query string.
3. El cursor ``last`` avanza, de modo que el sondeo no relee lo ya entregado.
"""
import pytest
from addons.authz.models import Role, RoleAssignment
from addons.authz.services import invalidate_capabilities
from addons.bus.models import BusMessage
from addons.bus.services import user_channel
from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.test import APIClient

pytestmark = pytest.mark.integration

User = get_user_model()
POLL_URL = '/api/v2/bus/poll/'


def _con_rol(email):
    rol, _ = Role.objects.get_or_create(code='lector-bus', defaults={'name': 'Lector bus'})
    call_command('seed_authz')
    u = User.objects.create_user(email=email, password='BusPass123!')
    RoleAssignment.objects.create(user=u, role=rol)
    invalidate_capabilities(u.id)
    cliente = APIClient()
    cliente.force_authenticate(u)
    return u, cliente


def test_sin_rol_el_candado_aplica(db):
    call_command('seed_authz')
    u = User.objects.create_user(email='sinrol@e.com', password='BusPass123!')
    cliente = APIClient()
    cliente.force_authenticate(u)

    assert cliente.get(POLL_URL).status_code == 403


def test_con_la_capacidad_devuelve_su_canal(db):
    u, cliente = _con_rol('lector@e.com')
    BusMessage.sendone(user_channel(u), 'notificacion', {'texto': 'hola'})

    r = cliente.get(POLL_URL)

    assert r.status_code == 200
    assert [n['message']['payload']['texto'] for n in r.data['notifications']] == ['hola']


def test_no_puede_leer_el_canal_de_otro(db):
    u, cliente = _con_rol('propio@e.com')
    otro = User.objects.create_user(email='otro@e.com', password='BusPass123!')
    BusMessage.sendone(user_channel(otro), 'notificacion', {'texto': 'ajeno'})

    # Aunque intente pedirlo explícitamente: el canal no se toma del query string.
    r = cliente.get(POLL_URL, {'channel': user_channel(otro)})

    assert r.status_code == 200
    assert r.data['notifications'] == []


def test_el_cursor_avanza_y_no_reentrega(db):
    u, cliente = _con_rol('cursor@e.com')
    BusMessage.sendone(user_channel(u), 'notificacion', {'n': 1})

    primera = cliente.get(POLL_URL)
    corte = primera.data['last']
    segunda = cliente.get(POLL_URL, {'last': corte})

    assert [n['message']['payload']['n'] for n in primera.data['notifications']] == [1]
    assert segunda.data['notifications'] == []
    assert segunda.data['last'] == corte


def test_last_no_numerico_es_400_con_codigo_error(db):
    _, cliente = _con_rol('malcursor@e.com')

    r = cliente.get(POLL_URL, {'last': 'abc'})

    assert r.status_code == 400
    assert r.data['codigo_error'] == 'INVALID_LAST'
