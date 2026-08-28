"""Registro de resolutores de audiencia — familia ``mail``.

``mail`` sabe **a quién** notificar sólo para los públicos que él mismo posee
(un usuario por email). Los públicos definidos por un dominio de negocio —"los
compradores de este producto"— los resuelve ese dominio, que **se inscribe**
aquí, igual que cada ``payment_<provider>`` se inscribe en el registro de
gateways (T-033).

La dirección importa: antes ``mail/views.py`` importaba ``sale.SaleOrderLine``
para armar la audiencia, una arista de ``mail`` (profundidad 4 en la
referencia) hacia ``sale`` (profundidad 10). Con el registro, ``sale`` conoce a
``mail`` y no al revés.

Un tipo de destinatario sin resolutor inscrito devuelve audiencia vacía —
fail-closed: no se notifica a nadie por accidente.
"""
import logging

logger = logging.getLogger('apps')

# Poblado por ``register_audience_resolver`` desde el addon dueño del público.
AUDIENCE_RESOLVERS = {}


def register_audience_resolver(recipient_type, resolver):
    """Inscribe el resolutor del público ``recipient_type``.

    ``resolver(**kwargs)`` devuelve un iterable de ``user_id`` (idealmente un
    queryset, para que el conteo no materialice la lista).
    """
    previo = AUDIENCE_RESOLVERS.get(recipient_type)
    if previo is not None and previo is not resolver:
        logger.warning(
            'register_audience_resolver: %s ya estaba inscrito por %s; '
            'lo reemplaza %s',
            recipient_type, getattr(previo, '__module__', previo),
            getattr(resolver, '__module__', resolver),
        )
    AUDIENCE_RESOLVERS[recipient_type] = resolver
    return resolver


def resolve_audience_user_ids(recipient_type, **kwargs):
    """Devuelve el iterable de ``user_id`` del público, o vacío si no hay resolutor."""
    resolver = AUDIENCE_RESOLVERS.get(recipient_type)
    if resolver is None:
        return []
    return resolver(**kwargs)


def count_audience(recipient_type, **kwargs):
    """Cuenta el público sin materializar la lista cuando es un queryset."""
    audience = resolve_audience_user_ids(recipient_type, **kwargs)
    counter = getattr(audience, 'count', None)
    return counter() if callable(counter) else len(list(audience))
