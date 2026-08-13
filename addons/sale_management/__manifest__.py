# Adaptado de Odoo Community `sale_management/__manifest__.py` (LGPL-3, odoo19c:)
# — atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Gestión de ventas',
    'version': '1.0',
    'category': 'Sales/Sales',
    'summary': (
        'La capa de gestión sobre el pedido: plantillas de cotización, el '
        'reporte imprimible y sus extensiones'
    ),
    # `depends` MEDIDO da cuatro; la referencia declara ['sale', 'digest'].
    # `digest` no se mide: el resumen consume las cifras de venta, no al revés.
    #
    # `authz` es el gate de capacidad, no dependencia de datos (ver lote 2).
    'depends': [
        'base',     # ResCompany
        'product',  # Product — las líneas de la plantilla
        'sale',     # SaleOrder — lo que este addon gestiona
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
