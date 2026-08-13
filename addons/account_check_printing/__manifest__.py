# Adaptado de Odoo Community `account_check_printing/__manifest__.py`
# (LGPL-3, odoo19c:) — atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Impresión de cheques',
    'version': '1.0',
    'category': 'Accounting/Accounting',
    'summary': (
        'Numeración y formato del cheque como método de pago: siguiente '
        'folio del diario, importe en letra y su asiento'
    ),
    # `depends` MEDIDO coincide con el de la referencia (['account']) más
    # `base`, que aquí es explícito porque `ResCompany` y `ResPartnerBank`
    # viven allí y el import es de Python, no resuelto por el ORM.
    #
    # Porte PARCIAL declarado: 18 símbolos ausentes (tarea #244) y el
    # `ReportSpec` del cheque sin declarar (tarea #280).
    'depends': [
        'base',     # ResCompany, ResPartnerBank
        'account',  # AccountPayment, AccountJournal — el eje que numera
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
