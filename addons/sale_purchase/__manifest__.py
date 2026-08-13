# Adaptado de Odoo Community `sale_purchase/__manifest__.py` (LGPL-3, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Pedido que dispara compra',
    'version': '1.0',
    'category': 'Sales/Sales',
    'summary': (
        'El pedido de un producto bajo pedido lanza su solicitud de compra '
        'y enlaza las dos por su origen'
    ),
    # `depends` MEDIDO coincide con el de la referencia (['sale', 'purchase'])
    # más `base`, explícito aquí porque el import es de Python.
    'depends': [
        'base',      # ResCompany
        'purchase',  # PurchaseOrder — lo que el pedido lanza
        'sale',      # SaleOrder — el disparador
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
