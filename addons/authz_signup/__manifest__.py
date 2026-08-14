# Adaptado de Odoo Community `auth_signup/__manifest__.py` (LGPL-3, odoo19c:)
# — atribución y aviso de licencia preservados (DEC-KX-03). El renombre
# `auth_*` → `authz_*` es de este árbol; ver tarea #20.
{
    'name': 'Alta de cuenta y restablecimiento',
    'version': '1.0',
    'category': 'Hidden/Tools',
    'summary': (
        'SignupRequest: alta con verificación de correo, reenvío del enlace y '
        'restablecimiento de contraseña por token de un solo uso'
    ),
    # `depends` MEDIDO contra los imports reales. La referencia declara
    # ['base_setup', 'mail', 'web']; de los tres sólo `mail` aplica:
    #
    #   base_setup  hospeda `res.config.settings` (el interruptor "permitir
    #               alta externa"). Aquí eso es un SystemParameter de `base`.
    #   web         es el bundle de assets del formulario. Este monolito
    #               expone el alta como endpoint DRF; la pantalla es de `ui`.
    'depends': [
        'base',                   # ResUsers, ResPartner, SystemParameter (models/*.py)
        'mail',                   # MailTemplate + envío del correo (res_users.py:37-38)
        'authz_password_policy',  # valida la contraseña elegida (controllers/main.py:28)
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
