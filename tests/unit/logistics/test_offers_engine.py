"""
Unit tests — motor de cotización puro (apps.modules.logistics.offers).

Sin Django ORM: opera sobre ``RateCard`` y dicts. Cubre la lógica núcleo
de la "Shipment Offer API" adaptada:

  - Elegibilidad: CUALQUIER regla violada por CUALQUIER paquete → inelegible.
  - Ranking: costo asc → tránsito asc → ambiental desc.
  - Cálculo de costo = base + por_kg × peso_total.
"""
from decimal import Decimal
from apps.modules.logistics.offers import RateCard, build_offers

import pytest

pytestmark = pytest.mark.unit


def _pkg(length=10, width=10, height=10, weight=1, value=100, hazardous=False):
    return dict(length=length, width=width, height=height,
                weight=weight, value=value, hazardous=hazardous)


def test_costo_base_mas_por_kg():
    rc = RateCard(carrier='A', base_cost=Decimal('100'),
                  cost_per_kg=Decimal('10'), transit_days=3, environmental='low')
    out = build_offers([_pkg(weight=2), _pkg(weight=3)], [rc])
    assert out['ineligible'] == []
    assert out['offers'][0]['total_cost'] == Decimal('150.00')  # 100 + 10*5


def test_ranking_costo_asc_luego_transito_luego_ambiental():
    barato_lento = RateCard('Barato', Decimal('50'), Decimal('0'), 9, 'low')
    caro_rapido  = RateCard('Caro', Decimal('200'), Decimal('0'), 1, 'high')
    out = build_offers([_pkg()], [caro_rapido, barato_lento])
    assert [o['carrier'] for o in out['offers']] == ['Barato', 'Caro']


def test_empate_costo_desempata_por_transito():
    lento  = RateCard('Lento', Decimal('50'), Decimal('0'), 5, 'high')
    rapido = RateCard('Rapido', Decimal('50'), Decimal('0'), 2, 'low')
    out = build_offers([_pkg()], [lento, rapido])
    assert out['offers'][0]['carrier'] == 'Rapido'


def test_empate_costo_y_transito_desempata_por_ambiental_desc():
    verde = RateCard('Verde', Decimal('50'), Decimal('0'), 3, 'high')
    gris  = RateCard('Gris', Decimal('50'), Decimal('0'), 3, 'low')
    out = build_offers([_pkg()], [gris, verde])
    assert out['offers'][0]['carrier'] == 'Verde'


def test_peso_por_paquete_excede_limite_inelegible():
    rc = RateCard('A', Decimal('50'), Decimal('1'), 3, 'low',
                  max_package_weight_kg=Decimal('5'))
    out = build_offers([_pkg(weight=6)], [rc])
    assert out['offers'] == []
    assert out['ineligible'][0]['carrier'] == 'A'
    assert any('paquete' in r for r in out['ineligible'][0]['reasons'])


def test_dimension_por_eje_excede_limite_inelegible():
    rc = RateCard('A', Decimal('50'), Decimal('1'), 3, 'low',
                  max_length_cm=Decimal('100'),
                  max_width_cm=Decimal('100'),
                  max_height_cm=Decimal('100'))
    out = build_offers([_pkg(length=120)], [rc])
    assert out['offers'] == []
    assert any('length' in r for r in out['ineligible'][0]['reasons'])


def test_material_peligroso_rechazado_si_no_lo_permite():
    rc = RateCard('A', Decimal('50'), Decimal('1'), 3, 'low',
                  allows_hazardous=False)
    out = build_offers([_pkg(hazardous=True)], [rc])
    assert out['offers'] == []
    assert any('peligroso' in r for r in out['ineligible'][0]['reasons'])


def test_valor_total_excede_limite_inelegible():
    rc = RateCard('A', Decimal('50'), Decimal('1'), 3, 'low',
                  max_total_value=Decimal('1000'))
    out = build_offers([_pkg(value=600), _pkg(value=600)], [rc])
    assert out['offers'] == []
    assert any('valor total' in r for r in out['ineligible'][0]['reasons'])


def test_cualquier_paquete_que_viola_hace_inelegible_al_carrier():
    # Un paquete cumple, otro excede peso → carrier inelegible (ANY-violation).
    rc = RateCard('A', Decimal('50'), Decimal('1'), 3, 'low',
                  max_package_weight_kg=Decimal('5'))
    out = build_offers([_pkg(weight=1), _pkg(weight=99)], [rc])
    assert out['offers'] == []
    assert out['ineligible'][0]['carrier'] == 'A'


def test_elegibles_e_inelegibles_coexisten():
    ok  = RateCard('OK', Decimal('50'), Decimal('1'), 3, 'low')
    bad = RateCard('BAD', Decimal('50'), Decimal('1'), 3, 'low',
                   max_package_weight_kg=Decimal('0.5'))
    out = build_offers([_pkg(weight=2)], [ok, bad])
    assert [o['carrier'] for o in out['offers']] == ['OK']
    assert [i['carrier'] for i in out['ineligible']] == ['BAD']
