"""``account.move.line`` — el apunte de factura que desenlaza horas al
borrarse (Odoo ``sale_timesheet``).

Adaptación de Odoo ``sale_timesheet/models/account_move_line.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 54 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Medido por AST sobre la referencia: 1 clase (``AccountMoveLine``,
``_inherit``), **0 campos**, **2 métodos**. Ambos con desenlace declarado; el
archivo es un **no-op medido**, no un olvido.

Porte símbolo por símbolo — 0 de 2
=====================================

.. list-table::
   :header-rows: 1

   * - Método de la referencia (línea)
     - Desenlace aquí
   * - ``_timesheet_domain_get_invoiced_lines`` (:9-24)
     - **BLOQUEADO** — el dominio se arma sobre ``so_line`` y
       ``timesheet_invoice_id.payment_state``. La segunda mitad **sí** existe
       aquí (``models/hr_timesheet.py`` cuelga ``timesheet_invoice``, y
       ``account.move`` tiene ``payment_state``); la primera es el bloqueo
       raíz del addon: ``so_line`` lo declara ``sale``
       (``odoo19c: sale/models/analytic.py:9``) y no existe en este árbol.
       Sin la hoja ``('so_line','in',…)`` el dominio devolvería **todos** los
       apuntes de las facturas, no los de estas líneas — un filtro más ancho
       que el de la fuente, que es peor que ninguno. Sucesor: tarea PENDIENTE
       DE ASIGNAR (hogar ``addons/sale``).
   * - ``unlink`` (:26-52)
     - **BLOQUEADO** — antes de borrar líneas de factura en borrador,
       desenlaza los apuntes cuya factura es esa y cuya ``so_line`` está entre
       las líneas de venta de la línea borrada. Cuatro bloqueadores:
       ``AccountMoveLine.sale_line_ids`` (0 hits aquí),
       ``product.invoice_policy`` y ``product.service_type``
       (``odoo19c: sale/models/product_template.py:35`` y
       ``sale_project/models/product_template.py:45``, 0 hits), y ``so_line``.
       Sucesor: la misma tarea.

Por qué no se fabrica una versión "aproximada"
================================================

Los dos símbolos son **filtros**, y un filtro con una hoja menos no es una
versión parcial: es un filtro distinto que selecciona de más. Desenlazar
apuntes que la fuente no habría tocado es peor que no desenlazar ninguno —
por eso ninguno de los dos se porta a medias, y la función de este módulo es
declarar por qué, con la pieza que falta nombrada para que un ``grep so_line``
lo recupere.
"""


def apply_sale_timesheet_account_move_line_extensions():
    """No-op declarado — los dos símbolos de la referencia están bloqueados
    por ``sale.AccountAnalyticLine.so_line``. Ver el docstring del módulo.

    Se conserva la función (y su entrada en ``SaleTimesheetConfig._EXTENSIONES``)
    porque es el punto exacto donde se cablean los dos el día que ``so_line``
    aterrice — mismo criterio que ``hr/models/res_config_settings.py``.
    """
    return None


__all__ = ['apply_sale_timesheet_account_move_line_extensions']
