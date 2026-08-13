# Adaptado de Odoo Community `payment_aps/__manifest__.py` (LGPL-3, odoo19c:)
# — atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Proveedor de pago: Amazon Payment Services',
    'version': '1.0',
    'category': 'Accounting/Payment Providers',
    'summary': 'APS — el proveedor de la región MENA, con su firma SHA por petición',
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
