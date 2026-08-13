# Adaptado de Odoo Community `sale_mrp_margin/__manifest__.py` (LGPL-3, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Margen de lo fabricado',
    'version': '1.0',
    'category': 'Sales/Sales',
    'summary': (
        'Toma el coste real de la orden de producción como coste de la '
        'línea de pedido, en vez del coste estándar'
    ),
    # `depends` MEDIDO da ['mrp', 'sale_margin'] y la referencia declara
    # ['sale_mrp', 'sale_stock_margin']. La divergencia sigue a la de `sale_mrp`:
    # este recorte no pasa por el albarán, así que enlaza con el margen de venta
    # directamente y no con su variante de stock.
    'depends': [
        'mrp',          # MrpProduction — de donde sale el coste real
        'sale_margin',  # el cálculo de margen que corrige
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
