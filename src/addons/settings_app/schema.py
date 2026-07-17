"""
schema.py — addons.settings_app

Extensiones drf-spectacular para la configuración del sistema.
Importado desde SettingsAppConfig.ready().
"""

SPECTACULAR_TAGS = [
    {
        'name': 'config',
        'description': (
            'Configuración global del sistema (SiteSettings): IVA, '
            'tamaño de avatar, límite de direcciones, etc. '
            'Solo lectura pública; modificación requiere is_staff.'
        ),
    },
]
