"""Datos semilla del addon ``helpdesk``.

Hoy sólo el registro de horario del cierre por inactividad. La referencia
declara sus crons en el ``data/`` del addon que los posee; esto es su
equivalente nativo.
"""

# UC-NOT-08. Diario: el barrido busca tickets sin actividad por 7 días, así que
# una resolución de horas no aporta nada — sólo consultas.
#
# La referencia declara un cron análogo en su helpdesk (``odoo19e:``), pero esa
# edición es propietaria (OEEL-1) y por DEC-KX-03 no se copia: el intervalo es
# decisión propia, tomada del comando que hospedaba la lógica.
CRON_AUTO_CLOSE_TICKETS = {
    'name': 'Helpdesk: cerrar tickets sin actividad',
    'model_name': 'helpdesk.SupportTicket',
    'method_name': 'auto_close_stale',
    'interval_number': 1,
    'interval_type': 'days',
    'priority': 5,
}
