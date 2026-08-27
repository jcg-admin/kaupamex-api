# Adaptado de Odoo Community `project_hr_skills/__manifest__.py`
# (LGPL-3, odoo19c:) — atribución y aviso de licencia preservados
# (DEC-KX-03).
{
    'name': 'Project - Skills',
    'version': '1.0',
    'category': 'Services/Project',
    'summary': 'Project skills',
    'description': """
        Search project tasks according to the assignees' skills
    """,
    # `depends` MEDIDO contra los imports reales de este addon:
    # - project   → destino de la extensión ('project', 'ProjectTask').
    # - hr_skills → HrEmployeeSkill (las habilidades que se exponen).
    # Coincide con la referencia (['project', 'hr_skills']). La extensión
    # sobre res.users va a `base.ResUsers` — `base` es raíz implícita de
    # todo el grafo de manifiestos, no se declara (mismo criterio que el
    # resto de addons que extienden base).
    'depends': [
        'project',
        'hr_skills',
    ],
    # `data` de la referencia (vistas XML) no se porta: backend Django REST
    # sin cliente Odoo.
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': True,
}
