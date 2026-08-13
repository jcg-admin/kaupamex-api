"""``res.users`` extendido por ``bus`` — un usuario emite en el canal de su partner.

Adaptación de ``addons/bus/models/res_users.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 11 líneas). La referencia declara
``_inherit = ["res.users", "bus.listener.mixin"]`` y redefine
``_bus_channel`` para devolver ``self.partner_id``.

Por qué la delegación importa
=============================

Un usuario y su partner son **la misma persona** para quien recibe la
notificación, pero sólo uno de los dos tiene canal propio. Delegar al partner
hace que un mensaje dirigido "al usuario" y otro dirigido "al partner"
lleguen al **mismo** sitio; sin la delegación, un cliente suscrito al canal
del partner se perdería la mitad.

Es una de las tres delegaciones que hacen útil el recorrido hasta el punto
fijo de ``_bus_send`` — las otras dos son ``ir_attachment`` y
``res_users_settings``.
"""
from addons.bus.models.bus_listener_mixin import register_channel


@register_channel('base.ResUsers')
def user_channel(user, actor=None):
    """El partner del usuario (``_bus_channel`` de la referencia)."""
    return getattr(user, 'partner', None)
