"""Tests — un código TOTP vale UNA vez, no toda su ventana.

Contrato adaptado de ``odoo19c: auth_totp/models/res_users.py:84-88``, la
segunda guarda de ``_check_credentials``::

    if sudo.totp_last_counter and match <= sudo.totp_last_counter:
        _logger.warning("2FA check: REUSE for %s %r", self, sudo.login)
        raise AccessDenied(_("Verification failed, please use the latest
                             6-digit code"))

El eje NO es *"el código correcto entra"* —eso ya lo medía la suite— sino que
el **mismo** código no entre dos veces. ``TOTP.match`` recorre
``[t-TIMESTEP, t+TIMESTEP]``, así que sin la guarda cada código es un pase
reutilizable durante ~90 s: basta verlo de reojo, leerlo de un registro o
interceptarlo una vez.

Los controles que exige el sub-patrón D de ``metrica-decide-la-conclusion.md``
—cada uno declara qué lo haría fallar—:

``TestReplay.test_the_same_code_does_not_work_twice``
    El caso central. Qué lo haría fallar: retirar la comparación
    ``counter <= row.last_counter`` de ``verify_code``. Ningún otro caso lo
    mide — todos los demás presentan cada código una sola vez.

``TestReplay.test_a_newer_code_still_works_after_one_was_used``
    CONTROL de la dirección contraria, y no es redundante: una guarda escrita
    ``counter != row.last_counter`` —o un simple *"ya usó uno, no más"*—
    pasaría el caso de arriba y **rompería el login legítimo** del minuto
    siguiente. Este caso separa las dos lecturas.

``TestEnrollment.test_the_enrollment_code_cannot_open_the_session``
    Qué lo haría fallar: que ``confirm_setup`` no asiente el contador
    (``:110``). El alta y el primer login ocurren con segundos de diferencia,
    así que caen en la misma ventana: sin asentar, el código que activó el 2FA
    abre además la sesión.

``TestEnrollment.test_a_new_secret_resets_the_counter``
    Qué lo haría fallar: que ``begin_setup`` no reinicie ``last_counter``
    (≙ ``_inverse_token``, ``:228``). **Su primera versión no lo medía**, y se
    midió: retirando esa línea el caso seguía en verde, porque pasaba por un
    ``disable`` que BORRA la fila — la que nacía después traía el ``None`` del
    modelo, así que el verde no distinguía *"la guarda reinicia"* de *"nunca
    hubo nada que reiniciar"*. Es el sub-patrón D de
    ``metrica-decide-la-conclusion.md`` dentro de la propia suite que lo cita.
    Reescrito para que la fila SOBREVIVA con su contador puesto, que es la
    única forma de que el control pueda fallar.

``TestDisable.test_a_reused_code_cannot_turn_2fa_off``
    Qué lo haría fallar: dejar ``disable`` fuera de la guarda. Apagar el 2FA
    es la acción que más protege el segundo factor; aceptar ahí un código ya
    gastado sería el rodeo de todo lo demás.
"""
import base64

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from addons.authz_totp.models import TotpSecret
from addons.authz_totp.models.totp import TIMESTEP, hotp
from addons.authz_totp.services import (
    begin_setup,
    confirm_setup,
    disable,
    verify_code,
)

User = get_user_model()

pytestmark = pytest.mark.integration

PASSWORD = 'CodigoUnaVez123!'


def _code_for(secret, offset=0):
    """El código del intervalo actual desplazado ``offset`` pasos."""
    key = base64.b32decode(secret)
    counter = int(timezone.now().timestamp()) // TIMESTEP + offset
    return f'{hotp(key, counter):06d}'


@pytest.fixture
def enrolled(db):
    """Usuario con 2FA activo; devuelve ``(user, secret)``."""
    user = User.objects.create_user(
        login='codigo.unico@practicayoruba.mx', password=PASSWORD,
        name='Usuario Con Codigo Unico')
    secret, _uri = begin_setup(user)
    # El alta consume el intervalo MÁS VIEJO de la ventana. ``match`` recorre
    # sólo ``[n-1, n+1]`` —tres intervalos—, así que empezar por ``n-1`` deja
    # dos códigos legítimos y crecientes por delante, que es lo que los casos
    # de abajo necesitan para distinguir ``<=`` de ``!=``.
    assert confirm_setup(user, _code_for(secret, offset=-1)), 'el alta falló'
    return user, secret


class TestReplay:
    """≙ la guarda ``match <= totp_last_counter`` (``:84-88``)."""

    def test_the_same_code_does_not_work_twice(self, enrolled):
        """CONTROL — el eje entero de este pase."""
        user, secret = enrolled
        code = _code_for(secret)
        assert verify_code(user, code) is True
        assert verify_code(user, code) is False

    def test_a_newer_code_still_works_after_one_was_used(self, enrolled):
        """CONTROL de la dirección contraria — la guarda es ``<=``, no ``!=``.

        Un usuario legítimo que entra dos veces seguidas presenta códigos
        DISTINTOS y crecientes. Si la guarda los rechazara, el 2FA quedaría
        inservible a partir del primer login.
        """
        user, secret = enrolled
        assert verify_code(user, _code_for(secret)) is True
        assert verify_code(user, _code_for(secret, offset=1)) is True

    def test_an_older_code_of_the_window_does_not_work(self, enrolled):
        """El intervalo anterior sigue dentro de ``match``, y aun así no vale.

        Es la mitad que un anti-repetición por "el último exacto" no cubre: la
        ventana admite el código de hace 30 s, que un atacante pudo capturar
        antes de que el titular usara el suyo.
        """
        user, secret = enrolled
        assert verify_code(user, _code_for(secret, offset=1)) is True
        assert verify_code(user, _code_for(secret, offset=0)) is False
        # y el del alta, dos intervalos atrás, tampoco
        assert verify_code(user, _code_for(secret, offset=-1)) is False


class TestEnrollment:
    """≙ ``_totp_try_setting`` (``:110``) y ``_inverse_token`` (``:228``)."""

    def test_the_enrollment_code_cannot_open_the_session(self, db):
        """CONTROL — el alta asienta su propio contador.

        El código que activa el 2FA cae en la misma ventana que el login que
        viene detrás; sin asentarlo, sirve para las dos cosas.
        """
        user = User.objects.create_user(
            login='alta.y.login@practicayoruba.mx', password=PASSWORD,
            name='Usuario Recien Dado De Alta')
        secret, _uri = begin_setup(user)
        code = _code_for(secret)
        assert confirm_setup(user, code)
        assert verify_code(user, code) is False

    def test_a_new_secret_resets_the_counter(self, db):
        """CONTROL — el contador es del secreto, no del usuario.

        El estado que esta guarda protege **sólo lo construye este caso**, y no
        es un descuido: ``disable`` borra la fila, así que hoy ningún camino de
        producción llega a ``begin_setup`` con un contador puesto. Y aunque
        llegara, ``confirm_setup`` asienta el suyo encima antes de que ningún
        ``verify_code`` lo lea — de modo que el ÚNICO observable del reinicio es
        el campo mismo, entre las dos llamadas. Por eso la aserción es una y no
        dos: una segunda sobre ``confirm_setup`` pasaría con la línea puesta o
        retirada, que es el defecto que este caso acaba de corregir.

        La línea se conserva porque es el porte fiel de ``_inverse_token``
        (``:228``) y porque el día que la fila sobreviva a un cambio de secreto
        —o que ``confirm_setup`` deje de escribir el contador— heredar el umbral
        del secreto retirado rechazaría códigos legítimos del nuevo.
        """
        user = User.objects.create_user(
            login='secreto.nuevo@practicayoruba.mx', password=PASSWORD,
            name='Usuario Que Reinicia Su Secreto')
        begin_setup(user)
        # Un umbral del futuro lejano: si se heredara, ningún código de hoy
        # pasaría la comparación ``counter <= last_counter``.
        TotpSecret.objects.filter(user_id=user.pk).update(last_counter=99_999_999)

        begin_setup(user)   # segunda alta sobre la MISMA fila
        assert TotpSecret.objects.get(user_id=user.pk).last_counter is None


class TestDisable:
    """Apagar el 2FA también confirma identidad — ≙ ``check_identity``."""

    def test_a_reused_code_cannot_turn_2fa_off(self, enrolled):
        """CONTROL — la acción que más protege el segundo factor."""
        user, secret = enrolled
        code = _code_for(secret)
        assert verify_code(user, code) is True
        assert disable(user, code) is False
        assert TotpSecret.objects.filter(user_id=user.pk).exists()

    def test_a_fresh_code_still_turns_2fa_off(self, enrolled):
        """La guarda no rompe el camino legítimo."""
        user, secret = enrolled
        assert disable(user, _code_for(secret)) is True
        assert not TotpSecret.objects.filter(user_id=user.pk).exists()
