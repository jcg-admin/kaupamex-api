# Adaptado de Odoo Community `base_geolocalize/__manifest__.py` (LGPL-3,
# odoo19c:) — atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Geolocalización de contactos',
    'version': '1.0',
    'category': 'Sales/Sales',
    'summary': (
        'Geocoder y GeoProvider: resuelve latitud/longitud de una dirección '
        'contra un proveedor configurable, con el resultado en PartnerGeolocation'
    ),
    # `depends` MEDIDO contra los imports reales (`base` por ResPartner). La
    # referencia declara ['base_setup'] porque su clave de API vive en
    # `res.config.settings`; aquí es un SystemParameter, que está en `base`.
    'depends': [
        'base',  # ResPartner + SystemParameter (la clave del proveedor)
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
