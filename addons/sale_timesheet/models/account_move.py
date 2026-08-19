"""``account.move`` — la factura vista desde las horas que la originan
(Odoo ``sale_timesheet``).

Adaptación de Odoo ``sale_timesheet/models/account_move.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 105 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Medido por AST sobre la referencia: 1 clase (``AccountMove``, ``_inherit``),
**4 campos** y **6 métodos**.

Porte símbolo por símbolo
============================

.. list-table:: Campos — 1 reverso de FK, 3 properties
   :header-rows: 1

   * - Campo de la referencia (línea)
     - Desenlace aquí
   * - ``timesheet_ids`` (:5)
     - **portado como el reverso de la FK** — es el
       ``related_name='timesheet_ids'`` de
       ``AccountAnalyticLine.timesheet_invoice``, colgado por
       ``models/hr_timesheet.py``. Mismo nombre que la referencia, a
       propósito.
   * - ``timesheet_count`` (:6)
     - **portado como property** — ``compute`` sin ``store`` en la fuente
       (:30-35).
   * - ``timesheet_encode_uom_id`` (:7)
     - **portado como property** — ``related='company_id.timesheet_encode_uom_id'``
       (columna colgada por ``hr_timesheet`` sobre ``res.company``).
   * - ``timesheet_total_duration`` (:8-10)
     - **portado como property** — ``compute`` sin ``store``, con la
       conversión ``project_time_mode_id → timesheet_encode_uom_id`` y el
       ``rounding_method='HALF-UP'`` verbatim (:12-28).
       **Divergencia declarada:** la fuente corta en seco devolviendo 0 si el
       usuario no está en ``hr_timesheet.group_hr_timesheet_user`` (:14-16);
       aquí la autorización es por CAPACIDAD a nivel de vista DRF
       (``HasCapability``), no una rama dentro del cálculo — el modelo
       calcula y quien decide si se muestra es la vista.

.. list-table:: Métodos — 2 portados, 4 con desenlace
   :header-rows: 1

   * - Método de la referencia (línea)
     - Desenlace aquí
   * - ``_compute_timesheet_total_duration`` (:12-28) /
       ``_compute_timesheet_count`` (:30-35)
     - **portados** dentro de las properties homónimas.
   * - ``_get_range_dates`` (:83-86)
     - **portado** — *"A method that can be overridden"*: devuelve
       ``(None, None)``. Es un punto de extensión declarado, y su ausencia
       dejaría a ``_link_timesheets_to_invoice`` sin el gancho que la fuente
       le da. Se porta aunque su único consumidor esté bloqueado.
   * - ``action_view_timesheet`` (:37-59)
     - no portado — navegación pura (``ir.actions.act_window``). Mismo
       criterio que ``project_account/models/project_project.py``.
   * - ``_link_timesheets_to_invoice`` (:61-81)
     - **BLOQUEADO** — recorre ``invoice_line_ids.sale_line_ids`` para
       encontrar las líneas facturadas por entrega y escribe
       ``timesheet_invoice_id`` en los apuntes de ``so_line``. Tres
       bloqueadores: ``AccountMove.invoice_line_ids`` (0 hits aquí),
       ``AccountMoveLine.sale_line_ids`` (0 hits) y ``so_line`` (ver el
       bloqueo raíz en ``models/hr_timesheet.py``). Sucesor: tarea PENDIENTE
       DE ASIGNAR. La mitad **inversa** del mecanismo —desenlazar el apunte
       cuando la factura se revierte— sí se porta, en
       ``models/account_move_reversal.py``.
   * - ``action_post`` (:88-105)
     - **BLOQUEADO** — desenlaza los apuntes de la factura original cuando se
       postea su nota de crédito. Depende de ``AccountMove.reversed_entry_id``
       (0 hits en ``addons/account/models/account_move.py``), de
       ``invoice_line_ids.sale_line_ids`` y de ``so_line``. Sucesor: la misma
       tarea que ``_link_timesheets_to_invoice`` — son las dos mitades del
       mismo enlace.
"""
from orm.method_chain import chain_method
from orm.model_classes import extend_model

from addons.analytic.models import AccountAnalyticLine


def timesheet_encode_uom(self):
    """≙ ``timesheet_encode_uom_id``
    (``related='company_id.timesheet_encode_uom_id'``,
    ``odoo19c: account_move.py:7``)."""
    return self.company.timesheet_encode_uom_id if self.company_id else None


def timesheet_count(self):
    """≙ ``timesheet_count`` + ``_compute_timesheet_count``
    (``odoo19c: account_move.py:6, 30-35``) — cuántos apuntes de hoja de horas
    generó esta factura."""
    if self.pk is None:
        return 0
    return AccountAnalyticLine.objects.filter(timesheet_invoice=self).count()


def timesheet_total_duration(self):
    """≙ ``timesheet_total_duration`` + ``_compute_timesheet_total_duration``
    (``odoo19c: account_move.py:8-10, 12-28``).

    Suma ``unit_amount`` de los apuntes enlazados a esta factura y convierte
    de la unidad de tiempo de la compañía a la de captura, con
    ``rounding_method='HALF-UP'`` verbatim. Ver la divergencia sobre el corte
    por grupo en el docstring del módulo.
    """
    if self.pk is None:
        return 0
    total = 0.0
    for entry in AccountAnalyticLine.objects.filter(timesheet_invoice=self):
        total += entry.unit_amount or 0.0

    company = self.company if self.company_id else None
    source_uom = getattr(company, 'project_time_mode_id', None) if company else None
    target_uom = getattr(company, 'timesheet_encode_uom_id', None) if company else None
    if source_uom is not None and target_uom is not None:
        total = source_uom.compute_quantity(
            total, target_uom, rounding_method='HALF-UP')
    return round(total)


def _get_range_dates(self, order=None):
    """≙ ``_get_range_dates`` (``odoo19c: account_move.py:83-86``).

    *"A method that can be overridden to set the start and end dates
    according to order values"* — devuelve ``(None, None)``, verbatim. Se
    porta porque es el punto de extensión, no el cálculo.
    """
    return None, None


def _chain_account_move_hooks(model):
    """El ``luego`` de ``extend_model``: ``_get_range_dates`` devuelve una
    tupla y **nunca** ``None``, así que el relevo por ``None`` del bloque
    ``metodos`` jamás cedería al anterior — que es justo lo que se quiere,
    porque en la fuente este método no llama a ``super()``. Se instala por
    ``chain_method`` igualmente, para que un addon posterior pueda encadenarlo.
    """
    chain_method(model, '_get_range_dates', _get_range_dates)


def apply_sale_timesheet_account_move_extensions():
    """Cuelga las tres properties + el hook sobre ``account.AccountMove`` — ≙
    ``_inherit = 'account.move'``.

    Sin bloque ``campos``: el único campo con columna de la referencia
    (``timesheet_ids``) es el reverso de una FK que ya cuelga
    ``models/hr_timesheet.py``.
    """
    extend_model(
        'account', 'AccountMove',
        propiedades={
            'timesheet_encode_uom': timesheet_encode_uom,
            'timesheet_count': timesheet_count,
            'timesheet_total_duration': timesheet_total_duration,
        },
        luego=_chain_account_move_hooks,
    )


__all__ = ['apply_sale_timesheet_account_move_extensions']
