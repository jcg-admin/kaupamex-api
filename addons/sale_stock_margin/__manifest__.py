# Adaptado de Odoo Community `sale_stock_margin/__manifest__.py` (LGPL-3, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Margen de lo entregado',
    'version': '1.0',
    'category': 'Sales/Sales',
    'summary': (
        'Toma el coste real del movimiento de salida como coste de la '
        'línea, en vez del coste estándar del producto'
    ),
    # `depends` MEDIDO da sólo ['sale_margin'] y la referencia declara
    # ['sale_stock', 'sale_margin'] — el par que define al puente. Se declaran
    # los dos: el código sub-declara porque el porte llega al margen pero
    # todavía no al movimiento (Grupo A, tarea #64).
    'depends': [
        'sale_stock',   # el albarán del que sale el coste real
        'sale_margin',  # el cálculo de margen que corrige
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
