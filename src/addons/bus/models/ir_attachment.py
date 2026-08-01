"""``ir.attachment`` extendido por ``bus`` — emite en el canal del usuario que actúa.

Adaptación de ``addons/bus/models/ir_attachment.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 11 líneas): ``_bus_channel`` devuelve
``self.env.user``.

El caso que obligó a pasar el actor
===================================

Los otros dos delegantes devuelven **un campo del registro** (el partner del
usuario, el usuario de los ajustes). Éste no: devuelve el usuario **que está
actuando**, que no es una propiedad del adjunto — el mismo adjunto notifica a
usuarios distintos según quién lo toque.

Por eso el protocolo de ``register_channel`` recibe ``(registro, actor)``. Sin
ese segundo parámetro este archivo no se podría portar y habría que declararlo
"no aplica", que es lo que H-API-134 prohíbe.
"""
from addons.bus.models.bus_listener_mixin import register_channel


@register_channel('base.IrAttachment')
def attachment_channel(attachment, actor=None):
    """El usuario que actúa (``self.env.user`` de la referencia).

    Devuelve ``None`` si no se pasó actor: sin él no hay canal que resolver, y
    el mixin cae a emitir en el propio adjunto en vez de fallar.
    """
    return actor
