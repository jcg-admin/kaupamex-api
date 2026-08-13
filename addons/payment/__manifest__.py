# Adaptado de Odoo Community `payment/__manifest__.py` (LGPL-3, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Motor de pagos',
    'version': '1.0',
    'category': 'Hidden',
    'summary': (
        'PaymentProvider, PaymentMethod, PaymentToken y PaymentTransaction: '
        'el contrato común que cada proveedor implementa, y su máquina de estados'
    ),
    # `depends` MEDIDO da cinco destinos; se declaran DOS. La referencia
    # declara ['onboarding', 'portal'] — el asistente de alta del proveedor y
    # la vista de cliente. Aquí ninguno se mide: el alta es DRF y la pantalla
    # vive en el repo `ui`.
    #
    # Dos aristas medidas NO se declaran porque invierten la dirección de la
    # referencia, donde `payment` es fundacional y el negocio lo consume:
    #
    #   sale   `payment` importa SaleOrder para conciliar el cobro con su
    #          pedido. En la referencia ese puente es `sale_payment`, un
    #          addon aparte. Registrado, no legitimado — el gate de dirección
    #          (`scripts/check_addon_cycles.py`) es su dueño.
    #   authz  el gate de capacidad de las vistas, no dependencia de datos.
    'depends': [
        'base',  # ResCompany, ResPartner, ResCurrency
        'mail',  # el aviso al comprador del resultado de la transacción
        'bus',   # la notificación del webhook al resto del árbol
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
