"""Tags de OpenAPI del escaparate — recogidos por ``collect_app_tags``.

Patrón Open/Closed: el addon declara sus tags aquí y el hook los agrega al
schema final; ``config/settings/base.py`` no se toca al añadir una familia.
"""
SPECTACULAR_TAGS = [
    {
        'name': 'cart',
        'description': (
            'Carrito del escaparate. El carrito **es** la orden de venta en '
            'borrador (``SaleOrder`` con ``state=draft``), igual que en la '
            'referencia. Rutas públicas: comprar sin cuenta es el caso '
            'normal; el carrito anónimo se ancla por ``X-Cart-Token``.'
        ),
    },
]
