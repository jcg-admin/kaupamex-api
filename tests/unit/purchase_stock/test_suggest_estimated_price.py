"""``ProductProduct.suggest_estimated_price`` — el precio de comprar lo sugerido.

Fiel a ``odoo19c: purchase_stock/models/product.py:40,62-78`` (``odoo-tools``,
LGPL-3). La fuente encadena dos ``_select_seller``: primero por la cantidad
exacta sugerida y, sólo si eso no da nada, por la tarifa de menor cantidad
mínima. El respaldo al costo estándar del producto entra únicamente cuando
ninguna de las dos llamadas devuelve tarifa.

Cada caso se construye para que una implementación parcial de la cascada —
sólo la primera llamada, o sin la guarda de cantidad cero— falle: el
sub-patrón D de ``metrica-decide-la-conclusion.md`` (un verde que no
distingue el fenómeno del instrumento).
"""
from decimal import Decimal
from unittest.mock import PropertyMock, patch

import pytest

from addons.base.models import ResPartner
from addons.product.models import ProductProduct, ProductSupplierinfo, ProductTemplate

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def _variant(name='Eleke', standard_price=Decimal('1.00')):
    tmpl = ProductTemplate.objects.create(name=name)
    return ProductProduct.objects.create(
        product_tmpl=tmpl, standard_price=standard_price)


def _tariff(tmpl, partner, **kwargs):
    return ProductSupplierinfo.objects.create(
        partner=partner, product_tmpl=tmpl, **kwargs)


def _suggesting(variant, qty):
    """Fija ``suggested_qty`` sin pasar por el motor de demanda.

    Lo que estos casos prueban es la cascada de precio, no cómo se calcula la
    cantidad sugerida — eso lo cubren (o deben cubrirlo) los tests de
    ``_compute_suggested_quantity``. ``suggested_qty`` ya es una ``property``
    real instalada por ``extend_model`` (``propiedades=``), así que
    ``PropertyMock`` sobre la clase es la sustitución de alcance mínimo.
    """
    return patch.object(
        type(variant), 'suggested_qty', new_callable=PropertyMock,
        return_value=qty)


class TestSuggestEstimatedPrice:
    """``suggest_estimated_price`` + ``_compute_suggest_estimated_price``."""

    def test_zero_or_negative_suggested_qty_short_circuits_to_zero(self):
        """La guarda de la fuente (``if suggested_qty <= 0: continue``).

        Con un proveedor caro configurado a propósito: si la guarda no
        existiera, el resultado sería ``price * 0`` — también ``0.0`` con
        una tarifa, pero **no** con la guarda ausente y ``suggested_qty``
        negativo (``price * -5`` sería negativo). Se prueban los dos signos.
        """
        variant = _variant(standard_price=Decimal('999.00'))
        supplier = ResPartner.objects.create(name='Proveedor')
        _tariff(variant.product_tmpl, supplier, price=Decimal('1.00'))
        with _suggesting(variant, 0):
            assert variant.suggest_estimated_price == 0.0
        with _suggesting(variant, -5):
            assert variant.suggest_estimated_price == 0.0

    def test_uses_the_tariff_that_matches_the_suggested_quantity(self):
        """Primera llamada de la cascada: la tarifa cuyo ``min_qty`` la
        cantidad sugerida ya cubre — y no el costo estándar, mucho más caro
        a propósito para que un ``standard_price`` filtrado por error se
        note de inmediato."""
        variant = _variant(standard_price=Decimal('999.00'))
        supplier = ResPartner.objects.create(name='Proveedor')
        _tariff(variant.product_tmpl, supplier, min_qty=1, price=Decimal('7.00'))
        with _suggesting(variant, 3):
            assert variant.suggest_estimated_price == Decimal('7.00') * 3

    def test_falls_back_to_the_min_qty_tariff_when_none_matches_the_quantity(self):
        """Segunda llamada de la cascada: ninguna tarifa cubre la cantidad
        sugerida (los dos ``min_qty`` la superan), así que se toma la de
        menor ``min_qty`` sin filtrar por cantidad. Discrimina contra una
        implementación de una sola llamada, que caería al costo estándar."""
        variant = _variant(standard_price=Decimal('999.00'))
        supplier = ResPartner.objects.create(name='Proveedor')
        _tariff(variant.product_tmpl, supplier, min_qty=50, price=Decimal('4.00'))
        _tariff(variant.product_tmpl, supplier, min_qty=100, price=Decimal('2.00'))
        with _suggesting(variant, 3):
            # Control: la primera llamada de la cascada no encuentra nada —
            # si esto fallara, el caso mediría otra cosa (una tarifa que sí
            # cubre la cantidad), no la caída al respaldo.
            assert variant._select_seller(quantity=3) == []
            assert variant.suggest_estimated_price == Decimal('4.00') * 3

    def test_falls_back_to_standard_price_when_no_tariff_exists(self):
        """Sin ninguna tarifa, las dos llamadas de la cascada devuelven
        vacío y el precio cae al costo estándar del producto."""
        variant = _variant(standard_price=Decimal('12.50'))
        with _suggesting(variant, 2):
            assert variant.suggest_estimated_price == Decimal('12.50') * 2
