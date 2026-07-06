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
