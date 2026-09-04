"""``res.partner`` extendido por ``bus`` — es canal, no delega.

Adaptación de ``addons/bus/models/res_partner.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 8 líneas). Declara
``_inherit = ["res.partner", "bus.listener.mixin"]`` y **no** redefine
``_bus_channel``.

Que no redefina nada es el dato, no la ausencia de él: el partner es el
**punto fijo** al que llegan las delegaciones de ``res.users`` y, a través de
él, de ``res.users.settings``. Si delegara en otro sitio, el recorrido de
``_bus_send`` no terminaría donde el cliente escucha.

No hay resolutor que registrar — el comportamiento por defecto del mixin
(emitir en uno mismo) es exactamente el correcto. El archivo existe porque la
referencia lo tiene y porque esta explicación es lo que se perdería al no
tenerlo.
"""

#: ≙ la cabecera que la fuente declara en su clase (la extensión aquí no es clase).
_name = 'res.partner'
_inherit = ['res.partner', 'bus.listener.mixin']

