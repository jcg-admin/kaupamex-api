"""``reset_cached_properties`` — el vaciado de las propiedades memorizadas.

≙ ``odoo19c: odoo/tools/func.py:reset_cached_properties``. La consume
``Transaction.reset`` (``odoo19c: odoo/orm/environments.py:610-618``), que tras
reasignar el registro tiene que tirar lo que cada entorno hubiera memorizado
sobre el registro viejo.

El control que discrimina es el caso ``a_plain_attribute_survives``: si el
guion borrara todo ``vars(obj)`` en vez de sólo lo que respalda a una
``functools.cached_property``, ese caso caería. Sin él, un borrado indiscriminado
pasaría igual de verde.
"""
import functools

import pytest

from tools.func import reset_cached_properties


class _Probe:
    """Un objeto con las tres formas que el guion tiene que distinguir."""

    def __init__(self):
        self.calls = 0
        self.plain = 'sin memoria'

    @functools.cached_property
    def memoized(self):
        self.calls += 1
        return self.calls

    @property
    def plain_property(self):
        return 'nunca se memoriza'


class TestResetCachedPropertiesClearsWhatWasMemoized:

    def test_the_memoized_value_is_computed_once(self):
        probe = _Probe()
        assert probe.memoized == 1
        assert probe.memoized == 1
        assert probe.calls == 1

    def test_after_the_reset_it_is_computed_again(self):
        probe = _Probe()
        assert probe.memoized == 1
        reset_cached_properties(probe)
        assert probe.memoized == 2
        assert probe.calls == 2

    def test_it_removes_the_entry_from_the_instance_dict(self):
        probe = _Probe()
        probe.memoized  # noqa: B018 — poblar el respaldo
        assert 'memoized' in vars(probe)
        reset_cached_properties(probe)
        assert 'memoized' not in vars(probe)

    def test_a_plain_attribute_survives(self):
        """El control que discrimina: sólo cae lo que respalda una
        ``cached_property``, no todo ``vars(obj)``."""
        probe = _Probe()
        probe.memoized  # noqa: B018
        reset_cached_properties(probe)
        assert probe.plain == 'sin memoria'
        assert probe.calls == 1

    def test_a_plain_property_is_untouched(self):
        probe = _Probe()
        reset_cached_properties(probe)
        assert probe.plain_property == 'nunca se memoriza'

    def test_resetting_twice_is_a_no_op(self):
        probe = _Probe()
        probe.memoized  # noqa: B018
        reset_cached_properties(probe)
        reset_cached_properties(probe)
        assert probe.memoized == 2

    def test_an_object_without_a_dict_is_refused_like_vars(self):
        """``vars()`` de un objeto con ``__slots__`` levanta ``TypeError``, y
        el guion no lo disimula: la fuente llama a ``vars(obj)`` directo."""

        class _Slotted:
            __slots__ = ('value',)

        with pytest.raises(TypeError):
            reset_cached_properties(_Slotted())
