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
        'hr',  # HrEmployee, HrVersion (FKs + extensiones)
        'resource',  # ResourceCalendar{,Attendance,Leaves} (extensiones)
        'base',  # TimeStampedModel, ResUsers, ResCompany, ResCountry
    ],
    # Licencia de la fuente de la que se adapta este addon, tal como su
    # manifest la declara (DEC-KX-03 punto 1): LGPL-3.
    'license': 'LGPL-3',
    # Seguridad de la fuente
    # (``odoo19c: hr_work_entry/__manifest__.py:13-14``), por ``load_data``
    # en el ciclo de instalación y en el mismo orden. El CSV es copia fiel
    # sin la fila de ``hr.work.entry.regeneration.wizard``: es un
    # ``TransientModel`` abstracto, sin fila en ``ir.model``. La omisión del
    # XML se declara en su cabecera. ``data/*.xml`` es la unidad
    # ``hr-work-entry-data-0397``; las vistas no se cargan.
    'data': [
        'security/hr_work_entry_security.xml',
        'security/ir.model.access.csv',
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
}
