"""Tests — el candado por tiempo estrecha la confianza del dispositivo.

Adaptación de ``odoo19c: auth_timeout/models/auth_totp_device.py``, cuyo cuerpo
entero es una sola pregunta: si el usuario pertenece a un grupo cuyo candado
**absoluto** exige segundo factor, la confianza del dispositivo no puede durar
más que ese candado.

El estrechamiento se cuelga con ``chain_method(..., combine=)`` desde
``AuthzTimeoutConfig.ready()``, así que estos casos miden el modelo **ya
extendido** — que es como corre en producción. La forma de la extensión (relevo
por defecto contra ``combine``) no se afirma aquí: se afirma su consecuencia.

Los controles del sub-patrón D de ``metrica-decide-la-conclusion.md``
=====================================================================

El caso 2 afirma que el umbral MFA gana cuando es más corto. Un verde ahí es
compatible con varias implementaciones equivocadas, así que **la suite se
midió con cada pieza anulada** —no se supuso que discriminaba—. Lo que cayó,
verbatim de la salida:

===================================  ===========================================
Pieza anulada                        Qué cae (de 7 casos)
===================================  ===========================================
``min([age, *ts])`` → ``min(ts)``    **1** — ``…longer_mfa_lock_does_not_stretch…``
comprensión sin el filtro ``if mfa`` **2** — ``…lock_without_mfa_does_not_narrow``
                                     y ``…only_the_mfa_threshold_counts…``
``combine=`` (queda el relevo)       **7** — la suite entera
guarda ``if actor is None``          **1** — ``…without_an_actor…``, con
                                     ``AttributeError``
===================================  ===========================================

Cada control cae por la pieza que dice medir, y **sólo** por ella. La
excepción es ``combine=``, que tumba los siete porque sin él el método
devuelve la lista de umbrales en vez de un número: no es un control fino, es
la diferencia entre el mecanismo y ningún mecanismo.

*Métrica:* casos que fallan al sustituir una pieza por su versión defectuosa,
restaurando el archivo después (``git diff --stat`` vacío).
*Ciega a:* un defecto que las cuatro versiones defectuosas compartan con la
correcta — p. ej. leer el eje de inactividad en vez del absoluto, que ninguna
de las cuatro mutaciones toca.
"""
import pytest
from django.contrib.auth import get_user_model

from addons.authz_timeout.models import res_groups as candado
from addons.authz_totp.models.auth_totp import (
    TRUSTED_DEVICE_AGE_DAYS, AuthTotpDevice)
from addons.base.models.res_groups import ResGroups
from orm.environments import user_scope

User = get_user_model()

pytestmark = pytest.mark.django_db

#: La edad sin estrechar, en segundos — el ``age`` que devuelve la previa.
UNNARROWED_AGE = TRUSTED_DEVICE_AGE_DAYS * 86400

#: 90 días en minutos, que es la unidad de ``lock_timeout``.
AGE_IN_MINUTES = TRUSTED_DEVICE_AGE_DAYS * 24 * 60


@pytest.fixture(autouse=True)
def clean_cache():
    """El candado cachea por grupo; cada caso arranca sin residuo."""
    candado._clear_lock_timeouts_cache()
    yield
    candado._clear_lock_timeouts_cache()


@pytest.fixture
def user():
    return User.objects.create_user(
        login='estrechamiento@practicayoruba.mx',
        password='EstrechaPass123!',
        name='Sujeto del Candado',
    )


def _age_for(user):
    """La edad que ve el usuario — ≙ ``self.env.user`` en la fuente."""
    with user_scope(user.pk):
        return AuthTotpDevice._get_trusted_device_age()


def _group(name, **umbrales):
    return ResGroups.objects.create(name=name, **umbrales)


# === 1. CONTROL — sin candado, la edad sale intacta =====================

def test_a_user_without_lock_thresholds_keeps_the_full_age(user):
    """≙ ``return age`` cuando la lista sale vacía (``:12``).

    Es el control del relevo: si la extensión se hubiera colgado con el relevo
    por defecto de ``chain_method``, una lista vacía —que **no** es ``None``—
    se devolvería tal cual y esto daría ``[]`` en vez de la edad.
    """
    user.group_ids.set([_group('Sin candado')])

    assert _age_for(user) == UNNARROWED_AGE


# === 2. El caso que la fuente existe para cubrir ========================

def test_a_shorter_mfa_lock_narrows_the_trusted_age(user):
    """≙ ``min(age, *user_lock_timeout_mfa)`` (``:13-14``).

    Un candado absoluto de 12 h con MFA obliga a reconfirmar identidad mucho
    antes de que caduquen los 90 días de confianza del navegador. Sin este
    estrechamiento, el dispositivo recordado dejaría pasar un candado que
    existe precisamente para no dejar pasar.
    """
    user.group_ids.set([_group('12h MFA', lock_timeout=720,
                               lock_timeout_mfa=True)])

    assert _age_for(user) == 720 * 60


# === 3. CONTROL — el umbral MFA más largo NO alarga la confianza ========

def test_a_longer_mfa_lock_does_not_stretch_the_trusted_age(user):
    """CONTROL: ``min`` toma la edad, no el umbral.

    Un ``return min(mfa_thresholds)`` —sin incluir ``age``— pasaría el caso 2 y
    fallaría aquí devolviendo un año de confianza. El estrechamiento sólo puede
    acortar.
    """
    one_year_in_minutes = AGE_IN_MINUTES * 4
    user.group_ids.set([_group('Muy largo MFA', lock_timeout=one_year_in_minutes,
                               lock_timeout_mfa=True)])

    assert _age_for(user) == UNNARROWED_AGE


# === 4. CONTROL — un candado SIN MFA no estrecha ========================

def test_a_lock_without_mfa_does_not_narrow(user):
    """CONTROL: ≙ el filtro ``if mfa`` de la comprensión (``:10``).

    Un candado absoluto sin segundo factor se resuelve reintroduciendo la
    contraseña; no invalida lo que el dispositivo ya demostró. Un
    ``min(age, *todos_los_umbrales)`` pasaría los casos 1-3 y fallaría aquí.
    """
    user.group_ids.set([_group('12h sin MFA', lock_timeout=720,
                               lock_timeout_mfa=False)])

    assert _age_for(user) == UNNARROWED_AGE


def test_only_the_mfa_threshold_counts_when_both_are_present(user):
    """Los dos ejes conviven y sólo el que exige MFA estrecha.

    El de 6 h sin MFA es **más corto** que el de 12 h con MFA, así que un
    instrumento que mezclara ambos devolvería 6 h. La respuesta correcta es
    12 h: el eje sin MFA no participa en esta pregunta.
    """
    user.group_ids.set([
        _group('6h sin MFA', lock_timeout=360, lock_timeout_mfa=False),
        _group('12h MFA', lock_timeout=720, lock_timeout_mfa=True),
    ])

    assert _age_for(user) == 720 * 60


# === 5. CONTROL — sin usuario en contexto ===============================

def test_without_an_actor_the_age_is_not_narrowed(user):
    """CONTROL: la extensión lee al actor del contexto, no del modelo.

    Fuera de una petición no hay a quién consultarle sus grupos. La lista sale
    vacía y la edad pasa entera — nunca ``None`` ni una excepción, que es lo
    que un ``get_current_user()`` sin guarda produciría.
    """
    user.group_ids.set([_group('12h MFA', lock_timeout=720,
                               lock_timeout_mfa=True)])

    assert AuthTotpDevice._get_trusted_device_age() == UNNARROWED_AGE


# === 6. El umbral implicado también estrecha ============================

def test_an_implied_group_narrows_too(user):
    """≙ ``all_implied_ids`` — el candado de un grupo base alcanza al derivado."""
    base = _group('Base 1h MFA', lock_timeout=60, lock_timeout_mfa=True)
    derivado = _group('Derivado')
    derivado.implied_ids.add(base)
    user.group_ids.set([derivado])

    assert _age_for(user) == 3600
