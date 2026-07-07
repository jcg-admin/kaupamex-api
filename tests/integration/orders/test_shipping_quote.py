"""
Tests — resolve_shipping_quote (apps.orders.shipping)

Política vigente (REVIERTE DEC-BC-25): envío GRATIS siempre. El resolver es el
único punto de extensión (open-closed) del costo de envío del checkout.
"""
import pytest
from decimal import Decimal

from apps.orders.models import ShippingZone
from apps.orders.shipping import ShippingQuote, resolve_shipping_quote

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _tabla_zonas_vacia(db):
    """Aísla del seed de zonas (migración de datos 0012_seed_shipping_zones).

    Las migraciones de datos siembran C.P. reales (01, 06, 066, 44, 64, …).
    Sin limpiar, el resolver hace longest-prefix match contra el seed (p. ej.
    '06600' matchea la zona sembrada '066' antes que la '06' que crea el test),
    y los tests que crean un prefijo ya sembrado chocan con la unique de
    ``zip_code_prefix`` (migración 0017). El delete lo revierte la transacción
    del fixture ``db`` de pytest-django, así que otros módulos ven el seed.
    """
    ShippingZone.objects.all().delete()


class TestResolveShippingQuote:

    def test_quote_es_gratis_con_zona(self, db):
        """Con zona que cubre el C.P.: cost 0, is_free True y expone la
        ventana de entrega de la zona."""
        zone = ShippingZone.objects.create(
            zip_code_prefix='06', name='Ciudad de México', is_active=True,
            estimated_days_min=2, estimated_days_max=4,
            cost=Decimal('99.00'), free_threshold=Decimal('800.00'),
        )
        quote = resolve_shipping_quote('06600', Decimal('100.00'))
        assert isinstance(quote, ShippingQuote)
        assert quote.cost == Decimal('0.00')
        assert quote.is_free is True
        assert quote.zone == zone
        assert quote.estimated_days_min == 2
        assert quote.estimated_days_max == 4

    def test_quote_es_gratis_sin_zona(self, db):
        """C.P. sin zona sembrada: sigue siendo gratis; zona y ventana None."""
        quote = resolve_shipping_quote('64000', Decimal('50.00'))
        assert quote.cost == Decimal('0.00')
        assert quote.is_free is True
        assert quote.zone is None
        assert quote.estimated_days_min is None
        assert quote.estimated_days_max is None

    def test_quote_gratis_ignora_subtotal_bajo(self, db):
        """El subtotal NO afecta el costo hoy: aun bajo un umbral gratis de
        zona, el envío es gratis (el cobro bajo-umbral es el punto de
        extensión PENDIENTE, no implementado)."""
        ShippingZone.objects.create(
            zip_code_prefix='06', name='CDMX', is_active=True,
            cost=Decimal('99.00'), free_threshold=Decimal('800.00'),
        )
        quote = resolve_shipping_quote('06600', Decimal('10.00'))
        assert quote.cost == Decimal('0.00')
        assert quote.is_free is True
