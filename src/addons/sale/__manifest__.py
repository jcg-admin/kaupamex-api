# Adaptado de Odoo Community `sale/__manifest__.py` (LGPL-3) — atribución y
# aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Pedidos',
    'version': '1.0',
    'category': 'Order Management',
    'summary': 'La venta ES la orden: cotización, confirmación y su recorrido',
    'depends': [
        'catalogue',
        'inventory',
    ],
    # Declaración de la licencia de la fuente de la que se adapta este addon,
    # tal como su manifest la declara (DEC-KX-03 punto 1): una licencia NO se
    # re-etiqueta. Aquí es la de `sale` en Odoo Community.
    'license': 'LGPL-3',
    # `application` de Odoo: módulo vendible, no técnico. Alimenta
    # `authz.Module.is_application`.
    'application': True,
    'installable': True,
    'auto_install': False,
}
