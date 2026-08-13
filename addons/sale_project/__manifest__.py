# Adaptado de Odoo Community `sale_project/__manifest__.py` (LGPL-3, odoo19c:)
# — atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Pedido que abre proyecto',
    'version': '1.0',
    'category': 'Sales/Sales',
    'summary': (
        'El pedido de un servicio por proyecto crea su proyecto o su tarea '
        'y devuelve el avance al pedido'
    ),
    # `depends` MEDIDO da tres y la referencia declara ['sale_management',
    # 'sale_service'] más `project_account`, que este árbol no tiene (tarea
    # #199). La divergencia es de HOGAR, como en `sale_margin`: aquí el
    # terminal es la línea de pedido y el proyecto, no la vista de gestión.
    #
    # Porte PARCIAL declarado: `sale_project` es de la Capa 0 (tarea #202).
    'depends': [
        'base',     # ResCompany
        'project',  # Project, ProjectTask — lo que el pedido crea
        'sale',     # SaleOrder — el disparador
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
