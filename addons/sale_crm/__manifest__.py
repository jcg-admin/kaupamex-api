# Adaptado de Odoo Community `sale_crm/__manifest__.py` (LGPL-3, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Oportunidad a cotización',
    'version': '1.0',
    'category': 'Sales/Sales',
    'summary': (
        'Convierte la oportunidad de CRM en pedido y devuelve el importe '
        'ganado a la oportunidad de origen'
    ),
    # `depends` MEDIDO coincide con el de la referencia (['sale', 'crm']) más
    # `base`, explícito aquí porque el import es de Python.
    'depends': [
        'base',  # ResCompany, ResUsers
        'crm',   # CrmLead — el origen
        'sale',  # SaleOrder — el destino
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
