# Adaptado de Odoo Community `html_builder/__manifest__.py` (LGPL-3, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03). La licencia se leyó
# del manifiesto de la fuente, no de la reputación del árbol:
#   grep -oP "'license'\s*:\s*'\K[^']+" $ODOO19C/addons/html_builder/__manifest__.py
# Mecanismo que esa licencia habilita: copia + adaptación con atribución.
{
    'name': 'HTML Builder',
    'summary': 'Generic html builder',
    'description': """
    This addon contains a generic html builder application. It is designed to be
    used by the website builder and mass mailing editor.
    """,
    'author': 'Odoo S.A.',
    'category': 'Uncategorized',
    'version': '0.1',
    # `depends` verbatim de la referencia. Los tres se conservan aunque este
    # addon no tenga código propio: el grafo de manifiestos es lo que fija el
    # orden de carga, y quien dependa de `html_builder` hereda por él la
    # garantía de que `html_editor` ya está.
    #
    # - `base`        — la raíz de todo addon
    # - `html_editor` — el editor sobre el que este constructor opera; es
    #                   quien sirve sus formas SVG desde
    #                   `/html_editor/shape/html_builder/...`
    # - `mail`        — la referencia lo declara con su motivo escrito
    #                   ("we need to use the defineMailModel helper"), que es
    #                   una necesidad de su lado JS
    'depends': [
        'base',
        'html_editor',
        'mail',
    ],
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
    # La referencia declara aquí un bloque `assets` con nueve bundles de JS y
    # SCSS — la práctica totalidad de su manifiesto. NO tiene contraparte
    # aquí: el constructor es un componente de React y vive en `kaupamex-ui`,
    # empaquetado por webpack. Ver el docstring de `__init__.py`.
}
