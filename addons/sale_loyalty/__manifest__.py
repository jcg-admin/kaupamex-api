# Adaptado de Odoo Community `sale_loyalty/__manifest__.py` (LGPL-3, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Pedido con cupones',
    'version': '1.0',
    'category': 'Sales/Sales',
    'summary': (
        'Aplica programa, cupón y recompensa sobre el pedido: valida las '
        'reglas, descuenta puntos y añade la línea de descuento'
    ),
    # `depends` MEDIDO coincide con el de la referencia (['sale', 'loyalty'])
    # más `base` y `product`, explícitos aquí porque los imports son de Python.
    # Este addon es el puente cuya existencia justifica que `sale` y `loyalty`
    # NO se declaren mutuamente (ver los dos manifiestos).
    'depends': [
        'base',     # ResPartner — el titular de la tarjeta
        'product',  # Product — la recompensa en especie
        'loyalty',  # LoyaltyProgram, LoyaltyCard — el motor
        'sale',     # SaleOrder — donde se aplica
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
