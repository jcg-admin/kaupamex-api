"""``base.geo_provider`` + ``base.geocoder`` (Odoo ``base_geolocalize``).

Portación fiel de ``models/base_geocoder.py`` — idéntico entre Odoo 18
(``scratchpad/odoo18/extracted/addons/base_geolocalize/models/base_geocoder.py``)
y 19 (``odoo19c: addons/base_geolocalize/models/base_geocoder.py``).

**Porte completo — 12 de 12 símbolos** (tarea #281). Las tres exclusiones que
este docstring declaraba —``_call_googlemap``, ``_geo_query_address_googlemap``
y el par ``_call_openstreetmap_reverse``/``_get_localisation``— **ya no
existen**: los cuatro están portados abajo, más ``get_google_map_api_key`` y
``_raise_query_error``, que la versión anterior tampoco tenía.

Correspondencia Odoo -> Django:

- ``base.geo_provider`` (``models.Model``, 19:16-22 / 18:17-22) -> ``GeoProvider``
  (``models.Model``): ``tech_name`` + ``name``, ambos ``Char``.
- ``base.geocoder`` (``models.AbstractModel`` **sin tabla**, 19:24-30 / 18:25-31)
  -> clase de servicio ``Geocoder`` (NO ``models.Model`` — Odoo tampoco le da
  persistencia; ``AbstractModel`` sólo aporta métodos, igual que aquí).
  Los métodos ``@api.model`` de Odoo -> ``classmethod`` de ``Geocoder``.

Decisiones de portación (H-BASE, ver reporte del orquestador):

- ``ir.config_parameter`` (Odoo) -> ``SystemParameter`` (``addons.base``, L2).
- ``requests`` (Odoo, dependencia externa) -> stdlib ``urllib.request`` +
  ``json`` (evita agregar una dependencia nueva al ``pyproject.toml`` sólo para
  esta slice; ``requests`` no está en las dependencias declaradas del proyecto,
  ver ``pyproject.toml``). La llamada HTTP real vive aislada en
  ``_http_get_json`` para que los tests la mockeen sin red real.
- ``UserError`` (Odoo, capa HTTP/UI) -> ``GeoProviderNotImplemented`` (excepción
  de dominio propia de este addon; no hay equivalente ``UserError`` en el árbol
  Django del proyecto — ``ir_config_parameter.py`` sólo usa
  ``django.core.exceptions.ValidationError`` para validaciones de modelo, que no
  aplica aquí porque esto no es una validación de campo).
- **``_call_googlemap`` SÍ se porta** (corregido en #281). El docstring
  anterior lo excluía porque *"su llamada HTTP no es verificable sin
  credenciales reales"*, y eso confunde **no poder probar contra el servicio
  real** con **no poder portar**: la llamada sale por ``_http_get_json``, que
  existe precisamente para que un test la sustituya sin red. Lo que la clave
  ausente cambia es la conducta —se levanta el mismo error que la fuente—, no
  el alcance del porte. Igual ``_geo_query_address_googlemap``, que es
  reordenación de cadena y no toca la red en absoluto.

- **``_get_localisation`` recibe la petición explícita.** La fuente lee
  ``odoo.http.request.geoip`` de un global de su capa HTTP; aquí no hay ese
  global (medido: 0 definiciones de un resolutor GeoIP en ``src/`` —
  ``src/addons/base/models/res_device.py:308`` ya lo declara: *"No hay
  proveedor GeoIP en esta pila"*). El parámetro ``geoip`` viaja explícito,
  el mismo criterio con que ``base_automation.get_webhook_request_payload``
  recibe su ``request``. Sin él, el método cae directo a la resolución inversa
  por coordenadas, que es la rama que la fuente toma cuando su GeoIP no
  responde.
"""
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

import fields
import models

from addons.base.models import ResCountry, SystemParameter

_logger = logging.getLogger(__name__)

# Parámetro SystemParameter que fija el proveedor activo (Odoo
# 'base_geolocalize.geo_provider', 19:34 / 18:35). Guarda el pk de GeoProvider
# como string, igual que Odoo guarda el id de base.geo_provider.
GEO_PROVIDER_PARAM = 'base_geolocalize.geo_provider'

#: ≙ la clave que ``get_google_map_api_key`` lee (``odoo19c: :12-13``).
GOOGLE_MAP_API_KEY_PARAM = 'base_geolocalize.google_map_api_key'

#: ≙ la URL del servicio de geocodificación de Google (``:148``).
_GOOGLEMAP_URL = 'https://maps.googleapis.com/maps/api/geocode/json'
#: ≙ la URL de resolución inversa de Nominatim (``:121``).
_NOMINATIM_REVERSE_URL = 'https://nominatim.openstreetmap.org/reverse'


def get_google_map_api_key():
    """≙ ``get_google_map_api_key`` (``odoo19c: :12-13``).

    La fuente recibe el ``env`` y lee ``ir.config_parameter``; aquí el
    parámetro vive en ``SystemParameter`` y no hace falta pasarlo de mano en
    mano, que es la misma resolución que ya usa ``_get_provider``.
    """
    return SystemParameter.get_param(GOOGLE_MAP_API_KEY_PARAM)

# User-Agent obligatorio por la política de uso de Nominatim (Odoo hardcodea
# 'Odoo (http://www.odoo.com/contactus)', 19:94); se adapta al proyecto.
_NOMINATIM_USER_AGENT = 'Kaupamex (contacto@kaupamex.com)'
_NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'


class GeoProviderNotImplemented(Exception):
    """Dominio: no hay ``_call_<tech_name>`` para el proveedor activo.

    Equivalente a la ``UserError`` que Odoo levanta en ``geo_find`` (19:72-74)
    cuando ``getattr(self, '_call_' + provider)`` falla con ``AttributeError``.
    """


class GeoProvider(models.Model):
    """``base.geo_provider`` (Odoo 19:16-22 / 18:17-22) — catálogo de
    proveedores de geolocalización. Global de instancia (como ``ResCountry``).
    """

    tech_name = fields.Char(
        max_length=64, blank=True, default='',
        help_text='Nombre técnico del proveedor (Odoo tech_name, p.ej. '
                   '"openstreetmap").',
    )
    name = fields.Char(
        max_length=128, blank=True, default='',
        help_text='Nombre visible del proveedor (Odoo name).',
    )

    class Meta:
        db_table = 'base_geo_provider'
        ordering = ['pk']
        verbose_name = 'Geo Provider'
        verbose_name_plural = 'Geo Providers'

    def __str__(self):
        return self.name or self.tech_name


def _http_get_json(url, headers=None, timeout=10):
    """Wrapper delgado sobre ``urllib`` para permitir mock sin red real.

    Equivalente a ``requests.get(url, headers=headers, params=...).json()``
    de Odoo (19:95,99); aquí la URL ya trae el querystring codificado
    (``urllib.parse.urlencode``) por el llamador.
    """
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return json.loads(response.read().decode('utf-8'))


class BaseGeocoder:
    """``base.geocoder`` — ≙ ``BaseGeocoder`` (``odoo19c: :24-30``).

    El nombre es el de la fuente. Se llamaba ``Geocoder`` y eso no era una
    traducción sino un rebautizo: la referencia declara ``class BaseGeocoder``,
    y quitarle el prefijo dejaba el símbolo sin localizar por su nombre.

    Clase de servicio (sin tabla, sin instancia persistida) — fiel a que Odoo
    tampoco le da persistencia a un ``AbstractModel``. Todos los métodos son
    ``classmethod`` (equivalente a ``@api.model`` en Odoo: no dependen de un
    registro concreto, sólo del entorno/config global).
    """

    # -- Selección de proveedor (Odoo _get_provider, 19:32-39) --------------

    @classmethod
    def _get_provider(cls):
        """Devuelve el ``GeoProvider`` activo, o ``None`` si el catálogo está
        vacío.

        Fiel a Odoo: si el parámetro ``geo_provider`` apunta a un id que ya no
        existe (o no está seteado), cae al primero del catálogo (``search([],
        limit=1)`` -> aquí ``order_by('pk').first()``, mismo orden implícito
        por id ascendente).
        """
        provider_id = SystemParameter.get_param(GEO_PROVIDER_PARAM)
        provider = None
        if provider_id:
            provider = GeoProvider.objects.filter(pk=int(provider_id)).first()
        if provider is None:
            provider = GeoProvider.objects.order_by('pk').first()
        return provider

    # -- Construcción del string de búsqueda (Odoo geo_query_address, 19:41-58) --

    @classmethod
    def geo_query_address(cls, street=None, zip=None, city=None, state=None,
                           country=None):
        """Convierte los campos de dirección en un string de búsqueda.

        Si el proveedor activo define ``_geo_query_address_<tech_name>``,
        delega ahí (Odoo ``hasattr`` dispatch); si no, usa el joiner por
        defecto.
        """
        provider = cls._get_provider()
        tech_name = provider.tech_name if provider else None
        method = getattr(cls, '_geo_query_address_' + tech_name, None) \
            if tech_name else None
        if method is not None:
            return method(street=street, zip=zip, city=city, state=state,
                           country=country)
        return cls._geo_query_address_default(
            street=street, zip=zip, city=city, state=state, country=country)

    @classmethod
    def _geo_query_address_default(cls, street=None, zip=None, city=None,
                                    state=None, country=None):
        """Joiner por defecto (Odoo 19:179-187): concatena los no-vacíos."""
        address_list = [
            street,
            ('%s %s' % (zip or '', city or '')).strip(),
            state,
            country,
        ]
        return ', '.join(filter(None, address_list))

    # -- Resolución address -> (lat, lng) (Odoo geo_find, 19:60-80) ---------

    @classmethod
    def geo_find(cls, addr, **kw):
        """Resuelve ``addr`` a ``(latitude, longitude)`` usando el proveedor
        activo, o ``None`` si no hay match.

        Fiel a Odoo: ``AttributeError`` (proveedor sin ``_call_<tech_name>``)
        se convierte en un error de dominio explícito
        (``GeoProviderNotImplemented`` ≙ ``UserError``); cualquier otra
        excepción de la llamada al proveedor se loguea y degrada a ``None``
        (Odoo 19:77-79, ``except Exception: ... result = None``).
        """
        provider = cls._get_provider()
        tech_name = provider.tech_name if provider else None
        method = getattr(cls, '_call_' + tech_name, None) if tech_name else None
        if method is None:
            raise GeoProviderNotImplemented(
                'Provider %s is not implemented for geolocation service.'
                % tech_name)
        try:
            return method(addr, **kw)
        except GeoProviderNotImplemented:
            raise
        except Exception:
            _logger.debug('Geolocalize call failed', exc_info=True)
            return None

    @classmethod
    def _call_openstreetmap(cls, addr, **kw):
        """Nominatim de OpenStreetMap (Odoo 19:82-103). Proveedor por defecto.

        ``**kw`` se acepta por paridad de firma con ``geo_find`` (Odoo pasa
        ``force_country`` a todos los ``_call_*``); Nominatim ``/search`` no lo
        usa (a diferencia de ``_call_googlemap``, no portado — ver docstring
        del módulo).
        """
        if not addr:
            _logger.info('invalid address given')
            return None
        url = _NOMINATIM_URL + '?' + urllib.parse.urlencode(
            {'format': 'json', 'q': addr})
        try:
            result = _http_get_json(
                url, headers={'User-Agent': _NOMINATIM_USER_AGENT})
        except Exception as error:  # noqa: BLE001 — ≙ el except de la fuente
            cls._raise_query_error(error)
        _logger.info('openstreetmap nominatim service called')
        if not result:
            return None
        geo = result[0]
        return float(geo['lat']), float(geo['lon'])

    @classmethod
    def _call_openstreetmap_reverse(cls, lat, lon):
        """≙ ``_call_openstreetmap_reverse`` (``odoo19c: :105-135``).

        De coordenadas a dirección. Devuelve el cuerpo entero de la respuesta,
        como la fuente — quien lo consume (``_get_localisation``) elige qué
        campo leer de su clave ``address``.

        La fuente aborta con ``UserError`` cuando corre bajo su bandera de
        test (*"OpenStreetMap calls disabled in testing environment"*). Aquí
        esa guarda **no se porta como tal**: la llamada sale por
        ``_http_get_json``, que un test sustituye, así que no hay red que
        proteger. Es divergencia de mecanismo, no de alcance — la fuente
        necesita la bandera porque llama a ``requests`` en línea.
        """
        if not (lat and lon):
            _logger.info('invalid latitude or longitude given')
            return None
        url = _NOMINATIM_REVERSE_URL + '?' + urllib.parse.urlencode(
            {'format': 'json', 'lat': lat, 'lon': lon})
        try:
            result = _http_get_json(
                url, headers={'User-Agent': _NOMINATIM_USER_AGENT})
        except Exception as error:  # noqa: BLE001 — ≙ el except de la fuente
            cls._raise_query_error(error)
        _logger.info('openstreetmap nominatim service called')
        return result

    @classmethod
    def _call_googlemap(cls, addr, **kw):
        """≙ ``_call_googlemap`` (``odoo19c: :137-172``).

        Docstring de la fuente, verbatim: *"Use google maps API. It won't work
        without a valid API key."*

        Se conservan sus tres desenlaces: ``ZERO_RESULTS`` devuelve ``None``,
        un ``status`` distinto de ``OK`` levanta con el texto de la fuente
        —incluida su explicación de que Google lo volvió de pago—, y una
        respuesta con forma inesperada devuelve ``None`` sin levantar.

        ``force_country`` viaja como ``components``, igual que allá.
        """
        apikey = get_google_map_api_key()
        if not apikey:
            raise GeoProviderNotImplemented(
                'API key for GeoCoding (Places) required.\n'
                'Visit https://developers.google.com/maps/documentation/'
                'geocoding/get-api-key for more information.')
        params = {'sensor': 'false', 'address': addr, 'key': apikey}
        if kw.get('force_country'):
            params['components'] = 'country:%s' % kw['force_country']
        url = _GOOGLEMAP_URL + '?' + urllib.parse.urlencode(params)
        try:
            result = _http_get_json(url)
        except Exception as error:  # noqa: BLE001 — ≙ el except de la fuente
            cls._raise_query_error(error)
        try:
            if result['status'] == 'ZERO_RESULTS':
                return None
            if result['status'] != 'OK':
                _logger.debug('Invalid Gmaps call: %s - %s', result['status'],
                              result.get('error_message', ''))
                raise GeoProviderNotImplemented(
                    'Unable to geolocate, received the error:\n%s\n\n'
                    'Google made this a paid feature.\n'
                    'You should first enable billing on your Google account.\n'
                    'Then, go to Developer Console, and enable the APIs:\n'
                    'Geocoding, Maps Static, Maps Javascript.\n'
                    % result.get('error_message'))
            geo = result['results'][0]['geometry']['location']
            return float(geo['lat']), float(geo['lng'])
        except (KeyError, ValueError):
            _logger.debug('Unexpected Gmaps API answer %s',
                          result.get('error_message', ''))
            return None

    @classmethod
    def _geo_query_address_googlemap(cls, street=None, zip=None, city=None,
                                     state=None, country=None):
        """≙ ``_geo_query_address_googlemap`` (``odoo19c: :189-195``).

        Comentario de la fuente, verbatim: *"put country qualifier in front,
        otherwise GMap gives wrong results — e.g. 'Congo, Democratic Republic
        of the' => 'Democratic Republic of the Congo'"*.
        """
        if country and ',' in country and (
                country.endswith(' of') or country.endswith(' of the')):
            country = '{1} {0}'.format(*country.split(',', 1))
        return cls._geo_query_address_default(
            street=street, zip=zip, city=city, state=state, country=country)

    @classmethod
    def _raise_query_error(cls, error):
        """≙ ``_raise_query_error`` (``odoo19c: :197-198``).

        La fuente levanta ``UserError``; aquí el error de dominio del addon es
        ``GeoProviderNotImplemented``, que ``geo_find`` re-eleva sin degradar a
        ``None`` — la misma frontera que la fuente traza con su ``except
        UserError: raise``.
        """
        raise GeoProviderNotImplemented(
            'Error with geolocation server: %s' % error)

    @classmethod
    def _get_localisation(cls, latitude, longitude, geoip=None):
        """≙ ``_get_localisation`` (``odoo19c: :200-224``).

        Comentario de la fuente, verbatim: *"try to get city and/or country
        from request.geoip first; if not possible, get them from latitude and
        longitude"*, y su nota sobre por qué usa OpenStreetMap para la inversa:
        *"for now, we use openstreetmap; if needed, we will add a setting like
        'partner geolocation' that let the user decide which provider to use"*.

        ``geoip`` llega explícito porque aquí no hay global de petición (ver el
        docstring del módulo). Con ``None`` —el caso normal fuera de una
        vista— se va derecho a la resolución inversa, que es la rama que la
        fuente toma cuando su GeoIP no resuelve.

        Devuelve ``'Unknown'`` cuando no reúne ni ciudad ni país, como la
        fuente.
        """
        city = getattr(getattr(geoip, 'city', None), 'name', None)
        country_code = getattr(geoip, 'country_code', None)
        postcode = None
        if not (city and country_code):
            result = cls._call_openstreetmap_reverse(latitude, longitude)
            address = (result or {}).get('address') if result else None
            if address:
                country_code = address.get('country_code')
                city = (address.get('city_district') or address.get('town')
                        or address.get('village') or address.get('city'))
                postcode = address.get('postcode')

        country = None
        if country_code:
            country = ResCountry.objects.filter(
                code=country_code.upper()).first()

        res = postcode or ''
        if city:
            res += ' %s' % city if res else city
        if country:
            res += ', %s' % country.name if res else country.name
        return res or 'Unknown'
