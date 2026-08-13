# Adaptado de Odoo Community `uom/__manifest__.py` (LGPL-3, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Unidades de medida',
    'version': '1.0',
    'category': 'Sales/Sales',
    'summary': (
        'Uom: la unidad, su factor contra la de referencia de su categoría y '
        'la conversión entre unidades de la misma categoría'
    ),
    # `depends` MEDIDO coincide EXACTO con el de la referencia (['base']).
    'depends': [
        'base',  # ResCompany, DecimalPrecision, los mixins
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
