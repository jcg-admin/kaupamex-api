"""``project.project`` — cómo se factura el tiempo del proyecto
(Odoo ``sale_timesheet``).

Adaptación de Odoo ``sale_timesheet/models/project_project.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 529 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Medido por AST sobre la referencia: 1 clase (``ProjectProject``,
``_inherit``), **7 campos** y **32 métodos** — es el archivo más grande del
addon, y el que más superficie pierde por bloqueo ajeno.

Las tres piezas que este addon aporta al proyecto
====================================================

1. ``pricing_type`` — **cómo se decide el precio del tiempo**: por tarea, por
   proyecto, o por empleado. Es lo que consume ``_hourly_cost`` de
   ``models/hr_timesheet.py`` para preferir la tarifa del mapeo.
2. ``billing_type`` — si el proyecto se factura a mano o no se factura. Lo
   consume la clasificación ``timesheet_invoice_type``.
3. ``timesheet_product`` — el producto de servicio con el que se factura el
   tiempo por defecto.

Porte símbolo por símbolo
============================

.. list-table:: Campos — 2 columnas, 2 properties, 3 con desenlace
   :header-rows: 1

   * - Campo de la referencia (línea)
     - Desenlace aquí
   * - ``billing_type`` (:61-71)
     - **portado** — columna ``Selection`` con los dos valores verbatim
       (``not_billable``/``manually``), ``default='not_billable'``,
       ``required`` (no nullable). Su ``compute`` (:158-159) queda bloqueado
       por ``allow_billable``.
   * - ``timesheet_product_id`` (:46-56)
     - **portado** — ``timesheet_product`` (FK ``product.ProductProduct``).
       Su ``domain`` (``type=service``, ``invoice_policy=delivery``,
       ``service_type=timesheet``) y su ``default``
       (``env.ref('sale_timesheet.time_product')``) quedan bloqueados: ninguno
       de los tres campos del dominio existe aquí (``invoice_policy`` y
       ``service_type`` los declaran ``sale``/``sale_project``), y el default
       exige la fila semilla ``sale_timesheet.time_product`` de
       ``data/sale_service_data.xml``. Sucesor de la semilla: tarea PENDIENTE
       DE ASIGNAR (es data, no esquema — mismo criterio que el seed de
       ``account_fleet``).
   * - ``pricing_type`` (:29-36)
     - **portado como property, parcial declarado** — la fuente lo declara
       ``compute`` **sin** ``store``, así que ``property`` es su forma exacta
       en este idioma. Dos de sus tres ramas son alcanzables:
       ``employee_rate`` cuando hay entradas de
       ``project.sale.line.employee.map`` (modelo propio de este addon), y
       ``task_rate`` en otro caso. La rama ``fixed_rate`` depende de
       ``Project.sale_line_id`` (``odoo19c: sale_project/models/
       project_project.py:28``), ausente aquí. El apagado por
       ``allow_billable`` (``(self - billable_projects).update(...)``) tampoco
       es alcanzable, por el mismo addon.
   * - ``warning_employee_rate`` (:57)
     - **portado como property** — su ``compute`` (:123-124) asigna ``False``
       incondicionalmente en la referencia; la property lo devuelve verbatim.
   * - ``sale_line_employee_ids`` (:37-45)
     - **portado como el reverso de la FK** — no hace falta campo: es el
       ``related_name='sale_line_employee_ids'`` de
       ``ProjectSaleLineEmployeeMap.project``
       (``models/project_sale_line_employee_map.py``). Mismo nombre que la
       referencia, a propósito.
   * - ``partner_id`` (:58-59)
     - **BLOQUEADO** — redeclaración que sólo añade ``compute``/``store``; el
       compute (:127-135) deriva el cliente de ``sale_line_id.order_partner_id``
       (``sale_project``). La columna ``partner`` ya existe en
       ``project.Project`` de este árbol, intacta.
   * - ``allocated_hours`` (:60)
     - **no-op declarado** — ``fields.Float()`` sin argumentos: en la
       referencia sólo levanta la restricción de grupo del campo heredado. La
       columna ya la cuelga ``hr_timesheet``
       (``api: addons/hr_timesheet/models/project_project.py:140``); volver a
       colgarla la duplicaría.

.. list-table:: Métodos — 6 portados, 26 con desenlace
   :header-rows: 1

   * - Método de la referencia (línea)
     - Desenlace aquí
   * - ``_get_profitability_labels`` (:350-360)
     - **portado** — encadenado con fusión de dict sobre el de
       ``project_account`` (precedente idéntico:
       ``api: addons/project_account/models/project_project.py``). Siete
       etiquetas, verbatim.
   * - ``_get_profitability_sequence_per_invoice_type`` (:362-372)
     - **portado** — ídem, siete secuencias verbatim.
   * - ``_get_service_policy_to_invoice_type`` (:492-499)
     - **portado** — cuatro pares verbatim, fusión de dict.
   * - ``_get_foldable_section`` (:270-277)
     - **portado** — cuatro secciones verbatim, concatenación de lista
       (``extend_list`` de ``orm.method_chain``).
   * - ``_get_template_default_context_whitelist`` (:514-518)
     - **portado** — ídem, un elemento (``allow_timesheets``).
   * - ``_get_project_to_template_warnings`` (:507-512)
     - **portado** — el aviso "este proyecto tiene horas registradas" se puede
       medir: ``AccountAnalyticLine.objects.filter(project=...)`` existe desde
       ``hr_timesheet``. Concatenación de lista.
   * - ``default_get`` (:17-24) / ``_default_timesheet_product_id`` (:26-27)
     - BLOQUEADOS por la semilla ``sale_timesheet.time_product`` (ver
       ``timesheet_product`` arriba).
   * - ``_get_view`` (:74-79)
     - no portado — reescribe una etiqueta del XML de la vista de formulario
       de Odoo; sin ese motor de vistas aquí.
   * - ``_compute_pricing_type`` (:82-91)
     - portado dentro de la property ``pricing_type`` (parcial declarado).
   * - ``_search_pricing_type`` (:93-112)
     - BLOQUEADO — traduce el compute a dominio de búsqueda sobre
       ``sale_line_id``/``allow_billable`` (``sale_project``). Con
       ``pricing_type`` como property no hay columna que buscar; el sucesor
       natural es un ``QuerySet`` helper cuando ``allow_billable`` aterrice.
   * - ``_compute_timesheet_product_id`` (:115-121)
     - BLOQUEADO por ``allow_billable`` y por la semilla del producto.
   * - ``_compute_warning_employee_rate`` (:123-124)
     - portado dentro de la property ``warning_employee_rate``.
   * - ``_compute_partner_id`` (:127-135) / ``_compute_sale_line_id`` (:138-147)
     - BLOQUEADOS por ``sale_line_id``/``order_partner_id`` (``sale_project``).
   * - ``_compute_sale_order_count`` (:150-155)
     - BLOQUEADO — ``sale_order_count``/``sale_order_line_count`` los declara
       ``sale_project`` (0 hits aquí).
   * - ``_compute_billing_type`` (:158-159)
     - BLOQUEADO por ``allow_billable``. La mitad que sí se puede medir
       (``allow_timesheets``) no basta: apagar ``billing_type`` sólo por ella
       sería más agresivo que la fuente.
   * - ``_check_sale_line_type`` (:162-167)
     - BLOQUEADO por ``sale_line_id`` y por ``is_service``/``is_expense`` de
       la línea de pedido.
   * - ``write`` (:169-175)
     - BLOQUEADO por ``so_line`` (ver el bloqueo raíz en
       ``models/hr_timesheet.py``) y por ``allow_billable``.
   * - ``_update_timesheets_sale_line_id`` (:177-184)
     - BLOQUEADO por ``so_line``. Es el efecto que
       ``ProjectSaleLineEmployeeMap.save()`` invoca y que hoy es un no-op
       declarado (``update_project_timesheet``).
   * - ``action_view_timesheet`` (:186-209),
       ``action_billable_time_button`` (:211-221),
       ``action_profitability_items`` (:223-247),
       ``action_project_timesheets`` (:249-257)
     - no portados — navegación pura del cliente web
       (``ir.actions.act_window`` / ``_for_xml_id`` / vistas pivot). Mismo
       criterio que ``project_account/models/project_project.py`` para
       ``action_profitability_items``.
   * - ``get_panel_data`` (:263-268)
     - BLOQUEADO por ``Project.account_id`` — el mismo bloqueador que
       ``project_account`` ya declaró para cinco de sus símbolos.
   * - ``_get_sale_order_items_query`` (:279-320)
     - BLOQUEADO — construye SQL con ``odoo.tools.SQL``/``Query`` sobre
       ``project_sale_order_item``, tabla que arma ``sale_project``; y usa
       ``so_line``. Dos bloqueadores independientes.
   * - ``_get_domain_from_section_id`` (:322-348)
     - BLOQUEADO por ``_get_sale_items_domain`` (``sale_project``) y por
       ``product.invoice_policy``/``service_type``.
   * - ``_get_profitability_aal_domain`` (:374-379),
       ``_get_profitability_items_from_aal`` (:381-483),
       ``_get_profitability_items`` (:501-505),
       ``_get_domain_aal_with_no_move_line`` (:485-490)
     - BLOQUEADOS — el panel de rentabilidad completo. Tres bloqueadores a la
       vez: ``so_line``, ``Project.account_id`` (ya declarado por
       ``project_account``) y ``res.currency._convert`` (la misma divergencia
       multi-moneda que ``hr_timesheet`` declaró para ``amount``). Sucesor
       único: tarea PENDIENTE DE ASIGNAR — el panel se cablea cuando las tres
       aterricen, no por partes.
   * - ``_get_processed_analytic_account_vals`` (:520-529)
     - BLOQUEADO por ``Project.account_id`` (mismo bloqueador).
"""
import fields
import models

from addons.analytic.models import AccountAnalyticLine
from addons.product.models import ProductProduct
from orm.method_chain import chain_method, extend_list
from orm.model_classes import extend_model

#: ≙ el ``selection`` de ``pricing_type`` (``odoo19c: project_project.py:29-33``),
#: verbatim. Se conserva aunque el campo sea una ``property``: nombra el
#: vocabulario, que es lo que se pierde al portar sólo el cálculo.
PRICING_TYPE_TASK_RATE = 'task_rate'
PRICING_TYPE_FIXED_RATE = 'fixed_rate'
PRICING_TYPE_EMPLOYEE_RATE = 'employee_rate'
PRICING_TYPES = [
    (PRICING_TYPE_TASK_RATE, 'Task rate'),
    (PRICING_TYPE_FIXED_RATE, 'Project rate'),
    (PRICING_TYPE_EMPLOYEE_RATE, 'Employee rate'),
]

#: ≙ el ``selection`` de ``billing_type`` (``odoo19c: project_project.py:63-66``).
BILLING_TYPE_NOT_BILLABLE = 'not_billable'
BILLING_TYPE_MANUALLY = 'manually'
BILLING_TYPES = [
    (BILLING_TYPE_NOT_BILLABLE, 'not billable'),
    (BILLING_TYPE_MANUALLY, 'billed manually'),
]


def _merge_with_previous(new, previous):
    """``combine`` para hooks que aportan claves a un dict — ≙
    ``{**super()…, **propio}``. Idéntico al de
    ``project_account/models/project_project.py``: primero lo que ya había,
    después lo que aporta este addon, como en la referencia.
    """
    return {**(previous or {}), **(new or {})}


def pricing_type(self):
    """≙ ``pricing_type`` + ``_compute_pricing_type``
    (``odoo19c: project_project.py:29-36, 82-91``) — **parcial declarado**.

    ``employee_rate`` cuando el proyecto tiene tarifas por empleado;
    ``task_rate`` en otro caso. La rama ``fixed_rate`` (``sale_line_id``
    fijado) y el apagado por ``allow_billable`` quedan bloqueados por
    ``sale_project`` — ver el docstring del módulo.
    """
    if self.pk is not None and self.sale_line_employee_ids.exists():
        return PRICING_TYPE_EMPLOYEE_RATE
    return PRICING_TYPE_TASK_RATE


def warning_employee_rate(self):
    """≙ ``warning_employee_rate`` + ``_compute_warning_employee_rate``
    (``odoo19c: project_project.py:57, 123-124``).

    La referencia asigna ``False`` incondicionalmente — el aviso lo levanta
    un addon Enterprise que redefine el compute. Se porta verbatim para no
    perder el punto de extensión.
    """
    return False


def _get_profitability_labels(self):
    """≙ ``_get_profitability_labels`` (``odoo19c: project_project.py:350-360``)
    — las siete etiquetas que este addon aporta al panel de rentabilidad,
    verbatim.

    Devuelve SOLO el aporte propio; la fusión con la implementación previa la
    hace ``chain_method`` con ``_merge_with_previous``.
    """
    return {
        'billable_fixed': 'Timesheets (Fixed Price)',
        'billable_time': 'Timesheets (Billed on Timesheets)',
        'billable_milestones': 'Timesheets (Billed on Milestones)',
        'billable_manual': 'Timesheets (Billed Manually)',
        'non_billable': 'Timesheets (Non-Billable)',
        'timesheet_revenues': 'Timesheets revenues',
        'other_costs': 'Materials',
    }


def _get_profitability_sequence_per_invoice_type(self):
    """≙ ``_get_profitability_sequence_per_invoice_type``
    (``odoo19c: project_project.py:362-372``) — el orden de las siete
    secciones dentro del panel. Valores verbatim de la fuente."""
    return {
        'billable_fixed': 1,
        'billable_time': 2,
        'billable_milestones': 3,
        'billable_manual': 4,
        'non_billable': 5,
        'timesheet_revenues': 6,
        'other_costs': 12,
    }


def _get_service_policy_to_invoice_type(self):
    """≙ ``_get_service_policy_to_invoice_type``
    (``odoo19c: project_project.py:492-499``) — de política de servicio del
    producto a tipo de facturación del apunte. Cuatro pares verbatim.

    Se porta aunque ``service_policy`` no exista todavía en este árbol
    (``sale_project``): es una **tabla de correspondencia pura**, sin lectura
    de campo, y su ausencia dejaría al panel sin la mitad del mapeo el día que
    el campo aterrice.
    """
    return {
        'ordered_prepaid': 'billable_fixed',
        'delivered_milestones': 'billable_milestones',
        'delivered_timesheet': 'billable_time',
        'delivered_manual': 'billable_manual',
    }


def _get_foldable_section(self):
    """≙ ``_get_foldable_section`` (``odoo19c: project_project.py:270-277``) —
    las cuatro secciones plegables que aporta este addon, verbatim.

    Devuelve SOLO el aporte propio; ``extend_list`` concatena con lo previo en
    el orden de la fuente (primero ``super()``, después lo propio).
    """
    return [
        'billable_fixed',
        'billable_milestones',
        'billable_time',
        'billable_manual',
    ]


def _get_template_default_context_whitelist(self):
    """≙ ``_get_template_default_context_whitelist``
    (``odoo19c: project_project.py:514-518``) — qué campo se arrastra al
    crear un proyecto desde plantilla."""
    return ['allow_timesheets']


def _get_project_to_template_warnings(self):
    """≙ ``_get_project_to_template_warnings``
    (``odoo19c: project_project.py:507-512``) — avisa si el proyecto que se va
    a convertir en plantilla ya tiene horas registradas.

    Portado entero: la medición que la fuente hace con ``search_count`` sobre
    ``account.analytic.line`` filtrando por proyecto es exactamente el
    ``project`` que ``hr_timesheet`` cuelga sobre el apunte
    (``api: addons/hr_timesheet/models/hr_timesheet.py``).
    """
    if self.pk is not None and AccountAnalyticLine.objects.filter(
            project=self).exists():
        return ['This project is current linked to timesheet.']
    return []


def _chain_project_hooks(model):
    """Encadena los seis hooks de datos puros con la combinación correcta.

    Es el ``luego`` de ``extend_model``, y no su bloque ``metodos``, porque
    ese bloque usa el relevo por ``None`` y aquí la semántica correcta es la
    combinación: fusión de dict para tres, concatenación de lista para tres.
    Mismo criterio que ``project_account``.
    """
    for name, function in (
        ('_get_profitability_labels', _get_profitability_labels),
        ('_get_profitability_sequence_per_invoice_type',
         _get_profitability_sequence_per_invoice_type),
        ('_get_service_policy_to_invoice_type',
         _get_service_policy_to_invoice_type),
    ):
        chain_method(model, name, function, combine=_merge_with_previous)

    for name, function in (
        ('_get_foldable_section', _get_foldable_section),
        ('_get_template_default_context_whitelist',
         _get_template_default_context_whitelist),
        ('_get_project_to_template_warnings', _get_project_to_template_warnings),
    ):
        chain_method(model, name, function, combine=extend_list)


def apply_sale_timesheet_project_project_extensions():
    """Cuelga sobre ``project.Project`` el vocabulario de facturación del
    tiempo — ≙ ``_inherit = 'project.project'``.

    Par de Django (``'project', 'Project'``) porque el destino no declara
    ``_name`` (``api: addons/project/models/project_project.py``).
    """
    extend_model(
        'project', 'Project',
        campos={
            'billing_type': fields.Selection(
                max_length=16, choices=BILLING_TYPES,
                default=BILLING_TYPE_NOT_BILLABLE,
                verbose_name='Modo de facturación',
                help_text='Odoo billing_type (compute, store, required, '
                          'default=not_billable). El compute queda bloqueado '
                          'por allow_billable (sale_project).',
            ),
            'timesheet_product': fields.Many2one(
                ProductProduct, on_delete=models.SET_NULL,
                null=True, blank=True,
                related_name='timesheet_projects',
                verbose_name='Producto de hoja de horas',
                help_text='Odoo timesheet_product_id. Servicio con el que se '
                          'factura por defecto el tiempo de una tarea. Su '
                          'domain y su default quedan bloqueados — ver el '
                          'docstring del módulo.',
            ),
        },
        propiedades={
            'pricing_type': pricing_type,
            'warning_employee_rate': warning_employee_rate,
        },
        luego=_chain_project_hooks,
    )


__all__ = [
    'PRICING_TYPES',
    'BILLING_TYPES',
    'apply_sale_timesheet_project_project_extensions',
]
