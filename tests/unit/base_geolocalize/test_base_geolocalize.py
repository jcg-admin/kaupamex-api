"""Contrato de ``base_geolocalize`` — ``GeoProvider`` / ``Geocoder`` /
``AddressGeolocation``.

Portación fiel del addon ``base_geolocalize`` de Odoo (18/19, "Partners
Geolocation"). Cada test verifica un comportamiento del original:

- ``GeoProvider`` — catálogo (Odoo ``base.geo_provider``, 19:16-22).
- ``Geocoder._get_provider`` — fallback al primero del catálogo si el
  parámetro no está seteado o apunta a un id inexistente (Odoo 19:32-39).
- ``Geocoder.geo_query_address`` — joiner por defecto (Odoo 19:41-58,
  180-187).
- ``Geocoder.geo_find`` — dispatch a ``_call_<tech_name>`` (Odoo 19:60-80);
  ``_call_openstreetmap`` parsea ``(lat, lng)`` de Nominatim (Odoo 19:82-103).
  Sin red real: ``_http_get_json`` se mockea.
- ``AddressGeolocation`` — RELATED OneToOne sobre ``users.Address``; reset de
  lat/lng al cambiar la dirección (Odoo ``ResPartner.write``, 19:12-21);
  ``geo_localize()`` persiste el resultado (Odoo 19:33-65, geocoder mockeado).
- Migración de seed — crea ambos proveedores (Odoo ``data/data.xml``).
"""
from unittest.mock import patch

import pytest

from django.contrib.auth import get_user_model

from addons.base.models import SystemParameter, _PARAM_CACHE
from addons.base_geolocalize.models import (
    AddressGeolocation,
    Geocoder,
    GeoProvider,
    GeoProviderNotImplemented,
)
from addons.base_geolocalize.models.base_geocoder import GEO_PROVIDER_PARAM
from addons.users.models import Address

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_param_cache():
    # Mismo patrón que tests/unit/base/test_system_parameter.py: la caché de
    # SystemParameter es módulo-nivel (per-proceso), se limpia entre tests
    # para que no sobreviva al rollback de la transacción de cada test.
    _PARAM_CACHE.clear()
    yield
    _PARAM_CACHE.clear()


def _make_address(**overrides):
    user = User.objects.create_user(
        email=overrides.pop('email', 'geo@example.com'), password='x')
    defaults = dict(
        user=user, recipient_name='Nestor', street='Av. Insurgentes Sur 1234',
        city='CDMX', state='CDMX', zip_code='03100', country='MX',
        phone='5512345678',
    )
    defaults.update(overrides)
    return Address.objects.create(**defaults)


class TestGeoProvider:
    def test_fields_persist(self):
        provider = GeoProvider.objects.create(
            tech_name='openstreetmap', name='Open Street Map')
        provider.refresh_from_db()
        assert provider.tech_name == 'openstreetmap'
        assert provider.name == 'Open Street Map'

    def test_str_uses_name(self):
        provider = GeoProvider.objects.create(
            tech_name='openstreetmap', name='Open Street Map')
        assert str(provider) == 'Open Street Map'

    def test_str_falls_back_to_tech_name_without_name(self):
        provider = GeoProvider.objects.create(tech_name='openstreetmap', name='')
        assert str(provider) == 'openstreetmap'


class TestSeedMigration:
    # Odoo data/data.xml siembra exactamente estos dos registros.
    def test_openstreetmap_and_googlemap_seeded(self):
        assert GeoProvider.objects.filter(tech_name='openstreetmap').exists()
        assert GeoProvider.objects.filter(tech_name='googlemap').exists()
        assert GeoProvider.objects.count() == 2


class TestGetProvider:
    def test_falls_back_to_first_when_param_unset(self):
        # Sin SystemParameter seteado, cae al primero por pk (Odoo:
        # search([], limit=1) sin _get_param previo).
        first = GeoProvider.objects.order_by('pk').first()
        assert Geocoder._get_provider() == first

    def test_falls_back_to_first_when_param_points_to_missing_id(self):
        SystemParameter.set_param(GEO_PROVIDER_PARAM, '999999')
        first = GeoProvider.objects.order_by('pk').first()
        assert Geocoder._get_provider() == first

    def test_uses_param_when_valid(self):
        googlemap = GeoProvider.objects.get(tech_name='googlemap')
        SystemParameter.set_param(GEO_PROVIDER_PARAM, str(googlemap.pk))
        assert Geocoder._get_provider() == googlemap


class TestGeoQueryAddress:
    def test_default_joiner_matches_expected_string(self):
        result = Geocoder._geo_query_address_default(
            street='Av. Insurgentes Sur 1234', zip='03100', city='CDMX',
            state='CDMX', country='MX')
        assert result == 'Av. Insurgentes Sur 1234, 03100 CDMX, CDMX, MX'

    def test_default_joiner_skips_empty_parts(self):
        result = Geocoder._geo_query_address_default(
            street=None, zip=None, city='CDMX', state=None, country='MX')
        assert result == 'CDMX, MX'

    def test_geo_query_address_delegates_to_default(self):
        result = Geocoder.geo_query_address(
            street='Main 12', zip='', city='', state='', country='MX')
        assert result == 'Main 12, MX'


class TestGeoFind:
    def test_dispatches_to_openstreetmap_and_parses_lat_lng(self):
        with patch(
            'addons.base_geolocalize.models.base_geocoder._http_get_json',
            return_value=[{'lat': '19.4326', 'lon': '-99.1332'}],
        ) as mocked:
            result = Geocoder.geo_find('Zocalo, CDMX, MX')
        mocked.assert_called_once()
        assert result == (19.4326, -99.1332)

    def test_empty_result_returns_none(self):
        with patch(
            'addons.base_geolocalize.models.base_geocoder._http_get_json',
            return_value=[],
        ):
            assert Geocoder.geo_find('direccion inexistente') is None

    def test_no_addr_returns_none_without_http_call(self):
        with patch(
            'addons.base_geolocalize.models.base_geocoder._http_get_json',
        ) as mocked:
            assert Geocoder.geo_find('') is None
        mocked.assert_not_called()

    def test_http_failure_is_caught_and_returns_none(self):
        # Odoo 19:77-79: cualquier excepcion de la llamada al proveedor se
        # loguea y degrada a None (no propaga).
        with patch(
            'addons.base_geolocalize.models.base_geocoder._http_get_json',
            side_effect=OSError('network down'),
        ):
            assert Geocoder.geo_find('Zocalo, CDMX, MX') is None

    def test_unknown_provider_raises_not_implemented(self):
        unknown = GeoProvider.objects.create(
            tech_name='unknown_provider_xyz', name='Unknown')
        SystemParameter.set_param(GEO_PROVIDER_PARAM, str(unknown.pk))
        with pytest.raises(GeoProviderNotImplemented):
            Geocoder.geo_find('Zocalo, CDMX, MX')

    def test_no_provider_at_all_raises_not_implemented(self):
        GeoProvider.objects.all().delete()
        with pytest.raises(GeoProviderNotImplemented):
            Geocoder.geo_find('Zocalo, CDMX, MX')


class TestAddressGeolocation:
    def test_one_to_one_on_address(self):
        addr = _make_address()
        geo = AddressGeolocation.objects.create(address=addr, latitude=19.4,
                                                 longitude=-99.1)
        addr.refresh_from_db()
        assert addr.geolocation == geo
        assert addr.geolocation.latitude == 19.4

    def test_defaults_zero(self):
        addr = _make_address()
        geo = AddressGeolocation.objects.create(address=addr)
        assert geo.latitude == 0.0
        assert geo.longitude == 0.0
        assert geo.date_localization is None

    def test_str(self):
        addr = _make_address()
        geo = AddressGeolocation.objects.create(address=addr, latitude=1.0,
                                                 longitude=2.0)
        assert str(geo) == f'{addr.pk}: (1.0, 2.0)'

    def test_write_reset_clears_lat_lng_on_address_field_change(self):
        addr = _make_address()
        geo = AddressGeolocation.objects.create(
            address=addr, latitude=19.4, longitude=-99.1)
        geo.apply_write_reset(['street'])
        assert geo.latitude == 0.0
        assert geo.longitude == 0.0

    def test_write_reset_skipped_when_geolocation_fields_also_changed(self):
        addr = _make_address()
        geo = AddressGeolocation.objects.create(
            address=addr, latitude=19.4, longitude=-99.1)
        # Si el caller actualiza street Y latitude/longitude en el mismo
        # write, Odoo NO resetea (19:15-16: not all('partner_%s' % f in vals
        # for f in ['latitude', 'longitude'])).
        geo.apply_write_reset(['street', 'latitude', 'longitude'])
        assert geo.latitude == 19.4
        assert geo.longitude == -99.1

    def test_write_reset_ignored_for_unrelated_fields(self):
        addr = _make_address()
        geo = AddressGeolocation.objects.create(
            address=addr, latitude=19.4, longitude=-99.1)
        geo.apply_write_reset(['is_default', 'phone'])
        assert geo.latitude == 19.4
        assert geo.longitude == -99.1

    def test_geo_localize_persists_result_and_date(self):
        addr = _make_address()
        geo = AddressGeolocation.objects.create(address=addr)
        with patch(
            'addons.base_geolocalize.models.res_partner.Geocoder.geo_find',
            return_value=(19.4326, -99.1332),
        ):
            ok = geo.geo_localize()
        assert ok is True
        geo.refresh_from_db()
        assert geo.latitude == 19.4326
        assert geo.longitude == -99.1332
        assert geo.date_localization is not None

    def test_geo_localize_returns_false_without_match(self):
        addr = _make_address()
        geo = AddressGeolocation.objects.create(address=addr)
        with patch(
            'addons.base_geolocalize.models.res_partner.Geocoder.geo_find',
            return_value=None,
        ):
            ok = geo.geo_localize()
        assert ok is False
        geo.refresh_from_db()
        assert geo.latitude == 0.0
        assert geo.date_localization is None

    def test_cascade_delete_with_address(self):
        addr = _make_address()
        AddressGeolocation.objects.create(address=addr)
        addr.hard_delete()
        assert AddressGeolocation.objects.count() == 0
