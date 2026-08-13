# Forma propia: la contraparte de la referencia es propietaria (OEEL-1),
# así que se reimplementa nativa sin copiar código (DEC-KX-03).
{
    'name': 'Mesa de ayuda',
    'version': '1.0',
    'category': 'Services/Helpdesk',
    'summary': (
        'El ticket de soporte con su etapa y su hilo: la atención al '
        'comprador sobre un pedido'
    ),
    # Reimplementación NATIVA: la contraparte `helpdesk` sólo existe en Odoo 19
    # Enterprise y declara `OEEL-1` (medido en odoo19e), así que NO se copia
    # código (DEC-KX-03). El eje es propio y su `depends` es el MEDIDO.
    #
    # `authz` es el gate de capacidad, no dependencia de datos (ver lote 2).
    'depends': [
        'base',  # ResUsers, ResPartner, ResCompany
        'mail',  # MailThread — el hilo del ticket
        'sale',  # SaleOrder — el pedido sobre el que se abre el ticket
    ],
    # Eje propio: sin licencia heredada que declarar (DEC-KX-03).
    'license': 'propio',
    'application': True,
    'installable': True,
    'auto_install': False,
}
