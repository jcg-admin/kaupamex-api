# Adaptado de Odoo Community `hr_recruitment_skills/__manifest__.py`
# (LGPL-3, odoo19c:) — atribución y aviso de licencia preservados
# (DEC-KX-03).
{
    'name': 'Recruitment - Skills Management',
    'version': '1.0',
    'category': 'Human Resources/Recruitment',
    'sequence': 270,
    'summary': 'Manage skills of your employees',
    # `depends` MEDIDO contra los imports reales de este addon:
    # - hr_skills      → HrIndividualSkillMixin (base de hr.applicant.skill),
    #                    HrSkill ('hr_skills.HrSkill' en skill_ids).
    # - hr_recruitment → HrApplicant (FK de hr.applicant.skill y destino de
    #                    la extensión), HrRecruitmentStage (action_add_to_job).
    # Coincide con la referencia (['hr_skills', 'hr_recruitment']). La
    # extensión sobre hr.job va al modelo `hr.HrJob` (app `hr`), transitivo
    # vía hr_skills → hr, así que `hr` no se declara aparte (mismo criterio
    # que `hr_skills/__manifest__.py` con `resource`).
    'depends': [
        'hr_skills',
        'hr_recruitment',
    ],
    # `data`/`assets`/`demo` de la referencia (vistas XML, seguridad,
    # static, demo) no se portan: backend Django REST sin cliente Odoo.
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': True,
}
