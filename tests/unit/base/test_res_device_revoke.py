"""``ResDevice._revoke`` y la acción que revoca todos los dispositivos.

Porta ``odoo19c: odoo/addons/base/models/res_device.py:182-196`` (``revoke`` /
``_revoke``) y ``odoo19c: odoo/addons/base/models/res_users.py:1021-1031``
(``action_revoke_all_devices`` / ``_action_revoke_all_devices``), LGPL-3.

Qué protege, en palabras de la fuente
--------------------------------------

Revocar un dispositivo son **tres** efectos, no uno: borrar su sesión del
almacén, marcar ``revoked`` en el log —que es donde vive el dato, porque
``res.device`` es una vista de sólo lectura— y, si entre los revocados estaba
el actual, cerrar la sesión en curso (``:194-196``).

Y la acción de «todos» excluye el dispositivo actual
(``devices.filtered(lambda d: not d.is_current)``): si también lo cerrara, el
gesto de expulsar al intruso expulsaría a quien lo pide.

El control que puede fallar
---------------------------

Anulando ``ResDeviceQuerySet._revoke`` —``return 0`` al entrar— la suite pasa
de **9 passed** a **6 failed, 3 passed**. Caen los seis que afirman que algo
**ocurre**: la sesión desaparece del almacén, la fila del log queda marcada,
el retorno cuenta, la sesión en curso se cierra, y los dos de la acción de
«todos».

Sobreviven tres, y conviene saber **por qué cada uno**: dos miden ramas
negativas —recordset vacío y fila sin identificador— y pasan igual con el
método muerto porque afirman que **no** pasa nada; el tercero,
``test_two_devices_sharing_a_session_delete_it_once``, sobrevive porque no
ejercita ``_revoke`` en absoluto: llama directo a
``delete_sessions_from_identifiers``. Mide el ``unique(...)`` de la fuente,
que es otra cosa, y está bien que la mida — lo que no valdría es no saberlo.

*Métrica:* casos que caen al anular ``_revoke``, sobre los 9 del archivo.
*Ciega a:* un almacén de sesiones que no sea el de base de datos. La función
que borra por prefijo lo declara y no borra nada con los otros motores; aquí
se mide el que ``config/settings/base.py:675`` configura.
"""
import pytest

from addons.base.models.res_device import (ResDevice, ResDeviceLog,
                                           delete_sessions_from_identifiers)
from addons.base.models.res_partner import ResPartner
from addons.base.models.res_users import ResUsers
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def _make_user(login):
    partner = ResPartner.objects.create(name=login, email='')
    return ResUsers.objects.create(login=login, partner=partner)


def _make_session():
    """Una sesión real en el almacén, para que el borrado tenga qué borrar."""
    store = SessionStore()
    store['algo'] = 1
    store.create()
    return store.session_key


def _make_log(user, session_key, platform='linux', browser='firefox'):
    return ResDeviceLog.objects.create(
        session_identifier=session_key, platform=platform, browser=browser,
        user_id=user.pk, revoked=False)


class _Request:
    """Lo mínimo que ``_revoke`` mira de la petición: su ``session_key``."""

    def __init__(self, session_key=None):
        self.session = SessionStore(session_key) if session_key else None


def test_an_empty_recordset_revokes_nothing(db):
    """La rama negativa: sin dispositivos no hay identificador que borrar."""
    assert ResDevice.objects.none()._revoke(_Request()) == 0


def test_a_device_without_identifier_is_skipped(db):
    """≙ el ``unique(...)`` de la fuente sobre identificadores reales.

    Una fila sin identificador no designa ninguna sesión: incluirla borraría
    por un prefijo vacío, que casa con **todas**.
    """
    user = _make_user('sin-id@ejemplo.mx')
    _make_log(user, '')
    assert ResDevice.objects.filter(user_id=user.pk)._revoke(_Request()) == 0


def test_revoking_deletes_the_session_from_the_store(db):
    """≙ ``root.session_store.delete_from_identifiers`` (``:188``)."""
    user = _make_user('borra-sesion@ejemplo.mx')
    key = _make_session()
    _make_log(user, key)
    assert Session.objects.filter(session_key=key).exists()
    ResDevice.objects.filter(user_id=user.pk)._revoke(_Request())
    assert not Session.objects.filter(session_key=key).exists()


def test_revoking_marks_the_log_row(db):
    """≙ ``revoked_devices.write({'revoked': True})`` (``:190``)."""
    user = _make_user('marca-log@ejemplo.mx')
    key = _make_session()
    fila = _make_log(user, key)
    ResDevice.objects.filter(user_id=user.pk)._revoke(_Request())
    fila.refresh_from_db()
    assert fila.revoked is True


def test_revoking_returns_how_many_log_rows_it_marked(db):
    """El retorno es el dato que el llamador puede verificar.

    DIVERGENCIA declarada: la fuente no devuelve nada útil —su ``_revoke`` cae
    en ``None``— porque su cliente web recarga la vista y ya.
    """
    user = _make_user('cuenta@ejemplo.mx')
    key = _make_session()
    _make_log(user, key)
    _make_log(user, key, browser='chrome')
    assert ResDevice.objects.filter(user_id=user.pk)._revoke(_Request()) == 2


def test_two_devices_sharing_a_session_delete_it_once(db):
    """≙ ``unique(...)`` (``:187``) — un identificador se borra una vez."""
    user = _make_user('comparten@ejemplo.mx')
    key = _make_session()
    _make_log(user, key, browser='firefox')
    _make_log(user, key, browser='chrome')
    assert delete_sessions_from_identifiers([key, key]) == 1


def test_revoking_the_current_device_logs_the_session_out(db, rf):
    """≙ ``if must_logout: request.session.logout()`` (``:194-196``).

    Es el caso que distingue revocar «los otros» de revocar «todos»: si el
    actual entra en el conjunto, quien pidió la revocación sale con él.
    """
    user = _make_user('cierra-la-mia@ejemplo.mx')
    key = _make_session()
    _make_log(user, key)
    request = rf.get('/')
    request.session = SessionStore(key)
    request.user = user
    ResDevice.objects.filter(user_id=user.pk)._revoke(request)
    assert request.session.session_key != key


def test_revoke_all_devices_spares_the_current_one(db, rf):
    """≙ ``devices.filtered(lambda d: not d.is_current)`` (``:1030``)."""
    user = _make_user('perdona-la-mia@ejemplo.mx')
    actual, otro = _make_session(), _make_session()
    fila_actual = _make_log(user, actual)
    fila_otro = _make_log(user, otro, browser='chrome')
    request = rf.get('/')
    request.session = SessionStore(actual)
    request.user = user

    assert user._action_revoke_all_devices(request) == 1
    fila_actual.refresh_from_db()
    fila_otro.refresh_from_db()
    assert fila_actual.revoked is False
    assert fila_otro.revoked is True


def test_revoke_all_devices_leaves_the_current_session_alive(db, rf):
    """La rama negativa del anterior, sobre el almacén y no sobre el log."""
    user = _make_user('sigue-viva@ejemplo.mx')
    actual, otro = _make_session(), _make_session()
    _make_log(user, actual)
    _make_log(user, otro, browser='chrome')
    request = rf.get('/')
    request.session = SessionStore(actual)
    request.user = user

    user._action_revoke_all_devices(request)
    assert Session.objects.filter(session_key=actual).exists()
    assert not Session.objects.filter(session_key=otro).exists()
