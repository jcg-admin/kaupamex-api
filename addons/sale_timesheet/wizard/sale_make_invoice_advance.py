"""``sale.advance.payment.inv`` — facturar sólo las horas de un periodo
(Odoo ``sale_timesheet``).

Adaptación de Odoo ``sale_timesheet/wizard/sale_make_invoice_advance.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 50 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Medido por AST sobre la referencia: 1 clase (``SaleAdvancePaymentInv``,
``TransientModel``, ``_inherit``), **3 campos**, **2 métodos**. **No-op
medido** — 0 de 5, por razón de SITIO.

Por qué este archivo no declara ningún asistente
==================================================

El asistente base **no existe en este árbol**: ``sale.advance.payment.inv`` lo
declara ``sale`` (``odoo19c: addons/sale/wizard/sale_make_invoice_advance.py``),
y el puerto de ``sale`` aquí **no tiene directorio ``wizard/``** — medido:
``ls addons/sale/`` da ``controllers/``, ``data/``, ``migrations/``,
``models/``, ``report/``, ``security/`` y ningún ``wizard/``; 0 hits de
``SaleAdvancePaymentInv`` en ``addons/`` y ``src/``.

``sale_timesheet`` sólo lo **extiende**: le añade el rango de fechas y hace
que la facturación por entrega recalcule antes la cantidad a facturar de los
productos de tiempo. Declarar aquí el asistente entero lo pondría en el hogar
equivocado (``H-API-568`` / ``H-API-578``).

Sucesor: tarea PENDIENTE DE ASIGNAR — portar
``sale/wizard/sale_make_invoice_advance.py`` en ``addons/sale/wizard/``, con
la forma que este árbol ya usa para los asistentes (``TransientModel`` con
``Meta.abstract = True, managed = False`` + ``@classmethod``; precedente:
``api: addons/account/wizard/account_move_reversal.py:146-148``).

Porte símbolo por símbolo — 0 de 5
=====================================

.. list-table::
   :header-rows: 1

   * - Símbolo de la referencia (línea)
     - Desenlace aquí
   * - ``date_start_invoice_timesheet`` (:9-11) /
       ``date_end_invoice_timesheet`` (:12-14)
     - **BLOQUEADOS** por el asistente base. Son dos ``fields.Date`` sin más
       dependencia: el día que el base aterrice, son dos parámetros del
       ``@classmethod`` que lo porte — no dos columnas, porque el asistente no
       tiene tabla en este árbol.
   * - ``invoicing_timesheet_enabled`` (:15)
     - **BLOQUEADO** por el asistente base **y** por su compute (:20-28), que
       filtra las líneas por ``invoice_status == 'to invoice'`` (``addons/sale``,
       0 hits) y los productos por ``_is_delivered_timesheet``, bloqueado a su
       vez en ``models/product_product.py``.
   * - ``_compute_invoicing_timesheet_enabled`` (:20-28)
     - **BLOQUEADO** — ver arriba.
   * - ``_create_invoices`` (:32-50)
     - **BLOQUEADO** — tres bloqueadores encadenados: el asistente base;
       ``SaleOrderLine._recompute_qty_to_invoice``, bloqueado en
       ``models/sale_order_line.py``; y el paso de ``timesheet_start_date`` /
       ``timesheet_end_date`` por ``env.context`` hasta
       ``AccountMove._link_timesheets_to_invoice``, que está bloqueado en
       ``models/account_move.py``. La cadena entera se cablea de una vez o no
       se cablea: es la ruta "facturar las horas de este periodo", y a medias
       facturaría un periodo distinto del pedido.
"""


def apply_sale_timesheet_sale_make_invoice_advance_extensions():
    """No-op declarado — el asistente base no existe en este árbol. Ver el
    docstring del módulo.

    Se conserva la función (y su entrada en
    ``SaleTimesheetConfig._EXTENSIONES``) porque es el punto exacto donde se
    cuelga el rango de fechas el día que ``sale`` porte su asistente.
    """
    return None


__all__ = ['apply_sale_timesheet_sale_make_invoice_advance_extensions']
