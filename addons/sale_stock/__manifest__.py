# Adaptado de Odoo Community `sale_stock/__manifest__.py` (LGPL-3, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Pedido que reserva inventario',
    'version': '1.0',
    'category': 'Sales/Sales',
    'summary': (
        'El pedido confirmado genera su albarán de salida, reserva la '
        'mercancía y devuelve el estado de entrega al pedido'
    ),
    # `depends` MEDIDO da ['base', 'sale'] y la referencia declara ['sale',
    # 'stock_account'] — el par que define al puente. Se declara `stock_account`
    # por fidelidad al encuadre: la salida de mercancía se valora. El import
    # todavía no existe (porte parcial, Capa 2 · tarea #204).
    'depends': [
        'base',           # ResCompany
        'sale',           # SaleOrder — el origen
        'stock_account',  # la valoración de lo que sale (fidelidad a la ref)
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
