# Adaptado de Odoo `project_todo/__manifest__.py` (LGPL-3, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'To-Do',
    'version': '1.0',
    'category': 'Productivity/To-Do',
    'summary': 'Organize your work with memos and to-do lists',
    'sequence': 260,
    # `depends` MEDIDO contra los imports reales de este addon:
    # - project → destino de la extensión ('project', 'ProjectTask') y origen
    #   de `ProjectTask` en el asistente.
    # - mail    → `MailActivity` y su `_default_activity_type_for_model` en
    #   `wizard/mail_activity_todo_create.py`.
    # La referencia declara sólo ['project'] y recibe `mail` por transitividad
    # (su `project` depende de `mail`); aquí se declara explícito porque el
    # import es de Python, mismo criterio que `account_debit_note` con `base`.
    'depends': [
        'project',
        'mail',
    ],
    'auto_install': True,
    # `data` (6 XML: seguridad, plantilla QWeb de bienvenida, vistas, menús y
    # el formulario del asistente) no se porta: capa del cliente web de Odoo y
    # ACL de modelo — ver el docstring de `__init__.py` para el desenlace de
    # cada uno.
    'installable': True,
    'application': True,
    # `post_init_hook: _todo_post_init` de la referencia NO se porta — su
    # cadena está bloqueada por el compilador QWeb y por `share`, que aquí es
    # una property y no una columna. Ver `__init__.py` y `models/res_users.py`.
    'author': 'Odoo S.A.',
    # Licencia de la fuente de la que se adapta este addon, tal como su
    # manifest la declara (DEC-KX-03 punto 1).
    'license': 'LGPL-3',
}
