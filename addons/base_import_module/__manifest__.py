# Adaptado de Odoo Community `base_import_module/__manifest__.py` (LGPL-3) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Importación de módulos en runtime (frontera declarada)',
    'version': '1.0',
    'category': 'Technical',
    'summary': (
        'base_import_module — BLOQUEADO por completo: instalar un addon aquí '
        'es INSTALLED_APPS + migrate en deploy, no una acción de runtime. '
        'Ver models/base_import_module.py'
    ),
    # La referencia declara `depends: ['web']` — allá el addon sube el ZIP por
    # el cliente web. Aquí el addon no declara modelos ni importa nada: es la
    # frontera documentada. `base` se declara como mínimo común del árbol.
    'depends': [
        'base',
    ],
    'license': 'LGPL-3',
    # Seguridad de la fuente
    # (``odoo19c: addons/base_import_module/__manifest__.py:16-17``),
    # por ``load_data`` en el ciclo de instalación: copia fiel del CSV.
    # Las vistas no se cargan: este árbol no sirve el cliente web.
    'data': [
        'security/ir.model.access.csv',
    ],
    'installable': True,
}
