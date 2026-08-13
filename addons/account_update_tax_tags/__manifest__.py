# Adaptado de Odoo Community `account_update_tax_tags/__manifest__.py`
# (LGPL-3, odoo19c:) — atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Actualizar etiquetas de impuesto',
    'version': '1.0',
    'category': 'Accounting/Accounting',
    'summary': (
        'Permite reasignar la etiqueta fiscal de asientos ya registrados '
        'cuando una localización cambia su mapeo de casillas'
    ),
    # `depends` MEDIDO coincide EXACTO con el de la referencia (['account']).
    'depends': [
        'account',  # AccountMoveLine, AccountAccountTag — lo que reetiqueta
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
