# Adaptado de Odoo Community `http_routing/__manifest__.py` (LGPL-3) —
# atribución y aviso de licencia preservados (DEC-KX-03). La licencia se leyó
# del manifest de la fuente, no de la reputación del árbol:
#   grep -oP "'license'\s*:\s*'\K[^']+" $ODOO19C/addons/http_routing/__manifest__.py
#   -> LGPL-3
# Mecanismo que esa licencia habilita: copia + adaptación con atribución.
{
    'name': 'Enrutado web (slug legible, idioma en la URL)',
    'version': '1.0',
    'category': 'Hidden',
    'summary': (
        'ir.http._slug/_unslug/_unslug_url + el convertidor de ruta y las '
        'utilidades de idioma — el hogar del slug con nombre legible'
    ),
    # `depends` MEDIDO contra los imports reales de este addon. La referencia
    # declara `['web']`; aquí se conserva porque `web` es quien cuelga
    # `is_a_bot` sobre `base.IrHttp` (`addons/web/models/ir_http.py`), que
    # `_match` consulta en su rama /3. `base` entra explícito porque de ahí
    # salen `IrHttp`, `ResLang`, `IrDefault`, `IrTemplateExpressions` y
    # `keep_query`.
    'depends': [
        'base',  # IrHttp, ResLang, IrDefault, IrTemplateExpressions, keep_query
        'web',   # IrHttp.is_a_bot — la rama /3 de `_match`
    ],
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
