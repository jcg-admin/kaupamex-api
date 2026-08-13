# Adaptado de Odoo Community `payment_custom/__manifest__.py` (LGPL-3, odoo19c:)
# — atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Proveedor de pago: modos manuales',
    'version': '1.0',
    'category': 'Accounting/Payment Providers',
    'summary': 'Transferencia bancaria y otros modos manuales: el pago que un humano confirma',
    # `depends` MEDIDO coincide EXACTO con el de la referencia: un proveedor
    # implementa el contrato de `payment` y no toca nada más.
    'depends': [
        'payment',  # PaymentProvider/PaymentTransaction — el contrato
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
