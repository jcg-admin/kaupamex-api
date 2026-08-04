"""``ir.attachment`` extendido por ``bus`` — emite en el canal del usuario que actúa.

Adaptación de ``addons/bus/models/ir_attachment.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, 11 líneas): ``_bus_channel`` devuelve
``self.env.user``.

El canal no es un campo del registro
=====================================

Los otros dos delegantes devuelven **un campo del registro** (el partner del
usuario, el usuario de los ajustes). Éste no: devuelve el usuario **que está
actuando**, que no es una propiedad del adjunto — el mismo adjunto notifica a
usuarios distintos según quién lo toque.

La referencia lo resuelve **sin parámetro alguno**, porque el actor viaja en el
entorno (``self.env.user``). Aquí igual: sale de
``orm.environments.get_current_user()``, el eje ``uid`` que el middleware de
``ir_http`` deja fijado antes del despacho.

Hubo una versión que lo recibía como segundo parámetro del resolutor. Cubría
este caso ensanchando el contrato de **todos** los ``_bus_channel``, y con ello
la firma del mixin dejaba de coincidir con la de la referencia. Ver H-API-277.
"""
from addons.bus.models.bus_listener_mixin import register_channel
from orm.environments import get_current_user


@register_channel('base.IrAttachment')
def attachment_channel(attachment):
    """El usuario que actúa (``self.env.user`` de la referencia).

    Devuelve ``None`` fuera de una petición autenticada: sin actor no hay
    canal que resolver, y el mixin cae a emitir en el propio adjunto en vez
    de fallar.
    """
    return get_current_user()
