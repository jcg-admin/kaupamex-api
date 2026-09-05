"""Tests — el segundo factor tiene freno, y el acierto lo suelta.

Contrato adaptado de ``odoo19c: auth_totp/models/res_users.py:120-152``
(``_totp_rate_limit`` / ``_totp_rate_limit_purge``) y de sus cinco llamadores:
``:76`` y ``:90`` en ``auth_totp``, ``:140``, ``:149-150`` y ``:183`` en
``auth_totp_mail``.

Sin el freno, quien conoce la contraseña puede probar códigos de seis dígitos
sin límite —un millón de combinaciones, y el segundo factor deja de serlo— y
puede pedir correos de código sin límite contra la bandeja del titular. El
freno es lo único que separa esas dos cosas de un ataque viable.

Los controles que exige el sub-patrón D de ``metrica-decide-la-conclusion.md``
—cada uno declara qué lo haría fallar—:

``TestCodeCheck.test_the_sixth_attempt_is_denied_by_the_limiter``
    El eje. Y **no basta con que el sexto intento sea rechazado**: los cinco
    anteriores también lo son, por código inválido. Lo que este caso afirma es
    que el sexto trae el mensaje del limitador y no el de código erróneo, que
    es la única diferencia observable entre *"hay freno"* y *"no lo hay"*.

``TestCodeCheck.test_a_success_gives_the_whole_quota_back``
    Qué lo haría fallar: retirar la purga de ``:90``. Sin ella el usuario
    legítimo que se equivoca cuatro veces y acierta a la quinta arrastra el
    castigo al login siguiente, y a la hora se queda fuera de su propia cuenta.

``TestCodeCheck.test_an_attempt_outside_the_interval_does_not_count``
    Qué lo haría fallar: contar todas las filas en vez de las del intervalo.
    Un limitador sin ventana es un candado permanente tras el quinto error de
    toda la vida de la cuenta.

``TestCodeCheck.test_the_two_counters_are_separate``
    Qué lo haría fallar: contar sin filtrar por ``limit_type``. Cinco correos
    pedidos cerrarían la puerta a verificar el código que traen, que es
    exactamente el flujo que el correo existe para servir.

``TestMailCode.test_the_sixth_send_is_denied_by_the_limiter``
    Qué lo haría fallar: retirar la llamada de ``:183``. Es el otro eje: sin
    ella el endpoint de envío es un generador de correo ilimitado contra
    cualquier cuenta cuyo ``login`` se conozca.

``TestMailCode.test_a_correct_code_purges_both_counters``
    Qué lo haría fallar: purgar sólo ``code_check``. La fuente purga los dos
    (``:149-150``) y la diferencia es real: quien demuestra tener el correo ya
    no necesita que se le racione el envío a ese mismo correo.

``TestSweep.test_the_sweep_keeps_what_still_counts``
    Qué lo haría fallar: un barrido sin filtro de edad. Borraría la fila que
    todavía está dentro de su intervalo y le devolvería al atacante un intento
    que ya gastó — el barrido pasaría a ser el rodeo del limitador.

``TestSendCodeEndpoint.test_the_limiter_answers_403_not_400``
    Qué lo haría fallar: poner el ``except AccessDenied`` **después** del
    ``except UserError``. ``AccessDenied`` hereda de ``UserError``, así que el
    orden inverso lo traga y el agotamiento de cuota sale como *"el envío
    falló"* con 400 — y un cliente que lee eso reintenta, que es justo lo que el
    freno existe para impedir. El caso separa las dos lecturas por su código y
    por su ``codigo_error``.

``TestSweep.test_the_window_covers_the_longest_interval``
    Duplica a propósito la aserción que ``res_users.py`` hace al importar. Sin
    este caso, subir un intervalo por encima del barrido rompe la **colección**
    de la suite entera con un ``AssertionError`` sin contexto; con él, falla un
    caso que dice cuál es el invariante y por qué.
"""
import base64

import pytest
from django.contrib.auth import get_user_model
from django.core import mail as django_mail
from django.core.management import call_command
from django.utils import timezone

from exceptions import AccessDenied

from addons.authz.bootstrap import assign_buyer_role
from addons.authz.services import invalidate_capabilities
from addons.authz_totp.models import AuthTotpRateLimitLog
from addons.authz_totp.models.auth_totp_rate_limit_log import (
    GC_MAX_AGE_SECONDS,
)
from addons.authz_totp.models.res_users import (
    RATE_LIMIT_DESCRIPTIONS, TOTP_RATE_LIMITS,
)
from addons.authz_totp.models.totp import TIMESTEP, hotp
from addons.authz_totp.services import begin_setup, confirm_setup
from addons.authz_totp_mail.data import seed as seed_totp_mail
from addons.authz_totp_mail.models.res_users import (
    _get_totp_mail_code, _send_totp_mail_code,
)

User = get_user_model()

pytestmark = pytest.mark.integration

PASSWORD = 'ConFreno123!'
SEND_CODE = '/api/v2/authz/totp-mail/send-code/'

#: Los dos valores de la fuente, leídos del módulo — no transcritos: una copia
#: en el test convertiría un cambio de política en un verde que no discrimina.
LIMIT_CODE_CHECK, INTERVAL_CODE_CHECK = TOTP_RATE_LIMITS['code_check']
LIMIT_SEND_EMAIL, _INTERVAL_SEND_EMAIL = TOTP_RATE_LIMITS['send_email']


def _code_for(secret, offset=0):
    key = base64.b32decode(secret)
    counter = int(timezone.now().timestamp()) // TIMESTEP + offset
    return f'{hotp(key, counter):06d}'


def _credential(token):
    return {'type': 'totp', 'token': token}


def _wrong_code(secret):
    """Un código que NO casa el secreto, para gastar cuota sin acertar."""
    real = _code_for(secret)
    return '000000' if real != '000000' else '111111'


@pytest.fixture
def enrolled(db):
    """Usuario con 2FA de app confirmado; devuelve ``(user, secret)``."""
    user = User.objects.create_user(
        login='con.freno@kaupamex.mx', password=PASSWORD,
        name='Usuario Con Freno')
    secret, _uri = begin_setup(user)
    assert confirm_setup(user, _code_for(secret, offset=-1)), 'el alta falló'
    return user, secret


def _burn(user, secret, veces):
    """Gasta ``veces`` intentos fallidos de ``code_check``, uno a uno."""
    for _ in range(veces):
        with pytest.raises(AccessDenied):
            user._check_credentials(_credential(_wrong_code(secret)),
                                    {'interactive': True})


class TestCodeCheck:
    """≙ el freno de ``:76`` y la purga de ``:90``."""

    def test_the_sixth_attempt_is_denied_by_the_limiter(self, enrolled):
        """CONTROL — el sexto rechazo es de OTRA naturaleza que los cinco."""
        user, secret = enrolled
        _burn(user, secret, LIMIT_CODE_CHECK)

        with pytest.raises(AccessDenied) as excinfo:
            user._check_credentials(_credential(_wrong_code(secret)),
                                    {'interactive': True})
        assert str(excinfo.value) == RATE_LIMIT_DESCRIPTIONS['code_check']

    def test_the_attempts_below_the_limit_fail_for_the_other_reason(
            self, enrolled):
        """CONTROL de la dirección contraria — el freno no se adelanta.

        Sin él este caso pasaría igual; con un freno demasiado temprano —de
        cuatro, o contando desde cero mal— el quinto intento traería el mensaje
        del limitador y el usuario legítimo perdería un intento que la política
        le concede.
        """
        user, secret = enrolled
        for _ in range(LIMIT_CODE_CHECK):
            with pytest.raises(AccessDenied) as excinfo:
                user._check_credentials(_credential(_wrong_code(secret)),
                                        {'interactive': True})
            assert str(excinfo.value) != RATE_LIMIT_DESCRIPTIONS['code_check']

    def test_a_success_gives_the_whole_quota_back(self, enrolled):
        """≙ ``_totp_rate_limit_purge('code_check')`` (``:90``)."""
        user, secret = enrolled
        _burn(user, secret, LIMIT_CODE_CHECK - 1)

        resultado = user._check_credentials(_credential(_code_for(secret)),
                                            {'interactive': True})
        assert resultado['auth_method'] == 'totp'
        assert AuthTotpRateLimitLog.objects.filter(
            user_id_id=user.pk, limit_type='code_check').count() == 0

        # La cuota entera está de vuelta: los cinco siguientes fallan por
        # código, no por freno.
        for _ in range(LIMIT_CODE_CHECK):
            with pytest.raises(AccessDenied) as excinfo:
                user._check_credentials(_credential(_wrong_code(secret)),
                                        {'interactive': True})
            assert str(excinfo.value) != RATE_LIMIT_DESCRIPTIONS['code_check']

    def test_an_attempt_outside_the_interval_does_not_count(self, enrolled):
        """La ventana es de ``TOTP_RATE_LIMITS``, no «desde siempre»."""
        user, secret = enrolled
        _burn(user, secret, LIMIT_CODE_CHECK)
        # ``created_at`` es ``auto_now_add``: se envejece con UPDATE, que es la
        # única vía que no vuelve a pasar por el default del campo.
        viejo = timezone.now() - timezone.timedelta(
            seconds=INTERVAL_CODE_CHECK + 60)
        AuthTotpRateLimitLog.objects.filter(user_id_id=user.pk).update(
            created_at=viejo)

        with pytest.raises(AccessDenied) as excinfo:
            user._check_credentials(_credential(_wrong_code(secret)),
                                    {'interactive': True})
        assert str(excinfo.value) != RATE_LIMIT_DESCRIPTIONS['code_check']

    def test_the_two_counters_are_separate(self, enrolled):
        """``send_email`` agotado no cierra la puerta a ``code_check``."""
        user, _secret = enrolled
        for _ in range(LIMIT_SEND_EMAIL + 3):
            AuthTotpRateLimitLog.objects.create(
                user_id_id=user.pk, ip='', limit_type='send_email')

        user._totp_rate_limit('code_check')  # no levanta
        assert AuthTotpRateLimitLog.objects.filter(
            user_id_id=user.pk, limit_type='code_check').count() == 1


class TestMailCode:
    """≙ el freno de ``:183`` y la purga doble de ``:149-150``."""

    @pytest.fixture
    def mail_user(self, db):
        seed_totp_mail()
        user = User.objects.create_user(
            login='freno.correo@kaupamex.mx', password=PASSWORD,
            name='Usuario Con Freno De Correo')
        django_mail.outbox.clear()
        return user

    def test_the_sixth_send_is_denied_by_the_limiter(self, mail_user):
        """CONTROL — el envío tiene su propia cuota, y se agota."""
        for _ in range(LIMIT_SEND_EMAIL):
            _send_totp_mail_code(mail_user)
        assert len(django_mail.outbox) == LIMIT_SEND_EMAIL

        with pytest.raises(AccessDenied) as excinfo:
            _send_totp_mail_code(mail_user)
        assert str(excinfo.value) == RATE_LIMIT_DESCRIPTIONS['send_email']
        # Y el sexto correo NO salió: el freno va antes del despacho.
        assert len(django_mail.outbox) == LIMIT_SEND_EMAIL

    def test_a_correct_code_purges_both_counters(self, mail_user):
        """La fuente purga los DOS al acertar, no sólo el que gastó."""
        for _ in range(LIMIT_SEND_EMAIL):
            _send_totp_mail_code(mail_user)
        assert AuthTotpRateLimitLog.objects.filter(
            user_id_id=mail_user.pk, limit_type='send_email').count() == \
            LIMIT_SEND_EMAIL

        code, _expiration = _get_totp_mail_code(mail_user)
        resultado = mail_user._check_credentials(
            {'type': 'totp_mail', 'token': code}, {'interactive': True})
        assert resultado['auth_method'] == 'totp_mail'

        assert AuthTotpRateLimitLog.objects.filter(
            user_id_id=mail_user.pk).count() == 0
        # Y la prueba de que la purga sirve para algo: se puede volver a pedir.
        _send_totp_mail_code(mail_user)


class TestSweep:
    """≙ el barrido que la fuente hereda de ``TransientModel``."""

    def test_the_sweep_keeps_what_still_counts(self, enrolled):
        """CONTROL — el barrido tiene filtro de edad, y discrimina.

        Las dos filas nacen iguales; sólo se envejece una. Un barrido sin
        filtro las borraría las dos y este caso caería.
        """
        user, _secret = enrolled
        vieja = AuthTotpRateLimitLog.objects.create(
            user_id_id=user.pk, ip='', limit_type='code_check')
        reciente = AuthTotpRateLimitLog.objects.create(
            user_id_id=user.pk, ip='', limit_type='code_check')
        AuthTotpRateLimitLog.objects.filter(pk=vieja.pk).update(
            created_at=timezone.now() - timezone.timedelta(
                seconds=GC_MAX_AGE_SECONDS + 60))

        AuthTotpRateLimitLog._gc_rate_limit_log()

        vivas = list(AuthTotpRateLimitLog.objects.values_list('pk', flat=True))
        assert vivas == [reciente.pk]

    def test_the_window_covers_the_longest_interval(self):
        """El barrido nunca puede cortar por debajo de un intervalo vigente."""
        mas_largo = max(interval for _l, interval in TOTP_RATE_LIMITS.values())
        assert GC_MAX_AGE_SECONDS >= mas_largo, (
            'el barrido borraría filas que todavía cuentan, y con ellas los '
            'intentos que el atacante ya gastó'
        )


class TestSendCodeEndpoint:
    """El freno visto desde la superficie HTTP, no desde el modelo."""

    def test_the_limiter_answers_403_not_400(self, api_client, db):
        """CONTROL — el orden de los dos ``except`` de la vista."""
        seed_totp_mail()
        user = User.objects.create_user(
            login='freno.vista@kaupamex.mx', password=PASSWORD,
            name='Usuario Del Endpoint Con Freno')
        # account.security viaja en los roles sembrados (DEC-ENF-01), igual
        # que en ``tests/integration/authz_totp_mail/test_authz_totp_mail.py``.
        call_command('seed_authz')
        assign_buyer_role(user)
        invalidate_capabilities(user.id)
        api_client.force_authenticate(user)

        for _ in range(LIMIT_SEND_EMAIL):
            r = api_client.post(SEND_CODE, {}, format='json')
            assert r.status_code == 202, r.data

        r = api_client.post(SEND_CODE, {}, format='json')
        assert r.status_code == 403, r.data
        assert r.data['codigo_error'] == 'TOTP_RATE_LIMITED'
