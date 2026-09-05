"""Tests — el aviso al retirar un dispositivo de confianza.

Contrato adaptado de ``odoo19c: auth_totp_mail/models/auth_totp_device.py``
(``Auth_TotpDevice.unlink`` + ``_classify_by_user``, LGPL-3). Docstring de la
fuente, verbatim: *"Notify users when trusted devices are removed from their
account."*

Este archivo existe porque su premisa era falsa. El ``models/__init__.py`` de
``authz_totp_mail`` declaraba el archivo de la referencia como no portable
—``modelo NO portado``— cuando ``AuthTotpDevice`` vive desde
``addons/authz_totp/models/auth_totp.py:121``. La nota fue cierta al escribirse
y caducó cuando el addon hermano portó el modelo, sin que ningún archivo de
éste cambiara. Ver :ref:`h-api-829`.

Los controles que exige el sub-patrón D de ``metrica-decide-la-conclusion.md``
—cada uno declara qué lo haría fallar—:

``test_removing_one_device_alerts_its_owner``
    El control positivo. Qué lo haría fallar: retirar el receptor
    ``notify_device_removed``. Sin él no hay correo y el titular no se entera
    de que alguien le quitó un dispositivo recordado.

``test_revoking_all_devices_sends_one_mail_with_every_name``
    El agrupamiento, que es la mitad del mecanismo y la que un caso de un solo
    dispositivo NO puede ver. Qué lo haría fallar: despachar en ``pre_delete``
    en vez de acumular. ``revoke_all_devices`` borra por *queryset*, así que
    sin agrupar el titular recibiría tres correos donde la fuente manda uno.

``test_each_owner_gets_only_their_own_devices``
    Qué lo haría fallar: acumular en una lista plana en vez de por ``user_id``
    — el defecto que ``_classify_by_user`` existe para impedir. Los nombres del
    vecino son una fuga: dicen qué navegadores usa.

``test_a_rolled_back_removal_does_not_alert``
    La divergencia declarada, medida. Qué lo haría fallar: notificar dentro de
    ``pre_delete`` como hace la fuente. El dispositivo sigue en la tabla y el
    titular ya recibió el aviso de que se lo quitaron.

``test_deleting_the_owner_does_not_try_to_mail_them``
    Qué lo haría fallar: notificar dentro de ``pre_delete``. Con la guarda de
    usuario inexistente retirada **no falla** —medido—, así que este caso NO
    la mide; lo que mide es que la cascada no produzca un aviso. La guarda
    sigue puesta porque el lote sí llega a ``on_commit`` apuntando a una fila
    que ya no está, pero su control positivo no existe todavía: es el
    DESCONOCIDO que el hallazgo declara.

``test_a_rollback_does_not_poison_the_next_removal``
    El caso que ningún otro cubría, y el que destapó un defecto real del
    porte. Qué lo haría fallar: acumular el lote en un ``threading.local`` en
    vez de en la conexión, o no comprobar que el ``on_commit`` siga en pie.
    Django descarta las llamadas de un bloque que revierte pero no toca
    nuestro acumulador; sin la prueba de vida, la retirada siguiente ve un
    lote no vacío, no registra su propio ``on_commit``, y **el aviso no sale**.
    Un fallo silencioso de una notificación de seguridad — ver
    :ref:`h-api-830`.
"""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core import mail as django_mail
from django.utils import timezone

from addons.authz_totp.models.auth_totp import (
    BROWSER_SCOPE, AuthTotpDevice, revoke_all_devices,
)
from addons.authz_totp_mail.data import seed as seed_totp_mail
from orm.environments import sudo, user_scope

User = get_user_model()

pytestmark = pytest.mark.integration

DEVICE_REMOVED_SUBJECT = 'Security Update: Device Removed'
PASSWORD = 'DispositivoRetirado123!'


def _device_alerts():
    """Los correos de la bandeja que son este aviso, y sólo ésos."""
    return [m for m in django_mail.outbox
            if m.subject == DEVICE_REMOVED_SUBJECT]


def _make_user(login, name):
    return User.objects.create_user(login=login, password=PASSWORD, name=name)


def _add_device(user, name):
    """Emite un dispositivo de confianza para ``user`` con el nombre dado."""
    with user_scope(user.pk), sudo():
        AuthTotpDevice._generate(
            BROWSER_SCOPE, name, timezone.now() + timedelta(days=90))
    return AuthTotpDevice.objects.filter(user_id=user.pk, name=name).first()


@pytest.fixture
def owner(db):
    seed_totp_mail()
    user = _make_user('retiro.dispositivo@kaupamex.mx', 'Titular')
    django_mail.outbox.clear()
    return user


def test_removing_one_device_alerts_its_owner(
        owner, django_capture_on_commit_callbacks):
    device = _add_device(owner, 'Firefox on Linux')
    django_mail.outbox.clear()

    with django_capture_on_commit_callbacks(execute=True):
        device.delete()

    avisos = _device_alerts()
    assert len(avisos) == 1, f'se esperaba un aviso, hubo {len(avisos)}'
    assert avisos[0].to == [owner.login]
    assert 'Firefox on Linux' in avisos[0].body


def test_revoking_all_devices_sends_one_mail_with_every_name(
        owner, django_capture_on_commit_callbacks):
    nombres = ['Chrome on Windows', 'Safari on Macos', 'Firefox on Linux']
    for n in nombres:
        _add_device(owner, n)
    django_mail.outbox.clear()

    with django_capture_on_commit_callbacks(execute=True):
        assert revoke_all_devices(owner) == 3

    avisos = _device_alerts()
    assert len(avisos) == 1, (
        f'la fuente agrupa por usuario: un correo, no {len(avisos)}')
    for n in nombres:
        assert n in avisos[0].body, f'falta {n!r} en el aviso agrupado'


def test_each_owner_gets_only_their_own_devices(
        owner, django_capture_on_commit_callbacks):
    vecino = _make_user('vecino.dispositivo@kaupamex.mx', 'Vecino')
    _add_device(owner, 'Chrome on Windows')
    _add_device(vecino, 'Safari on Macos')
    django_mail.outbox.clear()

    with django_capture_on_commit_callbacks(execute=True):
        AuthTotpDevice.objects.all().delete()

    avisos = {m.to[0]: m.body for m in _device_alerts()}
    assert set(avisos) == {owner.login, vecino.login}
    assert 'Chrome on Windows' in avisos[owner.login]
    assert 'Safari on Macos' not in avisos[owner.login]
    assert 'Chrome on Windows' not in avisos[vecino.login]


def test_a_rolled_back_removal_does_not_alert(owner):
    device = _add_device(owner, 'Chrome on Windows')
    # El pk se captura ANTES: ``delete()`` deja ``instance.pk`` en None, así
    # que leerlo después mediría una fila inexistente y el control no
    # discriminaría entre "revirtió" y "el pk se perdió".
    device_pk = device.pk
    django_mail.outbox.clear()

    class _Abortar(Exception):
        pass

    with pytest.raises(_Abortar):
        with transaction.atomic():
            device.delete()
            raise _Abortar

    assert AuthTotpDevice.objects.filter(pk=device_pk).exists(), \
        'el borrado no revirtió: el caso mide otra cosa'
    assert _device_alerts() == [], \
        'la fuente avisa antes del commit; aquí el aviso espera al commit'


def test_deleting_the_owner_does_not_try_to_mail_them(
        owner, django_capture_on_commit_callbacks):
    _add_device(owner, 'Chrome on Windows')
    django_mail.outbox.clear()

    with django_capture_on_commit_callbacks(execute=True):
        owner.delete()

    assert _device_alerts() == [], \
        'no hay a quién avisar: la cascada se llevó al titular'


def test_a_rollback_does_not_poison_the_next_removal(
        owner, django_capture_on_commit_callbacks):
    """Dos transacciones seguidas: la primera revierte, la segunda debe avisar.

    Es el orden exacto que destapó el defecto. Correr cada mitad por separado
    da verde — la primera porque no espera correo, la segunda porque arranca
    con el acumulador limpio. Sólo la secuencia discrimina.
    """
    revertido = _add_device(owner, 'Safari on Macos')
    django_mail.outbox.clear()

    class _Abortar(Exception):
        pass

    with pytest.raises(_Abortar):
        with transaction.atomic():
            revertido.delete()
            raise _Abortar

    # Segunda transacción, retirada de verdad.
    real = _add_device(owner, 'Chrome on Windows')
    with django_capture_on_commit_callbacks(execute=True):
        real.delete()

    avisos = _device_alerts()
    assert len(avisos) == 1, (
        'el lote del rollback dejó sin aviso a la retirada siguiente')
    assert 'Chrome on Windows' in avisos[0].body
    assert 'Safari on Macos' not in avisos[0].body, (
        'el nombre del borrado revertido se coló en el aviso')
