# Adaptado de Odoo Community `account_payment/__manifest__.py` (LGPL-3,
# odoo19c:) — atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Pago en línea de facturas',
    'version': '1.0',
    'category': 'Accounting/Accounting',
    'summary': (
        'El puente entre la transacción del proveedor de pago y el asiento: '
        'concilia el cobro con la factura que lo originó'
    ),
    # `depends` MEDIDO coincide EXACTO con el de la referencia.
    #
    # Porte PARCIAL declarado: 46 símbolos ausentes (tarea #244).
    'depends': [
        'account',  # AccountMove, AccountPayment — el lado del libro
        'payment',  # PaymentTransaction — el lado del proveedor
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
