# Adaptado de Odoo Community `auth_totp_mail/__manifest__.py` (LGPL-3) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Invitación 2FA por correo',
    'version': '1.0',
    'category': 'Extra Tools',
    'summary': 'Código 2FA por correo, invitación a activar 2FA y '
               'notificaciones de seguridad',
    # Igual que la referencia: ['auth_totp', 'mail'] → aquí con el prefijo
    # de la familia. auto_install fiel: aparece solo en cuanto sus dos lados
    # existen (es el mecanismo que resuelve ModuleGraph.auto_installable).
    'depends': [
        'authz_totp',
        'mail',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
}
