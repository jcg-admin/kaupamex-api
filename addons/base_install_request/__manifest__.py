# Adaptado de Odoo Community `base_install_request/__manifest__.py` (LGPL-3) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Solicitud de activación de módulos',
    'version': '1.0',
    'category': 'Technical',
    'summary': (
        'base_install_request — la ceremonia de pedir y revisar la activación '
        'de un módulo: dos asistentes y la acción que los abre. La instalación '
        'en caliente (button_immediate_install) sigue bloqueada, con su razón '
        'medida y su sucesor en wizard/base_module_install_request.py'
    ),
    # `mail` es la dependencia que la referencia declara: la solicitud viaja
    # por plantilla de correo (`MailTemplate` + `email_executor`). `base`
    # aporta `ir.module.module`, `res.users` y el grupo de sistema.
    'depends': [
        'base',
        'mail',
    ],
    'license': 'LGPL-3',
    'installable': True,
}
