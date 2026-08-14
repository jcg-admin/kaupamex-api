# Adaptado de Odoo Community `mrp/__manifest__.py` (LGPL-3, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Fabricación',
    'version': '1.0',
    'category': 'Supply Chain/Manufacturing',
    'summary': (
        'Lista de materiales y sus líneas, orden de producción y su consumo '
        'de componentes contra el inventario'
    ),
    # `depends` MEDIDO da cuatro; la referencia declara ['product', 'stock',
    # 'resource']. `resource` NO se mide: allí aporta el calendario de trabajo
    # del centro de producción, que este recorte aún no cablea (el addon
    # `resource` está portado — ver tarea #72 — pero nadie lo consume desde
    # aquí todavía).
    'depends': [
        'base',           # ResCompany, los mixins
        'product',        # Product — el fabricado y sus componentes
        'stock',          # StockMove — el consumo y la entrada a almacén
        'stock_account',  # la valoración de lo fabricado
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': True,   # módulo vendible del catálogo L0
    'installable': True,
    'auto_install': False,
}
