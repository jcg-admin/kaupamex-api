"""``BusListenerMixin`` — el punto de extensión del addon ``bus``.

Adaptación de ``bus.listener.mixin`` (``bus/models/bus_listener_mixin.py``).
En la referencia son **30 líneas** y es todo el patrón: un modelo que quiera
emitir hereda el mixin y declara cuál es su canal. Aquí es un mixin de Python
plano, no un modelo Django, porque el original tampoco aporta campos — es un
``AbstractModel`` con dos métodos.
"""
from addons.bus.models import BusMessage


class BusListenerMixin:
    """Permite a un modelo emitir mensajes en su propio canal del bus."""

    def _bus_channel(self):
        """Canal en el que emite este objeto.

        Por defecto, él mismo. Un modelo puede delegar en otro devolviéndolo
        aquí — ``_bus_send`` recorre la delegación hasta el punto fijo, igual
        que la referencia.
        """
        return self

    def bus_channel_key(self) -> str:
        """Clave estable del canal.

        La referencia serializa el propio registro (y lo prefija con el nombre
        de la base). Un modelo que herede el mixin sobreescribe esto con algo
        que **no sea adivinable** por un tercero: es la propiedad de seguridad
        que la referencia señala al advertir contra el uso directo de
        ``_sendone``.
        """
        raise NotImplementedError(
            f'{type(self).__name__} hereda BusListenerMixin y debe declarar '
            f'bus_channel_key()'
        )

    def _bus_send(self, notification_type: str, message, *, subchannel=None):
        """Encola una notificación en el canal de este objeto.

        Recorre ``_bus_channel()`` hasta el punto fijo antes de emitir, de modo
        que un objeto puede delegar su canal en otro sin que quien emite tenga
        que saberlo.
        """
        target = self
        while (siguiente := target._bus_channel()) is not target:
            target = siguiente
        canal = target.bus_channel_key()
        if subchannel is not None:
            canal = f'{canal}/{subchannel}'
        return BusMessage.sendone(canal, notification_type, message)
