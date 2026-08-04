"""``bus.listener.mixin`` — el punto de extensión del addon ``bus``.

Adaptación de ``addons/bus/models/bus_listener_mixin.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 30 líneas).

Archivo propio, como en la referencia
=====================================

Vivía en ``bus/mixins.py``, agrupado por naturaleza. La referencia tiene **un
archivo por mixin** —``bus_listener_mixin.py``— igual que ``base`` tiene
``image_mixin.py`` y ``avatar_mixin.py``. Se movió aquí para respetar esa
forma. ``bus/mixins.py`` queda como shim reexportador porque **dos migraciones
lo referencian por ruta**; su docstring explica por qué no se borra.

El registro de canales por modelo
=================================

La referencia extiende cinco modelos del núcleo con ``_inherit = [X,
"bus.listener.mixin"]``, y tres de ellos **redefinen** ``_bus_channel`` para
delegar: un adjunto emite en el canal de su usuario, un usuario en el de su
partner, los ajustes de usuario en el de su usuario.

Python no permite reabrir una clase de modelo de Django, así que esa
redefinición se declara en un **registro** ``CHANNEL_RESOLVERS``, poblado por
``register_channel``. Cada extensión conserva **su propio archivo**
(``res_users.py``, ``ir_attachment.py``…), que es lo que la referencia hace;
lo único que cambia es el mecanismo con que se engancha.

Son **30 líneas** en la referencia y es todo el patrón: un modelo que quiera
emitir hereda el mixin y declara cuál es su canal. Aquí es un mixin de Python
plano, no un modelo Django, porque el original tampoco aporta campos — es un
``AbstractModel`` con dos métodos.
"""
from addons.bus.models.bus import BusMessage

#: ``etiqueta de modelo`` → ``fn(registro)`` que devuelve el objeto en cuyo
#: canal emite. Poblado por ``register_channel`` desde un archivo por modelo,
#: igual que la referencia declara un archivo por ``_inherit``.
#:
#: **Un solo parámetro**, como ``def _bus_channel(self)`` de la referencia
#: (``odoo19c: addons/bus/models/bus_listener_mixin.py:29``; idéntico en
#: ``odoo18c: …:24``). Hubo una versión con un segundo parámetro ``actor``,
#: añadido porque el canal de ``ir.attachment`` es ``self.env.user`` y el
#: entorno portado no exponía el usuario actual. Eso cambiaba el contrato de
#: **todos** los resolutores para cubrir la carencia de uno; el actor ahora
#: sale del entorno (``orm.environments.get_current_user``), que es de donde
#: la referencia lo toma. Ver H-API-277.
CHANNEL_RESOLVERS = {}


def register_channel(model_label):
    """Declara el ``_bus_channel`` de un modelo — un archivo por modelo.

    Sustituye al ``_inherit = [X, "bus.listener.mixin"]`` de la referencia con
    su ``_bus_channel`` redefinido, que Python no permite expresar reabriendo
    una clase de Django.
    """
    def decorator(resolver):
        CHANNEL_RESOLVERS[model_label] = resolver
        return resolver
    return decorator


class BusListenerMixin:
    """Permite a un modelo emitir mensajes en su propio canal del bus."""

    def _bus_channel(self):
        """Canal en el que emite este objeto.

        Por defecto, él mismo. Un modelo puede delegar en otro registrando su
        resolutor con ``register_channel`` — ``_bus_send`` recorre la
        delegación hasta el punto fijo, igual que la referencia.
        """
        meta = getattr(self, '_meta', None)
        if meta is not None:
            resolver = CHANNEL_RESOLVERS.get(
                f'{meta.app_label}.{meta.object_name}')
            if resolver is not None:
                return resolver(self) or self
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
        que saberlo. Es el bucle de ``odoo19c:`` (``bus_listener_mixin.py:19``);
        ``odoo18c:`` resuelve con **una sola** llamada, sin punto fijo — cuando
        las poblaciones difieren gobierna 19.

        La comparación es por **igualdad**, no por identidad: la referencia usa
        ``!=`` sobre recordsets, que comparan por contenido. Con ``is not``, un
        resolutor que devuelva un registro equivalente pero otro objeto Python
        (lo normal al leerlo de la base) haría bucle infinito.
        """
        target = self
        while (siguiente := target._bus_channel()) != target:
            target = siguiente
        canal = target.bus_channel_key()
        if subchannel is not None:
            canal = f'{canal}/{subchannel}'
        return BusMessage.sendone(canal, notification_type, message)
