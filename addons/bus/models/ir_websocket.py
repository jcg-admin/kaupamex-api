"""``ir.websocket`` — la política de suscripción a canales.

Adaptación de ``addons/bus/models/ir_websocket.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 83 líneas).

El transporte no; la política sí
================================

DEC-AF-06 descarta el WebSocket: ``pg_notify`` no existe en MariaDB y el bucle
de entrega exigiría ASGI, incompatible con CNST-ARQ-001 (Apache + mod_wsgi).
Esa decisión saca de aquí ``_subscribe``, ``_on_websocket_closed``,
``_serve_ir_websocket`` y ``_authenticate`` — todos hablan con ``wsrequest``.

Pero **dos métodos de este archivo no son transporte**, y son los que deciden
qué ve un cliente. Se portan:

``_build_bus_channel_list`` — a qué se suscribe una sesión
----------------------------------------------------------

A los canales que pide el cliente se **añaden** tres cosas, y las tres
importan:

1. ``broadcast`` — el canal global, siempre;
2. **todos los grupos del usuario** — por eso ``res_groups.py`` declara que un
   grupo es canal: notificar a un grupo llega a sus miembros sin enumerarlos;
3. **el partner del usuario**, sólo si hay sesión — que es el punto fijo al
   que ``res_users.py`` delega.

Es decir: la lista de suscripción y las delegaciones de canal son **el mismo
diseño visto desde los dos lados**. Portar una sin la otra deja mensajes que
se emiten a un canal al que nadie se suscribe.

``_prepare_subscribe_data`` — la validación que evita un cliente mudo
--------------------------------------------------------------------

Dos guardas, y la segunda es la que no se adivina:

- los canales tienen que ser **cadenas** (``ValueError`` si no);
- ``last`` se **acota** contra el último id de la cola: si el cliente manda un
  ``last`` mayor que el máximo existente, se pone a **0**.

Sin ese acotado, un cliente que pide desde un id futuro —tras restaurar una
base, o por un id de otra instancia— no recibiría **nunca** nada, sin error y
sin señal. Volver a 0 hace que relea la ventana reciente.
"""
from addons.bus.models.bus import BusMessage

#: Canal global al que se suscribe toda sesión.
BROADCAST_CHANNEL = 'broadcast'


def build_bus_channel_list(channels, user=None, groups=(), authenticated=True):
    """``_build_bus_channel_list`` — los canales de una sesión.

    Los del cliente más el ``broadcast``, los grupos del usuario y —sólo si
    hay sesión— su partner. Devuelve una lista **sin duplicados y en orden de
    llegada** (la referencia usa ``OrderedSet`` por lo mismo: el orden es
    reproducible y la suscripción no se repite).
    """
    result = list(channels)
    result.append(BROADCAST_CHANNEL)
    result.extend(groups)
    if authenticated and user is not None:
        partner = getattr(user, 'partner', None)
        if partner is not None:
            result.append(partner)

    seen, ordered = set(), []
    for channel in result:
        key = channel if isinstance(channel, str) else id(channel)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(channel)
    return ordered


def prepare_subscribe_data(channels, last, user=None, groups=(),
                           authenticated=True):
    """``_prepare_subscribe_data`` — valida y normaliza lo que manda el cliente.

    Devuelve ``{'channels': [...], 'last': N}``. Ver el docstring del módulo
    sobre por qué acotar ``last`` no es una comprobación de cortesía.
    """
    if not all(isinstance(channel, str) for channel in channels):
        raise ValueError('bus.Bus sólo admite canales de tipo cadena.')
    if last > BusMessage.last_id():
        last = 0
    return {
        'channels': build_bus_channel_list(
            list(channels), user=user, groups=groups,
            authenticated=authenticated),
        'last': last,
    }
