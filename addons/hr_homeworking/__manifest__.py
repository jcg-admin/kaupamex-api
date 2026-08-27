# Adaptado de Odoo `hr_homeworking/__manifest__.py` (LGPL-3,
# odoo-tools@622ddc2a, odoo19c:) — atribución y aviso de licencia
# preservados (DEC-KX-03).
{
    # `name` verbatim de la fuente (odoo19c: hr_homeworking/__manifest__.py:4).
    'name': 'Remote Work',
    'version': '2.0',
    'category': 'Human Resources/Remote Work',
    # `depends` MEDIDO contra los imports reales de este addon, no copiado a
    # ciegas de la referencia (que declara sólo ['hr']): además de los
    # modelos de `hr` (hr.employee, hr.employee.public, hr.work.location),
    # este addon cuelga extensiones DIRECTAMENTE sobre `base.ResUsers` y
    # `base.ResPartner` (res_users.py / res_partner.py importan
    # addons.base.models), así que `base` se declara explícito aunque `hr`
    # ya lo arrastre transitivamente.
    'depends': [
        'hr',    # HrEmployee, HrEmployeePublic, HrWorkLocation
        'base',  # ResUsers, ResPartner (extensiones directas)
    ],
    # `data`/`assets` de la referencia (security XML/CSV, vistas, JS) son
    # capa de cliente Odoo — sin equivalente en este stack (DRF headless).
    # Licencia de la fuente, tal como su manifest la declara (DEC-KX-03
    # punto 1): `hr_homeworking` en Odoo Community es LGPL-3.
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    # `auto_install: True` en la referencia (se activa con `hr`). Aquí no
    # hay instalador de módulos en caliente — el alta es INSTALLED_APPS.
    'auto_install': False,
    'author': 'Odoo S.A.',
}
