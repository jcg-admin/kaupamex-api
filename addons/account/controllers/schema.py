"""``SPECTACULAR_TAGS`` — ``addons.account.controllers``.

``account`` no había expuesto capa DRF propia hasta ahora (H-API-408,
UC-PAY-14, tarea #55): el endpoint de registro de pago es el primero. El
addon es el **dueño del módulo** ``finance`` (``authz_catalog.py``: "finance
— los movimientos financieros"), así que su tag va aquí, no en un addon
satélite — Open/Closed (``config/spectacular_hooks.py``): el tag se declara
una sola vez, donde vive el dominio.
"""

SPECTACULAR_TAGS = [
    {'name': 'finance',
     'description': 'Movimientos financieros y sus asistentes: registro de '
                    'pago (abono/liquidación total), cheques prenumerados, '
                    'notas de débito, recálculo de casillas fiscales.'},
]
