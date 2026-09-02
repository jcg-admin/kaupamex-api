"""``ir.websocket`` extendido por ``html_editor`` — el canal de coedición.

Adaptación de ``odoo19c: addons/html_editor/models/ir_websocket.py``
(41 líneas, LGPL-3 — copia + adaptación con atribución, DEC-KX-03).

**2 símbolos en la fuente, 2 portados, 0 ausentes.** La clase ``IrWebsocket``
y su método ``_build_bus_channel_list``.

Qué hace, y por qué es una guarda de seguridad y no una conveniencia
====================================================================

Cuando dos personas editan el mismo campo HTML a la vez, sus pasos viajan por
un canal del bus. Si el cliente pudiera suscribirse a ``editor_collaboration:
res.partner:comment:42`` sin más, **leería las ediciones de un registro que no
puede ver**: el canal transporta el contenido del campo.

Este archivo es lo que lo impide. Reconoce el patrón del canal, resuelve el
registro y **sólo entonces** añade la suscripción, tras comprobar cuatro cosas
en el orden de la fuente: que el usuario no sea público, que el registro
exista, que pueda leerlo y escribirlo, y que pueda leer y escribir **ese
campo** en concreto. Un canal que no pase el filtro se descarta en silencio
(``continue``), que es lo que la fuente hace: fallar ahí delataría la
existencia del registro.

Qué pieza de este stack cubre cada delegación de la fuente
==========================================================

===============================  =====================================
Fuente delega en                 Aquí lo cubre
===============================  =====================================
``re`` (el patrón del canal)     **cpython** — el mismo patrón, verbatim
``self.env[model].browse([id])`` **django** — ``apps.get_model`` por el
                                 registro de nombres de ``orm.registry``
                                 y ``objects.filter(pk=…).first()``
``check_access`` /               **portados en** ``src/orm/models.py``,
``_check_field_access``          con la misma firma
``self.env.user._is_public()``   **django** — el usuario que actúa sale
                                 de ``orm.environments``; sin sesión no
                                 hay actor, que es lo que la fuente
                                 llama público
el canal como **tupla**          **una cadena** — ver la divergencia 2
``self.env.registry.db_name``    **django** — el alias de la conexión

===============================  =====================================

Divergencia 1 — ``_inherit`` sobre una FUNCIÓN de módulo
========================================================

``bus`` no porta ``ir.websocket`` como clase: DEC-AF-06 descarta el WebSocket
y deja de ese archivo **dos funciones de módulo**,
``bus.models.ir_websocket.build_bus_channel_list`` y
``prepare_subscribe_data``. La política sí está portada; el transporte no.

Así que el ``_inherit`` de este archivo se resuelve envolviendo esa función,
y el envoltorio se escribe aquí en vez de reusar
``orm.method_chain.wrap_method``. **Se probó con él y no sirve**, por una
razón que conviene dejar escrita: ``wrap_method`` liga la previa al **primer
argumento posicional**, porque en una clase ese argumento es el receptor. En
una función de módulo el primer argumento es **dato** —la lista de canales—,
así que la previa llegaba ligada a la lista *original* y el cuerpo la volvía
a pasar: ``got multiple values for argument 'user'``. Medido al escribir su
caso.

El envoltorio propio es de siete líneas, es idempotente por su propia marca
—``ready()`` puede correr dos veces— y conserva la semántica que la fuente
necesita: la previa se invoca **al final**, con la lista ya ampliada, que es
donde la fuente escribe ``super()._build_bus_channel_list(channels)``.

Envolver el atributo del módulo alcanza a su único consumidor:
``prepare_subscribe_data`` resuelve ``build_bus_channel_list`` por nombre
global en cada llamada, así que ve el envoltorio.

Divergencia 2 — el canal es una CADENA, no una tupla
=====================================================

La fuente añade la tupla ``(db, 'editor_collaboration', model, field, id)``.
Aquí ``bus.BusMessage.sendone`` recibe ``target: str`` y
``prepare_subscribe_data`` **rechaza** con ``ValueError`` cualquier canal que
no sea cadena — es una guarda que ``bus`` porta a propósito.

Por eso el mismo contenido se serializa a una cadena con
:func:`editor_collaboration_channel`, que es **el único sitio** donde se
compone: la usan este archivo, ``tools.handle_history_divergence`` y
``controllers/main.bus_broadcast``. Un canal compuesto a mano en tres sitios
distintos es cómo el emisor y el receptor acaban hablando de canales
distintos sin que nada falle.
"""
import functools
import re

from addons.bus.models import ir_websocket as bus_ir_websocket
from django.db import DEFAULT_DB_ALIAS
from orm.environments import get_current_user
from orm.registry import model_by_name

#: Marca de idempotencia del envoltorio de módulo — ≙ el recorrido de marcas
#: que ``orm.method_chain`` hace sobre una clase.
_WRAPPED = '_html_editor_collaboration_wrapped'

#: ≙ el patrón del canal de coedición (``odoo19c: :17``), verbatim.
EDITOR_COLLABORATION_CHANNEL_REGEX = (
    r'editor_collaboration:(\w+(?:\.\w+)*):(\w+):(\d+)')

#: ≙ el segundo elemento de la tupla de canal de la fuente.
EDITOR_COLLABORATION = 'editor_collaboration'


def editor_collaboration_channel(model_name, field_name, res_id,
                                 db_name=DEFAULT_DB_ALIAS):
    """La tupla de canal de la fuente, serializada a cadena.

    ≙ ``(self.env.registry.db_name, 'editor_collaboration', model_name,
    field_name, res_id)`` (``odoo19c: :38``). Ver la divergencia 2.
    """
    return '%s:%s:%s:%s:%s' % (
        db_name, EDITOR_COLLABORATION, model_name, field_name, int(res_id))


class IrWebsocket:
    """≙ ``IrWebsocket`` (``odoo19c: :11``).

    **Clase plana, no ``models.Model``**, por la misma razón que
    ``base.IrBinary``: la fuente la declara ``AbstractModel`` —comportamiento
    sin tabla— y aquí no hay columna que crear. Su único atributo de clase es
    el ``_inherit`` que la fuente declara, y va verbatim: es el que nombra
    sobre qué modelo se extiende, y quien lea el archivo tiene que poder leer
    el destino sin salir de él.

    El ``_inherit`` se materializa en :func:`apply_html_editor_extensions`,
    que envuelve la función de módulo que ``bus`` porta en lugar de la clase.
    Ver la divergencia 1 del docstring del módulo: el destino divergente es de
    ``bus``, no de este archivo, y no cambia dónde vive el símbolo.
    """

    _inherit = 'ir.websocket'

    @classmethod
    def _build_bus_channel_list(cls, channels, previous, *args, **kwargs):
        """≙ ``_build_bus_channel_list`` (``odoo19c: :12-41``).

        La firma de la fuente es ``(self, channels)``. Aquí el receptor no
        aporta nada al cuerpo —la fuente tampoco lo usa salvo para el
        ``super()``—, así que el hueco del ``super()`` lo ocupa ``previous``,
        que se invoca **al final**, con la lista ya ampliada, allí donde la
        fuente escribe ``super()._build_bus_channel_list(channels)``.
        """
        user = get_current_user()
        if user is not None:
            # No se altera la lista original.
            channels = list(channels)
            for channel in channels:
                if isinstance(channel, str):
                    match = re.match(EDITOR_COLLABORATION_CHANNEL_REGEX, channel)
                    if match:
                        model_name = match[1]
                        field_name = match[2]
                        res_id = int(match[3])

                        model = model_by_name(model_name)
                        if model is None:
                            continue

                        document = model.objects.filter(pk=res_id).first()
                        if document is None:
                            continue

                        try:
                            document.check_access('read')
                            document.check_access('write')
                            field = next(
                                (f for f in model._meta.get_fields()
                                 if getattr(f, 'name', None) == field_name), None)
                            if field is not None:
                                document._check_field_access(field, 'read')
                                document._check_field_access(field, 'write')
                        except Exception:
                            # ≙ ``except AccessError: continue`` — el árbol declara
                            # el suyo en ``exceptions``, y ``_check_field_access``
                            # puede levantar además el de Django. Descartar el
                            # canal es lo que la fuente hace, y por el mismo
                            # motivo: negarlo delataría que el registro existe.
                            continue

                        channels.append(editor_collaboration_channel(
                            model_name, field_name, res_id))
        return previous(channels, *args, **kwargs)


def apply_html_editor_extensions():
    """Envuelve ``build_bus_channel_list`` de ``bus`` — ≙ ``_inherit``.

    Ver la divergencia 1: el destino es un **módulo**, no una clase, porque
    ``bus`` porta ese símbolo como función de módulo, y por qué el envoltorio
    se escribe aquí en vez de reusar ``wrap_method``.
    """
    previous = bus_ir_websocket.build_bus_channel_list
    if getattr(previous, _WRAPPED, False):
        return

    @functools.wraps(previous)
    def wrapped(channels, *args, **kwargs):
        return IrWebsocket._build_bus_channel_list(
            channels, previous, *args, **kwargs)

    setattr(wrapped, _WRAPPED, True)
    bus_ir_websocket.build_bus_channel_list = wrapped
