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
    # Datos de la fuente (``odoo19c: uom/__manifest__.py:13-18``), por
    # ``load_data`` en el ciclo de instalación, en el mismo orden. Los tres
    # son copia fiel. ``views/uom_uom_views.xml`` no se carga: este árbol no
    # sirve el cliente web, como en el resto de los addons portados.
    'data': [
        'data/uom_data.xml',
        'security/uom_security.xml',
        'security/ir.model.access.csv',
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
