"""Modelos del addon ``hr_hourly_cost``.

**Deliberadamente vacío de imports** — mismo criterio que
``addons.account_fleet.models``/``addons.product_expiry.models``:
``HrHourlyCostConfig.ready()`` importa el módulo y aplica su extensión, no
este paquete. En tiempo de import del paquete el registro de modelos aún no
está poblado y ``add_to_class`` sobre ``hr.HrEmployee`` fallaría con
``AppRegistryNotReady``.

Este addon **no declara ningún modelo propio** (``_name`` nuevo) — el único
modelo que toca (``hr.employee``) ya existe en ``hr``; lo que este paquete
cuelga es un campo (≙ ``_inherit``).
"""
