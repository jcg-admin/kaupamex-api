"""Contrato de ``base_geolocalize`` — ``GeoProvider`` / ``BaseGeocoder`` /
``PartnerGeolocation``.

Portación fiel del addon ``base_geolocalize`` de Odoo (18/19, "Partners
Geolocation"). Cada test verifica un comportamiento del original:

- ``GeoProvider`` — catálogo (Odoo ``base.geo_provider``, 19:16-22).
- ``BaseGeocoder._get_provider`` — fallback al primero del catálogo si el
  parámetro no está seteado o apunta a un id inexistente (Odoo 19:32-39).
- ``BaseGeocoder.geo_query_address`` — joiner por defecto (Odoo 19:41-58,
  180-187).
- ``BaseGeocoder.geo_find`` — dispatch a ``_call_<tech_name>`` (Odoo 19:60-80);
  ``_call_openstreetmap`` parsea ``(lat, lng)`` de Nominatim (Odoo 19:82-103).
  Sin red real: ``_http_get_json`` se mockea.
- ``PartnerGeolocation`` — RELATED OneToOne sobre ``base.ResPartner``; reset de
  lat/lng al cambiar la dirección (Odoo ``ResPartner.write``, 19:12-21);
  ``geo_localize()`` persiste el resultado (Odoo 19:33-65, geocoder mockeado).
- Migración de seed — crea ambos proveedores (Odoo ``data/data.xml``).
"""
from unittest.mock import patch

import pytest

from addons.base.models import ResPartner, SystemParameter
from orm.registry import clear_cache
from addons.base_geolocalize.models import (
    BaseGeocoder,
    GeoProvider,
    GeoProviderNotImplemented,
    PartnerGeolocation,
)
from addons.base_geolocalize.models.base_geocoder import GEO_PROVIDER_PARAM

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_param_cache():
    # Mismo patrón que tests/unit/base/test_system_parameter.py: la caché de
    # SystemParameter es módulo-nivel (per-proceso), se limpia entre tests
    # para que no sobreviva al rollback de la transacción de cada test.
    clear_cache('stable')
    yield
    clear_cache('stable')


def _make_partner(**overrides):
    # En la referencia el addon extiende ``res.partner`` — la dirección ES el
    # partner (odoo19c: base_geolocalize/models/res_partner.py:8). ``state`` y
    # ``country`` son Many2one; se omiten cuando el test no los necesita.
    defaults = dict(
        name='Nestor', street='Av. Insurgentes Sur 1234', city='CDMX',
        zip='03100', phone='5512345678',
    )
    defaults.update(overrides)
    return ResPartner.objects.create(**defaults)


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
        assert BaseGeocoder._get_provider() == first

    def test_falls_back_to_first_when_param_points_to_missing_id(self):
        SystemParameter.set_param(GEO_PROVIDER_PARAM, '999999')
        first = GeoProvider.objects.order_by('pk').first()
        assert BaseGeocoder._get_provider() == first

    def test_uses_param_when_valid(self):
        googlemap = GeoProvider.objects.get(tech_name='googlemap')
        SystemParameter.set_param(GEO_PROVIDER_PARAM, str(googlemap.pk))
        assert BaseGeocoder._get_provider() == googlemap


class TestGeoQueryAddress:
    def test_default_joiner_matches_expected_string(self):
        result = BaseGeocoder._geo_query_address_default(
            street='Av. Insurgentes Sur 1234', zip='03100', city='CDMX',
            state='CDMX', country='MX')
        assert result == 'Av. Insurgentes Sur 1234, 03100 CDMX, CDMX, MX'

    def test_default_joiner_skips_empty_parts(self):
        result = BaseGeocoder._geo_query_address_default(
            street=None, zip=None, city='CDMX', state=None, country='MX')
        assert result == 'CDMX, MX'

    def test_geo_query_address_delegates_to_default(self):
        result = BaseGeocoder.geo_query_address(
            street='Main 12', zip='', city='', state='', country='MX')
        assert result == 'Main 12, MX'


class TestGeoFind:
    def test_dispatches_to_openstreetmap_and_parses_lat_lng(self):
        with patch(
            'addons.base_geolocalize.models.base_geocoder._http_get_json',
            return_value=[{'lat': '19.4326', 'lon': '-99.1332'}],
        ) as mocked:
            result = BaseGeocoder.geo_find('Zocalo, CDMX, MX')
        mocked.assert_called_once()
        assert result == (19.4326, -99.1332)

    def test_empty_result_returns_none(self):
        with patch(
            'addons.base_geolocalize.models.base_geocoder._http_get_json',
            return_value=[],
        ):
            assert BaseGeocoder.geo_find('direccion inexistente') is None

    def test_no_addr_returns_none_without_http_call(self):
        with patch(
            'addons.base_geolocalize.models.base_geocoder._http_get_json',
        ) as mocked:
            assert BaseGeocoder.geo_find('') is None
        mocked.assert_not_called()

    def test_http_failure_raises_the_query_error(self):
        """Un fallo de red SÍ propaga — ≙ ``_raise_query_error`` (``:197``).

        Este caso afirmaba ``is None`` y era la conducta equivocada: en la
        fuente ``_call_openstreetmap`` envuelve la petición y llama a
        ``self._raise_query_error(e)``, que levanta ``UserError``; y
        ``geo_find`` declara ``except UserError: raise`` **antes** de su
        ``except Exception``, precisamente para dejarlo pasar. Lo que aquel
        ``except Exception: result = None`` degrada es otra cosa —una
        respuesta con forma inesperada—, no la caída del servicio.

        La conducta anterior existía porque ``_raise_query_error`` no estaba
        portado; se cerró en la tarea #281.
        """
        with patch(
            'addons.base_geolocalize.models.base_geocoder._http_get_json',
            side_effect=OSError('network down'),
        ):
            with pytest.raises(GeoProviderNotImplemented):
                BaseGeocoder.geo_find('Zocalo, CDMX, MX')

    def test_a_malformed_answer_degrades_to_none(self):
        """La rama que la fuente SÍ degrada: ``except Exception -> None``.

        Una respuesta sin las claves esperadas revienta al leerlas, y ése es
        el fallo que ``geo_find`` traga (``odoo19c: :77-79``).
        """
        with patch(
            'addons.base_geolocalize.models.base_geocoder._http_get_json',
            return_value=[{'sin': 'lat ni lon'}],
        ):
            assert BaseGeocoder.geo_find('Zocalo, CDMX, MX') is None

    def test_unknown_provider_raises_not_implemented(self):
        unknown = GeoProvider.objects.create(
            tech_name='unknown_provider_xyz', name='Unknown')
        SystemParameter.set_param(GEO_PROVIDER_PARAM, str(unknown.pk))
        with pytest.raises(GeoProviderNotImplemented):
            BaseGeocoder.geo_find('Zocalo, CDMX, MX')

    def test_no_provider_at_all_raises_not_implemented(self):
        GeoProvider.objects.all().delete()
        with pytest.raises(GeoProviderNotImplemented):
            BaseGeocoder.geo_find('Zocalo, CDMX, MX')


class TestPartnerGeolocation:
    def test_one_to_one_on_partner(self):
        partner = _make_partner()
        geo = PartnerGeolocation.objects.create(partner=partner, latitude=19.4,
                                                 longitude=-99.1)
        partner.refresh_from_db()
        assert partner.geolocation == geo
        assert partner.geolocation.latitude == 19.4

    def test_defaults_zero(self):
        partner = _make_partner()
        geo = PartnerGeolocation.objects.create(partner=partner)
        assert geo.latitude == 0.0
        assert geo.longitude == 0.0
        assert geo.date_localization is None

    def test_str(self):
        partner = _make_partner()
        geo = PartnerGeolocation.objects.create(partner=partner, latitude=1.0,
                                                 longitude=2.0)
        assert str(geo) == f'{partner.pk}: (1.0, 2.0)'

    def test_write_reset_clears_lat_lng_on_address_field_change(self):
        partner = _make_partner()
        geo = PartnerGeolocation.objects.create(
            partner=partner, latitude=19.4, longitude=-99.1)
        geo.apply_write_reset(['street'])
        assert geo.latitude == 0.0
        assert geo.longitude == 0.0

    def test_write_reset_skipped_when_geolocation_fields_also_changed(self):
        partner = _make_partner()
        geo = PartnerGeolocation.objects.create(
            partner=partner, latitude=19.4, longitude=-99.1)
        # Si el caller actualiza street Y latitude/longitude en el mismo
        # write, Odoo NO resetea (19:15-16: not all('partner_%s' % f in vals
        # for f in ['latitude', 'longitude'])).
        geo.apply_write_reset(['street', 'latitude', 'longitude'])
        assert geo.latitude == 19.4
        assert geo.longitude == -99.1

    def test_write_reset_ignored_for_unrelated_fields(self):
        partner = _make_partner()
        geo = PartnerGeolocation.objects.create(
            partner=partner, latitude=19.4, longitude=-99.1)
        geo.apply_write_reset(['is_default', 'phone'])
        assert geo.latitude == 19.4
        assert geo.longitude == -99.1

    def test_geo_localize_persists_result_and_date(self):
        partner = _make_partner()
        geo = PartnerGeolocation.objects.create(partner=partner)
        with patch(
            'addons.base_geolocalize.models.res_partner.BaseGeocoder.geo_find',
            return_value=(19.4326, -99.1332),
        ):
            ok = geo.geo_localize()
        assert ok is True
        geo.refresh_from_db()
        assert geo.latitude == 19.4326
        assert geo.longitude == -99.1332
        assert geo.date_localization is not None

    def test_geo_localize_returns_false_without_match(self):
        partner = _make_partner()
        geo = PartnerGeolocation.objects.create(partner=partner)
        with patch(
            'addons.base_geolocalize.models.res_partner.BaseGeocoder.geo_find',
            return_value=None,
        ):
            ok = geo.geo_localize()
        assert ok is False
        geo.refresh_from_db()
        assert geo.latitude == 0.0
        assert geo.date_localization is None

    def test_cascade_delete_with_partner(self):
        # ``res.partner`` no tiene borrado lógico (se archiva con ``active``);
        # ``delete()`` borra la fila y el CASCADE del OneToOne arrastra la
        # geolocalización.
        partner = _make_partner()
        PartnerGeolocation.objects.create(partner=partner)
        partner.delete()
        assert PartnerGeolocation.objects.count() == 0


class TestPartnerWriteResetsGeolocation:
    """≙ ``ResPartner.write`` (``odoo19c: base_geolocalize/models/res_partner.py:12-21``).

    La puerta que la fuente vigila es el ``write`` del **contacto**, no el de
    la fila RELATED: quien muda una dirección escribe en ``res.partner``.
    Estos casos ejercen esa puerta.
    """

    def test_changing_the_street_resets_the_coordinates(self):
        partner = _make_partner()
        geo = PartnerGeolocation.objects.create(
            partner=partner, latitude=19.4326, longitude=-99.1332)
        partner.write({'street': 'Otra calle 99'})
        geo.refresh_from_db()
        assert geo.latitude == 0.0
        assert geo.longitude == 0.0

    def test_changing_the_country_resets_the_coordinates(self):
        partner = _make_partner()
        geo = PartnerGeolocation.objects.create(
            partner=partner, latitude=19.4326, longitude=-99.1332)
        # ``country_id`` es el ``attname`` de la FK: el nombre con que un
        # llamador que trae ids escribe la columna.
        partner.write({'country_id': None})
        geo.refresh_from_db()
        assert geo.latitude == 0.0

    def test_writing_the_address_and_the_coordinates_together_keeps_them(self):
        """La segunda mitad de la condición de la fuente.

        Si el mismo ``write`` trae la dirección **y** las dos coordenadas, no
        hay reset: el llamador ya sabe dónde está el contacto.
        """
        partner = _make_partner()
        geo = PartnerGeolocation.objects.create(
            partner=partner, latitude=19.4326, longitude=-99.1332)
        partner.write({'street': 'Otra calle 99',
                       'latitude': 19.4326, 'longitude': -99.1332})
        geo.refresh_from_db()
        assert geo.latitude == 19.4326
        assert geo.longitude == -99.1332

    def test_an_unrelated_field_leaves_the_coordinates_alone(self):
        partner = _make_partner()
        geo = PartnerGeolocation.objects.create(
            partner=partner, latitude=19.4326, longitude=-99.1332)
        partner.write({'phone': '5599887766'})
        geo.refresh_from_db()
        assert geo.latitude == 19.4326

    def test_the_write_still_persists_the_partner(self):
        """El override delega en la previa — sin eso el contacto no se guarda."""
        partner = _make_partner()
        partner.write({'street': 'Otra calle 99'})
        partner.refresh_from_db()
        assert partner.street == 'Otra calle 99'

    def test_a_partner_without_geolocation_row_does_not_break(self):
        partner = _make_partner()
        assert not PartnerGeolocation.objects.filter(partner=partner).exists()
        partner.write({'city': 'Monterrey'})
        partner.refresh_from_db()
        assert partner.city == 'Monterrey'
