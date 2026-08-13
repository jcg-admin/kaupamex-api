# Adaptado de Odoo Community `delivery/__manifest__.py` (LGPL-3, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Costes de envío',
    'version': '1.0',
    'category': 'Sales/Delivery',
    'summary': (
        'DeliveryCarrier y su rejilla de precio: calcula el flete por peso, '
        'importe o regla, y lo añade como línea al pedido'
    ),
    # `depends` MEDIDO da seis; la referencia declara ['sale',
    # 'payment_custom']. La dirección `delivery → sale` SÍ es la de la
    # referencia (el transportista añade su línea al pedido), así que se
    # declara. `payment_custom` no se mide: allí aporta el modo
    # contra-reembolso, que este recorte no tiene.
    #
    # La arista hacia `authz` es el gate de capacidad, no dependencia de
    # datos — no se declara (ver lote 2).
    'depends': [
        'base',     # ResCompany, ResPartner, ResCurrency
        'product',  # Product — el flete se factura como un producto de servicio
        'sale',     # SaleOrder — el destinatario de la línea de flete
        'payment',  # el cobro del envío junto con el pedido
        'mail',     # el aviso de expedición al comprador
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
