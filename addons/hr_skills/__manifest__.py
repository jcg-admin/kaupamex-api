# Adaptado de Odoo Community `hr_skills/__manifest__.py` (LGPL-3) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Skills Management',
    'version': '1.0',
    'category': 'Human Resources/Employees',
    # `summary` verbatim de la referencia (`odoo19c: addons/hr_skills/
    # __manifest__.py`). Tenía 317 caracteres enumerando los modelos portados,
    # y `IrModule.summary` es `max_length=255`: el `update_module_list` moría
    # con `DataError: value too long`. El detalle del porte es un comentario,
    # no un `summary` — ese campo va a una columna y a la interfaz. Ver
    # :ref:`h-api-750`.
    #
    # Qué porta este addon: hr.skill.type + hr.skill + hr.skill.level +
    # hr.individual.skill.mixin + hr.employee.skill + hr.job.skill +
    # hr.resume.line(.type). Sin vistas XML ni `static` (backend Django REST
    # sin cliente Odoo, fuera del alcance de la API — mismo criterio que
    # `onboarding/__manifest__.py`).
    'summary': 'Manage skills, knowledge and resume of your employees',
    # `depends` MEDIDO contra los imports reales de los modelos portados
    # (HrEmployeeSkill.employee_id → hr.HrEmployee, HrJobSkill.job_id →
    # hr.HrJob, extensiones de hr.employee/hr.employee.public/hr.job/
    # resource.resource), NO copiado de la referencia (que también declara
    # ['hr'] — coincide).  `resource.resource` no se declara aparte: `hr`
    # depende transitivamente de `resource` (`addons/hr/__manifest__.py`),
    # así que el modelo ya está cargado cuando este addon se instala.
    'depends': [
        'hr',  # hr.HrEmployee, hr.HrEmployeePublic, hr.HrJob + resource.
               # ResourceResource (transitivo vía hr → resource)
    ],
    # Licencia de la fuente de la que se adapta este addon, tal como su
    # manifest la declara (DEC-KX-03 punto 1): `hr_skills` en Odoo Community
    # es LGPL-3.
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
