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
    # `depends` MEDIDO da tres; la referencia declara sólo ['stock'] porque su
    # ORM resuelve `product` de forma transitiva. Aquí los imports son de
    # Python y explícitos.
    'depends': [
        'base',     # ResCompany
        'product',  # Product — de él salen los días de caducidad por defecto
        'stock',    # StockLot — el portador de las cuatro fechas
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
