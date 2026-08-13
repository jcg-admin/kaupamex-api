# Adaptado de Odoo Community `base_vat/__manifest__.py` (LGPL-3, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Validación de identificador fiscal',
    'version': '1.0',
    'category': 'Accounting/Accounting',
    'summary': (
        'Validador por país del identificador fiscal de ResPartner — en '
        'México, el RFC con su dígito verificador'
    ),
    # `depends` MEDIDO contra los imports reales. La referencia declara
    # ['account'] porque allí el campo `vat` se valida al facturar y su vista
    # cuelga del módulo contable. Aquí el terminal es `ResPartner`, que vive
    # en `base`: el addon sólo le cuelga su validador, sin tocar el libro.
    'depends': [
        'base',  # ResPartner, ResCountry — el modelo que este addon valida
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
