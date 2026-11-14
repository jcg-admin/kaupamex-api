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
    'application': True,
    'installable': True,
    'auto_install': False,
}
