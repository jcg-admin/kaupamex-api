"""``project.sale.line.employee.map`` — la tarifa por empleado del proyecto.

Adaptación de Odoo ``sale_timesheet/models/project_sale_line_employee_map.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 140 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Es el **único modelo propio** de este addon (``_name`` declarado, no
``_inherit``): la fila que dice *"cuando el empleado E registra horas en el
proyecto P, esas horas se facturan contra la línea de pedido L y cuestan
C por hora"*. Sin ella, ``project.pricing_type`` nunca vale ``employee_rate``.

Porte símbolo por símbolo — 2 atributos de clase, 13 campos, 1 restricción,
13 métodos
=============================================================================

Medido por AST sobre la referencia.

Atributos de clase (``atributos-de-clase-de-modelo.md``): la fuente declara
**dos** (``_name`` :174, ``_description`` :175) y los dos se portan verbatim,
además de su forma Django (``Meta.db_table`` / ``Meta.verbose_name``).

.. list-table:: Campos
   :header-rows: 1

   * - Campo de la referencia (línea)
     - Desenlace aquí
   * - ``project_id`` (:187)
     - **portado** — ``project`` (FK ``project.Project``, requerido,
       ``db_index``). El ``domain=[('is_template','=',False)]`` de la fuente
       es filtro de vista: ``project.Project`` de este árbol no declara
       ``is_template`` (0 hits), así que la hoja no tiene columna que filtrar.
   * - ``employee_id`` (:188)
     - **portado** — ``employee`` (FK ``hr.HrEmployee``, requerido). El
       ``domain="[('id','not in',existing_employee_ids)]"`` lo cubre la
       restricción de unicidad, que es su forma en base de datos.
   * - ``sale_line_id`` (:190-194)
     - **portado** — ``sale_line`` (FK ``sale.SaleOrderLine``, nullable). Su
       ``compute``/``domain`` quedan BLOQUEADOS: dependen de
       ``sale.order.line._sellable_lines_domain`` y ``order_partner_id``,
       ninguno de los dos en este árbol (0 hits). El campo es escribible
       directo — mismo criterio que ``hr_timesheet`` para ``task``/``project``.
   * - ``price_unit`` (:198)
     - **portado** — ``price_unit`` (Float, ``compute`` + ``store``),
       sincronizado en ``pre_save`` desde ``sale_line.price_unit``.
   * - ``currency_id`` (:199)
     - **portado** — ``currency`` (FK ``base.ResCurrency``), sincronizado en
       el mismo receptor. La referencia lo deriva de
       ``sale_line_id.currency_id``; aquí de ``sale_line.order.company.currency``
       (``sale.SaleOrderLine`` no declara ``currency``: 0 hits).
   * - ``cost`` (:200-201)
     - **portado** — ``cost`` (Monetary), sincronizado desde
       ``employee.hourly_cost`` mientras ``is_cost_changed`` sea falso, ≙
       ``_compute_cost``.
   * - ``is_cost_changed`` (:204)
     - **portado** — Boolean, ≙ ``_compute_is_cost_changed``.
   * - ``existing_employee_ids`` (:189)
     - **portado** como ``property`` — ``compute`` sin ``store`` en la fuente.
   * - ``sale_order_id`` (:195)
     - **BLOQUEADO** — ``related='project_id.sale_order_id'``, y
       ``Project.sale_order_id`` lo declara ``sale_project``
       (``odoo19c: sale_project/models/project_project.py:35``), addon cuyo
       puerto en este árbol es PARCIAL declarado. Hogar ``addons/sale_project``,
       fuera del write-set. Sucesor: tarea PENDIENTE DE ASIGNAR.
   * - ``company_id`` (:196) / ``partner_id`` (:197)
     - **portados** como ``property`` (``related='project_id.*'``;
       ``Project.company``/``Project.partner`` sí existen aquí).
   * - ``cost_currency_id`` (:203)
     - **portado** como ``property`` — ``related='employee_id.currency_id'``,
       y ``HrEmployee.currency`` ya es property en este árbol
       (``api: addons/hr/models/hr_employee.py``).
   * - ``display_cost`` (:202)
     - **BLOQUEADO** — su ``compute``/``inverse`` convierten el costo horario
       a costo diario cuando ``env.company.timesheet_encode_uom_id`` es
       ``uom.product_uom_day``: hace falta la compañía **ambiental** (sin
       ``env`` aquí) y la fila semilla de UOM. La aritmética que sí es
       independiente del entorno queda expuesta en
       :func:`working_hours_per_calendar` / :func:`display_cost_for`, que el
       llamador invoca con la unidad ya resuelta.

.. list-table:: Métodos
   :header-rows: 1

   * - Método de la referencia (línea)
     - Desenlace aquí
   * - ``_compute_price_unit`` (:229-235)
     - **portado** — dentro del receptor ``pre_save``.
   * - ``_compute_currency_id`` (:237-240)
     - **portado** — ídem (con la divergencia de origen declarada arriba).
   * - ``_compute_cost`` (:242-247)
     - **portado** — ídem.
   * - ``_compute_is_cost_changed`` (:288-291)
     - **portado** — ídem.
   * - ``_compute_existing_employee_ids`` (:211-218)
     - **portado** — ``property existing_employees``.
   * - ``_get_working_hours_per_calendar`` (:249-264)
     - **portado** — :func:`working_hours_per_calendar`, sin el ``_read_group``
       del ORM de la fuente (agregación equivalente en Python sobre el
       queryset). ``ResourceCalendar.hours_per_day`` ya es property aquí.
   * - ``_compute_display_cost`` (:266-276) / ``_inverse_display_cost`` (:278-286)
     - **parcial declarado** — :func:`display_cost_for` /
       :func:`cost_from_display_cost` llevan la aritmética; quién decide
       ``is_uom_day`` es el llamador, porque la fuente lo lee de la compañía
       ambiental.
   * - ``_domain_sale_line_id`` (:177-185)
     - **BLOQUEADO** — ``sale.order.line._sellable_lines_domain`` no existe en
       este árbol (0 hits); ``_domain_sale_line_service`` sí, portado por
       ``sale_service`` como ``service_lines(queryset)``. Con una de las dos
       mitades ausente el dominio compuesto no se puede armar sin inventar la
       otra. Sucesor: tarea PENDIENTE DE ASIGNAR (hogar ``addons/sale``).
   * - ``create`` (:293-297) / ``write`` (:299-302)
     - **portados** — el ``save()`` del modelo llama a
       :func:`update_project_timesheet` cuando hay ``sale_line``, ≙ el
       ``_update_project_timesheet`` que ambos invocan en la fuente.
   * - ``_update_project_timesheet`` (:304-305)
     - **BLOQUEADO en su efecto** — delega en
       ``project.project._update_timesheets_sale_line_id``, que escribe
       ``so_line`` en los apuntes; ``so_line`` lo declara ``sale``
       (``odoo19c: sale/models/analytic.py:9``) y no existe aquí. Ver el
       bloqueo raíz en ``models/hr_timesheet.py``.

Restricción
==============

``_uniqueness_employee`` (:206-209) — ``UNIQUE(project_id, employee_id)``,
portada verbatim como ``Meta.constraints`` con el nombre de la referencia
(``objetos de tabla`` de ``atributos-de-clase-de-modelo.md``).
"""
from decimal import Decimal

import fields
import models
from django.db.models.signals import pre_save
from django.dispatch import receiver

from addons.base.models import ResCurrency, TimeStampedModel
from addons.hr.models import HrEmployee
from addons.project.models import Project
from addons.sale.models import SaleOrderLine


class ProjectSaleLineEmployeeMap(TimeStampedModel):
    """``project.sale.line.employee.map`` — la tarifa de un empleado en un
    proyecto: contra qué línea de pedido se factura su tiempo y a qué costo.
    """

    _name = 'project.sale.line.employee.map'
    _description = 'Project Sales line, employee mapping'

    project = fields.Many2one(
        Project, on_delete=models.CASCADE, db_index=True,
        related_name='sale_line_employee_ids', verbose_name='Proyecto',
        help_text='Odoo project_id (required, index).',
    )
    employee = fields.Many2one(
        HrEmployee, on_delete=models.CASCADE,
        related_name='project_sale_line_maps', verbose_name='Empleado',
        help_text='Odoo employee_id (required).',
    )
    sale_line = fields.Many2one(
        SaleOrderLine, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='project_sale_line_maps',
        verbose_name='Línea de pedido de venta',
        help_text='Odoo sale_line_id. Escribible directo — su compute y su '
                  'domain quedan bloqueados (ver docstring del módulo).',
    )
    price_unit = fields.Float(
        default=0.0, verbose_name='Precio unitario',
        help_text='Odoo price_unit (compute, store) — se sincroniza desde '
                  'sale_line.price_unit en pre_save.',
    )
    currency = fields.Many2one(
        ResCurrency, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='project_sale_line_maps', verbose_name='Moneda',
        help_text='Odoo currency_id (compute, store).',
    )
    cost = fields.Monetary(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Costo por hora',
        help_text='Odoo cost. Sustituye al hourly_cost por defecto del '
                  'empleado en los apuntes de este proyecto.',
    )
    is_cost_changed = fields.Boolean(
        default=False, verbose_name='Costo modificado a mano',
        help_text='Odoo is_cost_changed (compute, store).',
    )

    class Meta:
        db_table = 'project_sale_line_employee_map'
        verbose_name = 'Tarifa de empleado en proyecto'
        verbose_name_plural = 'Tarifas de empleado en proyecto'
        constraints = [
            # ``_uniqueness_employee`` (:206-209), con el nombre de la fuente.
            models.UniqueConstraint(
                fields=['project', 'employee'], name='uniqueness_employee',
            ),
        ]

    def __str__(self):
        return f'{self.project} / {self.employee}'

    # -- related sin columna → property (≙ compute sin store) --------------

    @property
    def company(self):
        """≙ ``company_id`` (``related='project_id.company_id'``, :196)."""
        return self.project.company if self.project_id else None

    @property
    def partner(self):
        """≙ ``partner_id`` (``related='project_id.partner_id'``, :197)."""
        return self.project.partner if self.project_id else None

    @property
    def cost_currency(self):
        """≙ ``cost_currency_id`` (``related='employee_id.currency_id'``, :203).

        ``HrEmployee.currency`` ya es property en este árbol.
        """
        return self.employee.currency if self.employee_id else None

    @property
    def existing_employees(self):
        """≙ ``_compute_existing_employee_ids`` (:211-218) — los empleados ya
        mapeados en el mismo proyecto. En la fuente alimenta el ``domain`` del
        selector; aquí es la lectura, y la unicidad la garantiza la
        restricción de tabla.
        """
        if not self.project_id:
            return HrEmployee.objects.none()
        return HrEmployee.objects.filter(project_sale_line_maps__project=self.project)

    # -- métodos de negocio -------------------------------------------------

    def save(self, *args, **kwargs):
        """≙ ``create`` (:293-297) y ``write`` (:299-302): los dos llaman a
        ``_update_project_timesheet`` después de persistir."""
        super().save(*args, **kwargs)
        if self.sale_line_id:
            update_project_timesheet(self)


def working_hours_per_calendar(entries, is_uom_day=False):
    """≙ ``_get_working_hours_per_calendar`` (:249-264).

    Devuelve ``{id de calendario: horas por día}`` para los calendarios de los
    empleados de ``entries``. Con ``is_uom_day`` falso devuelve un dict vacío,
    exactamente como la fuente — no hay conversión que hacer.

    Divergencia de mecanismo: la fuente agrupa con ``_read_group`` sobre
    ``resource.calendar``; aquí ``hours_per_day`` es una **property** de
    ``ResourceCalendar`` (``api: addons/resource/models/resource_calendar.py``),
    no una columna, así que la agregación se hace en Python sobre el queryset.

    Segunda medición, y explica el ``getattr``: ``hr.HrEmployee`` de este árbol
    **no declara** ``resource_calendar`` — lo declara ``ResourceMixin``
    (``api: addons/resource/models/resource_mixin.py:70``), que no está
    aplicado al empleado (medido: 0 hits de ``resource_calendar`` en
    ``addons/hr/models/hr_employee.py``). Mientras esa arista no exista, el
    dict sale vacío y la conversión a costo diario cae al factor 1 — que es la
    misma rama que toma la fuente cuando el empleado no tiene calendario.
    """
    if not is_uom_day:
        return {}
    hours_map = {}
    for entry in entries:
        employee = entry.employee if entry.employee_id else None
        calendar = getattr(employee, 'resource_calendar', None) if employee else None
        if calendar is not None and calendar.pk is not None:
            hours_map[calendar.pk] = calendar.hours_per_day
    return hours_map


def display_cost_for(entry, is_uom_day=False, hours_per_calendar=None):
    """≙ ``_compute_display_cost`` (:266-276) — el costo en la unidad de
    captura.

    Parcial declarado: ``is_uom_day`` lo decide el **llamador**. La fuente lo
    deriva de ``env.ref('uom.product_uom_day') == env.company.timesheet_encode_uom_id``,
    que exige compañía ambiental y la fila semilla de UOM; ninguna de las dos
    está disponible desde el modelo en este árbol.
    """
    if not is_uom_day:
        return entry.cost
    hours_map = hours_per_calendar or working_hours_per_calendar([entry], True)
    calendar = getattr(entry.employee, 'resource_calendar', None) if entry.employee_id else None
    factor = hours_map.get(calendar.pk, 1) if calendar is not None else 1
    return entry.cost * Decimal(str(factor))


def cost_from_display_cost(entry, display_cost, is_uom_day=False,
                           hours_per_calendar=None):
    """≙ ``_inverse_display_cost`` (:278-286) — el camino inverso del
    anterior, con la misma condición sobre ``is_uom_day``."""
    if not is_uom_day:
        return display_cost
    hours_map = hours_per_calendar or working_hours_per_calendar([entry], True)
    calendar = getattr(entry.employee, 'resource_calendar', None) if entry.employee_id else None
    factor = hours_map.get(calendar.pk, 1) if calendar is not None else 1
    return display_cost / Decimal(str(factor or 1))


def update_project_timesheet(entry):
    """≙ ``_update_project_timesheet`` (:304-305).

    **BLOQUEADO en su efecto**: la fuente delega en
    ``project.project._update_timesheets_sale_line_id``, que reasigna
    ``so_line`` en los apuntes del proyecto. ``so_line`` sobre
    ``account.analytic.line`` lo declara ``sale``
    (``odoo19c: sale/models/analytic.py:9``) y no existe en este árbol — ver
    el bloqueo raíz documentado en ``models/hr_timesheet.py``.

    Se conserva la función (no un ``pass`` anónimo) porque es el punto exacto
    donde se cablea el efecto el día que ``so_line`` aterrice, y porque su
    llamada desde ``save()`` ya replica el orden de la fuente.
    """
    return None


@receiver(pre_save, sender=ProjectSaleLineEmployeeMap,
          dispatch_uid='sale_timesheet.sync_employee_map_derived_fields')
def _sync_employee_map_derived_fields(sender, instance, **kwargs):
    """Sincroniza ``price_unit``/``currency``/``cost``/``is_cost_changed`` —
    ≙ ``_compute_price_unit`` (:229-235) + ``_compute_currency_id`` (:237-240)
    + ``_compute_cost`` (:242-247) + ``_compute_is_cost_changed`` (:288-291).

    Un ``pre_save`` corre en cada ``.save()``, el mismo disparador que
    ``@api.depends`` sin el motor que decide QUÉ recomputar. Mismo patrón que
    ``hr_timesheet/models/hr_timesheet.py``.
    """
    line = instance.sale_line if instance.sale_line_id else None

    # ≙ _compute_price_unit
    instance.price_unit = line.price_unit if line is not None else 0.0

    # ≙ _compute_currency_id. La fuente lee `sale_line_id.currency_id`;
    # `sale.SaleOrderLine` de este árbol no declara moneda propia, así que se
    # deriva de la compañía del pedido (divergencia declarada en el módulo).
    if line is not None and line.order_id and line.order.company_id:
        instance.currency = line.order.company.currency
    else:
        instance.currency = None

    employee = instance.employee if instance.employee_id else None
    hourly_cost = getattr(employee, 'hourly_cost', None) if employee else None

    # ≙ _compute_cost: sólo se pisa mientras el costo no se haya tocado a mano.
    if not instance.is_cost_changed:
        instance.cost = hourly_cost if hourly_cost is not None else Decimal('0.00')

    # ≙ _compute_is_cost_changed. La fuente lo evalúa DESPUÉS de _compute_cost
    # (por eso su `env.remove_to_compute`); aquí el orden es explícito.
    instance.is_cost_changed = bool(employee) and instance.cost != hourly_cost


__all__ = [
    'ProjectSaleLineEmployeeMap',
    'working_hours_per_calendar',
    'display_cost_for',
    'cost_from_display_cost',
    'update_project_timesheet',
]
