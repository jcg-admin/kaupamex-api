"""``utm_medium_data`` — los diez medios de entrega que la fuente siembra.

Adaptación de ``odoo19c: addons/utm/data/utm_medium_data.xml``
(``odoo-tools@622ddc2a``, LGPL-3; ``noupdate="1"``).

El identificador externo de cada uno **no es decorativo**:
``UtmMedium._unlink_except_utm_medium_record`` lo resuelve en tiempo de
ejecución para impedir que se borre un medio que otro módulo cita.
"""

UTM_MEDIUMS = [
    {'xmlid': 'utm.utm_medium_website', 'name': 'Website'},
    {'xmlid': 'utm.utm_medium_phone', 'name': 'Phone'},
    {'xmlid': 'utm.utm_medium_direct', 'name': 'Direct'},
    {'xmlid': 'utm.utm_medium_email', 'name': 'Email'},
    {'xmlid': 'utm.utm_medium_banner', 'name': 'Banner'},
    {'xmlid': 'utm.utm_medium_twitter', 'name': 'X'},
    {'xmlid': 'utm.utm_medium_facebook', 'name': 'Facebook'},
    {'xmlid': 'utm.utm_medium_linkedin', 'name': 'LinkedIn'},
    {'xmlid': 'utm.utm_medium_television', 'name': 'Television'},
    {'xmlid': 'utm.utm_medium_google_adwords', 'name': 'Google Adwords'},
]
