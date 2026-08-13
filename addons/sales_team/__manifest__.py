# Adaptado de Odoo Community `sales_team/__manifest__.py` (LGPL-3, odoo19c:)
# — atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Equipos de venta',
    'version': '1.0',
    'category': 'Sales/Sales',
    'summary': (
        'CrmTeam y su asignación de miembros: el equipo al que pertenece un '
        'pedido o una oportunidad'
    ),
    # `depends` MEDIDO da sólo ['base'] y la referencia declara ['base',
    # 'mail']. Se declara `mail` por fidelidad al encuadre: allí el equipo
    # hereda el hilo de mensajes. Aquí el import todavía no existe — porte
    # parcial, sin sucesor propio porque el addon entero es de la Capa 1
    # (tarea #203).
    'depends': [
        'base',  # ResUsers, ResCompany
        'mail',  # MailThread — el hilo del equipo (fidelidad a la ref)
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
