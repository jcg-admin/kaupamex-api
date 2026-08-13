# Adaptado de Odoo Community `mrp_subcontracting/__manifest__.py` (LGPL-3,
# odoo19c:) — atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Subcontratación de fabricación',
    'version': '1.0',
    'category': 'Supply Chain/Manufacturing',
    'summary': (
        'La orden que fabrica un tercero: envía componentes a su ubicación, '
        'recibe el producto terminado y liquida el consumo'
    ),
    # `depends` MEDIDO da cuatro; la referencia declara sólo ['mrp'] porque su
    # ORM resuelve `stock`/`stock_account` de forma transitiva. Aquí los
    # imports son de Python y explícitos.
    'depends': [
        'base',           # ResPartner — el subcontratista
        'mrp',            # MrpProduction, MrpBom — lo que este addon extiende
        'stock',          # la ubicación del tercero y sus movimientos
        'stock_account',  # la valoración del material entregado
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
