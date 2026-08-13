"""``base.geo_provider`` + ``base.geocoder`` (Odoo ``base_geolocalize``).

Portación fiel de ``models/base_geocoder.py`` — idéntico entre Odoo 18
(``scratchpad/odoo18/extracted/addons/base_geolocalize/models/base_geocoder.py``)
y 19 (``scratchpad/odoo19x/addons/base_geolocalize/models/base_geocoder.py``,
19:16-103); v19 solo agrega ``_call_openstreetmap_reverse``/``_get_localisation``
(dependen de ``odoo.http.request.geoip``, sin equivalente HTTP-request en este
addon — fuera de scope de esta slice).

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
- **``_call_googlemap`` NO se porta en esta slice** (H-BASE): requiere una
  API key paga (``base_geolocalize.google_map_api_key``) y su llamada HTTP no
  es verificable sin credenciales reales. El proveedor ``googlemap`` se sigue
  sembrando en el catálogo (fiel a ``data/data.xml``) para que
  ``_get_provider``/administración lo liste, pero seleccionarlo activo hace que
  ``geo_find`` levante ``GeoProviderNotImplemented`` — mismo comportamiento
  observable que tendría Odoo si ``_call_googlemap`` no existiera (``hasattr``
  falla -> ``UserError``). Análogamente, ``_geo_query_address_googlemap``
  (reordena el país, 19:190-196) tampoco se porta: sin la llamada HTTP no hay
  forma de ejercer esa rama con evidencia PROVEN en este slice.
"""
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

import fields
import models

from addons.base.models import SystemParameter

_logger = logging.getLogger(__name__)

# Parámetro SystemParameter que fija el proveedor activo (Odoo
# 'base_geolocalize.geo_provider', 19:34 / 18:35). Guarda el pk de GeoProvider
# como string, igual que Odoo guarda el id de base.geo_provider.
GEO_PROVIDER_PARAM = 'base_geolocalize.geo_provider'

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


class Geocoder:
    """``base.geocoder`` (Odoo ``AbstractModel``, 19:24-30 / 18:25-31).

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
        result = _http_get_json(url, headers={'User-Agent': _NOMINATIM_USER_AGENT})
        _logger.info('openstreetmap nominatim service called')
        if not result:
            return None
        geo = result[0]
        return float(geo['lat']), float(geo['lon'])
