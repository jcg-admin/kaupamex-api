"""``base_geolocalize`` — los seis símbolos que la tarea #281 portó.

``get_google_map_api_key``, ``_call_googlemap``,
``_geo_query_address_googlemap``, ``_call_openstreetmap_reverse``,
``_get_localisation`` y ``_raise_query_error``
(``odoo19c: base_geolocalize/models/base_geocoder.py:12-224``), más los dos
que ahora cuelgan de ``base.ResPartner`` (``…/res_partner.py:23-65``) y el
``write`` con el nombre de la fuente.
"""
from unittest.mock import patch

import pytest

from addons.base.models import ResCountry, ResPartner, SystemParameter
from addons.base_geolocalize.models import (
    BaseGeocoder, GeoProvider, GeoProviderNotImplemented, PartnerGeolocation,
    get_google_map_api_key)
from addons.base_geolocalize.models.base_geocoder import (
    GEO_PROVIDER_PARAM, GOOGLE_MAP_API_KEY_PARAM)
from orm.registry import clear_cache

pytestmark = pytest.mark.django_db

_RUTA_HTTP = 'addons.base_geolocalize.models.base_geocoder._http_get_json'


@pytest.fixture(autouse=True)
def _clear_param_cache():
    """La caché de ``SystemParameter`` es de módulo: no sobrevive al rollback."""
    clear_cache('stable')
    yield
    clear_cache('stable')


@pytest.fixture
def googlemap_active():
    """Deja ``googlemap`` como proveedor activo y le pone clave."""
    provider = GeoProvider.objects.get_or_create(
        tech_name='googlemap', defaults={'name': 'Google Place Map'})[0]
    SystemParameter.set_param(GEO_PROVIDER_PARAM, str(provider.pk))
    SystemParameter.set_param(GOOGLE_MAP_API_KEY_PARAM, 'clave-de-prueba')
    clear_cache('stable')
    return provider


class TestGetGoogleMapApiKey:
    """≙ ``get_google_map_api_key`` (``odoo19c: :12-13``)."""

    def test_it_reads_the_configuration_key(self):
        SystemParameter.set_param(GOOGLE_MAP_API_KEY_PARAM, 'abc123')
        clear_cache('stable')
        assert get_google_map_api_key() == 'abc123'

    def test_without_the_key_it_is_falsy(self):
        assert not get_google_map_api_key()


class TestGeoQueryAddressGooglemap:
    """≙ ``_geo_query_address_googlemap`` (``:189-195``) — el país delante."""

    def test_a_country_ending_in_of_the_is_reordered(self):
        salida = BaseGeocoder._geo_query_address_googlemap(
            city='Kinshasa', country='Congo, Democratic Republic of the')
        assert salida.endswith('Democratic Republic of the Congo')

    def test_a_country_ending_in_of_is_reordered(self):
        """El espacio inicial es de la fuente, no un descuido.

        Su ``'{1} {0}'.format(*country.split(',', 1))`` deja el espacio que
        seguía a la coma pegado al primer trozo (``' Republic of'``), y el
        joiner por defecto no recorta. Se conserva: recortarlo cambiaría la
        cadena que se le manda al servicio.
        """
        salida = BaseGeocoder._geo_query_address_googlemap(
            country='Korea, Republic of')
        assert salida == ' Republic of Korea'

    def test_a_plain_country_is_left_alone(self):
        salida = BaseGeocoder._geo_query_address_googlemap(
            city='CDMX', country='México')
        assert salida == 'CDMX, México'

    def test_the_dispatch_of_geo_query_address_reaches_it(self, googlemap_active):
        """``geo_query_address`` despacha por ``tech_name`` — ≙ ``:41-58``."""
        salida = BaseGeocoder.geo_query_address(
            country='Congo, Democratic Republic of the')
        assert salida == ' Democratic Republic of the Congo'


class TestCallGooglemap:
    """≙ ``_call_googlemap`` (``:137-172``) — sus cuatro desenlaces."""

    def test_without_an_api_key_it_refuses(self):
        """Sin clave no se llama al servicio — ≙ ``:141-146``.

        El ``patch`` que revienta **no es decorativo**: sin él este caso salía
        a la red de verdad, Google respondía con *"The provided API key is
        invalid"* y el ``match='API key'`` lo daba por bueno **por el motivo
        equivocado**. Medido con el control de anulación: con la guarda puesta
        a ``False`` el caso seguía en verde, que es el sub-patrón D de
        ``metrica-decide-la-conclusion.md``. Con el ``patch``, la única forma
        de ver ese texto es que la guarda esté.
        """
        SystemParameter.set_param(GOOGLE_MAP_API_KEY_PARAM, '')
        clear_cache('stable')
        with patch(_RUTA_HTTP, side_effect=AssertionError(
                'no debe salir a la red sin clave')):
            with pytest.raises(GeoProviderNotImplemented, match='API key'):
                BaseGeocoder._call_googlemap('Zocalo, CDMX')

    def test_ok_returns_the_coordinates(self, googlemap_active):
        respuesta = {'status': 'OK', 'results': [
            {'geometry': {'location': {'lat': 19.43, 'lng': -99.13}}}]}
        with patch(_RUTA_HTTP, return_value=respuesta):
            assert BaseGeocoder._call_googlemap('Zocalo, CDMX') == (19.43, -99.13)

    def test_zero_results_returns_none(self, googlemap_active):
        with patch(_RUTA_HTTP, return_value={'status': 'ZERO_RESULTS'}):
            assert BaseGeocoder._call_googlemap('nada de nada') is None

    def test_another_status_raises_with_the_billing_message(self, googlemap_active):
        respuesta = {'status': 'REQUEST_DENIED',
                     'error_message': 'billing not enabled'}
        with patch(_RUTA_HTTP, return_value=respuesta):
            with pytest.raises(GeoProviderNotImplemented, match='paid feature'):
                BaseGeocoder._call_googlemap('Zocalo, CDMX')

    def test_an_answer_without_geometry_returns_none(self, googlemap_active):
        """≙ ``except (KeyError, ValueError): return None`` (``:170-172``).

        La fuente lista **esas dos** excepciones y ninguna más, así que un
        ``results`` vacío —que da ``IndexError``— NO se traga: propaga. Este
        caso ejerce la rama que sí se traga, la clave ausente.
        """
        with patch(_RUTA_HTTP,
                   return_value={'status': 'OK', 'results': [{}]}):
            assert BaseGeocoder._call_googlemap('Zocalo, CDMX') is None

    def test_force_country_travels_as_components(self, googlemap_active):
        """≙ ``params['components'] = 'country:%s'`` (``:154``)."""
        respuesta = {'status': 'OK', 'results': [
            {'geometry': {'location': {'lat': 1.0, 'lng': 2.0}}}]}
        with patch(_RUTA_HTTP, return_value=respuesta) as llamada:
            BaseGeocoder._call_googlemap('Zocalo', force_country='MX')
        assert 'components=country%3AMX' in llamada.call_args[0][0]

    def test_a_network_failure_raises_the_query_error(self, googlemap_active):
        with patch(_RUTA_HTTP, side_effect=OSError('sin red')):
            with pytest.raises(GeoProviderNotImplemented,
                               match='geolocation server'):
                BaseGeocoder._call_googlemap('Zocalo, CDMX')

    def test_geo_find_dispatches_to_it(self, googlemap_active):
        """El despacho por ``_call_<tech_name>`` lo alcanza — ≙ ``:60-80``."""
        respuesta = {'status': 'OK', 'results': [
            {'geometry': {'location': {'lat': 19.43, 'lng': -99.13}}}]}
        with patch(_RUTA_HTTP, return_value=respuesta):
            assert BaseGeocoder.geo_find('Zocalo, CDMX') == (19.43, -99.13)


class TestCallOpenstreetmapReverse:
    """≙ ``_call_openstreetmap_reverse`` (``:105-135``)."""

    def test_it_returns_the_whole_body(self):
        cuerpo = {'address': {'city': 'CDMX', 'country_code': 'mx'}}
        with patch(_RUTA_HTTP, return_value=cuerpo):
            assert BaseGeocoder._call_openstreetmap_reverse(19.43, -99.13) == cuerpo

    def test_without_coordinates_it_does_not_call(self):
        with patch(_RUTA_HTTP) as llamada:
            assert BaseGeocoder._call_openstreetmap_reverse(None, None) is None
        assert llamada.call_count == 0

    def test_the_coordinates_travel_in_the_query(self):
        with patch(_RUTA_HTTP, return_value={}) as llamada:
            BaseGeocoder._call_openstreetmap_reverse(19.43, -99.13)
        url = llamada.call_args[0][0]
        assert 'lat=19.43' in url and 'lon=-99.13' in url

    def test_a_network_failure_raises_the_query_error(self):
        with patch(_RUTA_HTTP, side_effect=OSError('sin red')):
            with pytest.raises(GeoProviderNotImplemented,
                               match='geolocation server'):
                BaseGeocoder._call_openstreetmap_reverse(19.43, -99.13)


class TestRaiseQueryError:
    """≙ ``_raise_query_error`` (``:197-198``)."""

    def test_it_names_the_underlying_error(self):
        with pytest.raises(GeoProviderNotImplemented, match='se rompió'):
            BaseGeocoder._raise_query_error(RuntimeError('se rompió'))


class TestGetLocalisation:
    """≙ ``_get_localisation`` (``:200-224``)."""

    @pytest.fixture
    def mexico(self):
        return ResCountry.objects.get_or_create(
            code='MX', defaults={'name': 'México'})[0]

    def test_without_geoip_it_falls_back_to_the_reverse_lookup(self, mexico):
        cuerpo = {'address': {'city': 'Ciudad de México',
                              'country_code': 'mx', 'postcode': '06000'}}
        with patch(_RUTA_HTTP, return_value=cuerpo):
            salida = BaseGeocoder._get_localisation(19.43, -99.13)
        assert salida == '06000 Ciudad de México, %s' % mexico.name

    def test_the_city_falls_through_the_four_keys_of_the_source(self, mexico):
        """``city_district`` → ``town`` → ``village`` → ``city``."""
        cuerpo = {'address': {'village': 'Tepoztlán', 'country_code': 'mx'}}
        with patch(_RUTA_HTTP, return_value=cuerpo):
            assert 'Tepoztlán' in BaseGeocoder._get_localisation(18.98, -99.09)

    def test_a_geoip_that_resolves_skips_the_reverse_lookup(self, mexico):
        class _Ciudad:
            name = 'Monterrey'

        class _GeoIp:
            city = _Ciudad()
            country_code = 'mx'

        with patch(_RUTA_HTTP) as llamada:
            salida = BaseGeocoder._get_localisation(25.68, -100.31, geoip=_GeoIp())
        assert llamada.call_count == 0
        assert salida == 'Monterrey, %s' % mexico.name

    def test_without_anything_it_answers_unknown(self):
        with patch(_RUTA_HTTP, return_value={}):
            assert BaseGeocoder._get_localisation(0.0, 0.0) == 'Unknown'


class TestPartnerReceivesTheSourceSymbols:
    """Los dos símbolos que la fuente declara sobre ``res.partner``."""

    @pytest.fixture
    def partner(self):
        return ResPartner.objects.create(
            name='Nestor', street='Av. Insurgentes Sur 1234', city='CDMX',
            zip='03100')

    def test_geo_localize_is_callable_on_a_partner(self, partner):
        with patch(_RUTA_HTTP, return_value=[{'lat': '19.43', 'lon': '-99.13'}]):
            assert partner.geo_localize() is True
        fila = PartnerGeolocation.objects.get(partner=partner)
        assert (fila.latitude, fila.longitude) == (19.43, -99.13)

    def test_geo_localize_creates_the_related_row_when_absent(self, partner):
        assert not PartnerGeolocation.objects.filter(partner=partner).exists()
        with patch(_RUTA_HTTP, return_value=[{'lat': '1.0', 'lon': '2.0'}]):
            partner.geo_localize()
        assert PartnerGeolocation.objects.filter(partner=partner).exists()

    def test_geo_localize_class_method_is_callable_on_the_partner(self):
        with patch(_RUTA_HTTP, return_value=[{'lat': '19.43', 'lon': '-99.13'}]):
            assert ResPartner._geo_localize(city='CDMX') == (19.43, -99.13)

    def test_write_keeps_the_name_of_the_source(self, partner):
        fila = PartnerGeolocation.objects.create(
            partner=partner, latitude=19.43, longitude=-99.13)
        assert fila.write(latitude=1.5) is fila
        assert PartnerGeolocation.objects.get(pk=fila.pk).latitude == 1.5

    def test_write_resets_the_coordinates_when_the_address_moves(self, partner):
        fila = PartnerGeolocation.objects.create(
            partner=partner, latitude=19.43, longitude=-99.13)
        fila.write(city='Monterrey')
        assert (fila.latitude, fila.longitude) == (0.0, 0.0)

    def test_write_does_not_reset_when_the_coordinates_travel_too(self, partner):
        fila = PartnerGeolocation.objects.create(partner=partner)
        fila.write(city='Monterrey', latitude=25.68, longitude=-100.31)
        assert (fila.latitude, fila.longitude) == (25.68, -100.31)
