"""``res.groups`` extendido por ``bus`` — es canal, no delega.

Adaptación de ``addons/bus/models/res_groups.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 8 líneas). Igual que ``res_partner``:
``_inherit = ["res.groups", "bus.listener.mixin"]`` sin redefinir
``_bus_channel``.

Un grupo es canal propio porque ``ir_websocket.py`` suscribe a cada sesión a
**todos los grupos de su usuario** (``channels.extend(self.env.user.
all_group_ids)``). Así una notificación dirigida a un grupo llega a todos sus
miembros sin enumerarlos: el emisor nombra el grupo, no la lista.

Sin resolutor que registrar, por la misma razón que ``res_partner``.
"""
