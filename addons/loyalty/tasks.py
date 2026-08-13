"""
Tareas periodicas de sistema — addons.loyalty (UC-SYS-02).

**La logica vive en el modelo**, no aqui: ``Voucher.expire_overdue()``. Este
modulo se conserva como alias estable para los consumidores que ya importaban
``expire_vouchers`` — no duplica el comportamiento, lo delega.

El motivo del traslado: ``ir.cron`` resuelve ``<model>.<method>()``
(``ir_cron.py:440``, ``apps.get_model(self.model_name)``), no modulos sueltos ni
management commands. Mientras la caducidad fuera una funcion de modulo, el
registro de horario no tenia a que apuntar y el job vivia como un comando que
alguien debia invocar desde el crontab del sistema.
"""
from addons.loyalty.models import Voucher


def expire_vouchers():
    """Alias de ``Voucher.expire_overdue()``. Devuelve cuantos se caducaron."""
    return Voucher.expire_overdue()
