# Adaptado de Odoo Community `sale_service/__manifest__.py` (LGPL-3, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Pedido de servicio',
    'version': '1.0',
    'category': 'Sales/Sales',
    'summary': (
        'El producto de tipo servicio en el pedido: sin movimiento de stock '
        'y con su propia política de facturación'
    ),
    # `depends` MEDIDO da sólo ['product'] y la referencia declara
    # ['sale_management']. Se declara `sale` en vez de `sale_management`: el
    # terminal de la política de facturación es la línea de pedido, no la vista
    # de gestión. El porte es del Grupo A (tarea #64) y sub-declara.
    'depends': [
        'product',  # Product — de donde sale el tipo servicio
        'sale',     # SaleOrder — donde la política se aplica
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
