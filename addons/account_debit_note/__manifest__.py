# Adaptado de Odoo Community `account_debit_note/__manifest__.py` (LGPL-3,
# odoo19c:) — atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Notas de débito',
    'version': '1.0',
    'category': 'Accounting/Accounting',
    'summary': (
        'La nota de débito como asiento derivado de una factura: copia sus '
        'líneas, la enlaza al origen y respeta su diario'
    ),
    # `depends` MEDIDO coincide con el de la referencia (['account']) más
    # `base`, explícito porque el import de `ResCompany` es de Python.
    'depends': [
        'base',     # ResCompany
        'account',  # AccountMove y sus líneas — lo que la nota deriva
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
