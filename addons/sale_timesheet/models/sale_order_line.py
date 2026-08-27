"""``sale.order.line`` — la línea de pedido que se entrega en horas
(Odoo ``sale_timesheet``).

Adaptación de Odoo ``sale_timesheet/models/sale_order_line.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 219 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Medido por AST sobre la referencia: 1 clase (``SaleOrderLine``, ``_inherit``),
**6 campos** y **13 métodos**.

Por qué este archivo queda casi entero bloqueado
==================================================

Todo lo que hace este addon sobre la línea de pedido cuelga de la **cantidad
entregada**: ``qty_delivered`` y su ``qty_delivered_method``, que declara
``sale`` (``odoo19c: sale/models/sale_order_line.py``) y extiende
``sale_project`` (``:10``). Medido en este árbol: ``sale.SaleOrderLine``
declara nueve campos (``order``, ``product``, ``name``, ``product_uom_qty``,
``price_unit``, ``discount``, ``is_delivery``, ``is_reward``, ``sequence``) y
**ninguno** de entrega, facturación ni unidad de medida — 0 hits de
``qty_delivered``, ``invoice_status``, ``product_uom_id`` y ``is_expense`` en
``addons/`` y ``src/``.

Sucesor único para las tres cadenas: tarea PENDIENTE DE ASIGNAR — el porte de
la entrega en ``addons/sale``, del que dependen ``remaining_hours``,
``_prepare_qty_delivered`` y ``_recompute_qty_to_invoice``.

Lo que SÍ se porta
=====================

Dos símbolos, y los dos son propios de este addon:

1. ``has_displayed_warning_upsell`` — la marca "ya avisé de la venta
   adicional". Es una columna sin dependencias: su **escritura** está
   bloqueada (la deciden ``_get_prepaid_service_lines_to_upsell`` y
   ``_reset_has_displayed_warning_upsell_order_lines``, en
   ``models/sale_order.py``), pero la columna es lo que sobrevive al bloqueo
   y lo que esas dos escribirán el día que aterricen.
2. ``_get_product_service_policy`` — tabla de correspondencia pura.

Porte símbolo por símbolo
============================

.. list-table:: Campos — 1 portado, 5 bloqueados
   :header-rows: 1

   * - Campo de la referencia (línea)
     - Desenlace aquí
   * - ``has_displayed_warning_upsell`` (:15)
     - **portado** — columna Boolean, ``default=False``. ``copy=False`` de la
       fuente no tiene análogo (este ORM no tiene copia de registro).
   * - ``qty_delivered_method`` (:11)
     - **BLOQUEADO** — ``selection_add`` sobre un campo de ``sale``
       inexistente aquí (0 hits).
   * - ``analytic_line_ids`` (:12)
     - **BLOQUEADO** — redeclaración que sólo estrecha el ``domain``; el campo
       lo declara ``sale`` (``odoo19c: sale/models/analytic.py``) junto con
       ``so_line``, su inverso. Mismo bloqueo raíz que
       ``models/hr_timesheet.py``.
   * - ``remaining_hours_available`` (:13)
     - **BLOQUEADO** — su compute (:45-50) lee
       ``product_id.service_policy`` (``sale_project``) y
       ``product_uom_id._has_common_reference`` (la línea no tiene unidad
       aquí).
   * - ``remaining_hours`` (:14)
     - **BLOQUEADO** — su compute (:52-60) resta ``qty_delivered`` de
       ``product_uom_qty`` y convierte de unidad. Es el campo del que penden
       ``ProjectTask.remaining_hours_so`` y ``last_sol_of_customer``.
   * - ``timesheet_ids`` (:16)
     - **BLOQUEADO** por ``so_line`` — es su inverso restringido a apuntes con
       proyecto.

.. list-table:: Métodos — 2 portados, 11 con desenlace
   :header-rows: 1

   * - Método de la referencia (línea)
     - Desenlace aquí
   * - ``_get_product_service_policy`` (:217-219)
     - **portado** — añade ``delivered_timesheet`` a la lista de políticas de
       servicio del producto. Concatenación de lista (``extend_list``); es
       dato puro, sin lectura de campo, así que sobrevive a que
       ``service_policy`` todavía no exista — mismo criterio que
       ``_get_service_policy_to_invoice_type`` en ``models/project_project.py``.
   * - ``_compute_display_name`` (:18-43)
     - no portado — decora el nombre visible con las horas restantes para el
       buscador del cliente web de Odoo; además depende de
       ``remaining_hours`` y de las semillas de UOM.
   * - ``_compute_remaining_hours_available`` (:45-50) /
       ``_compute_remaining_hours`` (:52-60)
     - BLOQUEADOS — ver los campos homónimos.
   * - ``_compute_qty_delivered_method`` (:62-68) /
       ``_compute_qty_delivered`` (:70-72) / ``_prepare_qty_delivered`` (:74-81)
     - BLOQUEADOS por ``qty_delivered``/``qty_delivered_method``
       (``addons/sale``) y por ``product.service_type``.
   * - ``_timesheet_compute_delivered_quantity_domain`` (:83-88)
     - **portado parcial declarado** —
       :func:`timesheet_delivered_quantity_queryset`. La hoja
       ``[('project_id','!=',False)]`` **sí** es medible (``project`` sobre el
       apunte lo cuelga ``hr_timesheet``); la hoja opcional por
       ``accrual_entry_date`` la recibe el llamador como parámetro, porque en
       la fuente viene de ``env.context``.
   * - ``_convert_qty_company_hours`` (:94-104)
     - BLOQUEADO — necesita ``product_uom_id`` en la línea (0 hits) y las
       semillas ``uom.product_uom_unit``/``product_uom_hour``.
   * - ``_timesheet_create_project`` (:106-142) /
       ``_timesheet_create_project_prepare_values`` (:144-148)
     - BLOQUEADOS — el base lo declara ``sale_project`` y su puerto aquí es
       PARCIAL (``SaleOrderLineProject.generate_task`` cubre la tarea, no el
       proyecto con horas asignadas). Además leen
       ``product_id.project_template_id`` y ``allow_billable``.
   * - ``_recompute_qty_to_invoice`` (:150-196)
     - BLOQUEADO — tres bloqueadores: ``invoice_status``/``qty_to_invoice``
       (``sale``), ``so_line`` y ``product._is_delivered_timesheet``
       (bloqueado a su vez en ``models/product_product.py``).
   * - ``_get_action_per_item`` (:198-215)
     - no portado — navegación pura (``_for_xml_id`` + ids para el cliente
       web), y depende de ``so_line``.
"""
import fields

from orm.method_chain import chain_method, extend_list
from orm.model_classes import extend_model


def timesheet_delivered_quantity_queryset(queryset, accrual_entry_date=None):
    """≙ ``_timesheet_compute_delivered_quantity_domain``
    (``odoo19c: sale_order_line.py:83-88``) — **parcial declarado**.

    La fuente devuelve el dominio ``[('project_id','!=',False)]`` y le añade
    ``('date','<=',accrual_entry_date)`` cuando esa clave está en
    ``env.context``. Aquí el llamador la pasa explícita: sin contexto
    ambiental no hay de dónde leerla, y leerla de otro sitio sería inventar un
    canal que la fuente no tiene.

    Es un *hook* en la referencia (*"Hook for validated timesheet in
    additional module"*): se porta como función de módulo para que un addon
    posterior pueda envolverla, que es su razón de ser.
    """
    queryset = queryset.filter(project__isnull=False)
    if accrual_entry_date is not None:
        queryset = queryset.filter(date__lte=accrual_entry_date)
    return queryset


def _get_product_service_policy(self):
    """≙ ``_get_product_service_policy``
    (``odoo19c: sale_order_line.py:217-219``) — la política de servicio que
    este addon añade al producto.

    Devuelve SOLO el aporte propio; ``extend_list`` concatena con lo previo en
    el orden de la fuente.
    """
    return ['delivered_timesheet']


def _chain_sale_order_line_hooks(model):
    """Encadena el hook de lista con ``extend_list`` — el ``luego`` de
    ``extend_model``, porque su bloque ``metodos`` usa el relevo por ``None``
    y aquí la semántica correcta es la concatenación."""
    chain_method(model, '_get_product_service_policy',
                 _get_product_service_policy, combine=extend_list)


def apply_sale_timesheet_sale_order_line_extensions():
    """Cuelga ``has_displayed_warning_upsell`` y el hook de política de
    servicio sobre ``sale.SaleOrderLine`` — ≙ ``_inherit = 'sale.order.line'``.

    Par de Django porque el destino no declara ``_name``.
    """
    extend_model(
        'sale', 'SaleOrderLine',
        campos={
            'has_displayed_warning_upsell': fields.Boolean(
                default=False,
                verbose_name='Aviso de venta adicional ya mostrado',
                help_text='Odoo has_displayed_warning_upsell (copy=False). '
                          'Quién la escribe está bloqueado por qty_delivered '
                          '— ver el docstring del módulo.',
            ),
        },
        luego=_chain_sale_order_line_hooks,
    )


__all__ = [
    'apply_sale_timesheet_sale_order_line_extensions',
    'timesheet_delivered_quantity_queryset',
]
