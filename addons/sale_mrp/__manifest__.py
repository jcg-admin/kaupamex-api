# Adaptado de Odoo Community `sale_mrp/__manifest__.py` (LGPL-3, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Pedido que dispara fabricación',
    'version': '1.0',
    'category': 'Sales/Sales',
    'summary': (
        'El pedido de un producto fabricable lanza su orden de producción y '
        'enlaza las dos por su origen'
    ),
    # `depends` MEDIDO da tres; la referencia declara ['mrp', 'sale_stock'].
    # Aquí se mide `sale` directo en vez de `sale_stock` porque el enlace que
    # este recorte porta es pedido→producción, sin pasar por el albarán.
    'depends': [
        'base',  # ResCompany
        'mrp',   # MrpProduction — lo que el pedido lanza
        'sale',  # SaleOrder — el disparador
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
