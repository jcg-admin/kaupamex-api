# Adaptado de Odoo Community `product/__manifest__.py` (LGPL-3, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Productos y tarifas',
    'version': '1.0',
    'category': 'Sales/Sales',
    'summary': (
        'ProductTemplate y sus variantes, categorías, atributos, listas de '
        'precio y sus reglas — el catálogo que vende el resto del árbol'
    ),
    # `depends` MEDIDO contra los imports reales. La referencia declara
    # ['base', 'mail', 'uom']; `mail` no se mide aquí porque el producto no
    # hereda el hilo de mensajes: la trazabilidad de cambios la lleva
    # `observability`, no un chatter.
    #
    # La arista medida hacia `authz` es el gate de capacidad de las vistas
    # DRF, no dependencia de datos — no se declara (ver lote 2).
    'depends': [
        'base',  # ResCompany, ResCurrency, ResPartner, DecimalPrecision
        'uom',   # Uom — el producto se vende y se almacena en una unidad
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
