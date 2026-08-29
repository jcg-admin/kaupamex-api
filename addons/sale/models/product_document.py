"""Lo que ``sale`` añade al documento de producto — ≙ ``_inherit``.

Origen: ``odoo19c: sale/models/product_document.py`` (LGPL-3 según su
``__manifest__.py``: copia + adaptación con atribución).

Un solo símbolo, y es un campo: ``attached_on_sale`` (``:9-24``). Decide **en
qué momento de la venta** el documento se comparte con el cliente: nunca, ya
desde el presupuesto, o sólo al confirmar el pedido. La ficha técnica quiere lo
primero; el manual de un producto digital, lo segundo.

Sus dos atributos que no son la enumeración:

``required=True`` (``:14``)
    Aquí ``blank=False`` — un ``CharField`` con ``default`` no acepta vacío en
    la validación de Django, que es lo que ``required`` significa en la fuente.

``groups='sales_team.group_sale_salesman'`` (``:24``)
    La fuente restringe **la lectura del campo** al grupo de ventas. Este árbol
    no tiene ``groups=`` en el campo: la restricción se aplica por capacidad en
    la vista DRF (DEC-11, ``HasCapability`` fail-closed), que es donde el dato
    sale al cliente. Es divergencia de mecanismo, no símbolo omitido, y se
    declara aquí para que el serializer que lo exponga sepa que hereda una
    restricción: :data:`ATTACHED_ON_SALE_GROUP` nombra el grupo de la fuente.
"""
import fields

from orm.model_classes import extend_model

#: ≙ ``('hidden', "Hidden")`` (``odoo19c: :11``) — el documento no viaja al
#: cliente. Es el valor por omisión.
ATTACHED_ON_SALE_HIDDEN = 'hidden'

#: ≙ ``('quotation', "On quote")`` (``odoo19c: :12``) — accesible desde el
#: presupuesto, antes de confirmar.
ATTACHED_ON_SALE_QUOTATION = 'quotation'

#: ≙ ``('sale_order', "On confirmed order")`` (``odoo19c: :13``) — sólo al
#: confirmar el pedido.
ATTACHED_ON_SALE_ORDER = 'sale_order'

#: ≙ el ``selection`` completo (``odoo19c: :10-14``). Los **valores** son
#: idénticos a los de la fuente; las etiquetas van en español.
ATTACHED_ON_SALE_CHOICES = [
    (ATTACHED_ON_SALE_HIDDEN, 'Oculto'),
    (ATTACHED_ON_SALE_QUOTATION, 'En el presupuesto'),
    (ATTACHED_ON_SALE_ORDER, 'En el pedido confirmado'),
]

#: ≙ ``groups='sales_team.group_sale_salesman'`` (``odoo19c: :24``). Ver la
#: divergencia de mecanismo declarada en la cabecera: aquí lo aplica la
#: capacidad de la vista, no el campo, y éste es el nombre que la fuente usa.
ATTACHED_ON_SALE_GROUP = 'sales_team.group_sale_salesman'


def apply_sale_product_document_extensions():
    """Cuelga ``attached_on_sale`` sobre ``product.document``.

    La invoca ``SaleConfig.ready()``. Su DDL lo emite
    ``product/migrations/0012``: la columna la aporta ``sale`` y el modelo es de
    la app ``product``.
    """
    extend_model(
        'product', 'ProductDocument',
        campos={
            'attached_on_sale': fields.Selection(
                max_length=16, choices=ATTACHED_ON_SALE_CHOICES,
                default=ATTACHED_ON_SALE_HIDDEN, blank=False,
                verbose_name='Venta: visible en',
                help_text='Odoo attached_on_sale ("Sale : Visible at"). '
                          'Permite compartir el documento con el cliente '
                          'dentro de una venta. En el presupuesto: se envía y '
                          'queda accesible en cualquier momento — útil para '
                          'fichas de producto. En el pedido confirmado: se '
                          'envía al confirmar — útil para manuales o contenido '
                          'digital comprado.',
            ),
        },
    )
