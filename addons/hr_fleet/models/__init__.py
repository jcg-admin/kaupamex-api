"""Modelos del addon ``hr_fleet`` (estructura Odoo: un archivo por modelo —
los ocho de la referencia).

**Deliberadamente vacío de imports** — mismo criterio que
``addons.account_fleet.models``: ``HrFleetConfig.ready()`` importa cada
archivo y aplica su extensión, no este paquete. En tiempo de import del
paquete el registro de modelos aún no está poblado y colgar sobre
``hr.HrEmployee``/``fleet.FleetVehicle`` fallaría con
``AppRegistryNotReady``.

Este addon **no declara ningún modelo propio** (``_name`` nuevo) — los
modelos que toca ya existen en ``hr``/``fleet``/``base``; lo que este
paquete cuelga es campos, métodos, properties y señales sobre ellos
(≙ ``_inherit``).
"""
