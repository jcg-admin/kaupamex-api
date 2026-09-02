"""Serializer del formulario de ajustes — ``base_setup``.

No es un ``ModelSerializer``: no hay tabla que serializar. Es la proyección
HTTP del formulario ``SiteConfigSettings``, cuyos valores viven en
``SystemParameter`` — una clave por dominio dueño, no una fila con todos los
ejes. El destino per-company de la referencia queda pendiente del resolutor
(ver el docstring del modelo).

El contrato publicado **no cambia** respecto de la versión que serializaba la
tabla ``SiteSettings``: mismos nombres de campo, mismos tipos, mismos
validadores. Lo que cambió es dónde aterrizan los valores.
"""
import json
from decimal import Decimal

from rest_framework import serializers

from addons.base.models.ir_config_parameter import SystemParameter
from addons.base_setup.models import SiteConfigSettings

_SOCIAL_KEYS = {'facebook', 'instagram', 'twitter', 'youtube', 'tiktok', 'whatsapp'}

#: Las redes sociales son un JSON suelto, no un campo con política: van al
#: mismo destino de parámetro, con la clave prefijada por su dominio dueño.
SOCIAL_LINKS_KEY = 'crm.social_links'


class SiteSettingsSerializer(serializers.Serializer):
    """Contrato admin de ``/api/v2/config/settings/`` (UC-CFG-03).

    Los campos deprecados (``currency``, ``site_name``,
    ``order_timeout_minutes``, ``max_return_days``) quedan fuera del contrato
    publicado aunque el formulario los conozca — DEC-DOC-005.
    """

    iva_rate = serializers.DecimalField(
        max_digits=5, decimal_places=4,
        min_value=Decimal('0'), max_value=Decimal('1'), required=False)
    payment_timeout_minutes = serializers.IntegerField(min_value=1, required=False)
    min_stock_threshold = serializers.IntegerField(min_value=0, required=False)
    free_shipping_threshold = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal('0'), required=False)
    support_email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    social_links = serializers.JSONField(required=False)

    def validate_social_links(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                'social_links debe ser un objeto JSON (dict).'
            )
        for key, url in value.items():
            if key not in _SOCIAL_KEYS:
                raise serializers.ValidationError(
                    f'Clave no permitida: "{key}". '
                    f'Claves validas: {sorted(_SOCIAL_KEYS)}.'
                )
            if not isinstance(url, str):
                raise serializers.ValidationError(
                    f'El valor de "{key}" debe ser una cadena de texto.'
                )
        return value

    @staticmethod
    def read_current():
        """Estado actual del formulario, leído de su destino.

        Pasa por el propio serializer para que los tipos del contrato sean
        los declarados (``DecimalField`` sale como cadena, no como float del
        encoder JSON) — el equivalente de que en la referencia el campo, no
        el almacén, decida la forma publicada.
        """
        state = SiteConfigSettings.current_values()
        values = {name: state[name] for name in SiteSettingsSerializer().fields
                  if name in state}
        raw = SystemParameter.get_param(SOCIAL_LINKS_KEY)
        values['social_links'] = json.loads(raw) if raw else {}
        return SiteSettingsSerializer(values).data

    @staticmethod
    def apply(validated):
        """Escribe los campos entrantes en su destino y devuelve el estado.

        Parcial por contrato (``PATCH``): lo que no viene conserva su valor
        actual, así que el formulario se instancia con el estado leído y se
        sobrescribe sólo lo entrante — igual que la referencia hace al
        rellenar el formulario con ``default_get`` antes de guardar.
        """
        social = validated.pop('social_links', None)

        state = SiteConfigSettings.current_values()
        state.update(validated)
        form = SiteConfigSettings(**{
            name: value for name, value in state.items()
            if name in {f.name for f in SiteConfigSettings._meta.get_fields()}
        })
        form.apply_values()

        if social is not None:
            SystemParameter.set_param(SOCIAL_LINKS_KEY, json.dumps(social))

        return SiteSettingsSerializer.read_current()


class BaseSetupDataSerializer(serializers.Serializer):
    """Contrato de ``GET /api/v2/config/base-setup-data/``.

    ≙ el diccionario que devuelve ``BaseSetup.base_setup_data``
    (``odoo19c: addons/base_setup/controllers/main.py:45-50``), con sus mismas
    tres claves. La cuarta —``action_pending_users``— queda fuera: está
    BLOQUEADA por ``res.users._action_show``, y la razón vive en el docstring
    de :class:`~addons.base_setup.controllers.main.BaseSetupDataView`.

    ``pending_users`` conserva la forma de la fuente: pares ``(id, login)``,
    no objetos. La fuente los saca de un ``cr.fetchall()`` y los publica tal
    cual; cambiarlos a diccionarios sería inventar un contrato que su UI no
    consume.
    """

    active_users = serializers.IntegerField(min_value=0)
    pending_count = serializers.IntegerField(min_value=0)
    pending_users = serializers.ListField(
        child=serializers.ListField(), allow_empty=True)
