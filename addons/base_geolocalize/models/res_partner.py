"""``PartnerGeolocation`` — RELATED de la extensión que Odoo pone en
``res.partner`` (Odoo ``base_geolocalize/models/res_partner.py``).

Portación fiel: idéntica entre Odoo 18
(``scratchpad/odoo18/extracted/addons/base_geolocalize/models/res_partner.py``)
y 19 (``scratchpad/odoo19x/addons/base_geolocalize/models/res_partner.py``,
19:1-65). En Odoo, ``res.partner`` YA trae ``partner_latitude``/
``partner_longitude`` desde ``odoo/addons/base/models/res_partner.py:270-271``
(``base`` core, no ``base_geolocalize``); este addon sólo agrega
``date_localization`` + el reset-on-write + ``geo_localize()``.

Nuestro ``base.ResPartner`` porta los seis ``ADDRESS_FIELDS`` de la referencia
(``odoo19c: base/models/res_partner.py:25,263-267``) pero **no**
``partner_latitude``/``partner_longitude`` — por eso, a diferencia de
``base_address_extended`` (que sólo agrega
``street_name``/``street_number``/``city_id``), aquí ``PartnerGeolocation``
SÍ porta las tres columnas completas (``latitude``, ``longitude``,
``date_localization``), no sólo la fecha. El ``_inherit`` se modela igual que
en ``base_address_extended``: RELATED OneToOne (DEC-SALE-01) —
``PartnerGeolocation`` cuelga de ``base.ResPartner`` sin inyectar columnas en
su tabla.

**Corrección (H-API-210).** Hasta ``api@e2c3022`` este FK apuntaba a
``users.Address``; al disolverse ``users`` en ``base`` quedó colgado. El
destino fiel es ``res.partner``, que es lo que el addon extiende en la
referencia (``odoo19c: addons/base_geolocalize/models/res_partner.py:8``).
"""
from django.utils import timezone

import fields
import models

from addons.base_geolocalize.models.base_geocoder import Geocoder

# Campos de ``res.partner`` cuyo cambio dispara el reset de geolocalización.
# Fiel a Odoo 19:15 ('street', 'zip', 'city', 'state_id', 'country_id') con la
# convención de nombres del proyecto (sin sufijo ``_id`` en los Many2one).
ADDRESS_FIELDS_TRIGGERING_RESET = (
    'street', 'zip', 'city', 'state', 'country',
)
# Campos de geolocalización propios (Odoo 19:16: 'latitude', 'longitude').
GEOLOCATION_FIELDS = ('latitude', 'longitude')


class PartnerGeolocation(models.Model):
    """``date_localization`` + ``partner_latitude``/``partner_longitude``
    (Odoo 19:10 + ``base`` core 270-271) para un ``res.partner``.
    """
    _inherit = 'res.partner'

    partner = models.OneToOneField(
        'base.ResPartner', on_delete=models.CASCADE, related_name='geolocation',
        help_text='Partner al que pertenece (Odoo _inherit res.partner).',
    )
    latitude = fields.Float(
        default=0.0,
        help_text='Latitud GPS (Odoo partner_latitude, base/res_partner.py:270).',
    )
    longitude = fields.Float(
        default=0.0,
        help_text='Longitud GPS (Odoo partner_longitude, base/res_partner.py:271).',
    )
    date_localization = fields.Date(
        null=True, blank=True,
        help_text='Fecha de la última geolocalización exitosa (Odoo '
                   'date_localization, 19:10).',
    )

    class Meta:
        db_table = 'res_partner_geolocation'
        verbose_name = 'Geolocalización de dirección'
        verbose_name_plural = 'Geolocalizaciones de dirección'

    def __str__(self):
        return f'{self.partner_id}: ({self.latitude}, {self.longitude})'

    # -- Reset on address change (Odoo write, 19:12-21) ---------------------

    def apply_write_reset(self, changed_fields):
        """Limpia ``latitude``/``longitude`` si ``changed_fields`` toca algún
        campo de dirección sin actualizar también la geolocalización.

        Fiel a Odoo ``ResPartner.write`` (19:12-21): resetea a 0.0 cuando se
        modifica la dirección "sin actualizar los campos de geolocalización
        relacionados" (comentario original). No incluye el guardado — el
        llamador (código que orquesta el ``save()`` de ``Address`` +
        ``PartnerGeolocation``) decide cuándo persistir, igual que Odoo lo hace
        dentro del mismo ``write()`` transaccional del partner.
        """
        changed = set(changed_fields)
        if (changed & set(ADDRESS_FIELDS_TRIGGERING_RESET)
                and not set(GEOLOCATION_FIELDS).issubset(changed)):
            self.latitude = 0.0
            self.longitude = 0.0

    # -- geo_localize (Odoo _geo_localize + geo_localize, 19:23-65) ---------

    @staticmethod
    def _geo_localize(street='', zip='', city='', state='', country=''):
        """Resuelve una dirección a ``(lat, lng)`` con fallback (Odoo 19:23-31):
        primero con la calle completa; si no hay match, sólo ciudad/estado/país.
        """
        search = Geocoder.geo_query_address(
            street=street, zip=zip, city=city, state=state, country=country)
        result = Geocoder.geo_find(search, force_country=country)
        if result is None:
            search = Geocoder.geo_query_address(city=city, state=state,
                                                 country=country)
            result = Geocoder.geo_find(search, force_country=country)
        return result

    def geo_localize(self):
        """Geolocaliza la dirección enlazada y persiste el resultado (Odoo
        ``geo_localize``, 19:33-65).

        Simplificado respecto de Odoo: no hay equivalente de
        ``self.env.context`` (import_file/current_test/install_demo) ni de
        ``_bus_send`` (notificación en vivo al usuario vía bus de Odoo) en este
        addon — ambos son detalles de sesión/UI de Odoo sin contraparte en este
        backend; documentado como H-BASE (finding del orquestador).

        Los **nombres** de estado y país se pasan al geocoder, no sus códigos,
        igual que la referencia (``odoo19c: 19:44-48`` →
        ``partner.state_id.name`` / ``partner.country_id.name``). La
        divergencia anterior —pasar el código ISO— existía porque
        ``users.Address.country`` era un ``Char``; ``res.partner.country`` es un
        Many2one a ``res.country``, así que la fidelidad ya es alcanzable.

        Devuelve ``True`` si hubo match (y persiste latitude/longitude/
        date_localization), ``False`` si no.
        """
        partner = self.partner
        result = self._geo_localize(
            street=partner.street, zip=partner.zip, city=partner.city,
            state=partner.state.name if partner.state_id else '',
            country=partner.country.name if partner.country_id else '',
        )
        if result is None:
            return False
        self.latitude, self.longitude = result
        self.date_localization = timezone.now().date()
        self.save(update_fields=['latitude', 'longitude', 'date_localization'])
        return True
