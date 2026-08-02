"""
Tests — resolve_shipping_quote (addons.delivery.quoting)

Política vigente (REVIERTE DEC-BC-25): envío GRATIS siempre. El resolver es el
único punto de extensión (open-closed) del costo de envío del checkout.
"""
import pytest
from decimal import Decimal

from addons.delivery.models import ShippingZone
from addons.delivery.quoting import ShippingQuote, resolve_shipping_quote

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

    def test_umbral_alcanzado_es_gratis(self, db):
        """Zona con costo + umbral; subtotal ≥ umbral → gratis + ventana."""
        zone = ShippingZone.objects.create(
            zip_code_prefix='06', name='Ciudad de México', is_active=True,
            estimated_days_min=2, estimated_days_max=4,
            cost=Decimal('99.00'), free_threshold=Decimal('800.00'),
        )
        quote = resolve_shipping_quote('06600', Decimal('800.00'))
        assert isinstance(quote, ShippingQuote)
        assert quote.cost == Decimal('0.00')
        assert quote.is_free is True
        assert quote.zone == zone
        assert quote.estimated_days_min == 2
        assert quote.estimated_days_max == 4

    def test_bajo_umbral_cobra_costo_de_zona(self, db):
        """Zona con costo + umbral; subtotal < umbral → cobra el costo manual."""
        ShippingZone.objects.create(
            zip_code_prefix='06', name='CDMX', is_active=True,
            cost=Decimal('99.00'), free_threshold=Decimal('800.00'),
        )
        quote = resolve_shipping_quote('06600', Decimal('100.00'))
        assert quote.cost == Decimal('99.00')
        assert quote.is_free is False

    def test_zona_sin_costo_es_gratis(self, db):
        """Zona sembrada sin ``cost`` (NULL) → gratis (rollout no disruptivo)."""
        ShippingZone.objects.create(
            zip_code_prefix='06', name='CDMX', is_active=True,
            free_threshold=Decimal('800.00'),  # umbral pero sin cost
        )
        quote = resolve_shipping_quote('06600', Decimal('10.00'))
        assert quote.cost == Decimal('0.00')
        assert quote.is_free is True

    def test_costo_sin_umbral_siempre_cobra(self, db):
        """Zona con ``cost`` y sin ``free_threshold`` → cobra siempre."""
        ShippingZone.objects.create(
            zip_code_prefix='44', name='Guadalajara', is_active=True,
            cost=Decimal('150.00'),
        )
        quote = resolve_shipping_quote('44100', Decimal('5000.00'))
        assert quote.cost == Decimal('150.00')
        assert quote.is_free is False

    def test_quote_es_gratis_sin_zona(self, db):
        """C.P. sin zona: gratis; zona y ventana None."""
        quote = resolve_shipping_quote('64000', Decimal('50.00'))
        assert quote.cost == Decimal('0.00')
        assert quote.is_free is True
        assert quote.zone is None
        assert quote.estimated_days_min is None
        assert quote.estimated_days_max is None

    def test_umbral_con_subtotal_float_no_falla_por_ieee754(self, db):
        """Un subtotal float contaminado (0.1+0.2 = 0.30000000000000004) se
        normaliza a Decimal antes de comparar el umbral — el cobro no depende
        del artefacto de coma flotante."""
        ShippingZone.objects.create(
            zip_code_prefix='06', name='CDMX', is_active=True,
            cost=Decimal('99.00'), free_threshold=Decimal('0.30'),
        )
        # 0.1 + 0.2 en float NO es exactamente 0.30, pero tras normalizar
        # a Decimal('0.30') alcanza el umbral 0.30 → gratis.
        quote = resolve_shipping_quote('06600', 0.1 + 0.2)
        assert quote.cost == Decimal('0.00')
        assert quote.is_free is True
