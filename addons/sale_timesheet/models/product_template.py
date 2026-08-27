"""``product.template`` — el producto que se vende como tiempo
(Odoo ``sale_timesheet``).

Adaptación de Odoo ``sale_timesheet/models/product_template.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 110 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Medido por AST sobre la referencia: 1 clase (``ProductTemplate``,
``_inherit``), **5 campos** y **10 métodos**.

El bloqueador de este archivo: la política de facturación del producto
=======================================================================

Cinco de sus quince símbolos leen ``service_policy`` o ``invoice_policy``:

- ``service_policy`` lo declara ``sale_project``
  (``odoo19c: sale_project/models/product_template.py:44``);
- ``invoice_policy`` lo declara ``sale``
  (``odoo19c: sale/models/product_template.py:35``).

Medido en este árbol: ``product.ProductTemplate`` declara ``type`` y
``service_tracking`` (con un solo valor, ``no``) y **ninguno** de los dos
anteriores — 0 hits de ``service_policy`` e ``invoice_policy`` en ``addons/``
y ``src/``. Sucesor: tarea PENDIENTE DE ASIGNAR (hogares ``addons/sale`` y
``addons/sale_project``).

Porte símbolo por símbolo
============================

.. list-table:: Campos — 1 portado, 4 bloqueados
   :header-rows: 1

   * - Campo de la referencia (línea)
     - Desenlace aquí
   * - ``service_upsell_threshold`` (:23)
     - **portado** — Float, ``default=1``. Es el umbral (fracción de lo
       vendido) a partir del cual se propone la venta adicional. Columna sin
       dependencias: quién la **lee** está bloqueado
       (``SaleOrder._get_prepaid_service_lines_to_upsell``), pero la columna es
       lo que sobrevive al bloqueo. Mismo criterio que
       ``has_displayed_warning_upsell`` en ``models/sale_order_line.py``.
   * - ``service_type`` (:17-19)
     - **BLOQUEADO** — ``selection_add=[('timesheet', …)]`` sobre un campo que
       declara ``sale_project`` (:45) y no existe aquí.
   * - ``project_id`` (:21) / ``project_template_id`` (:22)
     - **BLOQUEADOS** — redeclaraciones que sólo estrechan el ``domain``; los
       campos los declara ``sale_project`` (0 hits aquí).
   * - ``service_upsell_threshold_ratio`` (:24)
     - **BLOQUEADO** — su compute (:26-38) compara el ``factor`` de la unidad
       del producto contra ``uom.product_uom_hour``/``product_uom_unit`` y
       contra ``env.company.timesheet_encode_uom_id``. Dos bloqueadores: las
       filas semilla de UOM (data, no esquema) y la compañía ambiental. Es
       texto de UI (``"(1 unidad = 8.00 horas)"``), no una cifra de negocio.

.. list-table:: Métodos — 1 portado, 9 con desenlace
   :header-rows: 1

   * - Método de la referencia (línea)
     - Desenlace aquí
   * - ``_get_service_to_general_map`` (:75-81)
     - **portado** — dos pares verbatim
       (``delivered_timesheet``/``ordered_prepaid`` → política general +
       tipo de servicio). Tabla de correspondencia pura, sin lectura de campo:
       sobrevive a que ``service_policy`` no exista todavía, y su ausencia
       dejaría el mapeo cojo el día que aterrice. Mismo criterio que
       ``_get_service_policy_to_invoice_type`` en ``models/project_project.py``.
   * - ``_selection_service_policy`` (:11-14)
     - BLOQUEADO — inserta ``delivered_timesheet`` en el ``selection`` de un
       campo inexistente.
   * - ``_compute_service_upsell_threshold_ratio`` (:26-38)
     - BLOQUEADO — ver el campo homónimo.
   * - ``_compute_visible_expense_policy`` (:40-45)
     - BLOQUEADO — ``visible_expense_policy`` lo declara ``sale_expense``
       (0 hits aquí), y la rama que añade este addon lee
       ``env.user.has_group('project.group_project_user')``.
   * - ``_prepare_invoicing_tooltip`` (:47-50)
     - BLOQUEADO — texto de ayuda del formulario, condicionado a
       ``service_policy``.
   * - ``_onchange_service_fields`` (:52-68) / ``_onchange_service_policy`` (:96-102)
     - BLOQUEADOS — no hay motor de ``onchange`` en este árbol (mismo
       desenlace que ``hr_timesheet`` declaró para
       ``_onchange_project_id``), y además leen ``ir.default`` y las semillas
       de UOM.
   * - ``_get_onchange_service_policy_updates`` (:83-90)
     - BLOQUEADO — decide qué proyecto/plantilla limpiar según
       ``allow_timesheets``; ``allow_timesheets`` **sí** existe aquí
       (``hr_timesheet``), pero ``project_id``/``project_template_id`` del
       producto no. Bloqueado por la mitad ausente.
   * - ``_unlink_except_master_data`` (:104-107) / ``write`` (:109-110)
     - BLOQUEADOS — los dos protegen el producto semilla
       ``sale_timesheet.time_product`` (``data/sale_service_data.xml``) de ser
       archivado, borrado o atado a una compañía. Sin la fila semilla no hay
       qué proteger: el guardián sin su protegido sería un candado sobre un
       identificador que nunca resuelve. Sucesor: la tarea de la semilla
       (PENDIENTE DE ASIGNAR); el candado se cablea con ella, no antes.
"""
import fields

from orm.method_chain import chain_method
from orm.model_classes import extend_model


def _merge_with_previous(new, previous):
    """``combine`` para hooks que aportan claves a un dict — ≙
    ``{**super()…, **propio}``. Idéntico al de
    ``project_account``/``models/project_project.py``.
    """
    return {**(previous or {}), **(new or {})}


def _get_service_to_general_map(self):
    """≙ ``_get_service_to_general_map``
    (``odoo19c: product_template.py:75-81``) — de política de servicio a
    ``(invoice_policy, service_type)`` general. Dos pares verbatim.

    Devuelve SOLO el aporte propio; la fusión con lo previo la hace
    ``chain_method`` con ``_merge_with_previous``.
    """
    return {
        'delivered_timesheet': ('delivery', 'timesheet'),
        'ordered_prepaid': ('order', 'timesheet'),
    }


def _chain_product_template_hooks(model):
    """El ``luego`` de ``extend_model``: fusión de dict, no relevo por
    ``None`` — mismo criterio que ``models/project_project.py``."""
    chain_method(model, '_get_service_to_general_map',
                 _get_service_to_general_map, combine=_merge_with_previous)


def apply_sale_timesheet_product_template_extensions():
    """Cuelga ``service_upsell_threshold`` y el hook de mapeo sobre
    ``product.ProductTemplate`` — ≙ ``_inherit = 'product.template'``.

    Par de Django porque el destino no declara ``_name``
    (``api: addons/product/models/product_template.py``).
    """
    extend_model(
        'product', 'ProductTemplate',
        campos={
            'service_upsell_threshold': fields.Float(
                default=1.0, verbose_name='Umbral de venta adicional',
                help_text='Odoo service_upsell_threshold ("Threshold", '
                          'default=1). Fracción del tiempo vendido que hay '
                          'que entregar para que se proponga la venta '
                          'adicional. Quién lo lee está bloqueado — ver el '
                          'docstring del módulo.',
            ),
        },
        luego=_chain_product_template_hooks,
    )


__all__ = ['apply_sale_timesheet_product_template_extensions']
