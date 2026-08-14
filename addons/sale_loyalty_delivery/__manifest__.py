# Adaptado de Odoo Community `sale_loyalty_delivery/__manifest__.py` (LGPL-3, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Cupón de envío gratis',
    'version': '1.0',
    'category': 'Sales/Sales',
    'summary': (
        'La recompensa que cubre el flete: descuenta la línea del '
        'transportista en vez de la del producto'
    ),
    # `depends` MEDIDO da sólo ['loyalty'] y la referencia declara
    # ['sale_loyalty', 'delivery'] — el par que define al puente. Se declaran
    # los dos de la referencia: el código sub-declara porque el porte llega al
    # motor pero todavía no al transportista (Grupo A, tarea #64).
    'depends': [
        'sale_loyalty',  # el puente que aplica la recompensa
        'delivery',      # DeliveryCarrier — la línea que cubre
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
