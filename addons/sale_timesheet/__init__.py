"""``sale_timesheet`` — vender tiempo: la hora registrada se convierte en
cantidad entregada de un pedido, y de ahí en una línea de factura.

Adaptación de Odoo ``sale_timesheet`` (``odoo-tools@622ddc2a``, ``odoo19c:``,
licencia ``LGPL-3`` declarada en su ``__manifest__.py``) — atribución y aviso
de licencia preservados (DEC-KX-03).

Qué es: el puente entre ``hr_timesheet`` (quién dedicó cuánto tiempo a qué
tarea) y ``sale`` (qué se le vendió a quién). Cuelga sobre **doce modelos de
seis addons ajenos** — ``account.analytic.line``, ``project.project``,
``project.task``, ``sale.order``, ``sale.order.line``, ``account.move``,
``account.move.line``, ``account.move.reversal``, ``product.template``,
``product.product``, ``hr.employee``, ``res.config.settings`` — y declara **un
modelo propio**, ``project.sale.line.employee.map``: la tarifa a la que se
factura el tiempo de cada empleado en cada proyecto.

Medido contra la referencia (``odoo19c: addons/sale_timesheet/``): **23
archivos ``.py``** — 13 de modelo, 2 de informe, 1 de asistente, 1 de
controlador, 4 ``__init__`` de paquete, el ``__manifest__`` y el ``__init__``
raíz. Los 23 están portados con desenlace declarado símbolo por símbolo en su
propio docstring.

El bloqueo raíz, y por qué se declara en vez de rodearse
==========================================================

``so_line`` sobre ``account.analytic.line`` —*"a qué línea de pedido se le
carga esta hora"*— **no lo declara este addon**: lo declara ``sale``
(``odoo19c: sale/models/analytic.py:9``). ``sale_timesheet`` sólo lo
redefine. En este árbol ``addons/sale/models/`` tiene cuatro archivos y
ninguno lo declara (0 hits en ``addons/`` y ``src/``).

Portarlo desde aquí pondría un símbolo de ``sale`` en el hogar equivocado —
el defecto que :ref:`h-api-568` y :ref:`h-api-578` registran. Queda declarado
como bloqueo, y **cada símbolo que arrastra lo cita por su nombre**, de modo
que ``grep -rn so_line addons/sale_timesheet/`` recupera el conjunto completo
de lo que se desbloquea el día que aterrice.

La misma forma tienen los otros cuatro bloqueadores ajenos, todos de addons
cuyo puerto en este árbol es PARCIAL declarado o inexistente:

============================================  ==========================================
Pieza ausente                                  Hogar (fuera del write-set)
============================================  ==========================================
``AccountAnalyticLine.so_line``                ``addons/sale`` (``models/analytic.py``)
``SaleOrderLine.qty_delivered`` +              ``addons/sale``
``invoice_status`` + ``product_uom_id``
``ProductTemplate.invoice_policy``             ``addons/sale``
``Project.allow_billable`` +                   ``addons/sale_project``
``sale_line_id``; ``ProjectTask.sale_line_id``
``ProductTemplate.service_policy`` +           ``addons/sale_project``
``service_type``
============================================  ==========================================

Qué SÍ funciona hoy, entero
==============================

1. **La tarifa por empleado.** ``project.sale.line.employee.map`` (modelo
   propio, tabla real, unicidad ``(proyecto, empleado)``) más el override de
   ``_hourly_cost`` en ``models/hr_timesheet.py``: cuando el proyecto es de
   tarifa por empleado, el costo de la hora sale del mapeo y no del
   ``hourly_cost`` del empleado. Es el mecanismo central del addon y **no
   depende de ``so_line``**.
2. **El enlace hora ↔ factura**, en su mitad de integridad:
   ``AccountAnalyticLine.timesheet_invoice`` (columna), ``_is_not_billed``,
   el candado de borrado de horas ya facturadas, y el desenlace automático al
   rehacer una factura (``models/account_move_reversal.py``, único archivo
   del addon sin ningún símbolo bloqueado).
3. **Los agregados de tiempo** del pedido y de la factura, con conversión de
   unidad: ``SaleOrder.timesheet_count``/``timesheet_total_duration`` y
   ``AccountMove.timesheet_count``/``timesheet_total_duration``.
4. **El vocabulario**: ``pricing_type`` (3 valores), ``billing_type`` (2),
   ``timesheet_invoice_type`` (9) y las tablas de correspondencia del panel de
   rentabilidad (etiquetas, secuencias, secciones plegables, política de
   servicio → tipo de facturación), todas verbatim de la referencia.

Instalación automática — sin wiring pendiente en settings
============================================================

``LOCAL_APPS`` se deriva del grafo de addons
(``src/config/settings/base.py::_local_apps``, recorre todo directorio bajo
``ADDONS_PATHS`` con ``__init__.py``). Este addon entra a ``INSTALLED_APPS``
sin que el orquestador toque ``config/settings/base.py``.

Wiring pendiente (fuera del alcance de este agente)
=====================================================

1. **Migraciones de columna** en las apps DUEÑAS de cada modelo tocado —
   mismo criterio que ``hr_timesheet``/``account_fleet``:

   - ``addons/analytic/migrations/`` — ``timesheet_invoice``, ``order``,
     ``is_so_line_edited``, ``timesheet_invoice_type`` sobre
     ``AccountAnalyticLine``.
   - ``addons/project/migrations/`` — ``billing_type``, ``timesheet_product``
     sobre ``Project``.
   - ``addons/sale/migrations/`` — ``has_displayed_warning_upsell`` sobre
     ``SaleOrderLine``.
   - ``addons/product/migrations/`` — ``service_upsell_threshold`` sobre
     ``ProductTemplate``.
   - Este addon (``addons/sale_timesheet/migrations/``) — la tabla propia de
     ``ProjectSaleLineEmployeeMap``, con su restricción
     ``uniqueness_employee``.

2. **Data semilla** — ``sale_timesheet.time_product``
   (``odoo19c: data/sale_service_data.xml``), el producto "Time" con el que se
   factura el tiempo por defecto. Sin él quedan bloqueados el ``default`` de
   ``Project.timesheet_product`` y los cuatro candados
   ``_unlink_except_master_data``/``write`` de
   ``models/product_product.py``/``product_template.py``. Es **data, no
   esquema**; el precedente de forma es
   ``addons/account_fleet/data/fleet_service_types.py`` + su migración de
   siembra.

3. **``post_init_hook`` / ``uninstall_hook``** de la referencia
   (``__init__.py:9-25`` de la fuente): el primero reclasifica los productos de
   servicio existentes a ``service_type='timesheet'``; el segundo relaja dos
   reglas de registro de ``account``. Los dos operan sobre campos ausentes
   (``service_type``, ``invoice_policy``) y sobre ``ir.rule``, y los dos son
   ganchos del instalador de módulos de Odoo, que este árbol no tiene: quedan
   fuera del porte, con la misma tarea sucesora que los campos que leen.
"""
