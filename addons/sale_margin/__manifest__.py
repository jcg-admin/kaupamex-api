# Adaptado de Odoo Community `sale_margin/__manifest__.py` (LGPL-3, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Margen en el pedido',
    'version': '1.0',
    'category': 'Sales/Sales',
    'summary': (

        'Coste y margen por línea de pedido, y su acumulado en la cabecera'
    ),
    # `depends` MEDIDO da ['base', 'sale'] y la referencia declara
    # ['sale_management']. La divergencia es de HOGAR: allí el margen se estrena
    # en la vista de gestión de ventas; aquí el terminal es la línea de pedido,
    # que vive en `sale`.
    'depends': [
        'base',  # ResCurrency — el margen va en la divisa del pedido
        'sale',  # SaleOrderLine — donde se calcula
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
