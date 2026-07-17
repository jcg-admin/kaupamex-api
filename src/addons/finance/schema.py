"""Tags OpenAPI del módulo financiero (drf-spectacular / ADR-015).

``collect_app_tags`` (config.spectacular_hooks) recoge estos ``SPECTACULAR_TAGS``
de cada app en INSTALLED_APPS y los agrega al schema — OCP: se documenta el tag
del módulo sin tocar ``config/settings/base.py``.
"""
SPECTACULAR_TAGS = [
    {
        'name': 'finance',
        'description': (
            'Módulo financiero (MOD-028): caja/banco digital gateway-agnóstico. '
            'Conceptos (UC-FIN-06), conciliación de liquidaciones (UC-FIN-01), '
            'flete por pagar (UC-FIN-03), corte de caja (UC-FIN-02), proyección '
            'de flujo (UC-FIN-05), cierre de ejercicio (UC-FIN-08) y '
            'disponibilidad (UC-FIN-04). Gateado por el recurso graduado '
            '``finance`` + acciones SoD nombradas (DEC-11).'
        ),
    },
]
