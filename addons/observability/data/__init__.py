"""Datos semilla del addon ``observability``.

Hoy sólo el registro de horario de la retención de logs (DEC-LOG-05).
"""

# DEC-LOG-05. Diario y de madrugada en cuanto al efecto: las ventanas se miden
# en días (14/30/90), así que correr más seguido sólo añade consultas sin
# purgar nada distinto.
#
# Sin análogo en la referencia: su ``ir.logging`` no lleva política de retención
# declarada — la purga es adaptación de proyecto (DEC-LOG-05), y el intervalo se
# declara como decisión propia, no derivada.
CRON_PURGE_LOGS = {
    'name': 'Observability: purgar logs por retencion',
    'model_name': 'observability.RequestLog',
    'method_name': 'purge_expired',
    'interval_number': 1,
    'interval_type': 'days',
    'priority': 8,
}
