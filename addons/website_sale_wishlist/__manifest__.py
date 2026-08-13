# Adaptado de Odoo Community `website_sale_wishlist/__manifest__.py` (LGPL-3,
# odoo19c:) — atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Lista de deseos',
    'version': '1.0',
    'category': 'Website/Website',
    'summary': (
        'El producto guardado para después por un visitante o un comprador '
        'identificado, y su paso al carrito'
    ),
    # `depends` MEDIDO da cinco y la referencia declara sólo
    # ['website_sale'] — la tienda de la que este addon es satélite. Se
    # declara `website_sale` por fidelidad a la DIRECCIÓN: es el par de la
    # inversión que el manifiesto de `website_sale` registra (allí el código
    # mide la arista contraria).
    'depends': [
        'base',           # ResPartner — el dueño de la lista
        'product',        # Product — lo que se guarda
        'stock',          # la disponibilidad que se muestra en la lista
        'sale',           # SaleOrder — el destino al pasar al carrito
        'website_sale',   # la tienda de la que este addon es satélite
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
