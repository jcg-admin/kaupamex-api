# Adaptado de Odoo Community `website_sale/__manifest__.py` (LGPL-3, odoo19c:)
# — atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Comercio electrónico',
    'version': '1.0',
    'category': 'Website/Website',
    'summary': (
        'La tienda pública sobre el pedido: catálogo navegable, carrito, '
        'checkout y su paso a pedido confirmado'
    ),
    # `depends` MEDIDO da siete; se declaran CUATRO — los mismos presentes que
    # declara la referencia (['website', 'sale', 'delivery'] más `digest`, que
    # aquí no se mide porque el resumen consume las cifras, no al revés).
    #
    # La arista `website_sale → website_sale_wishlist` NO se declara: es una
    # inversión. En la referencia el wishlist depende de la tienda, nunca al
    # revés. Registrada aquí y en el gate de dirección
    # (`scripts/check_addon_cycles.py`), no legitimada.
    #
    # `authz` es el gate de capacidad, no dependencia de datos (ver lote 2).
    #
    # Porte PARCIAL declarado: es la Capa 2 de la campaña (tarea #204), y el
    # servicio de carrito todavía vive en `sale` (tarea #101).
    'depends': [
        'product',      # Product — el catálogo que se navega
        'sale',         # SaleOrder — el carrito ES el pedido en borrador
        'delivery',     # DeliveryCarrier — la elección de envío en el checkout
        'sale_loyalty', # el cupón aplicado en el carrito
        'website',      # el sitio que hospeda la tienda
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': True,   # módulo vendible del catálogo L0
    'installable': True,
    'auto_install': False,
}
