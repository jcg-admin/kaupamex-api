"""Modelos del addon ``account_fleet`` (estructura Odoo: un archivo por
modelo — aquí, los tres de la referencia: ``account_move.py``,
``fleet_vehicle.py``, ``fleet_vehicle_log_services.py``).

**Deliberadamente vacío de imports** — mismo criterio que
``addons.l10n_mx.models`` y ``addons.account_qr_code_emv.models``:
``AccountFleetConfig.ready()`` importa cada archivo y aplica su extensión, no
este paquete. En tiempo de import del paquete el registro de modelos aún no
está poblado y ``add_to_class``/``setattr`` sobre
``account.AccountMove``/``account.AccountMoveLine``/``fleet.FleetVehicle``/
``fleet.FleetVehicleLogServices`` fallaría con ``AppRegistryNotReady``.

Este addon **no declara ningún modelo propio** (``_name`` nuevo) — los cuatro
modelos que toca ya existen en ``account``/``fleet``; lo que este paquete
cuelga es campos, métodos y señales sobre ellos (≙ ``_inherit``).
"""
