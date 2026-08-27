"""Los cuatro símbolos que le faltaban al porte de ``res_device.py``.

Porta ``odoo19c: odoo/addons/base/models/res_device.py`` (LGPL-3):
``_compute_linked_ip_addresses`` (``:50-63``), ``_order_field_to_sql``
(``:65-68``), ``_gc_device_log`` (``:117-135``) y ``__update_revoked``
(``:138-169``). Tarea #71.

Qué protege, en palabras de la fuente
--------------------------------------

Los cuatro responden preguntas distintas sobre el mismo log:

- **desde cuántas IP** se usó el mismo dispositivo — se agrupa por
  (sesión, plataforma, navegador) y se agregan las IP, deduplicadas y en
  orden de aparición (la fuente usa ``OrderedSet``);
- **cuál es el dispositivo actual** — se empuja arriba comparando el prefijo
  de la sesión en curso, en SQL y no en Python;
- **qué filas sobran** — toda fila superada por otra más reciente del mismo
  (sesión, plataforma, navegador, IP);
- **qué sesiones ya no existen** — las que el almacén no tiene, que pasan a
  ``revoked``.

El control que puede fallar
---------------------------

Se anula cada símbolo por separado y se mide qué cae. La predicción se
escribe antes de correrlo y se corrige contra la medición, no al revés.
Resultado y supervivientes, en el hallazgo H-API-814.

*Métrica:* casos de este archivo, contra PostgreSQL real con el almacén de
sesiones de base de datos.
*Ciega a:* un almacén de sesiones que no sea el de base de datos — los dos
símbolos que consultan el almacén lo declaran y no responden con los otros
motores; y al plan real de la consulta de orden, que mide el orden devuelto
y no qué índice eligió el planificador.
"""
import datetime

import pytest

from addons.base.models.res_device import (ResDevice, ResDeviceLog,
                                           get_missing_session_identifiers)
from addons.base.models.res_partner import ResPartner
from addons.base.models.res_users import ResUsers
from django.contrib.sessions.backends.db import SessionStore
from django.utils import timezone

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def _make_user(login):
    partner = ResPartner.objects.create(name=login, email='')
    return ResUsers.objects.create(login=login, partner=partner)


def _make_session():
    store = SessionStore()
    store['algo'] = 1
    store.create()
    return store.session_key


def _make_log(user, session_key, ip='10.0.0.1', platform='linux',
              browser='firefox', last_activity=None, revoked=False):
    return ResDeviceLog.objects.create(
        session_identifier=session_key, platform=platform, browser=browser,
        ip_address=ip, user_id=user.pk, revoked=revoked,
        last_activity=last_activity or timezone.now(),
    )


class _Request:
    def __init__(self, session_key=None):
        self.session = SessionStore(session_key) if session_key else None


# ----------------------------------------------------------------------
# _compute_linked_ip_addresses (:50-63)
# ----------------------------------------------------------------------

def test_linked_ip_addresses_lists_every_ip_of_the_same_device(db):
    """≙ ``_compute_linked_ip_addresses`` — el agregado por dispositivo."""
    user = _make_user('dos-ips@ejemplo.mx')
    key = _make_session()
    _make_log(user, key, ip='10.0.0.1')
    _make_log(user, key, ip='10.0.0.2')

    device = ResDevice.objects.filter(user_id=user.pk).first()
    assert device._compute_linked_ip_addresses().split('\n') == \
        ['10.0.0.1', '10.0.0.2']


def test_linked_ip_addresses_deduplicates_keeping_order(db):
    """≙ el ``OrderedSet`` de la fuente (``:60``): una IP aparece una vez."""
    user = _make_user('ip-repetida@ejemplo.mx')
    key = _make_session()
    _make_log(user, key, ip='10.0.0.1')
    _make_log(user, key, ip='10.0.0.2')
    _make_log(user, key, ip='10.0.0.1')

    device = ResDevice.objects.filter(user_id=user.pk).first()
    assert device._compute_linked_ip_addresses().split('\n') == \
        ['10.0.0.1', '10.0.0.2']


def test_linked_ip_addresses_does_not_mix_two_browsers(db):
    """La clave de agrupación es la terna, no sólo la sesión (``:56``)."""
    user = _make_user('dos-navegadores@ejemplo.mx')
    key = _make_session()
    _make_log(user, key, ip='10.0.0.1', browser='firefox')
    _make_log(user, key, ip='10.0.0.9', browser='chrome')

    firefox = ResDevice.objects.filter(user_id=user.pk, browser='firefox').first()
    assert firefox._compute_linked_ip_addresses() == '10.0.0.1'


# ----------------------------------------------------------------------
# _order_field_to_sql (:65-68)
# ----------------------------------------------------------------------

def test_the_current_device_is_ordered_first(db):
    """≙ ``session_identifier = %s DESC`` (``:67``).

    El dispositivo actual va arriba aunque su actividad sea **más vieja** —
    que es lo que distingue este orden del ``last_activity desc`` por defecto.
    """
    user = _make_user('orden-actual@ejemplo.mx')
    current = _make_session()
    other = _make_session()
    yesterday = timezone.now() - datetime.timedelta(days=1)
    _make_log(user, other, ip='10.0.0.9')
    _make_log(user, current, ip='10.0.0.1', last_activity=yesterday)

    ordered = list(ResDevice.objects.filter(user_id=user.pk)
                   .order_by_is_current(_Request(current)))
    assert ordered[0].session_identifier == current[:42]


def test_without_a_session_the_default_order_stands(db):
    """Sin sesión en curso no hay a quién empujar: manda ``last_activity``."""
    user = _make_user('orden-sin-sesion@ejemplo.mx')
    yesterday = timezone.now() - datetime.timedelta(days=1)
    older = _make_session()
    newer = _make_session()
    _make_log(user, older, ip='10.0.0.1', last_activity=yesterday)
    _make_log(user, newer, ip='10.0.0.9')

    ordered = list(ResDevice.objects.filter(user_id=user.pk)
                   .order_by_is_current(_Request()))
    assert ordered[0].session_identifier == newer[:42]


# ----------------------------------------------------------------------
# _gc_device_log (:117-135)
# ----------------------------------------------------------------------

def test_gc_keeps_only_the_latest_row_of_each_device(db):
    """≙ el ``DELETE ... USING`` de la fuente (``:120-128``)."""
    user = _make_user('gc-una-fila@ejemplo.mx')
    key = _make_session()
    yesterday = timezone.now() - datetime.timedelta(days=1)
    old_row = _make_log(user, key, ip='10.0.0.1', last_activity=yesterday)
    new_row = _make_log(user, key, ip='10.0.0.1')

    ResDeviceLog._gc_device_log()

    alive = list(ResDeviceLog.objects.filter(session_identifier=key)
                 .values_list('pk', flat=True))
    assert alive == [new_row.pk]
    assert old_row.pk not in alive


def test_gc_does_not_touch_a_different_ip(db):
    """La IP entra en la clave (``:126``): otra IP es otro dispositivo."""
    user = _make_user('gc-otra-ip@ejemplo.mx')
    key = _make_session()
    yesterday = timezone.now() - datetime.timedelta(days=1)
    other_ip = _make_log(user, key, ip='10.0.0.2', last_activity=yesterday)
    _make_log(user, key, ip='10.0.0.1')

    ResDeviceLog._gc_device_log()

    assert ResDeviceLog.objects.filter(pk=other_ip.pk).exists()


def test_gc_keeps_the_last_row_even_if_revoked(db):
    """«Keep the last device log» de la fuente (``:118-119``), literal."""
    user = _make_user('gc-revocada@ejemplo.mx')
    key = _make_session()
    only_row = _make_log(user, key, ip='10.0.0.1', revoked=True)

    ResDeviceLog._gc_device_log()

    assert ResDeviceLog.objects.filter(pk=only_row.pk).exists()


# ----------------------------------------------------------------------
# get_missing_session_identifiers + __update_revoked (:138-169)
# ----------------------------------------------------------------------

def test_missing_identifiers_reports_only_the_dead_ones(db):
    """≙ ``get_missing_session_identifiers`` (``odoo19c: http.py:1099``)."""
    alive = _make_session()
    dead = 'x' * 42
    missing = get_missing_session_identifiers({alive[:42], dead})
    assert missing == {dead}


def test_update_revoked_marks_the_row_whose_session_is_gone(db):
    """≙ ``__update_revoked`` (``:138-169``): el log sigue al almacén."""
    user = _make_user('revoca-muerta@ejemplo.mx')
    long_ago = timezone.now() - datetime.timedelta(days=30)
    row = _make_log(user, 'y' * 42, last_activity=long_ago)

    ResDeviceLog._ResDeviceLog__update_revoked()

    row.refresh_from_db()
    assert row.revoked is True


def test_update_revoked_leaves_a_live_session_alone(db):
    """La otra mitad: una sesión que sí existe no se revoca."""
    user = _make_user('revoca-viva@ejemplo.mx')
    key = _make_session()
    long_ago = timezone.now() - datetime.timedelta(days=30)
    row = _make_log(user, key, last_activity=long_ago)

    ResDeviceLog._ResDeviceLog__update_revoked()

    row.refresh_from_db()
    assert row.revoked is False


def test_update_revoked_ignores_recent_activity(db):
    """El umbral de inactividad de la fuente (``:150``): lo reciente no se toca."""
    user = _make_user('revoca-reciente@ejemplo.mx')
    row = _make_log(user, 'z' * 42)

    ResDeviceLog._ResDeviceLog__update_revoked()

    row.refresh_from_db()
    assert row.revoked is False
