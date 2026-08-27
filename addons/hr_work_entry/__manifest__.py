# Adaptado de Odoo Community `hr_work_entry/__manifest__.py` (LGPL-3) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Work Entries',
    'version': '1.0',
    'category': 'Human Resources/Employees',
    'sequence': 39,
    'summary': 'Manage work entries',
    # `depends` MEDIDO contra los imports reales de este addon, no copiado.
    # La referencia declara SOLO `['hr']` (manifest multilínea, `:9-11`) —
    # allá `hr` arrastra `resource` y `base` transitivamente. Aquí los tres se
    # declaran explícitos porque los modelos/extensiones de este addon los
    # importan directo:
    'depends': [
        'hr',        # HrEmployee, HrVersion (FKs + extensiones)
        'resource',  # ResourceCalendar{,Attendance,Leaves} (extensiones)
        'base',      # TimeStampedModel, ResUsers, ResCompany, ResCountry
    ],
    # Licencia de la fuente de la que se adapta este addon, tal como su
    # manifest la declara (DEC-KX-03 punto 1): LGPL-3.
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
