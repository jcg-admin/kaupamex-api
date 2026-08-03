# Adaptado de Odoo Community `hr/__manifest__.py` (LGPL-3) — atribución y
# aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Empleados (núcleo: departamentos y puestos)',
    'version': '1.0',
    'category': 'Human Resources',
    'summary': 'hr.department + hr.job — sin hr.employee (cierre parcial)',
    # `depends` MEDIDO contra los imports reales de HrDepartment/HrJob, no
    # copiado de la referencia (que declara base_setup/digest/phone_validation/
    # resource_mail/web — deps de la familia hr COMPLETA, no de este corte).
    'depends': [
        'base',      # TimeStampedModel, _reject_hierarchy_cycle, ResUsers
        'mail',      # MailThread
        'platform',  # Company (D-2), Subsidiary
    ],
    # Licencia de la fuente de la que se adapta este addon, tal como su manifest
    # la declara (DEC-KX-03 punto 1): `hr` en Odoo Community es LGPL-3.
    'license': 'LGPL-3',
    'application': False,  # corte parcial, no el módulo completo
    'installable': True,
    'auto_install': False,
}
