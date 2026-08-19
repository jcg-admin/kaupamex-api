# Adaptado de Odoo `project_stock/__manifest__.py` (LGPL-3,
# odoo-tools@622ddc2a, odoo19c:) — atribución y aviso de licencia
# preservados (DEC-KX-03).
{
    'name': 'Project Stock',
    'version': '1.0',
    'summary': 'Link Stock pickings to Project',
    'category': 'Services/Project',
    # `depends` MEDIDO contra los destinos reales de extensión de este addon
    # (la FK `project` sobre stock.StockPicking; `pickings_of_type` sobre
    # project.Project) — coincide con los dos de la referencia.
    'depends': ['stock', 'project'],
    # `data` (2 XML de vistas) no se porta: cliente web de Odoo, criterio ya
    # establecido en el árbol (hr_timesheet, sale_project).
    'auto_install': True,
    'author': 'Odoo S.A.',
    # Licencia de la fuente de la que se adapta este addon, tal como su
    # manifest la declara (DEC-KX-03 punto 1).
    'license': 'LGPL-3',
}
