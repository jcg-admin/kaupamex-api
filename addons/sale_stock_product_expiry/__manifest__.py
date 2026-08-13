# Adaptado de Odoo Community `sale_stock_product_expiry/__manifest__.py` (LGPL-3, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Caducidad al entregar',
    'version': '1.0',
    'category': 'Sales/Sales',
    'summary': (
        'Impide entregar un lote caducado desde el pedido y avisa del que '
        'está por caducar'
    ),
    # `depends` MEDIDO da VACÍO y la referencia declara ['sale_stock',
    # 'product_expiry'] — el par que define al puente. El vacío es la señal: el
    # porte del Grupo A (tarea #64) dejó el addon sin importar a ninguno de los
    # dos. Se declaran los de la referencia, que es lo que necesita para existir.
    'depends': [
        'sale_stock',      # el albarán que este addon valida
        'product_expiry',  # las fechas del lote contra las que valida
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
