"""``res.device.log`` / ``res.device`` — el contrato del registro de dispositivos.

Cubre las tres piezas que la referencia gobierna (``odoo-tools@622ddc2a``):

- ``update_trace`` (``odoo19c: odoo/http.py:1301-1337``) — la traza en sesión,
  su terna de identidad y el umbral de una hora.
- ``_update_device`` (``odoo19c: res_device.py:77-114``) — la fila que se
  inserta, y que **no** se inserta cuando la traza no cambió.
- ``res.device`` (``odoo19c: res_device.py:175-256``) — la vista deja viva sólo
  la última actividad por dispositivo, y esconde las revocadas.
"""
from datetime import timedelta

import pytest
from django.test import RequestFactory
from django.utils import timezone

from addons.base.models.res_device import (
    STORED_SESSION_BYTES,
    TRACE_DISABLE_KEY,
    TRACE_MAX_IDLE_SECONDS,
    TRACE_SESSION_KEY,
    DeviceLogMiddleware,
    ResDevice,
    ResDeviceLog,
    update_trace,
)
from addons.base.models.res_users import ResUsers

UA_CHROME_LINUX = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/120.0 Safari/537.36')
UA_SAFARI_IPHONE = ('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) '
                    'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 '
                    'Mobile/15E148 Safari/604.1')


class _Sesion(dict):
    """Doble de ``request.session``: dict + ``session_key`` + ``modified``."""

    def __init__(self, session_key='a' * 32):
        super().__init__()
        self.session_key = session_key
        self.modified = False


class _Anonimo:
    is_authenticated = False


def _request(ua=UA_CHROME_LINUX, ip='203.0.113.7', usuario=None):
    request = RequestFactory().get('/', HTTP_USER_AGENT=ua, REMOTE_ADDR=ip)
    request.session = _Sesion()
    if usuario is not None:
        request.user = usuario
    return request


@pytest.fixture
def usuario(db):
    return ResUsers.objects.create_user(login='dev@kaupamex.test', password='x')


def _log(usuario, **kwargs):
    datos = dict(session_identifier='s1', platform='linux', browser='chrome',
                 ip_address='203.0.113.7', device_type='computer',
                 user=usuario, revoked=False)
    datos.update(kwargs)
    datos.setdefault('first_activity', datos.get('last_activity'))
    return ResDeviceLog.objects.create(**datos)


# ----------------------------------------------------------------------
# update_trace
# ----------------------------------------------------------------------

def test_primera_peticion_crea_traza():
    request = _request()
    traza = update_trace(request)
    assert traza['platform'] == 'linux' and traza['browser'] == 'chrome'
    assert traza['ip_address'] == '203.0.113.7'
    assert traza['first_activity'] == traza['last_activity']
    assert request.session.modified is True


def test_segunda_peticion_dentro_de_la_hora_no_traza():
    """``if bool(now - last_activity >= 3600)`` — antes de la hora, ``None``."""
    request = _request()
    update_trace(request)
    assert update_trace(request) is None


def test_pasada_la_hora_refresca_y_devuelve_la_misma_traza():
    request = _request()
    primera = update_trace(request)
    request.session[TRACE_SESSION_KEY][0]['last_activity'] -= TRACE_MAX_IDLE_SECONDS
    segunda = update_trace(request)
    assert segunda is not None
    assert segunda['first_activity'] == primera['first_activity']
    assert len(request.session[TRACE_SESSION_KEY]) == 1


def test_otra_terna_es_otro_dispositivo():
    """La identidad es (platform, browser, ip): cambiar uno abre traza nueva."""
    request = _request()
    update_trace(request)
    request.META['HTTP_USER_AGENT'] = UA_SAFARI_IPHONE
    assert update_trace(request) is not None
    assert len(request.session[TRACE_SESSION_KEY]) == 2


def test_trace_disable_apaga_el_registro():
    """Reservado a sesiones técnicas (``odoo19c: odoo/http.py:1305-1313``)."""
    request = _request()
    request.session[TRACE_DISABLE_KEY] = True
    assert update_trace(request) is None


def test_el_proxy_inverso_manda_sobre_remote_addr():
    request = _request()
    request.META['HTTP_X_FORWARDED_FOR'] = '198.51.100.9, 10.0.0.1'
    assert update_trace(request)['ip_address'] == '198.51.100.9'


# ----------------------------------------------------------------------
# _update_device
# ----------------------------------------------------------------------

def test_update_device_inserta_una_fila(usuario):
    fila = ResDeviceLog._update_device(_request(usuario=usuario))
    assert fila.user_id == usuario.pk
    assert (fila.platform, fila.browser) == ('linux', 'chrome')
    assert fila.device_type == ResDeviceLog.DEVICE_COMPUTER
    assert fila.revoked is False


def test_update_device_no_reinserta_dentro_de_la_hora(usuario):
    request = _request(usuario=usuario)
    ResDeviceLog._update_device(request)
    assert ResDeviceLog._update_device(request) is None
    assert ResDeviceLog.objects.filter(user=usuario).count() == 1


def test_movil_se_clasifica_como_movil(usuario):
    """``_is_mobile`` (``odoo19c: res_device.py:70-75``) sobre ``iphone``."""
    fila = ResDeviceLog._update_device(_request(ua=UA_SAFARI_IPHONE, usuario=usuario))
    assert fila.platform == 'iphone'
    assert fila.device_type == ResDeviceLog.DEVICE_MOBILE


def test_solo_se_guarda_el_prefijo_del_identificador_de_sesion(usuario):
    """Nunca el sid completo — ``sid[:STORED_SESSION_BYTES]`` en la fuente."""
    request = _request(usuario=usuario)
    request.session.session_key = 'k' * 90
    fila = ResDeviceLog._update_device(request)
    assert len(fila.session_identifier) == STORED_SESSION_BYTES


def test_middleware_ignora_al_anonimo(db):
    DeviceLogMiddleware(lambda r: 'respuesta')(_request(usuario=_Anonimo()))
    assert ResDeviceLog.objects.count() == 0


def test_middleware_no_rompe_la_respuesta_si_falla_el_trazado(usuario, monkeypatch):
    monkeypatch.setattr(ResDeviceLog, '_update_device',
                        classmethod(lambda cls, request: 1 / 0))
    assert DeviceLogMiddleware(lambda r: 'respuesta')(
        _request(usuario=usuario)) == 'respuesta'


# ----------------------------------------------------------------------
# res.device (la vista)
# ----------------------------------------------------------------------

def test_la_vista_deja_solo_la_ultima_actividad(usuario):
    ahora = timezone.now()
    _log(usuario, last_activity=ahora - timedelta(hours=2))
    reciente = _log(usuario, last_activity=ahora)
    assert ResDeviceLog.objects.filter(user=usuario).count() == 2
    assert [d.pk for d in ResDevice.objects.filter(user_id=usuario.pk)] == [reciente.pk]


def test_la_vista_esconde_las_revocadas(usuario):
    _log(usuario, last_activity=timezone.now(), revoked=True)
    assert ResDevice.objects.filter(user_id=usuario.pk).count() == 0


def test_dos_dispositivos_distintos_son_dos_filas(usuario):
    ahora = timezone.now()
    _log(usuario, last_activity=ahora, session_identifier='s1')
    _log(usuario, last_activity=ahora, session_identifier='s2', platform='iphone')
    assert ResDevice.objects.filter(user_id=usuario.pk).count() == 2


def test_is_current_compara_contra_la_sesion_de_la_peticion(usuario):
    _log(usuario, last_activity=timezone.now(), session_identifier='abc')
    device = ResDevice.objects.get(user_id=usuario.pk)
    request = _request()
    request.session.session_key = 'abcdef' + 'x' * 26
    assert device.is_current(request) is True
    request.session.session_key = 'zzz' + 'x' * 29
    assert device.is_current(request) is False


def test_la_vista_no_la_gestiona_django():
    """``managed = False`` — el análogo de ``_auto = False`` de la fuente."""
    assert ResDevice._meta.managed is False
    assert ResDevice._meta.db_table == 'res_device'
