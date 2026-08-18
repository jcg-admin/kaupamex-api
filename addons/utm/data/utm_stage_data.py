"""``utm_stage_data`` — la etapa por defecto de una campaña.

Adaptación de ``odoo19c: addons/utm/data/utm_stage_data.xml``
(``odoo-tools@622ddc2a``, LGPL-3).

**Por qué va en ``data`` y no en ``demo``:** el propio XML de la referencia lo
explica en un comentario —*"This one is kept in data instead of demo to avoid
crashing if the user starts creating campaigns before stages have been
created, as they are mandatory"*—. ``utm.campaign.stage_id`` es requerido y su
valor por defecto es la primera etapa; sin esta semilla, crear una campaña
reventaría.
"""

UTM_STAGES = [
    {'xmlid': 'utm.default_utm_stage', 'name': 'New', 'sequence': 10},
]
