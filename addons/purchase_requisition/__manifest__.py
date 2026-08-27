# Adaptado de Odoo Community `purchase_requisition/__manifest__.py`
# (LGPL-3, odoo19c: addons/purchase_requisition/__manifest__.py) — atribución y
# aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Purchase Agreements',
    'version': '0.1',
    'category': 'Supply Chain/Purchase',
    'description': """
This module allows you to manage your Purchase Agreements.
===========================================================

Manage calls for tenders and blanket orders. Calls for tenders are used to get
competing offers from different vendors and select the best ones. Blanket orders
are agreements you have with vendors to benefit from a predetermined pricing.
""",
    # `depends` MEDIDO contra los imports reales de este addon, no copiado de
    # la referencia. Los cinco salen de:
    #
    #   analytic  — from addons.analytic.models.analytic_mixin import
    #               AnalyticMixin (purchase_requisition.py) — es la clase base
    #               real de PurchaseRequisitionLine, ≙ su `_inherit`
    #   base      — from addons.base.models import IrSequence,
    #               TimeStampedModel; y las FK a base.ResPartner /
    #               base.ResCompany / base.ResCurrency
    #   product   — FK a product.ProductProduct y extend_model sobre
    #               product.ProductSupplierinfo
    #   purchase  — extend_model('purchase', 'PurchaseOrder'|
    #               'PurchaseOrderLine') y get_model('purchase',
    #               'PurchaseOrderLine')
    #   uom       — FK a uom.Uom (PurchaseRequisitionLine.product_uom)
    #
    # DIVERGENCIA declarada: la referencia declara sólo ['purchase'], porque
    # allá `analytic`, `base`, `product` y `uom` llegan transitivamente. Aquí
    # el import es de Python y tiene que ser explícito.
    #
    # `mail` NO se declara pese a que `purchase.requisition` lleve
    # `_inherit = ['mail.thread', 'mail.activity.mixin']`: la herencia no se
    # porta (D-1 de models/purchase_requisition.py) y este addon no importa un
    # solo símbolo de `mail`. Declararlo afirmaría un enlace inexistente.
    'depends': [
        'analytic',  # AnalyticMixin — el `_inherit` de la línea
        'base',      # IrSequence, ResPartner, ResCompany, ResCurrency
        'product',   # ProductProduct, ProductSupplierinfo
        'purchase',  # PurchaseOrder, PurchaseOrderLine — el destino
        'uom',       # Uom — la unidad de la línea
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
