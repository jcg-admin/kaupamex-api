"""
Tests unitarios del management command create_seed_catalog.

BD: kaupamex_qa (config.settings.testing)
"""
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from addons.catalogue.models import Category, Product
from addons.chartsize.models import ProductVariant, VariantOption, VariantType
from addons.orders.models import ShippingZone
from addons.settings_app.models import PaymentGateway, ShippingMethod

pytestmark = pytest.mark.unit


class TestCreateSeedCatalogCategory:
    """El command crea la categoría QA correctamente."""

    def test_category_created(self, db):
        call_command('create_seed_catalog')

        cat = Category.objects.get(slug='collar-qa-e2e')
        assert cat.name == 'Collares QA E2E'
        assert cat.is_active is True

    def test_category_idempotent(self, db):
        call_command('create_seed_catalog')
        call_command('create_seed_catalog')

        assert Category.objects.filter(slug='collar-qa-e2e').count() == 1


class TestCreateSeedCatalogProduct:
    """El command crea el producto QA con los flags correctos."""

    def test_product_created_with_correct_flags(self, db):
        call_command('create_seed_catalog')

        product = Product.objects.get(sku='QA-001')
        assert product.name == 'Collar QA E2E'
        assert product.is_active is True
        assert product.is_published is True
        assert product.stock >= 1
        assert product.price > 0

    def test_product_idempotent(self, db):
        call_command('create_seed_catalog')
        call_command('create_seed_catalog')

        assert Product.objects.filter(sku='QA-001').count() == 1


class TestCreateSeedCatalogVariant:
    """El command crea la cadena completa VariantType→VariantOption→ProductVariant."""

    def test_variant_chain_created(self, db):
        call_command('create_seed_catalog')

        product = Product.objects.get(sku='QA-001')
        vtype = VariantType.objects.get(product=product, name='Tamaño')
        voption = VariantOption.objects.get(variant_type=vtype, label='Único')
        variant = ProductVariant.objects.get(product=product, option=voption)

        assert vtype.is_active is True
        assert voption.is_active is True
        assert variant.is_active is True
        assert variant.stock >= 1

    def test_variant_idempotent(self, db):
        call_command('create_seed_catalog')
        call_command('create_seed_catalog')

        product = Product.objects.get(sku='QA-001')
        assert ProductVariant.objects.filter(product=product).count() == 1


class TestCreateSeedCatalogShipping:
    """El command crea ShippingZone y ShippingMethod correctamente."""

    def test_shipping_zone_covers_cp_06600(self, db):
        call_command('create_seed_catalog')

        zone = ShippingZone.objects.get(zip_code_prefix='066')
        assert zone.is_active is True
        # Verifica que '06600' pasa el startswith check del checkout
        assert '06600'.startswith(zone.zip_code_prefix)

    def test_shipping_method_active(self, db):
        call_command('create_seed_catalog')

        method = ShippingMethod.objects.get(name='Estándar QA')
        assert method.is_active is True
        assert method.estimated_days >= 1

    def test_shipping_idempotent(self, db):
        call_command('create_seed_catalog')
        call_command('create_seed_catalog')

        assert ShippingZone.objects.filter(zip_code_prefix='066').count() == 1
        assert ShippingMethod.objects.filter(name='Estándar QA').count() == 1


class TestCreateSeedCatalogPaymentGateway:
    """El command crea PaymentGateway TEST activo con credenciales válidas."""

    def test_gateway_created_active(self, db):
        call_command('create_seed_catalog')

        gw = PaymentGateway.objects.get(gateway=PaymentGateway.GATEWAY_TEST)
        assert gw.is_active is True

    def test_gateway_credentials_decryptable(self, db):
        call_command('create_seed_catalog')

        gw = PaymentGateway.objects.get(gateway=PaymentGateway.GATEWAY_TEST)
        creds = gw.get_credentials()
        assert isinstance(creds, dict)
        assert len(creds) > 0

    def test_gateway_idempotent(self, db):
        call_command('create_seed_catalog')
        call_command('create_seed_catalog')

        assert PaymentGateway.objects.filter(
            gateway=PaymentGateway.GATEWAY_TEST
        ).count() == 1

    def test_gateway_credentials_refreshed_on_rerun(self, db):
        call_command('create_seed_catalog')
        first_creds = PaymentGateway.objects.get(
            gateway=PaymentGateway.GATEWAY_TEST
        ).get_credentials()

        call_command('create_seed_catalog')
        second_creds = PaymentGateway.objects.get(
            gateway=PaymentGateway.GATEWAY_TEST
        ).get_credentials()

        # Credenciales del mismo dict — re-cifradas pero equivalentes
        assert first_creds == second_creds


class TestCreateSeedCatalogDryRun:
    """El flag --dry-run no escribe en la base de datos."""

    def test_dry_run_creates_nothing(self, db):
        call_command('create_seed_catalog', dry_run=True)

        assert not Product.objects.filter(sku='QA-001').exists()
        assert not Category.objects.filter(slug='collar-qa-e2e').exists()
        assert not ShippingZone.objects.filter(zip_code_prefix='066').exists()
        assert not PaymentGateway.objects.filter(
            gateway=PaymentGateway.GATEWAY_TEST
        ).exists()
