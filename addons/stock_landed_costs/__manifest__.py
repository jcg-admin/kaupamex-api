# Adaptado de Odoo Community `stock_landed_costs/__manifest__.py` (LGPL-3,
# odoo19c:) — atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Costes en destino',
    'version': '1.0',
    'category': 'Supply Chain/Inventory',
    'summary': (
        'Reparte flete, seguro y aranceles sobre las líneas recibidas, por '
        'peso, volumen, cantidad o importe, y ajusta su valoración'
    ),
    # `depends` MEDIDO da cuatro; la referencia declara ['stock_account'] más
    # `purchase_stock`, que este árbol no tiene. Los otros tres son imports de
    # Python explícitos aquí.
    'depends': [
        'base',           # ResCompany, ResCurrency
        'product',        # Product — el destinatario del reparto
        'stock',          # StockMove — las líneas sobre las que reparte
        'stock_account',  # la capa de valoración que este addon ajusta
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
