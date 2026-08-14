# Adaptado de Odoo Community `sale_product_matrix/__manifest__.py` (LGPL-3, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Matriz en el pedido',
    'version': '1.0',
    'category': 'Sales/Sales',
    'summary': (
        'Captura cantidades por variante en una rejilla y las vuelca como '
        'líneas del pedido'
    ),
    # `depends` MEDIDO da ['base', 'sale'] y la referencia declara ['sale',
    # 'product_matrix'] — el par que define al puente. Se declara
    # `product_matrix` por fidelidad: sin él no hay rejilla que volcar, aunque
    # el import todavía no exista (porte parcial).
    'depends': [
        'base',            # ResCompany
        'sale',            # SaleOrder — el destino de las líneas
        'product_matrix',  # la rejilla que este addon estrena en el pedido
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
