# Adaptado de Odoo Community `purchase_stock/__manifest__.py`
# (LGPL-3, odoo19c: addons/purchase_stock/__manifest__.py) — atribución y aviso
# de licencia preservados (DEC-KX-03).
{
    'name': 'Purchase Stock',
    'version': '1.2',
    'category': 'Supply Chain/Purchase',
    'sequence': 60,
    'summary': 'Purchase Orders, Receipts, Vendor Bills for Stock',
    # `depends` MEDIDO contra los imports reales de este addon, no copiado de
    # la referencia. Los cuatro salen de:
    #
    #   base     — apps.get_model('base', 'ResCompany'|'ResPartner'|
    #              'IrModelData') en res_company.py, res_partner.py,
    #              stock_move.py y stock.py
    #   product  — from addons.product.models import ProductSupplierinfo,
    #              ProductTemplate (product.py) + get_model('product', …)
    #   purchase — extend_model('purchase', 'PurchaseOrder'|
    #              'PurchaseOrderLine') en los dos archivos homónimos
    #   stock    — from addons.stock.models.stock_replenish_mixin import … y
    #              from addons.stock.models.stock_rule import Procurement
    #
    # DIVERGENCIA declarada contra la referencia, que declara
    # ['stock_account', 'purchase']:
    #
    #   * `stock_account` NO se declara. Medido: este addon no importa un solo
    #     símbolo suyo, y los cinco archivos que en la fuente lo necesitan
    #     —account_invoice.py, account_move_line.py, report/
    #     stock_valuation_report.py y el eje de valoración de stock_move.py—
    #     están NO PORTADOS, con su bloqueo medido en cada docstring.
    #     Declararlo sería afirmar un enlace que el código no tiene, y el gate
    #     de destinos muertos no puede distinguir eso de un olvido.
    #   * `base`, `product` y `stock` SÍ se declaran aunque la referencia no
    #     los liste: allá llegan transitivamente por `stock_account`; aquí el
    #     import es de Python y tiene que ser explícito.
    'depends': [
        'base',      # ResCompany, ResPartner, IrModelData
        'product',   # ProductTemplate, ProductProduct, ProductSupplierinfo
        'purchase',  # PurchaseOrder, PurchaseOrderLine — el origen
        'stock',     # el almacén, la regla, el movimiento, el punto de pedido
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    # La referencia lo declara `auto_install: True` (se instala solo en cuanto
    # están `stock_account` y `purchase`). Aquí es False: sin ciclo de
    # instalación de addons, `LOCAL_APPS` se autoderiva del grafo de
    # manifiestos (src/config/settings/base.py:152) y la bandera no tiene
    # consumidor. Se conserva la clave para que la divergencia sea visible.
    'auto_install': False,
    # `post_init_hook: _create_buy_rules` de la referencia NO se declara: no
    # hay ganchos de post-instalación en este árbol (medido: 0 hits de
    # `post_init_hook`). Su equivalente —una migración de datos— queda escrito
    # en el docstring de `__init__.py` con su cuerpo listo.
}
