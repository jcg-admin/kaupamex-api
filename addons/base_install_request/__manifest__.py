# Adaptado de Odoo Community `base_install_request/__manifest__.py` (LGPL-3) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Solicitud de instalación de módulos (frontera declarada)',
    'version': '1.0',
    'category': 'Technical',
    'summary': (
        'base_install_request — BLOQUEADO por completo: ceremonia alrededor '
        'de la instalación en runtime que base_import_module ya declara '
        'fuera de alcance. Ver models/base_module_install_request.py'
    ),
    # La referencia declara `depends: ['mail']` — allá notifica admins por
    # plantilla de correo. Aquí el addon no declara modelos ni importa nada:
    # es la frontera documentada. `base` como mínimo común del árbol.
    'depends': [
        'base',
    ],
    'license': 'LGPL-3',
    'installable': True,
}
