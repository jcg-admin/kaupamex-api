"""``account.analytic.line`` — el apunte de hoja de horas, facturable
(Odoo ``sale_timesheet``).

Adaptación de Odoo ``sale_timesheet/models/hr_timesheet.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 264 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Medido por AST sobre la referencia: 1 clase (``AccountAnalyticLine``,
``_inherit``), 1 constante de módulo, **8 campos**, **24 métodos**.

El bloqueo raíz de este addon: ``so_line``
============================================

``so_line`` sobre ``account.analytic.line`` **no lo declara este addon**: lo
declara ``sale`` (``odoo19c: sale/models/analytic.py:9`` —
``so_line = fields.Many2one('sale.order.line', …)``). ``sale_timesheet`` sólo
lo **redefine** (:39-41) para añadirle ``compute``, ``domain`` y ``help``.

Medido en este árbol: ``addons/sale/models/`` tiene cuatro archivos
(``res_company``, ``res_partner``, ``sale_order``, ``sale_order_line``) y
**ninguno** declara ``so_line`` (0 hits en ``addons/`` y ``src/``). Portarlo
desde aquí pondría un símbolo de ``sale`` en el hogar equivocado — el defecto
que ``H-API-568``/``H-API-578`` ya registraron. Queda **BLOQUEADO por
``sale.AccountAnalyticLine.so_line``**, con sucesor: tarea PENDIENTE DE
ASIGNAR (hogar ``addons/sale``, archivo ``models/analytic.py``).

Es el bloqueador de mayor alcance del addon: arrastra a
``_compute_so_line``, ``_domain_so_line``, ``_timesheet_determine_sale_line``,
``_timesheet_get_sale_domain``, ``timesheet_ids`` de tres modelos, y la mitad
de ``project_project.py``. Cada símbolo afectado lo cita por su nombre para
que un ``grep so_line`` recupere el conjunto entero.

Lo que SÍ se porta, y por qué vale la pena sin ``so_line``
=============================================================

Cuatro columnas propias de este addon y su aritmética:

1. ``timesheet_invoice`` — el enlace apunte → factura. Es lo que permite
   responder *"¿esta hora ya se facturó?"* (``_is_not_billed``), que a su vez
   gobierna el candado de borrado y el de la reversión de facturas.
2. ``order`` — el pedido al que pertenece la hora, denormalizado. La fuente lo
   almacena *"only in order to be able to groupby in the portal"* (:42).
3. ``timesheet_invoice_type`` — la clasificación de facturabilidad, con las
   nueve etiquetas verbatim de la referencia.
4. ``is_so_line_edited`` — la marca de "esto lo fijó una persona, no lo pises".

Y el override de ``_hourly_cost``, que es el mecanismo por el que la tarifa
por empleado del proyecto (``project.sale.line.employee.map``, modelo propio
de este addon) gana al ``hourly_cost`` del empleado. Ése funciona **completo**:
no depende de ``so_line``.

Porte símbolo por símbolo
============================

.. list-table:: Campos — 4 portados, 1 property, 2 bloqueados
   :header-rows: 1

   * - Campo de la referencia (línea)
     - Desenlace aquí
   * - ``timesheet_invoice_type`` (:35-36)
     - **portado** — columna ``Selection`` con ``TIMESHEET_INVOICE_TYPES``
       verbatim. Su ``compute`` se porta **parcial declarado** en
       :func:`timesheet_invoice_type_for` (ver abajo).
   * - ``timesheet_invoice_id`` (:38)
     - **portado** — ``timesheet_invoice`` (FK ``account.AccountMove``,
       ``on_delete=SET_NULL``, ``db_index`` ≙ ``index='btree_not_null'``).
   * - ``order_id`` (:43)
     - **portado** — ``order`` (FK ``sale.SaleOrder``). La fuente lo deriva de
       ``so_line.order_id``; sin ``so_line`` es escribible directo, mismo
       criterio que ``hr_timesheet`` para ``task``/``project``.
   * - ``is_so_line_edited`` (:44)
     - **portado** — Boolean.
   * - ``commercial_partner_id`` (:37)
     - **portado como property, parcial declarado** — la fuente lo compone de
       ``task_id.partner_id`` **o** ``project_id.partner_id``;
       ``project.ProjectTask`` de este árbol no declara ``partner`` (0 hits),
       así que sólo la segunda mitad es alcanzable.
       ``ResPartner.commercial_partner_id`` sí existe, y desde #314 como
       **columna** (``api: src/addons/base/models/res_partner.py:445``).
   * - ``so_line`` (:39-41)
     - **BLOQUEADO** — ver "El bloqueo raíz" arriba.
   * - ``allow_billable`` (:45)
     - **BLOQUEADO** — ``related='project_id.allow_billable'``, y
       ``Project.allow_billable`` lo declara ``sale_project``
       (``odoo19c: sale_project/models/project_project.py:27``), cuyo puerto
       aquí es PARCIAL declarado. Hogar ``addons/sale_project``, fuera del
       write-set. Sucesor: tarea PENDIENTE DE ASIGNAR.
   * - ``sale_order_state`` (:46)
     - **portado como property** — ``related='order_id.state'``, y ``order`` sí
       se porta.

.. list-table:: Métodos — 5 portados, 19 con desenlace
   :header-rows: 1

   * - Método de la referencia (línea)
     - Desenlace aquí
   * - ``_is_not_billed`` (:95-97)
     - **portado** verbatim en su lógica — ``account.AccountMove`` de este
       árbol tiene ``state`` y ``payment_state``.
   * - ``_get_employee_mapping_entry`` (:181-192)
     - **portado, parcial declarado** — la rama multi-compañía usa
       ``env.companies``/``env.user.employee_ids`` (usuario ambiental); aquí
       el llamador pasa el empleado y se resuelve la entrada por
       ``(project, employee)``, que es la rama que la fuente toma cuando
       ``self.employee_id`` está fijado.
   * - ``_hourly_cost`` (:194-199)
     - **portado** — encadenado sobre el de ``hr_timesheet``
       (``api: addons/hr_timesheet/models/hr_timesheet.py``) con
       ``chain_method``: devuelve el costo del mapeo cuando el proyecto es de
       tarifa por empleado, y ``None`` en otro caso para que el relevo por
       ``None`` de ``chain_method`` ceda al anterior. Es exactamente el
       ``super()`` de la fuente.
   * - ``_compute_timesheet_invoice_type`` (:53-77)
     - **portado parcial declarado** — :func:`timesheet_invoice_type_for`.
       Alcanzables las dos ramas que no leen ``so_line``: la de proyecto sin
       línea (``non_billable`` / ``billable_manual`` según
       ``project.billing_type``, que **sí** se porta en
       ``models/project_project.py``) y la de apunte sin proyecto
       (``other_revenues`` / ``other_costs``). Las cinco ramas que clasifican
       por ``so_line.product_id.invoice_policy``/``service_type`` quedan
       bloqueadas por ``so_line`` **y** por ``product.invoice_policy``
       (``odoo19c: sale/models/product_template.py:35``, 0 hits aquí).
   * - ``_unlink_except_invoiced`` (:176-179)
     - **portado** — como guardia de ``delete()`` sobre el modelo, con
       ``ValidationError`` (este árbol no tiene ``@api.ondelete``; el
       precedente es ``uom.Uom.check_can_delete``).
   * - ``_domain_so_line`` (:25-33)
     - BLOQUEADO por ``so_line`` **y** por
       ``sale.order.line._sellable_lines_domain`` (0 hits).
   * - ``_compute_commercial_partner`` (:48-51)
     - portado dentro de la property ``commercial_partner``. Que aquí siga
       siendo property y no columna es la divergencia de forma que la tarea
       **#302** barre; #314 sólo cerró la de ``res.partner``.
   * - ``_compute_so_line`` (:79-82)
     - BLOQUEADO por ``so_line``.
   * - ``_compute_partner_id`` (:84-86) / ``_compute_project_id`` (:88-90)
     - BLOQUEADOS — restringen el compute heredado a los apuntes no
       facturados; el compute heredado que restringen no existe en este árbol
       (``hr_timesheet`` ya declaró ``_compute_partner_id`` bloqueado y
       ``_compute_project_id`` reemplazado por su receptor ``pre_save``).
       Sucesor: cuando ese receptor se condicione, la condición es
       ``_is_not_billed``.
   * - ``_is_readonly`` (:92-93)
     - BLOQUEADO — el base es visibilidad de campo por grupo, que aquí es
       autorización por CAPACIDAD a nivel de vista DRF.
   * - ``_check_timesheet_can_be_billed`` (:99-100)
     - BLOQUEADO por ``so_line`` y por ``task.sale_line_id``/
       ``project.sale_line_id`` (``sale_project``).
   * - ``_check_can_write`` (:102-107) / ``write`` (:109-115)
     - BLOQUEADOS por ``so_line`` (el primero filtra por
       ``so_line.product_id.invoice_policy``; el segundo apaga
       ``is_so_line_edited``). El candado equivalente que **sí** se puede
       sostener hoy es el de borrado (``_unlink_except_invoiced``), portado.
   * - ``_timesheet_determine_sale_line`` (:117-144)
     - BLOQUEADO por ``so_line`` y ``sale_line_id``.
   * - ``_timesheet_get_portal_domain`` (:146-152)
     - BLOQUEADO — el base lo declara ``hr_timesheet``, que ya lo dejó sin
       portar (sesión/portal).
   * - ``_timesheet_get_sale_domain`` (:154-170)
     - BLOQUEADO por ``so_line``.
   * - ``_get_timesheets_to_merge`` (:172-174)
     - BLOQUEADO — el base no existe (0 hits de ``_get_timesheets_to_merge``).
   * - ``action_sale_order_from_timesheet`` (:201-210) /
       ``action_invoice_from_timesheet`` (:212-221)
     - no portados — navegación pura del cliente web de Odoo
       (``ir.actions.act_window``), sin lógica de negocio. Mismo criterio que
       ``project_account/models/project_project.py``.
   * - ``_timesheet_convert_sol_uom`` (:223-225)
     - BLOQUEADO — ``sale.SaleOrderLine`` de este árbol no declara
       ``product_uom_id`` (0 hits), y ``env.ref`` de la unidad exige la fila
       semilla de UOM.
   * - ``_is_updatable_timesheet`` (:227-228)
     - BLOQUEADO — el base tampoco se portó en ``hr_timesheet`` (declarado
       ahí: *"método de un solo return True, sin consumidor cableado"*).
   * - ``_timesheet_preprocess_get_accounts`` (:230-256)
     - BLOQUEADO por ``analytic_distribution`` sobre la línea de pedido y por
       ``_get_mandatory_plans`` (planes analíticos obligatorios), ninguno en
       este árbol.
   * - ``_timesheet_postprocess`` (:258-264)
     - BLOQUEADO por ``so_line`` y por ``Project.account_id`` (mismo
       bloqueador que ``project_account`` ya declaró).
"""
import fields
import models
from django.core.exceptions import ValidationError

from addons.account.models import AccountMove
from addons.analytic.models import AccountAnalyticLine
from addons.sale.models import SaleOrder
from orm.method_chain import chain_method

from .project_sale_line_employee_map import ProjectSaleLineEmployeeMap

#: ≙ ``TIMESHEET_INVOICE_TYPES`` (``odoo19c: sale_timesheet/models/
#: hr_timesheet.py:9-19``) — las nueve etiquetas, verbatim y en su orden.
TIMESHEET_INVOICE_TYPES = [
    ('billable_time', 'Billed on Timesheets'),
    ('billable_fixed', 'Billed at a Fixed price'),
    ('billable_milestones', 'Billed on Milestones'),
    ('billable_manual', 'Billed Manually'),
    ('non_billable', 'Non-Billable'),
    ('timesheet_revenues', 'Timesheet Revenues'),
    ('service_revenues', 'Service Revenues'),
    ('other_revenues', 'Other revenues'),
    ('other_costs', 'Other costs'),
]

#: El estado de factura que la referencia trata como "no facturado" pese a
#: existir el enlace — ``odoo19c: hr_timesheet.py:97``.
_LEGACY_PAYMENT_STATE = 'invoicing_legacy'


def _add_if_absent(model, name, field):
    """Añade el campo sólo si el modelo no lo tiene ya.

    Idéntico al de ``hr_timesheet``/``account_fleet``/``product_expiry``: el
    idioma de extensión por ``add_to_class`` no tiene MRO, así que dos addons
    que cuelguen el mismo campo duplicarían la columna.
    """
    if not any(f.name == name for f in model._meta.get_fields()):
        model.add_to_class(name, field)


def commercial_partner(self):
    """≙ ``_compute_commercial_partner`` (``odoo19c: hr_timesheet.py:48-51``).

    Parcial declarado: la fuente prefiere ``task_id.partner_id`` y cae a
    ``project_id.partner_id``. ``project.ProjectTask`` de este árbol no
    declara ``partner`` (medido: 0 hits), así que sólo queda la segunda mitad.
    """
    if self.project_id and self.project.partner_id:
        return self.project.partner.commercial_partner_id
    return None


def sale_order_state(self):
    """≙ ``sale_order_state`` (``related='order_id.state'``,
    ``odoo19c: hr_timesheet.py:46``)."""
    return self.order.state if self.order_id else None


def _is_not_billed(self):
    """≙ ``_is_not_billed`` (``odoo19c: hr_timesheet.py:95-97``).

    Un apunte cuenta como no facturado si no tiene factura enlazada, o si la
    que tiene está cancelada y no viene del régimen ``invoicing_legacy``.
    """
    if not self.timesheet_invoice_id:
        return True
    invoice = self.timesheet_invoice
    return (invoice.state == 'cancel'
            and invoice.payment_state != _LEGACY_PAYMENT_STATE)


def _get_employee_mapping_entry(self):
    """≙ ``_get_employee_mapping_entry`` (``odoo19c: hr_timesheet.py:181-192``).

    Parcial declarado: la fuente tiene dos ramas. La primera —una sola
    compañía, o el empleado ya fijado en el apunte— se porta entera. La
    segunda resuelve el empleado desde ``env.user.employee_ids`` y desempata
    por ``env.companies``: sin usuario ambiental no hay a quién preguntar, y
    fabricar un desempate distinto sería inventar conducta.
    """
    if not (self.project_id and self.employee_id):
        return None
    return ProjectSaleLineEmployeeMap.objects.filter(
        project=self.project, employee=self.employee,
    ).first()


def _hourly_cost(self):
    """≙ ``_hourly_cost`` (``odoo19c: hr_timesheet.py:194-199``).

    Devuelve el costo de la entrada de mapeo cuando el proyecto factura por
    tarifa de empleado; ``None`` en cualquier otro caso, para que el relevo
    por ``None`` de ``chain_method`` ceda al ``_hourly_cost`` de
    ``hr_timesheet`` — que es exactamente el ``super()`` de la fuente.
    """
    if self.project_id and self.project.pricing_type == 'employee_rate':
        entry = _get_employee_mapping_entry(self)
        if entry is not None:
            return entry.cost
    return None


def timesheet_invoice_type_for(line):
    """≙ ``_compute_timesheet_invoice_type``
    (``odoo19c: hr_timesheet.py:53-77``) — **parcial declarado**.

    Alcanzables las dos ramas que no leen ``so_line``:

    - apunte **con** proyecto y sin línea de pedido → ``non_billable``, o
      ``billable_manual`` si el proyecto factura manualmente
      (``project.billing_type``, portado en ``models/project_project.py``);
    - apunte **sin** proyecto → ``other_revenues`` si importe y cantidad no
      son negativos, ``other_costs`` en caso contrario.

    Las cinco ramas restantes clasifican por
    ``so_line.product_id.invoice_policy`` / ``service_type`` y quedan
    bloqueadas por dos piezas ausentes a la vez: ``so_line``
    (``odoo19c: sale/models/analytic.py:9``) y ``product.invoice_policy``
    (``odoo19c: sale/models/product_template.py:35``). Los valores
    ``billable_time``, ``billable_fixed``, ``billable_milestones``,
    ``timesheet_revenues`` y ``service_revenues`` siguen declarados en
    ``TIMESHEET_INVOICE_TYPES`` — la columna admite el vocabulario completo
    aunque hoy sólo cuatro valores sean derivables.
    """
    if line.project_id:
        # ≙ la rama `if not timesheet.so_line` de la fuente, que aquí es la
        # única alcanzable porque `so_line` no existe.
        billing = getattr(line.project, 'billing_type', None)
        return 'billable_manual' if billing == 'manually' else 'non_billable'
    if line.amount is not None and line.amount >= 0 and line.unit_amount >= 0:
        # ≙ la rama sin `so_line` de servicio → 'other_revenues'.
        return 'other_revenues'
    return 'other_costs'


def sync_timesheet_invoice_type(line, save=True):
    """Escribe :func:`timesheet_invoice_type_for` en la columna.

    No es un receptor ``pre_save`` a propósito: la fuente lo declara
    ``store=True`` con ``compute_sudo``, pero su valor **cambia con la
    factura**, no sólo con el apunte, así que un recálculo ciego en cada
    ``save()`` pisaría el valor que fijó el cierre de facturación. El llamador
    decide cuándo — mismo criterio que ``AccountMove.compute_payment_state``
    (``api: addons/account/models/account_move.py:232``).
    """
    line.timesheet_invoice_type = timesheet_invoice_type_for(line)
    if save:
        line.save(update_fields=['timesheet_invoice_type'])
    return line.timesheet_invoice_type


def check_can_delete(self):
    """≙ ``_unlink_except_invoiced`` (``odoo19c: hr_timesheet.py:176-179``).

    Este árbol no tiene ``@api.ondelete``; el precedente de guardia explícita
    es ``uom.Uom.check_can_delete`` (``api: addons/uom/models/uom_uom.py:243``).
    """
    if self.timesheet_invoice_id and self.timesheet_invoice.state == 'posted':
        raise ValidationError(
            'No se puede eliminar un apunte de hoja de horas que ya fue '
            'facturado.'
        )


def apply_sale_timesheet_hr_timesheet_extensions():
    """Cuelga las 4 columnas + 2 properties + 4 métodos sobre
    ``analytic.AccountAnalyticLine`` — ≙ ``_inherit = 'account.analytic.line'``.

    La llama ``SaleTimesheetConfig.ready()``.
    """
    _add_if_absent(AccountAnalyticLine, 'timesheet_invoice', fields.Many2one(
        AccountMove, on_delete=models.SET_NULL, null=True, blank=True,
        db_index=True, related_name='timesheet_ids',
        verbose_name='Factura',
        help_text='Odoo timesheet_invoice_id (readonly, copy=False, '
                  'index=btree_not_null). Factura creada a partir de la hoja '
                  'de horas. El related_name es el timesheet_ids de '
                  'account.move (odoo19c: account_move.py:185).',
    ))
    _add_if_absent(AccountAnalyticLine, 'order', fields.Many2one(
        SaleOrder, on_delete=models.SET_NULL, null=True, blank=True,
        db_index=True, related_name='timesheet_ids',
        verbose_name='Pedido de venta',
        help_text='Odoo order_id (related=so_line.order_id, store, index). '
                  'Escribible directo: so_line no existe en este árbol — ver '
                  'el bloqueo raíz del docstring del módulo.',
    ))
    _add_if_absent(AccountAnalyticLine, 'is_so_line_edited', fields.Boolean(
        default=False, verbose_name='Línea de pedido fijada a mano',
        help_text='Odoo is_so_line_edited.',
    ))
    _add_if_absent(
        AccountAnalyticLine, 'timesheet_invoice_type', fields.Selection(
            max_length=20, choices=TIMESHEET_INVOICE_TYPES,
            null=True, blank=True, default=None,
            verbose_name='Tipo de facturación',
            help_text='Odoo timesheet_invoice_type (compute, store, '
                      'readonly). Derivación parcial declarada — ver '
                      'timesheet_invoice_type_for.',
        ))

    if not hasattr(AccountAnalyticLine, 'commercial_partner'):
        AccountAnalyticLine.commercial_partner = property(commercial_partner)
    if not hasattr(AccountAnalyticLine, 'sale_order_state'):
        AccountAnalyticLine.sale_order_state = property(sale_order_state)

    chain_method(AccountAnalyticLine, '_hourly_cost', _hourly_cost)
    if not hasattr(AccountAnalyticLine, '_is_not_billed'):
        AccountAnalyticLine._is_not_billed = _is_not_billed
    if not hasattr(AccountAnalyticLine, '_get_employee_mapping_entry'):
        AccountAnalyticLine._get_employee_mapping_entry = _get_employee_mapping_entry
    if not hasattr(AccountAnalyticLine, 'check_can_delete'):
        AccountAnalyticLine.check_can_delete = check_can_delete


__all__ = [
    'TIMESHEET_INVOICE_TYPES',
    'apply_sale_timesheet_hr_timesheet_extensions',
    'timesheet_invoice_type_for',
    'sync_timesheet_invoice_type',
]
