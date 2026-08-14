# Adaptado de Odoo Community `stock_account/__manifest__.py` (LGPL-3,
# odoo19c:) — atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Valoración de inventario',
    'version': '1.0',
    'category': 'Supply Chain/Inventory',
    'summary': (
        'El puente entre el movimiento de stock y el libro: coste estándar o '
        'promedio, capa de valoración y su asiento'
    ),
    # `depends` MEDIDO da tres; la referencia declara ['stock', 'account'].
    # `account` NO se mide hoy porque el asiento de valoración todavía no está
    # cableado al libro — el addon calcula la capa y no la contabiliza. Se
    # declara igual, por fidelidad al encuadre de la referencia: sin `account`
    # este addon no tiene razón de existir.
    'depends': [
        'base',     # ResCompany — la política de valoración es por empresa
        'product',  # ProductCategory — donde vive el método de coste
        'stock',    # StockMove, StockQuant — lo que se valora
        'account',  # AccountMove — el destino del asiento de valoración
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
