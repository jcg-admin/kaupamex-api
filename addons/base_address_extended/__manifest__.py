# Adaptado de Odoo Community `base_address_extended/__manifest__.py` (LGPL-3,
# odoo19c:) — atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Dirección estructurada',
    'version': '1.0',
    'category': 'Sales/Sales',
    'summary': (
        'ResCity, CatalogPostalCode y CountryAddressPolicy: parte la calle en '
        'nombre y número y resuelve colonia/municipio por código postal'
    ),
    # `depends` MEDIDO contra los imports reales. La referencia declara
    # ['base', 'contacts']; `contacts` es la aplicación de agenda (la vista de
    # kanban de partners), que este árbol no tiene: aquí el partner se expone
    # por DRF y su pantalla vive en el repo `ui`.
    'depends': [
        'base',  # ResPartner, ResCountry, ResCountryState
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    # Seguridad de la fuente
    # (``odoo19c: addons/base_address_extended/__manifest__.py:17-18``), por
    # ``load_data`` en el ciclo de instalación: copia fiel del CSV. Las vistas
    # no se cargan: este árbol no sirve el cliente web.
    'data': [
        'security/ir.model.access.csv',
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
}
