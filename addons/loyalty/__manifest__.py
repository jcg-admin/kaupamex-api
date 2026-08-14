# Adaptado de Odoo Community `loyalty/__manifest__.py` (LGPL-3, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Cupones y fidelidad',
    'version': '1.0',
    'category': 'Sales',
    'summary': (
        'LoyaltyProgram, sus reglas y recompensas, y la tarjeta con su saldo '
        'de puntos — el motor de promoción que el pedido consume'
    ),
    # `depends` MEDIDO da tres; la referencia declara ['product', 'portal',
    # 'account'].
    #
    # La arista `loyalty → sale` NO se declara: es una inversión. En la
    # referencia el puente es `sale_loyalty`, un addon aparte que depende de
    # los dos, y `loyalty` nunca mira al pedido. Registrada aquí y en el gate
    # de dirección (`scripts/check_addon_cycles.py`), no legitimada — es la
    # otra mitad de la omisión que `sale` ya declara sobre `sale_loyalty`.
    'depends': [
        'base',  # ResCompany, ResPartner, ResCurrency
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
