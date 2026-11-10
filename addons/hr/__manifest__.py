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
        'base',  # TimeStampedModel, _reject_hierarchy_cycle, ResUsers
        'mail',  # MailThread
        # ResourceCalendar (hr.payroll.structure.type) +
        # ResCompany.resource_calendar
        'resource',
    ],
    # Licencia de la fuente de la que se adapta este addon, tal como su
    # manifest
    # la declara (DEC-KX-03 punto 1): `hr` en Odoo Community es LGPL-3.
    'license': 'LGPL-3',
    # Seguridad de la fuente (``odoo19c: hr/__manifest__.py:21-22``), por
    # ``load_data`` en el ciclo de instalación. ``ir.model.access.csv`` es
    # copia fiel sin seis filas cuyo modelo no tiene fila en ``ir.model``:
    # los cuatro asistentes (modelos abstractos de Django, sin tabla) y
    # ``mail.activity.plan[_template]`` (no portados). Las omisiones del XML
    # se declaran en su cabecera.
    'data': [
        'security/hr_security.xml',
        'security/ir.model.access.csv',
    ],
    'application': False,  # corte parcial, no el módulo completo
    'installable': True,
    'auto_install': False,
}
