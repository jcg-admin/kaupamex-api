"""Datos semilla del addon ``loyalty``.

Hoy sólo el registro de horario de la caducidad de vouchers. La referencia
declara sus crons en el ``data/`` del addon que los posee; esto es su
equivalente nativo.
"""

# UC-SYS-02. Cada hora, que es lo que el comando suelto ya prescribía en su
# propio help ("cron cada hora") desde antes de que existiera ir.cron.
#
# La referencia NO tiene análogo directo: su familia `loyalty` modela
# programas/tarjetas/recompensas (`odoo19c: addons/loyalty/models/`), no
# vouchers con vigencia — el dominio de vouchers es heredado pre-porte (gap
# nombrado en H-API-231). El intervalo es decisión propia, no derivada, y se
# declara como tal.
CRON_EXPIRE_VOUCHERS = {
    'name': 'Loyalty: caducar vouchers vencidos',
    'model_name': 'loyalty.Voucher',
    'method_name': 'expire_overdue',
    'interval_number': 1,
    'interval_type': 'hours',
    'priority': 5,
}
