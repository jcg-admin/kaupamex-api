# Adaptado de Odoo Community `product_matrix/__manifest__.py` (LGPL-3,
# odoo19c:) — atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Matriz de variantes',
    'version': '1.0',
    'category': 'Sales/Sales',
    'summary': (
        'La rejilla que cruza dos atributos del producto para capturar '
        'cantidades por variante en una sola pasada'
    ),
    # `depends` MEDIDO da ['base', 'product'] y la referencia declara
    # ['account']. La divergencia es de HOGAR: allí la matriz se estrena en la
    # factura, así que el addon cuelga del módulo contable; aquí el terminal
    # es el producto y sus atributos, y quien la consume es `sale_product_matrix`.
    'depends': [
        'base',     # ResCompany
        'product',  # ProductTemplate y sus atributos — los ejes de la rejilla
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
