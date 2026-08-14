# Adaptado de Odoo Community `product_expiry/__manifest__.py` (LGPL-3,
# odoo19c:) — atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Caducidad de producto',
    'version': '1.0',
    'category': 'Supply Chain/Inventory',
    'summary': (
        'Las cuatro fechas del lote —caducidad, uso, retirada y alerta— y su '
        'cálculo desde la recepción'
    ),
    # La referencia declara sólo ['stock'] porque su ORM resuelve `product` de
    # forma transitiva. Aquí los imports son de Python y explícitos: este addon
    # cuelga campos sobre `product.template` (los cinco de configuración) y
    # sobre `stock.lot`/`stock.quant`/`stock.move` (las fechas y el orden
    # FEFO), así que nombra los dos.
    'depends': [
        'product',  # ProductTemplate — donde viven los días de caducidad
        'stock',    # StockLot, StockQuant, StockMove — las fechas y FEFO
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
