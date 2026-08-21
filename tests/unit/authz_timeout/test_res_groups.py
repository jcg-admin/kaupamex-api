"""Tests — el candado por tiempo que ``authz_timeout`` cuelga de ``res.groups``.

Adaptación de las aserciones de ``odoo19c: auth_timeout/tests/test_auth_timeout.py``
(``:53-181``), que es donde la referencia fija el contrato de
``_get_lock_timeouts``: el umbral **más corto** entre los grupos implicados, en
**segundos**, separando el que exige MFA del que no.

Los casos 9 y 10 son el par que exige el sub-patrón D de
``metrica-decide-la-conclusion.md``: el 9 afirma que la caché se invalida al
escribir, y el 10 **anula la invalidación** para comprobar que el 9 discrimina.
Sin el 10, un verde del 9 no distingue «la caché se invalida» de «la caché
nunca se usó».
"""
import pytest

from addons.authz_timeout.models import res_groups as candado
from addons.base.models.res_groups import ResGroups


@pytest.fixture(autouse=True)
def cache_limpia():
    """Cada caso arranca sin residuo del anterior."""
    candado._clear_lock_timeouts_cache()
    yield
    candado._clear_lock_timeouts_cache()


def _grupo(name, **umbrales):
    return ResGroups.objects.create(name=name, **umbrales)


def _timeouts(*grupos):
    return ResGroups._get_lock_timeouts([g.pk for g in grupos])


# === 1. Las dos funciones puras, sin base de datos =======================

@pytest.mark.parametrize('minutes,expected', [
    (0, (0, 'minutes')),
    (None, (None, 'minutes')),
    (45, (45, 'minutes')),
    (120, (2, 'hours')),
    (1440, (1, 'days')),
    (2880, (2, 'days')),
    (90, (90, 'minutes')),      # no divide exacto en horas
])
def test_human_readable_delay_picks_the_coarsest_exact_unit(minutes, expected):
    assert candado.human_readable_delay(minutes) == expected


@pytest.mark.parametrize('delay,unit,expected', [
    (30, 'minutes', 30),
    (2, 'hours', 120),
    (3, 'days', 4320),
])
def test_human_readable_delay_to_minutes_is_the_inverse(delay, unit, expected):
    assert candado.human_readable_delay_to_minutes(delay, unit) == expected


# === 2-7. El contrato de _get_lock_timeouts ==============================

def test_a_group_without_thresholds_reports_both_axes_empty(db):
    grupo = _grupo('Sin candado')
    assert _timeouts(grupo) == {
        'lock_timeout': [],
        'lock_timeout_inactivity': [],
    }


def test_a_threshold_without_mfa_comes_out_in_seconds(db):
    grupo = _grupo('Un día', lock_timeout=1440, lock_timeout_mfa=False)
    assert _timeouts(grupo)['lock_timeout'] == [(86400, False)]


def test_a_threshold_with_mfa_carries_its_flag(db):
    grupo = _grupo('Un día con MFA', lock_timeout=1440, lock_timeout_mfa=True)
    assert _timeouts(grupo)['lock_timeout'] == [(86400, True)]


def test_the_longer_non_mfa_threshold_is_dropped(db):
    """≙ la rama ``not min_mfa or min_non_mfa < min_mfa`` (``:229``).

    Un umbral sin MFA más largo que el que sí lo exige no aporta nada: el
    corto ya obliga antes, y con más exigencia.
    """
    corto_mfa = _grupo('12h MFA', lock_timeout=720, lock_timeout_mfa=True)
    largo_sin = _grupo('24h', lock_timeout=1440, lock_timeout_mfa=False)
    assert _timeouts(corto_mfa, largo_sin)['lock_timeout'] == [(43200, True)]


def test_the_shorter_non_mfa_threshold_survives_next_to_the_mfa_one(db):
    """≙ el ejemplo del docstring de la fuente (``:216-219``)."""
    corto_sin = _grupo('12h', lock_timeout=720, lock_timeout_mfa=False)
    largo_mfa = _grupo('24h MFA', lock_timeout=1440, lock_timeout_mfa=True)
    assert _timeouts(corto_sin, largo_mfa)['lock_timeout'] == [
        (43200, False), (86400, True),
    ]


def test_the_two_axes_are_independent(db):
    grupo = _grupo(
        'Ambos ejes',
        lock_timeout=1440, lock_timeout_mfa=True,
        lock_timeout_inactivity=15, lock_timeout_inactivity_mfa=False)
    assert _timeouts(grupo) == {
        'lock_timeout': [(86400, True)],
        'lock_timeout_inactivity': [(900, False)],
    }


def test_an_implied_group_contributes_its_threshold(db):
    """≙ ``self.with_context({}).all_implied_ids`` (``:227``).

    El umbral del grupo implicado cuenta aunque el usuario sólo pertenezca al
    que lo implica — es lo que hace que un candado puesto en un grupo base
    alcance a todos los que lo heredan.
    """
    base = _grupo('Base con candado', lock_timeout=60, lock_timeout_mfa=False)
    derivado = _grupo('Derivado')
    derivado.implied_ids.add(base)
    assert _timeouts(derivado)['lock_timeout'] == [(3600, False)]


# === 8. La lectura desde el usuario ======================================

def test_the_user_reads_the_shortest_inactivity_threshold(db, django_user_model):
    corto = _grupo('5 min', lock_timeout_inactivity=5)
    largo = _grupo('30 min', lock_timeout_inactivity=30)
    user = django_user_model.objects.create_user(login='candado@kaupamex.test')
    user.group_ids.set([corto, largo])

    assert user._get_lock_timeout_inactivity() == 300


def test_a_user_without_thresholds_gets_none(db, django_user_model):
    user = django_user_model.objects.create_user(login='sincandado@kaupamex.test')
    user.group_ids.set([_grupo('Sin candado')])

    assert user._get_lock_timeout_inactivity() is None


# === 9 y 10. La caché, y el control de que el control discrimina =========

def test_writing_a_threshold_invalidates_the_cache(db):
    """Control positivo: el segundo cálculo ve el valor nuevo, no el cacheado."""
    grupo = _grupo('Mutable', lock_timeout=1440)
    assert _timeouts(grupo)['lock_timeout'] == [(86400, False)]

    grupo.lock_timeout = 60
    grupo.save()

    assert _timeouts(grupo)['lock_timeout'] == [(3600, False)]


def test_with_the_invalidation_annulled_the_stale_value_survives(db, monkeypatch):
    """El control del control — sub-patrón D de ``metrica-decide-la-conclusion``.

    Con ``_clear_lock_timeouts_cache`` convertido en un no-op, el caso anterior
    **tiene que** fallar. Si no fallara, su verde no estaría midiendo la
    invalidación sino la ausencia de caché.
    """
    grupo = _grupo('Mutable', lock_timeout=1440)
    assert _timeouts(grupo)['lock_timeout'] == [(86400, False)]

    monkeypatch.setattr(candado, '_clear_lock_timeouts_cache', lambda: None)
    grupo.lock_timeout = 60
    grupo.save()

    # El valor viejo sobrevive: la caché es real y su invalidación es lo que
    # el caso anterior mide.
    assert _timeouts(grupo)['lock_timeout'] == [(86400, False)]


def test_update_fields_narrows_the_invalidation_like_the_source(db):
    """≙ el predicado ``any(field in vals …)`` de ``write`` (``:182``).

    Guardar un campo ajeno al candado no invalida: es la divergencia 2 del
    docstring del módulo, y su mitad conservadora se mide en el caso de
    arriba (sin ``update_fields`` se invalida siempre).
    """
    grupo = _grupo('Mutable', lock_timeout=1440)
    assert _timeouts(grupo)['lock_timeout'] == [(86400, False)]

    grupo.name = 'Renombrado'
    grupo.save(update_fields=['name'])

    assert candado._LOCK_TIMEOUTS_CACHE, 'un campo ajeno no debe vaciar la caché'


def test_deleting_a_group_with_a_threshold_invalidates(db):
    grupo = _grupo('Efímero', lock_timeout=1440)
    otro = _grupo('Permanente', lock_timeout=60)
    _timeouts(grupo, otro)
    assert candado._LOCK_TIMEOUTS_CACHE

    grupo.delete()

    assert not candado._LOCK_TIMEOUTS_CACHE


# === 11. Los onchange ====================================================

def test_turning_the_absolute_lock_on_sets_a_day_and_demands_mfa(db):
    """≙ ``_onchange_has_lock_timeout`` (``:136-144``) — 1440 y MFA."""
    grupo = _grupo('Nuevo')
    grupo._onchange_has_lock_timeout(True)
    assert (grupo.lock_timeout, grupo.lock_timeout_mfa) == (1440, True)

    grupo._onchange_has_lock_timeout(False)
    assert (grupo.lock_timeout, grupo.lock_timeout_mfa) == (0, False)


def test_turning_the_inactivity_lock_on_sets_15_minutes_without_mfa(db):
    """≙ ``_onchange_has_lock_timeout_inactivity`` (``:154-161``).

    La asimetría con el candado absoluto es de la fuente, no nuestra: 15
    minutos y **sin** MFA.
    """
    grupo = _grupo('Nuevo')
    grupo._onchange_has_lock_timeout_inactivity(True)
    assert (grupo.lock_timeout_inactivity,
            grupo.lock_timeout_inactivity_mfa) == (15, False)


def test_the_delay_onchange_writes_minutes_from_the_readable_pair(db):
    grupo = _grupo('Nuevo')
    grupo._onchange_lock_timeout_delay_unit(3, 'hours')
    assert grupo.lock_timeout == 180

    grupo._onchange_lock_timeout_inactivity_delay_unit(2, 'days')
    assert grupo.lock_timeout_inactivity == 2880


# === 12. Las ocho propiedades y los dos inversos =========================

def test_the_technical_properties_read_through_to_the_stored_columns(db):
    grupo = _grupo(
        'Con candado',
        lock_timeout=2880, lock_timeout_mfa=True,
        lock_timeout_inactivity=90, lock_timeout_inactivity_mfa=False)

    assert grupo.has_lock_timeout is True
    assert (grupo.lock_timeout_delay_in_unit,
            grupo.lock_timeout_delay_unit) == (2, 'days')
    assert grupo.lock_timeout_2fa_selection == 'with_2fa'

    assert grupo.has_lock_timeout_inactivity is True
    assert (grupo.lock_timeout_inactivity_delay_in_unit,
            grupo.lock_timeout_inactivity_delay_unit) == (90, 'minutes')
    assert grupo.lock_timeout_inactivity_2fa_selection == 'without_2fa'


def test_the_properties_of_a_group_without_thresholds_report_absence(db):
    grupo = _grupo('Sin candado')
    assert grupo.has_lock_timeout is False
    assert grupo.has_lock_timeout_inactivity is False
    assert grupo.lock_timeout_2fa_selection == 'without_2fa'


def test_the_two_inverses_write_the_stored_flag(db):
    grupo = _grupo('Nuevo')

    grupo._inverse_lock_timeout_2fa_selection('with_2fa')
    assert grupo.lock_timeout_mfa is True
    grupo._inverse_lock_timeout_2fa_selection('without_2fa')
    assert grupo.lock_timeout_mfa is False

    grupo._inverse_lock_timeout_inactivity_2fa_selection('with_2fa')
    assert grupo.lock_timeout_inactivity_mfa is True
