"""Serializers de la configuración del sitio — ``base``.

``SiteSettings`` es el singleton de configuración del sistema; la referencia
declara su análogo ``res.config.settings`` en ``base`` en las dos poblaciones
medidas (``odoo19c: odoo/addons/base/models/res_config.py`` y
``odoo18c:`` el mismo símbolo ``_name = 'res.config.settings'``), así que la
superficie vive con el modelo y no en un addon de sitio.

Porte de la capa del ex-addon ``settings_app`` (retirado en ``api@115d219``);
el modelo ya vivía aquí desde el fold.
"""
from rest_framework import serializers

from addons.base.models import SiteSettings

_SOCIAL_KEYS = {'facebook', 'instagram', 'twitter', 'youtube', 'tiktok', 'whatsapp'}


class SiteSettingsSerializer(serializers.ModelSerializer):
    """Contrato admin de ``/api/v2/config/settings/`` (UC-CFG-03).

    La lista de campos es explícita: los deprecados (``currency``,
    ``site_name``, ``order_timeout_minutes``, ``max_return_days``) quedan
    fuera del contrato aunque sigan en el modelo (DEC-DOC-005).
    """

    class Meta:
        model = SiteSettings
        fields = [
            'id', 'iva_rate',
            'payment_timeout_minutes', 'min_stock_threshold',
            'free_shipping_threshold',
            'support_email', 'phone', 'address', 'social_links',
            'updated_at',
        ]
        read_only_fields = ['id', 'updated_at']

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
