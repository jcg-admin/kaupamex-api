# Adaptado de Odoo Community `base_install_request/__manifest__.py` (LGPL-3) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Solicitud de activación de módulos',
    'version': '1.0',
    'category': 'Technical',
    'summary': (
        'base_install_request — la ceremonia de pedir y revisar la activación'
        ' de un módulo: dos asistentes y la acción que los abre. La'
        ' instalación en caliente (button_immediate_install) sigue bloqueada,'
        ' con su razón medida y su sucesor en'
        ' wizard/base_module_install_request.py'
    ),
    # `mail` es la dependencia que la referencia declara: la solicitud viaja
    # por plantilla de correo (`MailTemplate` + `email_executor`). `base`
    # aporta `ir.module.module`, `res.users` y el grupo de sistema.
    'depends': [
        'base',
        'mail',
    ],
    'license': 'LGPL-3',
    # Seguridad de la fuente
    # (``odoo19c: addons/base_install_request/__manifest__.py:13-14``),
    # por ``load_data`` en el ciclo de instalación: copia fiel del CSV.
    # Las vistas no se cargan: este árbol no sirve el cliente web.
    'data': [
        'security/ir.model.access.csv',
    ],
    'installable': True,
}
