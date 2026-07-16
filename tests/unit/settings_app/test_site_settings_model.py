"""
Tests unitarios — SiteSettings (UC-CFG-03)
TDD: RED — estos tests deben fallar hasta que el modelo exista.

Contrato documentado en:
  FR-CFG-03.01: Actualizar configuracion global del sistema
  FR-CFG-03.02: Validar y persistir los parametros globales
"""
import pytest
from decimal import Decimal
from apps.addons.settings_app.models import SiteSettings
from django.core.exceptions import ValidationError

pytestmark = pytest.mark.unit


class TestSiteSettingsSingleton:
    """SiteSettings es un singleton — solo existe un registro."""

    def test_get_or_create_defaults_creates_one_record(self, db):
        settings = SiteSettings.get_or_create_defaults()
        assert settings.pk is not None
        assert SiteSettings.objects.count() == 1

    def test_get_or_create_defaults_returns_same_record(self, db):
        s1 = SiteSettings.get_or_create_defaults()
        s2 = SiteSettings.get_or_create_defaults()
        assert s1.pk == s2.pk

    def test_cannot_create_second_record(self, db):
        SiteSettings.get_or_create_defaults()
        with pytest.raises((ValidationError, Exception)):
            SiteSettings.objects.create(
                iva_rate=Decimal('0.08'),
                currency='USD',
            )


class TestSiteSettingsFields:
    """Campos del modelo según FR-CFG-03.01."""

    def test_default_iva_rate_is_16_percent(self, db):
        s = SiteSettings.get_or_create_defaults()
        assert s.iva_rate == Decimal('0.16')

    def test_default_currency_is_mxn(self, db):
        s = SiteSettings.get_or_create_defaults()
        assert s.currency == 'MXN'

    def test_default_order_timeout_is_30_minutes(self, db):
        s = SiteSettings.get_or_create_defaults()
        assert s.order_timeout_minutes == 30

    def test_default_max_return_days_is_30(self, db):
        s = SiteSettings.get_or_create_defaults()
        assert s.max_return_days == 30

    def test_default_free_shipping_threshold_is_500(self, db):
        s = SiteSettings.get_or_create_defaults()
        assert s.free_shipping_threshold == Decimal('500.00')

    def test_default_site_name(self, db):
        s = SiteSettings.get_or_create_defaults()
        assert s.site_name == 'PracticaYoruba'


class TestSiteSettingsValidation:
    """Validaciones según FR-CFG-03.02."""

    def test_iva_rate_must_be_between_0_and_1(self, db):
        s = SiteSettings.get_or_create_defaults()
        s.iva_rate = Decimal('1.5')
        with pytest.raises(ValidationError):
            s.full_clean()

    def test_iva_rate_negative_is_invalid(self, db):
        s = SiteSettings.get_or_create_defaults()
        s.iva_rate = Decimal('-0.05')
        with pytest.raises(ValidationError):
            s.full_clean()

    def test_iva_rate_zero_is_valid(self, db):
        s = SiteSettings.get_or_create_defaults()
        s.iva_rate = Decimal('0.00')
        s.full_clean()  # no debe lanzar

    def test_currency_must_be_3_chars(self, db):
        s = SiteSettings.get_or_create_defaults()
        s.currency = 'INVALID_LONG_CODE'
        with pytest.raises(ValidationError):
            s.full_clean()

    def test_order_timeout_must_be_positive(self, db):
        s = SiteSettings.get_or_create_defaults()
        s.order_timeout_minutes = 0
        with pytest.raises(ValidationError):
            s.full_clean()

    def test_free_shipping_threshold_cannot_be_negative(self, db):
        s = SiteSettings.get_or_create_defaults()
        s.free_shipping_threshold = Decimal('-1.00')
        with pytest.raises(ValidationError):
            s.full_clean()


class TestSiteSettingsUpdate:
    """Actualización con efecto inmediato según FR-CFG-03.02."""

    def test_update_iva_rate_persists(self, db):
        s = SiteSettings.get_or_create_defaults()
        s.iva_rate = Decimal('0.08')
        s.save()
        s_fresh = SiteSettings.objects.get(pk=s.pk)
        assert s_fresh.iva_rate == Decimal('0.08')

    def test_str_representation(self, db):
        s = SiteSettings.get_or_create_defaults()
        assert 'SiteSettings' in str(s) or 'PracticaYoruba' in str(s)
