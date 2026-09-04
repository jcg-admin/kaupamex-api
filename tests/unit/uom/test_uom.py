"""Contrato de ``Uom`` (``uom.uom``) — puerto del addon ``uom`` de la
referencia, T-060 de la iniciativa ``alinear-arbol-addons-a-familias-odoo``.

Los cuatro primeros casos son la traducción directa de
``uom/tests/test_uom.py`` de la referencia (``test_10_conversion``,
``test_20_rounding``, ``test_30_quantity``): mismos números, mismas unidades.
Los últimos verifican las dos restricciones del modelo
(``uom/models/uom_uom.py:47-50`` y ``:97-101``) y el cálculo de ``factor``
recursivo (``:69-75``).

Toca DB → django_db.
"""
import pytest

from addons.base.models import DecimalPrecision
from addons.uom.models import Uom
from exceptions import UserError

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture
def precision_product_unit():
    """``decimal.precision`` "Product Unit" — la que usa ``uom`` para redondear."""
    obj, _ = DecimalPrecision.objects.get_or_create(
        name='Product Unit', defaults={'digits': 2},
    )
    obj.digits = 2
    obj.save()
    return obj


@pytest.fixture
def unidades(precision_product_unit):
    """Las unidades del seed de la referencia (``uom/data/uom_data.xml``)."""
    gram = Uom.objects.create(name='g', relative_factor=1.0)
    kgm = Uom.objects.create(name='kg', relative_factor=1000, relative_uom_id=gram)
    ton = Uom.objects.create(name='Ton', relative_factor=1000, relative_uom_id=kgm)
    unit = Uom.objects.create(name='Units', relative_factor=1.0)
    dozen = Uom.objects.create(name='Dozens', relative_factor=12, relative_uom_id=unit)
    return {
        'gram': gram, 'kgm': kgm, 'ton': ton, 'unit': unit, 'dozen': dozen,
    }


# --- Conversión (referencia: test_10_conversion) ---------------------------

def test_conversion_gramo_a_tonelada(unidades):
    assert unidades['gram'].compute_quantity(1020000, unidades['ton']) == 1.02


def test_conversion_de_precio_gramo_a_tonelada(unidades):
    assert unidades['gram'].compute_price(2, unidades['ton']) == 2000000.0


def test_docena_a_unidad_no_arrastra_error_de_precision(unidades):
    """1 docena son 12 unidades exactas.

    Si el factor se guardara con precisión insuficiente daría 12.0000000000047
    y el redondeo lo subiría a 13 — la regresión que la referencia documenta.
    """
    assert unidades['dozen'].compute_quantity(1, unidades['unit']) == 12.0


def test_gramo_a_kilogramo_redondea_a_la_precision_del_destino(unidades):
    assert unidades['gram'].compute_quantity(1234, unidades['kgm']) == 1.24


# --- Redondeo (referencia: test_20_rounding) -------------------------------

def test_redondea_hacia_arriba_con_cero_decimales(unidades, precision_product_unit):
    score = Uom.objects.create(
        name='Score', relative_factor=20, relative_uom_id=unidades['unit'],
    )
    precision_product_unit.digits = 0
    precision_product_unit.save()

    assert unidades['unit'].compute_quantity(2, score) == 1


# --- check_qty (referencia: test_30_quantity) ------------------------------

def test_check_qty_no_redondea_si_la_unidad_es_la_misma(unidades):
    """Misma unidad de empaque que de producto → la cantidad no se toca."""
    assert unidades['unit'].check_qty(22.43, unidades['unit'], 'DOWN') == 22.43


# --- factor recursivo (uom_uom.py:69-75) -----------------------------------

def test_factor_es_el_producto_de_la_cadena(unidades):
    """``ton`` cuelga de ``kg`` que cuelga de ``g``: 1000 × 1000."""
    assert unidades['ton'].factor == 1000.0 * 1000.0
    assert unidades['kgm'].factor == 1000.0
    assert unidades['gram'].factor == 1.0


def test_cambiar_el_factor_del_padre_repropaga_a_los_hijos(unidades):
    unidades['kgm'].relative_factor = 500
    unidades['kgm'].save()

    unidades['ton'].refresh_from_db()
    assert unidades['ton'].factor == 500.0 * 1000.0


# --- Restricciones ---------------------------------------------------------

def test_factor_cero_es_rechazado(precision_product_unit):
    """``_factor_gt_zero`` (``uom_uom.py:47-50``)."""
    with pytest.raises(UserError):
        Uom.objects.create(name='Rota', relative_factor=0)


def test_sin_unidad_de_referencia_el_factor_debe_ser_uno(unidades):
    """``_check_factor`` (``uom_uom.py:97-101``)."""
    with pytest.raises(UserError):
        Uom.objects.create(name='Huerfana', relative_factor=5)


# --- Métricas de comparación ------------------------------------------------

def test_round_compare_is_zero_usan_la_precision_declarada(unidades):
    u = unidades['unit']
    # 1.005 se representa en IEEE-754 como 1.00499999999999989, así que un
    # redondeo ingenuo daría 1.0. El epsilon del algoritmo de la referencia
    # inclina el empate hacia afuera de cero: 1.01. Verificado contra
    # odoo/tools/float_utils.py ejecutado sobre la referencia.
    assert u.round(1.005) == 1.01
    assert u.compare(1.001, 1.002) == 0      # iguales a 2 decimales
    assert u.compare(1.02, 1.01) == 1
    assert u.is_zero(0.004) is True
    assert u.is_zero(0.02) is False


def test_has_common_reference(unidades):
    assert unidades['gram'].has_common_reference(unidades['ton']) is True
    assert unidades['gram'].has_common_reference(unidades['unit']) is False
