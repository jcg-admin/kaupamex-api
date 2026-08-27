"""``project.task`` — la tarea vista desde la facturación del tiempo
(Odoo ``sale_timesheet``).

Adaptación de Odoo ``sale_timesheet/models/project_task.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 119 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Medido por AST sobre la referencia: 1 clase (``ProjectTask``, ``_inherit``),
**8 campos** y **12 métodos** (uno de ellos, ``TASK_PORTAL_READABLE_FIELDS``,
declarado como ``property``).

Este archivo es casi todo espejo de la línea de pedido
========================================================

Seis de sus ocho campos son ``related``/``compute`` sobre
``sale_line_id.*``, y ``ProjectTask.sale_line_id`` lo declara ``sale_project``
(``odoo19c: sale_project/models/project_task.py:26``), cuyo puerto aquí es
PARCIAL declarado. Lo que sobrevive son las dos lecturas que van hacia el
**proyecto**, no hacia el pedido — y ésas sí se portan, porque
``models/project_project.py`` de este mismo addon cuelga sus dos campos.

Porte símbolo por símbolo
============================

.. list-table:: Campos — 3 properties, 5 bloqueados
   :header-rows: 1

   * - Campo de la referencia (línea)
     - Desenlace aquí
   * - ``pricing_type`` (:22)
     - **portado como property** — ``related='project_id.pricing_type'``, y
       ``Project.pricing_type`` es property en este árbol
       (``models/project_project.py``). El ``related`` sin ``store`` de la
       fuente es exactamente una property en este idioma.
   * - ``timesheet_product_id`` (:25)
     - **portado como property** ``timesheet_product`` —
       ``related='project_id.timesheet_product_id'``, columna colgada por
       ``models/project_project.py``.
   * - ``is_project_map_empty`` (:23)
     - **portado como property** — ``compute`` sin ``store`` (:85-88):
       ¿el proyecto tiene tarifas por empleado? El modelo que cuenta
       (``project.sale.line.employee.map``) es propio de este addon.
   * - ``sale_order_id`` (:21)
     - **BLOQUEADO** — redeclaración que sólo estrecha el ``domain``; el campo
       lo declara ``sale_project`` (``odoo19c: sale_project/models/
       project_task.py:25``) y no existe aquí (0 hits). Sucesor: tarea
       PENDIENTE DE ASIGNAR (hogar ``addons/sale_project``).
   * - ``has_multi_sol`` (:24)
     - **BLOQUEADO** — su compute (:90-93) compara ``timesheet_ids.so_line``
       contra ``sale_line_id``: dos bloqueadores, ``so_line`` (ver
       ``models/hr_timesheet.py``) y ``sale_line_id``.
   * - ``remaining_hours_so`` (:26)
     - **BLOQUEADO** por ``sale_line_id.remaining_hours``; ``remaining_hours``
       lo declara este addon sobre la línea de pedido (:14 de
       ``sale_order_line.py``) y allí queda bloqueado por ``qty_delivered``.
   * - ``remaining_hours_available`` (:27)
     - **BLOQUEADO** — ``related='sale_line_id.remaining_hours_available'``,
       misma cadena.
   * - ``last_sol_of_customer`` (:28)
     - **BLOQUEADO** — su compute (:61-70) busca la última línea vendible del
       cliente con ``_domain_sale_line_service`` + ``order_partner_id`` +
       ``remaining_hours``; sólo la primera mitad existe aquí (portada por
       ``sale_service`` como ``service_lines(queryset)``).

.. list-table:: Métodos — 0 portados, 12 con desenlace
   :header-rows: 1

   * - Método de la referencia (línea)
     - Desenlace aquí
   * - ``_get_default_partner_id`` (:10-19)
     - BLOQUEADO — ``project.ProjectTask`` de este árbol no declara
       ``partner`` (0 hits), y la rama que añade la fuente lee
       ``sale_line_employee_ids.sale_line_id.order_partner_id``.
   * - ``TASK_PORTAL_READABLE_FIELDS`` (:30-35)
     - BLOQUEADO — la lista base la declara ``project`` para su portal, que no
       existe en este árbol (0 hits); y los dos campos que añade están
       bloqueados.
   * - ``_compute_remaining_hours_so`` (:37-55) /
       ``_search_remaining_hours_so`` (:57-59)
     - BLOQUEADOS por ``sale_line_id.remaining_hours`` y ``so_line``.
   * - ``_compute_last_sol_of_customer`` (:61-70) /
       ``_get_last_sol_of_customer_domain`` (:95-111)
     - BLOQUEADOS — ver ``last_sol_of_customer`` arriba. El segundo además usa
       ``project_sale_order_id`` (``sale_project``).
   * - ``_inverse_partner_id`` (:72-77) / ``_compute_sale_line`` (:78-83)
     - BLOQUEADOS por ``sale_line_id`` y ``allow_billable``.
   * - ``_compute_is_project_map_empty`` (:85-88)
     - portado dentro de la property ``is_project_map_empty``.
   * - ``_compute_has_multi_sol`` (:90-93)
     - BLOQUEADO — ver ``has_multi_sol`` arriba.
   * - ``_get_timesheet`` (:113-116)
     - BLOQUEADO — el base lo declara ``hr_timesheet`` y no se portó (0 hits
       de ``_get_timesheet`` en ``addons/hr_timesheet``). El filtro que este
       addon le añade (``_is_not_billed``) **sí** existe aquí
       (``models/hr_timesheet.py``): el día que el base aterrice, la
       composición es de una línea.
   * - ``_get_action_view_so_ids`` (:118-119)
     - no portado — arma la lista de ids de un botón de navegación del cliente
       web; y depende de ``so_line``.
"""
from orm.model_classes import extend_model

from .project_sale_line_employee_map import ProjectSaleLineEmployeeMap


def pricing_type(self):
    """≙ ``pricing_type`` (``related='project_id.pricing_type'``,
    ``odoo19c: project_task.py:22``)."""
    return self.project.pricing_type if self.project_id else None


def timesheet_product(self):
    """≙ ``timesheet_product_id``
    (``related='project_id.timesheet_product_id'``,
    ``odoo19c: project_task.py:25``)."""
    return self.project.timesheet_product if self.project_id else None


def is_project_map_empty(self):
    """≙ ``is_project_map_empty`` + ``_compute_is_project_map_empty``
    (``odoo19c: project_task.py:23, 85-88``) — ¿el proyecto de la tarea NO
    tiene tarifas por empleado?

    La fuente lo lee con ``sudo()`` porque el mapeo es visible sólo al gestor;
    aquí la autorización es por CAPACIDAD a nivel de vista DRF, no por lectura
    de campo, así que la consulta va directa.
    """
    if not self.project_id:
        return True
    return not ProjectSaleLineEmployeeMap.objects.filter(
        project=self.project).exists()


def apply_sale_timesheet_project_task_extensions():
    """Cuelga las tres properties sobre ``project.ProjectTask`` — ≙
    ``_inherit = 'project.task'``.

    Sin bloque ``campos``: los cinco campos de la referencia que serían
    columna están bloqueados (ver el docstring del módulo). Par de Django
    porque el destino no declara ``_name``.
    """
    extend_model(
        'project', 'ProjectTask',
        propiedades={
            'pricing_type': pricing_type,
            'timesheet_product': timesheet_product,
            'is_project_map_empty': is_project_map_empty,
        },
    )


__all__ = ['apply_sale_timesheet_project_task_extensions']
