# Adaptado de Odoo Community `project/__manifest__.py` (LGPL-3, odoo19c:)
# — atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Proyectos',
    'version': '1.0',
    'category': 'Services/Project',
    'summary': (
        'Project y ProjectTask con su etapa configurable, el eje de trabajo '
        'que el pedido de servicio consume'
    ),
    # `depends` MEDIDO da sólo ['base'] contra los ocho de la referencia
    # (['analytic', 'base_setup', 'mail', 'portal', 'rating', 'resource',
    # 'web', 'digest'] más `web_tour`). La distancia mide el recorte, no una
    # decisión: `project` es de la Capa 1 de la campaña de cáscaras (tarea
    # #203) y hoy es poco más que sus dos modelos. No se declara lo que el
    # código no usa; el manifiesto crecerá con el porte.
    'depends': [
        'base',  # ResUsers, ResPartner, ResCompany
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': True,
    'installable': True,
    'auto_install': False,
}
