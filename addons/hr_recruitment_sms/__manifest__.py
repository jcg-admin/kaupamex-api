# Adaptado de Odoo Community `hr_recruitment_sms/__manifest__.py`
# (LGPL-3, odoo19c:) — atribución y aviso de licencia preservados
# (DEC-KX-03).
{
    'name': 'Recruitment - SMS',
    'version': '1.0',
    'summary': 'Mass mailing sms to job applicants',
    'description': 'Mass mailing sms to job applicants',
    'category': 'Human Resources/Recruitment',
    # `depends` MEDIDO contra los imports reales de este addon:
    # - hr_recruitment → destino de la extensión ('hr_recruitment',
    #                    'HrApplicant').
    # - sms            → SmsSms (el registro de envío que materializa el
    #                    composer) y SmsTemplate.
    # Coincide con la referencia (['hr_recruitment', 'sms']).
    'depends': [
        'hr_recruitment',
        'sms',
    ],
    # `data` de la referencia (vistas XML) no se porta: backend Django REST
    # sin cliente Odoo.
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': True,
}
