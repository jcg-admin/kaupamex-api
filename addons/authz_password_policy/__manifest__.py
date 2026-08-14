# Adaptado de Odoo Community `auth_password_policy/__manifest__.py` (LGPL-3,
# odoo19c:) — atribución y aviso de licencia preservados (DEC-KX-03). El
# renombre `auth_*` → `authz_*` es de este árbol; ver tarea #20.
{
    'name': 'Política de contraseñas',
    'version': '1.0',
    'category': 'Hidden/Tools',
    'summary': (
        'ConfigurablePasswordPolicyValidator: longitud y complejidad mínimas '
        'configurables por SystemParameter, cableado a AUTH_PASSWORD_VALIDATORS'
    ),
    # `depends` MEDIDO contra los imports reales (`validators.py:22`,
    # `data.py:17`). La referencia declara ['base_setup', 'web']; ninguno
    # aplica aquí:
    #
    #   base_setup  hospeda `res.config.settings`, la UI de ajustes. Aquí la
    #               política se lee de SystemParameter, que vive en `base`.
    #   web         es el bundle de assets JS del medidor de fuerza. Este
    #               monolito no sirve esa UI (la sirve `ui`, otro repo).
    'depends': [
        'base',  # SystemParameter (los umbrales) + ResUsers
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
