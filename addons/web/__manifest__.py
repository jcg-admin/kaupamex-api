# Adaptado de Odoo Community `web/__manifest__.py` (LGPL-3, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03). Allí es el cliente
# web entero (2324 archivos, mayoría JS/SCSS); aquí sólo su mitad de
# servidor: sesión, exportación e idioma.
{
    'name': 'Servicios web de sesión y exportación',
    'version': '1.0',
    'category': 'Hidden',
    'summary': (
        'session_info, el árbol de campos exportables, CSVExport/ExcelExport '
        'y BaseDocumentLayout — sin el bundle de assets, que vive en `ui`'
    ),
    # `depends` MEDIDO contra los imports reales; coincide con el de la
    # referencia (['base']) salvo la arista `web → authz`, que no se declara
    # por el mismo criterio que `base_setup`: el gate de capacidad atraviesa
    # toda vista DRF y no es dependencia de datos.
    #
    # Porte PARCIAL declarado: `binary.py` va 4 de 9 símbolos (tarea #216) y
    # el lote de `web` es la Capa 0 de la campaña de cáscaras (tarea #202).
    'depends': [
        'base',  # ResUsers, ResLang, ResCompany, ir.model.fields
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
