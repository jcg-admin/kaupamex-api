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
    # Seguridad de la fuente (``odoo19c: sales_team/__manifest__.py``), por
    # ``load_data`` en el ciclo de instalación, en el mismo orden. Copia fiel;
    # las omisiones del XML se declaran en su cabecera.
    # ``data/crm_team_data.xml`` (los tres equipos de la fuente) es la
    # unidad ``sales-team-data-0397``;
    # las vistas no se cargan: este árbol no sirve el cliente web.
    'data': [
        'security/sales_team_security.xml',
        'security/ir.model.access.csv',
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
