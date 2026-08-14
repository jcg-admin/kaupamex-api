# Adaptado de Odoo Community `stock/__manifest__.py` (LGPL-3, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Inventario',
    'version': '1.0',
    'category': 'Supply Chain/Inventory',
    'summary': (
        'StockQuant, StockMove y su línea, ubicaciones, almacenes, rutas, '
        'albaranes y sus tipos, lotes y reglas de reabastecimiento'
    ),
    # `depends` MEDIDO da cinco destinos; se declaran TRES. La referencia
    # declara ['product', 'digest'] más `barcodes_gs1_nomenclature`, que este
    # árbol no tiene.
    #
    # La arista `stock → sale` NO se declara: es una inversión. En la
    # referencia el puente es `sale_stock`, un addon aparte que depende de
    # los dos; `stock` nunca mira al pedido. Registrada aquí y en el gate de
    # dirección (`scripts/check_addon_cycles.py`), no legitimada.
    #
    # `authz` es el gate de capacidad de las vistas DRF, no dependencia de
    # datos — tampoco se declara (ver lote 2).
    'depends': [
        'base',     # ResCompany, ResPartner, los mixins
        'product',  # Product — lo que se mueve y se cuenta
        'mail',     # el aviso de reabastecimiento y de albarán listo
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': True,   # módulo vendible del catálogo L0
    'installable': True,
    'auto_install': False,
}
