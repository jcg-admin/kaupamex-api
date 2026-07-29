"""Derivación de canales — qué puede escuchar cada usuario.

Se mantiene aparte de la vista para que el criterio sea auditable en un solo
sitio: quien emite (``BusListenerMixin``) y quien lee (``bus_poll``) tienen que
coincidir en la clave del canal, y si divergen los mensajes se pierden en
silencio.
"""

#: Prefijo del canal privado de un usuario. Un modelo que emita hacia un usuario
#: concreto debe construir su ``bus_channel_key()`` con esta misma función.
USER_CHANNEL_PREFIX = 'user'


def user_channel(user) -> str:
    """Canal privado del usuario."""
    return f'{USER_CHANNEL_PREFIX}:{user.pk}'


def channels_for_user(user) -> list[str]:
    """Canales que el usuario autenticado puede leer.

    Hoy sólo el suyo. Cuando aparezca un canal compartido (por Company, por
    rol), se añade aquí — y el gate de capacidad de la vista sigue siendo el
    que decide si puede leer algo en absoluto.
    """
    return [user_channel(user)]
