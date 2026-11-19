# Adaptado de Odoo Community `purchase/__manifest__.py` (LGPL-3, odoo19c:)
# — atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Compras',
    'version': '1.0',
    'category': 'Supply Chain/Purchase',
    'summary': (
        'PurchaseOrder y sus líneas: la solicitud al proveedor, su '
        'confirmación y la recepción que la cierra'
    ),
    # `depends` MEDIDO da tres y la referencia declara sólo ['account'], que
    # aquí NO se mide: la factura de proveedor todavía no está cableada al
    # libro. No se declara `account` porque sería afirmar un enlace que el
    # código no tiene y el gate de destinos muertos no puede distinguir de un
    # olvido; el porte es de la Capa 1 (tarea #203).
    'depends': [
        # La fuente declara sólo `account` y recibe el resto transitivamente;
        # aquí cada import directo se declara, como en `sale`.
        'account',  # account.document.import.mixin de la orden
        'analytic',  # analytic.mixin de la línea
        'base',  # ResPartner — el proveedor
        'base_setup',  # los ajustes de compra por empresa
        'mail',  # mail.thread y mail.activity.mixin del _inherit de la orden
        'portal',  # portal.mixin de la orden
        'product',  # Product — lo que se compra
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    # Seguridad de la fuente (``odoo19c: purchase/__manifest__.py:12-14``).
    # El XML declara sus tres omisiones en la cabecera; el CSV es copia fiel
    # sin 7 filas cuyo modelo no tiene puerto ni fila en ``ir.model``
    # (``purchase.bill.line.match``, ``bill.to.po.wizard``,
    # ``purchase.bill.union``, ``purchase.report``). Las de
    # ``product.supplierinfo`` y ``product.pricelist.item`` cargan desde
    # ``product-model-headers-0122``, y la de ``account.analytic.line`` desde
    # ``analytic-model-headers-0121``.
    # Diseño: ``designs/purchase-security.md``.
    'data': [
        'security/purchase_security.xml',
        'security/ir.model.access.csv',
    ],
    'application': True,
    'installable': True,
    'auto_install': False,
}
