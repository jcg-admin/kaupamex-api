# Adaptado de Odoo Community `payment_mercado_pago/__manifest__.py` (LGPL-3,
# odoo19c:) — atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Proveedor de pago: Mercado Pago',
    'version': '1.0',
    'category': 'Accounting/Payment Providers',
    'summary': (
        'Mercado Pago — preferencia de pago, webhook de notificación y meses '
        'sin intereses (MSI), el modo de cuota del mercado mexicano'
    ),
    # `depends` MEDIDO da ['payment', 'sale'] y la referencia declara sólo
    # ['payment']. La arista a `sale` NO se declara: viene del cálculo de MSI,
    # que necesita el total del pedido. Es la misma inversión que `payment`
    # registra en su propio manifiesto —el motor de pago mirando al negocio—
    # y su dueño es el gate de dirección, no este `depends`.
    'depends': [
        'payment',  # PaymentProvider/PaymentTransaction — el contrato
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
