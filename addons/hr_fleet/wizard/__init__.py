"""Wizards del addon ``hr_fleet`` (estructura Odoo: el único de la
referencia, ``hr_departure_wizard.py``).

**Deliberadamente vacío de imports** — mismo criterio que
``addons.hr_fleet.models``: ``HrFleetConfig.ready()`` importa el archivo y
aplica su extensión sobre ``hr.departure.wizard`` (clase de ``hr``), que en
tiempo de import de este paquete aún no está garantizada.
"""
