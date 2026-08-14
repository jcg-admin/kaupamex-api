# Adaptado de Odoo Community `payment_stripe/__manifest__.py` (LGPL-3, odoo19c:)
# — atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Proveedor de pago: Stripe',
    'version': '1.0',
    'category': 'Accounting/Payment Providers',
    'summary': 'Stripe — Payment Intents, webhook firmado y tokenización de la tarjeta',
    # `depends` MEDIDO coincide EXACTO con el de la referencia: un proveedor
    # implementa el contrato de `payment` y no toca nada más.
    #
    # Porte PARCIAL declarado: 7 archivos con 60 símbolos ausentes; el lote
    # es la tarea #218, dentro de la Capa 0 de la campaña (#202).
    'depends': [
        'payment',  # PaymentProvider/PaymentTransaction — el contrato
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
