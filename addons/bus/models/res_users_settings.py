"""``res.users.settings`` extendido por ``bus`` — emite en el canal de su usuario.

Adaptación de ``addons/bus/models/res_users_settings.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 11 líneas): ``_bus_channel`` devuelve
``self.user_id``.

Encadena con ``res_users.py``: los ajustes delegan en el usuario, y el usuario
delega en su partner. El recorrido hasta el **punto fijo** de ``_bus_send``
resuelve los dos saltos sin que quien emite conozca ninguno — que es
exactamente para lo que ese bucle existe.
"""
from addons.bus.models.bus_listener_mixin import register_channel


@register_channel('base.ResUsersSettings')
def settings_channel(settings, actor=None):
    """El usuario dueño de los ajustes (``_bus_channel`` de la referencia)."""
    return getattr(settings, 'user', None)
