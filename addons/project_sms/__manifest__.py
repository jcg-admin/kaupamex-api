# Adaptado de Odoo Community `project_sms/__manifest__.py` (LGPL-3,
# odoo19c:) — atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Project - SMS',
    'version': '1.1',
    'category': 'Services/Project',
    'summary': 'Send text messages when project/task stage move',
    'description': 'Send text messages when project/task stage move',
    # `depends` MEDIDO contra los imports reales de este addon:
    # - project → ProjectTask (receptores de señal) y ProjectTaskType
    #             (destino de la extensión de campo).
    # - sms     → SmsSms + SmsTemplate (el registro y la plantilla).
    # Coincide con la referencia (['project', 'sms']).
    'depends': [
        'project',
        'sms',
    ],
    # `data` de la referencia (vistas XML + ir.rule de seguridad) no se
    # porta: backend Django REST sin cliente Odoo.
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': True,
}
