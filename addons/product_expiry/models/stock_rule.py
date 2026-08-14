"""``stock.rule`` — la alerta de caducidad como tarea del planificador.

Adaptación de Odoo ``product_expiry/models/stock_rule.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3) — atribución y aviso de
licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 2 de la referencia, 1 aquí
=======================================================

``odoo19c: addons/product_expiry/models/stock_rule.py`` (17 líneas):
2 métodos.

========================================  ===========================================
Símbolo de la referencia (línea)          Dónde queda en este puerto
========================================  ===========================================
``_run_scheduler_tasks`` (10-13)          ``run_expiry_alert_task`` (ver abajo)
``_get_scheduler_tasks_to_do`` (15-17)    **bloqueado** — el contador no existe aquí
========================================  ===========================================

``_run_scheduler_tasks`` — el gancho existe, con otro nombre
--------------------------------------------------------------

La referencia engancha la alerta al planificador de inventario::

    def _run_scheduler_tasks(self, use_new_cursor=False, company_id=False):
        super()._run_scheduler_tasks(use_new_cursor, company_id)
        self.env['stock.lot']._alert_date_exceeded()
        self._commit_progress(1)

El puerto de ``stock.rule`` (``api: addons/stock/models/stock_rule.py``)
declara ``run(product, qty, picking=None)`` — la aplicación de **una** regla,
no el barrido del planificador. El barrido vive en el orderpoint
(``run_scheduler``, portado en la tarea #257), y **ése** es el sitio análogo.

Este archivo expone la tarea como función nombrada,
``run_expiry_alert_task()``, para que el cron la invoque sin que
``product_expiry`` tenga que conocer la forma del planificador. Es la misma
composición de la referencia —el satélite aporta una tarea, el planificador la
corre— con el acoplamiento invertido, que es lo que este stack permite sin
inventar un ``_commit_progress`` que no tiene.

Lo que este archivo no cierra
===============================

``_get_scheduler_tasks_to_do`` (``return super() + 1``) incrementa el contador
de pasos que la barra de progreso del cliente Odoo consume. Sin
``_commit_progress`` ni barra de progreso —medido: ``grep -rn
"_commit_progress" addons/ src/`` → 0— el símbolo no tiene qué informar.
Sucesor registrado: tarea **#124** (sembrar los jobs de cron), donde se decide
si el planificador de este árbol lleva contador de progreso.
"""
from addons.stock.models import StockLot


def run_expiry_alert_task():
    """≙ la línea ``self.env['stock.lot']._alert_date_exceeded()`` de
    ``_run_scheduler_tasks`` (``odoo19c: stock_rule.py:12``).

    Devuelve los lotes marcados, para que el llamador pueda reportar cuántos
    fueron — información que la referencia descarta.
    """
    return StockLot.alert_date_exceeded()


def apply_product_expiry_extensions():
    """Nada que colgar sobre ``stock.rule``: la tarea se expone como función.

    Ver el docstring del módulo — el gancho del planificador vive en el
    orderpoint, no en la regla, así que este addon publica la tarea en vez de
    encadenar un método que aquí no existe.
    """
    return None


__all__ = ['apply_product_expiry_extensions', 'run_expiry_alert_task']
