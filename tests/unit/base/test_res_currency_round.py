"""``ResCurrency.round``/``compare_amounts``/``is_zero`` — centralización del
redondeo de divisa (H-API-325, tarea #115).

Fieles a ``odoo19c: res_currency.py:216-261``, con la divergencia declarada
en el docstring del módulo (``Decimal`` en vez de ``float`` — sin el epsilon
de compensación IEEE-754 que la referencia necesita). Estos tests fijan esa
equivalencia: los mismos ejemplos que usa el docstring de la referencia
(0.006 vs 0.002, redondeo a un factor no potencia de diez) dan el mismo
resultado que Odoo documenta.
"""
from decimal import Decimal

import pytest

from addons.base.models import ResCurrency

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture
def mxn():
    return ResCurrency.objects.create(
        name='MXN', full_name='Peso mexicano', symbol='$',
        rounding=Decimal('0.01'))


@pytest.fixture
def chf_like():
    """Divisa con factor de redondeo que NO es potencia de diez (Odoo
    ``float_round(1.3, precision_rounding=.5) == 1.5``, o19: docstring de
    ``float_round``) — el caso que un ``quantize`` fijo a ``decimal_places``
    no puede resolver correctamente."""
    return ResCurrency.objects.create(
        name='CHF', full_name='Franco suizo (redondeo a 0.05)', symbol='Fr',
        rounding=Decimal('0.05'))


class TestRound:
    def test_redondea_a_dos_decimales_half_up(self, mxn):
        assert mxn.round(Decimal('1.432')) == Decimal('1.43')
        assert mxn.round(Decimal('1.431')) == Decimal('1.43')

    def test_empate_se_aleja_de_cero_no_banker(self, mxn):
        # Decimal.ROUND_HALF_EVEN (el default de Python) redondearía 0.005 a
        # 0.00 (par más cercano). El HALF-UP de Odoo lo aleja de 0: 0.01.
        assert mxn.round(Decimal('0.005')) == Decimal('0.01')

    def test_empate_negativo_se_aleja_de_cero(self, mxn):
        assert mxn.round(Decimal('-0.005')) == Decimal('-0.01')

    def test_amount_cero_devuelve_cero(self, mxn):
        assert mxn.round(Decimal('0')) == Decimal('0')

    def test_acepta_str_o_int_convertibles(self, mxn):
        assert mxn.round('1.999') == Decimal('2.00')
        assert mxn.round(2) == Decimal('2.00')

    def test_factor_no_potencia_de_diez(self, chf_like):
        # Odoo: float_round(1.3, precision_rounding=.5) == 1.5 — mismo
        # principio con rounding=0.05: 23.91 redondea a 23.90, no 23.91.
        assert chf_like.round(Decimal('23.91')) == Decimal('23.90')
        assert chf_like.round(Decimal('23.93')) == Decimal('23.95')

    def test_escala_normalizada_a_decimal_places(self, mxn):
        # La división Decimal no preserva por sí sola la escala visible
        # (ver docstring del módulo) — round() la normaliza a decimal_places.
        resultado = mxn.round(Decimal('300'))
        assert resultado == Decimal('300.00')
        assert resultado.as_tuple().exponent == -2

    def test_rounding_cero_no_divide_por_cero(self, mxn):
        mxn.rounding = Decimal('0')
        assert mxn.round(Decimal('12.34')) == Decimal('0')


class TestIsZero:
    def test_amount_menor_que_precision_es_cero(self, mxn):
        assert mxn.is_zero(Decimal('0.004')) is True

    def test_amount_mayor_que_precision_no_es_cero(self, mxn):
        assert mxn.is_zero(Decimal('0.01')) is False

    def test_diferencia_de_montos_cercanos_es_cero(self, mxn):
        # Ejemplo textual de la referencia (o19: is_zero docstring):
        # is_zero(0.006 - 0.002) es True — la diferencia (0.004) redondea a 0.
        assert mxn.is_zero(Decimal('0.006') - Decimal('0.002')) is True


class TestCompareAmounts:
    def test_montos_iguales_a_la_precision(self, mxn):
        assert mxn.compare_amounts(Decimal('1.432'), Decimal('1.431')) == 0

    def test_primero_mayor(self, mxn):
        assert mxn.compare_amounts(Decimal('10.00'), Decimal('9.99')) == 1

    def test_primero_menor(self, mxn):
        assert mxn.compare_amounts(Decimal('9.99'), Decimal('10.00')) == -1

    def test_no_equivale_a_is_zero_de_la_diferencia(self, mxn):
        # Ejemplo textual de la referencia (o19: compare_amounts docstring):
        # 0.006 y 0.002 son "iguales" para is_zero(diff) (ver arriba) pero
        # DISTINTOS para compare_amounts — éste redondea antes de restar,
        # no la diferencia ya calculada.
        a, b = Decimal('0.006'), Decimal('0.002')
        assert mxn.is_zero(a - b) is True
        assert mxn.compare_amounts(a, b) == 1
