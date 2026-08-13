# Adaptado de Odoo Community `sale_sms/__manifest__.py` (LGPL-3, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Aviso por SMS del pedido',
    'version': '1.0',
    'category': 'Sales/Sales',
    'summary': (
        'Envía el SMS de confirmación y de expedición al comprador desde el '
        'pedido'
    ),
    # `depends` MEDIDO coincide con el de la referencia (['sale', 'sms']) más
    # `base`, explícito aquí porque el import es de Python.
    'depends': [
        'base',  # ResPartner — el destinatario
        'sale',  # SaleOrder — el disparador del aviso
        'sms',   # el canal de envío
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
