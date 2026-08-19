"""Portal del cliente — las horas y las facturas de su pedido
(Odoo ``sale_timesheet``).

Adaptación de Odoo ``sale_timesheet/controllers/portal.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 137 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Medido por AST sobre la referencia: **3 clases** (``PortalProjectAccount``,
``SaleTimesheetCustomerPortal``, ``SaleTimesheetSaleCustomerPortal``) y **9
métodos**. **No-op medido** — 0 de 9, y el bloqueo es de CAPA, no de símbolo.

Por qué ninguna de las tres clases se porta
==============================================

Las tres heredan de controladores de portal de Odoo que **no existen en este
árbol**, y no por olvido: la capa web de este proyecto es **DRF**, no el
portal renderizado por QWeb de la referencia. Medido, los cinco padres::

    odoo.addons.account.controllers.portal.PortalAccount        → 0 hits
    odoo.addons.hr_timesheet.controllers.portal.TimesheetCustomerPortal → 0 hits
    odoo.addons.portal.controllers.portal.pager                 → 0 hits
    odoo.addons.project.controllers.portal.ProjectCustomerPortal → 0 hits
    odoo.addons.sale.controllers.portal.CustomerPortal          → 0 hits

``addons/hr_timesheet/`` y ``addons/project/`` no tienen directorio
``controllers/``; ``addons/sale/controllers/`` sí, pero contiene
``main.py``/``serializers.py``/``urls.py`` — vistas DRF con rutas y
serializadores, no un ``CustomerPortal`` con ``@http.route`` y
``request.render``.

Los nueve métodos de la referencia son, sin excepción, **piezas de esa capa**:
``_invoice_get_page_view_values`` y ``_task_get_page_view_values`` rellenan el
diccionario de una plantilla QWeb; ``_get_searchbar_inputs`` /
``_get_searchbar_groupby`` / ``_get_searchbar_sortings`` describen la barra de
búsqueda del portal; ``_get_search_domain`` traduce esa barra a dominio;
``portal_my_tasks_invoices`` y ``portal_my_timesheets`` son rutas HTTP que
devuelven HTML renderizado.

Portarlos exigiría inventar el portal QWeb entero — no adaptar un símbolo,
sino traer una capa que este proyecto rechazó por diseño. El equivalente
legítimo es un **conjunto de vistas DRF** con sus serializadores, y ése es un
diseño nuevo (RUP: caso de uso + vista de arquitectura antes de construir,
``docs-design-first-rup.md``), no un porte.

Segundo bloqueador, independiente
====================================

Aunque la capa existiera, siete de los nueve métodos leen ``so_line`` o
``sale_line_ids`` —el bloqueo raíz del addon, ver ``models/hr_timesheet.py``—
o ``_timesheet_get_portal_domain`` / ``_timesheet_get_sale_domain`` /
``_is_timesheet_encode_uom_day``, los tres bloqueados en ese mismo archivo.

Sucesor
==========

Tarea PENDIENTE DE ASIGNAR: diseñar la superficie DRF de consulta de horas
facturables del cliente (qué horas de qué pedido, con su factura), a partir de
los tres agregados que **sí** están portados —
``SaleOrder.timesheet_count``/``timesheet_total_duration``
(``models/sale_order.py``) y ``AccountMove.timesheet_count``
(``models/account_move.py``)—, que es exactamente la información que los tres
controladores de la referencia sirven.
"""
