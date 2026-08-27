"""``sale.order`` — cuánto tiempo se ha registrado contra el pedido
(Odoo ``sale_timesheet``).

Adaptación de Odoo ``sale_timesheet/models/sale_order.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 165 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Medido por AST sobre la referencia: 1 clase (``SaleOrder``, ``_inherit``),
**4 campos** y **10 métodos**.

Los dos agregados que sí se pueden medir hoy
===============================================

``timesheet_count`` y ``timesheet_total_duration`` son las dos lecturas del
pedido que **no** pasan por ``so_line``: agregan sobre
``account.analytic.line.order``, la columna que ``models/hr_timesheet.py``
cuelga en este mismo addon. Los dos se portan enteros, incluida la conversión
de unidad — ``Uom.compute_quantity`` existe en este árbol
(``api: addons/uom/models/uom_uom.py:310``) y ``ResCompany.project_time_mode_id``
/ ``timesheet_encode_uom_id`` los cuelga ``hr_timesheet``
(``api: addons/hr_timesheet/models/res_company.py:96-107``).

Porte símbolo por símbolo
============================

.. list-table:: Campos — 2 properties portadas, 1 property + 1 bloqueado
   :header-rows: 1

   * - Campo de la referencia (línea)
     - Desenlace aquí
   * - ``timesheet_count`` (:14)
     - **portado como property** — ``compute`` sin ``store`` en la fuente.
       Cuenta apuntes con proyecto asignado, ≙ el ``_read_group`` de
       ``_compute_timesheet_count`` (:22-33).
   * - ``timesheet_total_duration`` (:16-18)
     - **portado como property** — ídem, con la conversión
       ``project_time_mode_id → timesheet_encode_uom_id`` y el
       ``rounding_method='HALF-UP'`` verbatim de la fuente.
   * - ``timesheet_encode_uom_id`` (:15)
     - **portado como property** — ``related='company_id.timesheet_encode_uom_id'``.
   * - ``show_hours_recorded_button`` (:19)
     - **BLOQUEADO** — su compute (:70-73) lee ``project_count``
       (``sale_project``, 0 hits aquí) y ``_get_order_with_valid_service_product``,
       que a su vez depende de ``product.service_type``/``invoice_policy``.

.. list-table:: Métodos — 2 portados, 8 con desenlace
   :header-rows: 1

   * - Método de la referencia (línea)
     - Desenlace aquí
   * - ``_compute_timesheet_count`` (:22-33)
     - **portado** dentro de la property ``timesheet_count``.
   * - ``_compute_timesheet_total_duration`` (:35-48)
     - **portado** dentro de la property ``timesheet_total_duration``.
   * - ``_compute_field_value`` (:50-68)
     - BLOQUEADO — engancha el motor de compute de Odoo para disparar la
       actividad de venta adicional al recalcular ``invoice_status``. Ni
       ``invoice_status`` (``sale``) ni el motor de actividades
       (``mail.activity``) existen aquí. Sucesor: tarea PENDIENTE DE ASIGNAR.
   * - ``_compute_show_hours_recorded_button`` (:70-73)
     - BLOQUEADO — ver ``show_hours_recorded_button`` arriba.
   * - ``create`` (:75-82)
     - BLOQUEADO — su rama entera está condicionada a la clave de contexto
       ``create_for_employee_mapping``; sin ``env.context`` no hay condición
       que evaluar, y forzar el ``action_confirm`` sin ella cambiaría la
       conducta del alta de cualquier pedido.
   * - ``_get_order_with_valid_service_product`` (:84-93)
     - BLOQUEADO por ``product.service_type``/``product.invoice_policy``
       (``odoo19c: sale/models/product_template.py:35`` y
       ``sale_project/models/product_template.py:45``), 0 hits aquí.
   * - ``_get_prepaid_service_lines_to_upsell`` (:95-114) /
       ``_reset_has_displayed_warning_upsell_order_lines`` (:152-156)
     - BLOQUEADOS por ``sol.qty_delivered`` e ``invoice_status``
       (``sale``, 0 hits). El campo que ambos escriben
       (``has_displayed_warning_upsell``) **sí** se porta, en
       ``models/sale_order_line.py``: es la columna, no su lógica de disparo.
   * - ``action_view_timesheet`` (:116-150)
     - no portado — navegación pura (``_for_xml_id`` + contexto de vista).
   * - ``_create_invoices`` (:158-165)
     - BLOQUEADO — el base no existe (0 hits de ``_create_invoices`` en
       ``addons/sale``; el análogo de este árbol es
       ``SaleOrder.action_create_invoice``) y su cuerpo llama a
       ``_link_timesheets_to_invoice``, bloqueado a su vez en
       ``models/account_move.py``.
"""
from orm.model_classes import extend_model

from addons.analytic.models import AccountAnalyticLine


def timesheet_encode_uom(self):
    """≙ ``timesheet_encode_uom_id``
    (``related='company_id.timesheet_encode_uom_id'``,
    ``odoo19c: sale_order.py:15``)."""
    return self.company.timesheet_encode_uom_id if self.company_id else None


def timesheet_count(self):
    """≙ ``timesheet_count`` + ``_compute_timesheet_count``
    (``odoo19c: sale_order.py:14, 22-33``).

    La fuente agrupa con ``_read_group`` sobre ``[('order_id','in',self.ids),
    ('project_id','!=',False)]``; aquí es el conteo del mismo filtro sobre un
    solo pedido. El campo es ``Float`` en la referencia y devuelve un conteo —
    se conserva como entero, que es lo que la operación produce.
    """
    if self.pk is None:
        return 0
    return AccountAnalyticLine.objects.filter(
        order=self, project__isnull=False).count()


def timesheet_total_duration(self):
    """≙ ``timesheet_total_duration`` + ``_compute_timesheet_total_duration``
    (``odoo19c: sale_order.py:16-18, 35-48``).

    Suma ``unit_amount`` de los apuntes del pedido con proyecto, convierte de
    la unidad de tiempo de la compañía (``project_time_mode_id``) a la unidad
    de captura (``timesheet_encode_uom_id``) con ``rounding_method='HALF-UP'``
    verbatim, y redondea al entero.

    Divergencia declarada: si la compañía no tiene fijadas las dos unidades
    (son nullable — ``hr_timesheet`` ya declaró que dependen de la fila
    semilla de UOM), la conversión se omite y se devuelve el total sin
    convertir. La fuente no tiene esa rama porque allá las dos tienen default.
    """
    if self.pk is None:
        return 0
    total = 0.0
    for entry in AccountAnalyticLine.objects.filter(
            order=self, project__isnull=False):
        total += entry.unit_amount or 0.0

    company = self.company if self.company_id else None
    source_uom = getattr(company, 'project_time_mode_id', None) if company else None
    target_uom = getattr(company, 'timesheet_encode_uom_id', None) if company else None
    if source_uom is not None and target_uom is not None:
        total = source_uom.compute_quantity(
            total, target_uom, rounding_method='HALF-UP')
    return round(total)


def apply_sale_timesheet_sale_order_extensions():
    """Cuelga las tres properties sobre ``sale.SaleOrder`` — ≙
    ``_inherit = 'sale.order'``.

    Sin bloque ``campos``: los cuatro campos de la referencia son ``compute``
    sin ``store`` o ``related``, salvo el único bloqueado. Par de Django
    porque el destino no declara ``_name``.
    """
    extend_model(
        'sale', 'SaleOrder',
        propiedades={
            'timesheet_encode_uom': timesheet_encode_uom,
            'timesheet_count': timesheet_count,
            'timesheet_total_duration': timesheet_total_duration,
        },
    )


__all__ = ['apply_sale_timesheet_sale_order_extensions']
