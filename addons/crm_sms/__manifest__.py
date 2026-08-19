# Adaptado de Odoo Community `crm_sms/__manifest__.py` (LGPL-3, odoo19c:)
# — atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'SMS in CRM',
    'version': '1.1',
    'category': 'Sales/CRM',
    'summary': 'Add SMS capabilities to CRM',
    # `depends` de la referencia, conservado verbatim: este addon no tiene
    # imports propios que medir (0 archivos de modelos — ver
    # `__init__.py`); el par ['crm', 'sms'] es lo que lo define como
    # puente auto-instalable.
    'depends': ['crm', 'sms'],
    # `data` de la referencia (vistas XML + seguridad) no se porta:
    # backend Django REST sin cliente Odoo.
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': True,
}
