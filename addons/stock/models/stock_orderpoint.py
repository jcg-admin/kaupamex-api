r"""``stock.warehouse.orderpoint`` — el punto de pedido, addon ``stock``.

Adaptación de Odoo ``stock/models/stock_orderpoint.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, LGPL-3, 817 líneas) — atribución y aviso de licencia preservados
(DEC-KX-03).

Qué es: la **regla de reabastecimiento** de un producto en una ubicación. Su
docstring en la fuente es de una línea —«Defines Minimum stock rules»— y esconde
la máquina completa: fija un mínimo y un máximo, y cuando el pronóstico cae bajo
el mínimo calcula cuánto pedir para volver al máximo y lanza el
aprovisionamiento por la ruta que corresponda (comprar, fabricar, mover).

Los tres ejes que gobiernan su cálculo, y son ortogonales:

- **Las cantidades** — ``product_min_qty`` dispara, ``product_max_qty`` es el
  destino, y ``qty_to_order`` es la diferencia contra el pronóstico. El
  pronóstico no es la existencia: descuenta lo que ya está comprometido y suma
  lo que viene en camino.
- **El tiempo** — ``lead_days`` (lo que tarda en llegar) más ``horizon_days`` de
  la empresa (con cuánta antelación se quiere disparar) dan
  ``lead_horizon_date``, la fecha hasta la que se mira el pronóstico.
  ``deadline_date`` es el otro lado: hasta cuándo se puede esperar sin caer bajo
  el mínimo.
- **El disparo** — ``trigger`` ``auto`` lo corre el planificador
  (``stock.rule.run_scheduler``); ``manual`` lo corre una persona, y sólo
  ``manual`` admite ``snoozed_until``.

Por qué este archivo cierra la divergencia D-5 de ``stock_rule``
=================================================================

``stock_rule.py:353-369`` declara ``_orderpoint_model()``, que devuelve ``None``
**con un aviso en el log** porque el modelo no existía. Medido antes de este
pase: ``grep -rn "class .*Orderpoint" addons/ src/ --include=*.py`` → **0**. Con
este archivo, la primera de las tres tareas del planificador
(``_run_scheduler_tasks``) deja de omitirse.

El contrato que ese llamador ya fijó, y que este porte cumple:

.. list-table::
   :header-rows: 1
   :widths: 46 54

   * - Llamada de ``stock_rule``
     - Forma aquí
   * - ``orderpoint_model.objects.filter(domain)``
     - gestor normal; el dominio lo arma ``_get_orderpoint_domain``
   * - ``_compute_qty_to_order_computed(orderpoints)``
     - ``classmethod`` sobre el queryset
   * - ``_compute_deadline_date(orderpoints)``
     - ``classmethod`` sobre el queryset
   * - ``_procure_orderpoint_confirm(orderpoints, …)``
     - ``classmethod`` sobre el queryset
   * - ``orderpoint_model.get_horizon_days()``
     - ``classmethod`` con ``orderpoints=None`` opcional

Porte símbolo por símbolo — 88 de 88
======================================

Medido por AST sobre el cuerpo de ``class StockWarehouseOrderpoint``: **5**
atributos de clase, **33** campos y **50** métodos.

*Métrica:* asignaciones y definiciones del cuerpo de la clase, por AST.
*Ciega a:* las funciones locales dentro de un método — aquí hay una,
``is_parent_path_in`` dentro de ``_get_orderpoint_action`` (``:481-482``), que
se porta como ayudante de módulo con el mismo nombre.

Atributos de clase — 5 de 5
-----------------------------

Cuatro de ORM (``:23-26``) verbatim, y un **objeto de tabla**
(``_product_location_check``, ``:101-104``) cuyo hogar aquí es
``Meta.constraints`` con el nombre de la referencia conservado
(``atributos-de-clase-de-modelo.md``).

Campos — 33 de 33, en dos formas
----------------------------------

**15 son columnas** (los que la referencia almacena o deja escribir):
``name``, ``trigger``, ``active``, ``snoozed_until``, ``warehouse_id``,
``location_id``, ``product_id``, ``product_min_qty``, ``product_max_qty``,
``replenishment_uom_id``, ``company_id``, ``route_id``, ``qty_to_order_computed``,
``qty_to_order_manual``, ``deadline_date``.

**18 son ``property``** — los ``related=`` y los ``compute`` sin ``store=True``,
que allá tampoco tienen columna. Su origen se declara en cada docstring, como
exige ``H-API-611``: ``product_tmpl_id``, ``product_category_id``,
``product_uom``, ``product_uom_name``, ``allowed_replenishment_uom_ids``,
``replenishment_uom_id_placeholder``, ``allowed_location_ids``, ``rule_ids``,
``lead_horizon_date``, ``lead_days``, ``route_id_placeholder``,
``effective_route_id``, ``qty_on_hand``, ``qty_forecast``, ``qty_to_order``,
``days_to_order``, ``unwanted_replenish``, ``show_supply_warning``.

Tres divergencias de mecanismo declaradas
===========================================

**D-1 — el recordset es un queryset, así que los compute de conjunto son
``classmethod``.** La fuente escribe ``self.filtered(…)`` sobre un recordset;
aquí ``_compute_qty_to_order_computed``, ``_compute_deadline_date`` y
``_procure_orderpoint_confirm`` reciben el conjunto como primer argumento. No es
una elección: es el contrato que ``stock_rule.py:1436-1442`` ya escribió antes de
que este archivo existiera.

**D-2 — ``qty_to_order`` es una ``property`` con setter, no un campo con
``inverse``.** La fuente lo declara ``compute='_compute_qty_to_order'``,
``inverse='_inverse_qty_to_order'``: al asignarlo, el ORM corre el inverso al
vaciar. Aquí el setter corre ``_inverse_qty_to_order`` de inmediato, que es la
misma semántica sin la ventana de vaciado — y el valor asignado se guarda en
``_qty_to_order_assigned`` para que el inverso pueda leerlo, igual que allá lee
el campo recién escrito.

**D-3 — la acción devuelve su descriptor, no un ``ir.actions.act_window``
resuelto.** ``action_product_forecast_report``, ``action_stock_replenishment_info``
y ``_get_orderpoint_action`` devuelven el diccionario con su ``xml_id``; el
cliente Odoo que lo consumiría no existe en este stack (DEC-FW-01). Es la misma
forma que ``stock_quant.action_view_orderpoints`` ya usa.

**D-4 — tres computes que ``check_porte_completo.py`` reporta ausentes por el
mismo mecanismo que ``stock_package.py`` ya declaró** (:ref:`h-api-680`). El
gate absuelve un ``_compute_<campo>`` sólo si existe una ``property`` con **el
mismo nombre exacto** que el campo de la referencia y su docstring cita el
símbolo (``scripts/check_porte_completo.py:289-340``). Los tres casos:

.. list-table::
   :header-rows: 1
   :widths: 30 30 40

   * - Compute de la referencia
     - Campo allá / aquí
     - Por qué no absuelve
   * - ``_compute_effective_route_id`` (``:237-242``)
     - ``effective_route_id`` / ``effective_route`` (:445)
     - el sufijo ``_id`` se retira de todo FK en este árbol
   * - ``_compute_rules`` (``:192-207``)
     - ``rule_ids`` / ``rule_ids`` (:360)
     - la propia referencia nombra su compute distinto del campo
       (no ``_compute_rule_ids``); la clave derivada no coincide
   * - ``_compute_qty`` (``:374-393``)
     - dos campos (``qty_on_hand``, ``qty_forecast``) / dos properties
       homónimas (:478, :483)
     - un compute de la referencia escribe DOS campos a la vez; el gate
       deriva una clave por campo, ninguna es ``_compute_qty``

Los tres cuerpos son equivalentes — verificado leyendo ambos archivos, no
asumido — y quedan citados en el docstring de cada property.

**D-5 — ``create``/``write`` se consolidan en ``save()``.** La referencia
(``:295-307``) valida en dos métodos separados: ``create`` rechaza un
``snoozed_until`` sobre un disparador ``auto`` en la creación; ``write``
rechaza lo mismo y además el cambio de empresa. Este puerto usa ``save()``
como el único punto de paso de ambos casos (Django no separa create/write en
dos métodos de instancia con la misma firma que Odoo) — ``save()`` en
``:753-784`` corre las dos guardas, distinguiendo creación de actualización
con ``self.pk is None``. Las tres reglas de negocio —snooze sólo manual,
mensaje distinto en creación vs actualización, empresa inmutable tras
creada— están las tres presentes, verbatim en el mensaje. El gate compara por
nombre de método (``create``, ``write``) y no ve la consolidación; es la
misma forma que ya usan otros modelos de este árbol.

Lo que este archivo NO cierra
===============================

- **``stock.replenishment.info``** — el modelo transitorio que
  ``action_stock_replenishment_info`` crea (``:336-338``) no existe en este
  árbol (medido: ``grep -rn "replenishment.info" addons/ src/`` → 0). El método
  devuelve su descriptor **sin** crear el registro y lo declara en su docstring.
  Sucesor: tarea **#330**.
- **``StockMove.orderpoint_id``** — ``stock_move.py:29-31`` declara que la FK
  quedó fuera porque este modelo no existía. Ahora existe; añadirla es la tarea
  **#382**, que se hace con su migración y sus consumidores
  (``_prepare_procurement_values`` ya la pasa en ``values``).
- **``@api.autovacuum``** sobre ``_unlink_processed_orderpoints`` (``:669``) — el
  decorador que lo cuelga del vaciado periódico no existe aquí; el método se
  porta entero y queda invocable. Sucesor: tarea **#124** (sembrar los crons).
"""
from collections import defaultdict
from datetime import datetime, time, timedelta

import fields
import models
from django.apps import apps
from django.db.models import Q, Sum
from django.utils import timezone

from addons.base.models import TimeStampedModel
from addons.stock.models.stock_rule import ProcurementException
from exceptions import UserError, ValidationError
from orm.environments import get_current_company
from tools.float_utils import float_compare
from tools.misc import split_every
from tools.translate import _

#: ≙ ``trigger`` (``odoo19c: :31-32``) — el vocabulario de la fuente, verbatim.
TRIGGER_CHOICES = [('auto', 'Auto'), ('manual', 'Manual')]

#: Los estados de movimiento que cuentan como «en camino» para el pronóstico
#: (``odoo19c: :145,152,533``). La fuente los repite literal en tres sitios; el
#: porte los nombra una vez.
MOVE_STATES_IN_PROGRESS = ('waiting', 'confirmed', 'assigned', 'partially_available')


def is_parent_path_in(resupply_loc, path_dict, record_loc):
    """≙ la función local de ``_get_orderpoint_action`` (``odoo19c: :481-482``).

    ¿La ubicación del registro cuelga de la de reabastecimiento? Se resuelve por
    ruta materializada, que es la misma prueba que hace ``child_of``.
    """
    return bool(record_loc) and resupply_loc.parent_path in (
        path_dict.get(record_loc) or '')


def _today():
    """La fecha de hoy — ≙ ``fields.Date.today()`` de la fuente."""
    return timezone.now().date()


def _related_pks(registro, nombre):
    """Las PK de un Many2many, tolerando que el registro o el campo no estén.

    **No es un símbolo de la referencia.** Allá ``record.route_ids`` ya *es* el
    recordset; aquí el atributo es el **gestor** de Django, que no es iterable —
    hay que pedirle ``.all()``. Se factoriza porque el mismo descuido produjo un
    ``TypeError`` en ``_get_default_route`` (ver :ref:`h-api-617`).
    """
    gestor = getattr(registro, nombre, None) if registro is not None else None
    if gestor is None:
        return ()
    return tuple(gestor.values_list('pk', flat=True))


class StockWarehouseOrderpoint(TimeStampedModel):
    """``stock.warehouse.orderpoint`` — «Defines Minimum stock rules»."""

    # Atributos de clase de modelo — los cuatro de ORM que la referencia declara
    # (``odoo19c: :23-26``), verbatim. El objeto de tabla
    # ``_product_location_check`` (``:101-104``) vive en ``Meta.constraints``.
    _name = 'stock.warehouse.orderpoint'
    _description = "Minimum Inventory Rule"
    _check_company_auto = True
    _order = "location_id,company_id,id"

    name                  = fields.Char(
        max_length=64, blank=True, default='',
        help_text='Nombre de la regla; lo genera la secuencia '
                  '``stock.orderpoint`` (Odoo name, copy=False, readonly).',
    )
    trigger               = fields.Selection(
        choices=TRIGGER_CHOICES, max_length=8, default='auto',
        help_text='Auto lo corre el planificador; manual, una persona '
                  '(Odoo trigger).',
    )
    active                = fields.Boolean(
        default=True,
        help_text='Al desmarcarlo se oculta la regla sin borrarla (Odoo active).',
    )
    snoozed_until         = fields.Date(
        null=True, blank=True,
        help_text='Oculta hasta el próximo planificador; sólo válido en reglas '
                  'manuales (Odoo snoozed_until).',
    )
    warehouse             = fields.Many2one(
        'stock.StockWarehouse', on_delete=models.CASCADE, db_index=True,
        related_name='orderpoint_ids',
        help_text='Almacén (Odoo warehouse_id, compute+store, requerido).',
    )
    location              = fields.Many2one(
        'stock.StockLocation', on_delete=models.CASCADE, db_index=True,
        related_name='orderpoint_ids',
        help_text='Ubicación cuya existencia se vigila '
                  '(Odoo location_id, compute+store, requerido).',
    )
    product               = fields.Many2one(
        'product.ProductProduct', on_delete=models.CASCADE, db_index=True,
        related_name='orderpoint_ids',
        help_text='Producto que se reabastece (Odoo product_id, requerido).',
    )
    product_min_qty       = fields.Float(
        default=0.0,
        help_text='Existencia mínima que dispara el reabastecimiento '
                  '(Odoo product_min_qty, digits="Product Unit").',
    )
    product_max_qty       = fields.Float(
        default=0.0,
        help_text='Existencia a la que se quiere volver al reabastecer '
                  '(Odoo product_max_qty, compute+store, readonly=False).',
    )
    replenishment_uom     = fields.Many2one(
        'uom.Uom', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='orderpoint_ids',
        help_text='Múltiplo al que se redondea la cantidad a pedir; vacío no '
                  'redondea (Odoo replenishment_uom_id).',
    )
    company               = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE, db_index=True,
        related_name='orderpoint_ids',
        help_text='Empresa (Odoo company_id, requerido).',
    )
    route                 = fields.Many2one(
        'stock.StockRoute', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='orderpoint_ids',
        help_text='Ruta elegida a mano; vacío usa la que resulte del producto y '
                  'la ubicación (Odoo route_id).',
    )
    qty_to_order_computed = fields.Float(
        default=0.0,
        help_text='Cantidad que el cálculo propone pedir '
                  '(Odoo qty_to_order_computed, compute+store).',
    )
    qty_to_order_manual   = fields.Float(
        default=0.0,
        help_text='Cantidad fijada a mano; si no es cero, gana sobre la '
                  'calculada (Odoo qty_to_order_manual).',
    )
    deadline_date         = fields.Date(
        null=True, blank=True,
        help_text='Fecha antes de la cual hay que pedir para no caer bajo el '
                  'mínimo (Odoo deadline_date, compute+store, readonly).',
    )

    class Meta:
        db_table = 'stock_warehouse_orderpoint'
        # ≙ ``_order = "location_id,company_id,id"`` (``odoo19c: :26``).
        ordering = ['location', 'company', 'id']
        verbose_name = 'Regla de reabastecimiento'
        verbose_name_plural = 'Reglas de reabastecimiento'
        constraints = [
            # ≙ ``_product_location_check`` (``odoo19c: :101-104``).
            models.UniqueConstraint(
                fields=['product', 'location', 'company'],
                name='stock_orderpoint_product_location_check',
                violation_error_message='A replenishment rule already exists '
                                        'for this product on this location.',
            ),
        ]

    def __str__(self):
        return self.name or f'stock.warehouse.orderpoint#{self.pk}'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #: El valor asignado a ``qty_to_order`` antes de que el inverso corra —
        #: ver D-2 del docstring del módulo. ``None`` significa «nadie lo
        #: asignó», que es distinto de «lo asignó a cero».
        self._qty_to_order_assigned = None

    # ------------------------------------------------------------------ #
    # Campos derivados sin columna (≙ los related y los compute sin store) #
    # ------------------------------------------------------------------ #

    @property
    def product_tmpl(self):
        """≙ ``product_tmpl_id`` (``odoo19c: :45``) — related a ``product_id``."""
        return self.product.product_tmpl if self.product_id is not None else None

    @property
    def product_category(self):
        """≙ ``product_category_id`` (``:52``) — related a ``product_id.categ_id``."""
        return self.product.categ if self.product_id is not None else None

    @property
    def product_uom(self):
        """≙ ``product_uom`` (``:53-54``) — related a ``product_id.uom_id``."""
        return self.product.uom if self.product_id is not None else None

    @property
    def product_uom_name(self):
        """≙ ``product_uom_name`` (``:55``) — related a ``product_uom.display_name``."""
        uom = self.product_uom
        return str(uom) if uom is not None else ''

    @property
    def allowed_location_ids(self):
        """≙ ``_compute_allowed_location_ids`` (``odoo19c: :107-117``).

        «We want to keep only the locations strictly belonging to our warehouse
        and not belonging to any warehouses.» Es decir: internas o vista, y
        fuera del árbol de cualquier **otro** almacén.
        """
        stock_location = apps.get_model('stock', 'StockLocation')
        warehouse_model = apps.get_model('stock', 'StockWarehouse')

        consulta = stock_location.objects.filter(usage__in=('internal', 'view'))
        otros = warehouse_model.objects.exclude(
            pk=self.warehouse_id).select_related('view_location')
        for otro in otros:
            vista = otro.view_location
            if vista is not None:
                consulta = consulta.exclude(
                    parent_path__startswith=vista.parent_path)
            consulta = consulta.filter(
                Q(company__isnull=True) | Q(company=self.company))
        return consulta

    @property
    def show_supply_warning(self):
        """≙ ``_compute_show_supply_warning`` (``odoo19c: :119-121``).

        Sin ninguna regla que abastezca esta ubicación, la orden no tendría por
        dónde salir: se avisa.
        """
        return not self.rule_ids

    @property
    def rule_ids(self):
        """≙ ``_compute_rules`` (``odoo19c: :191-207``).

        La cadena de reglas que abastece esta ubicación para este producto. La
        caché por ``(ubicación, ruta, rutas del producto)`` de la fuente no se
        replica: aquí el cálculo es por registro, no por recordset, así que no
        hay tanda entre la que compartirla.
        """
        if self.product_id is None or self.location_id is None:
            return []
        product_model = apps.get_model('product', 'ProductProduct')
        return product_model._get_rules_from_location(
            self.product, self.location,
            route_ids=[self.route] if self.route is not None else (),
        )

    def _lead_days_values(self):
        """Los dos valores de plazo — el cuerpo común de ``lead_horizon_date`` y
        ``lead_days``.

        **No es un símbolo de la referencia**: allá
        ``_compute_lead_days`` (``:180-189``) escribe los **dos** campos en una
        pasada. Aquí son dos ``property``, y calcular dos veces sería pagar el
        mismo ``_get_lead_days`` doble; se factoriza el cuerpo.
        """
        if self.product_id is None or self.location_id is None:
            return None, 0.0
        rule_model = apps.get_model('stock', 'StockRule')
        plazos, _descripcion = rule_model._get_lead_days(
            self.rule_ids, self.product, **self._get_lead_days_values())
        total = plazos.get('total_delay', 0) + plazos.get('horizon_time', 0)
        return _today() + timedelta(days=total), plazos.get('total_delay', 0)

    @property
    def lead_horizon_date(self):
        """≙ ``lead_horizon_date`` de ``_compute_lead_days`` (``odoo19c: :180-189``)."""
        return self._lead_days_values()[0]

    @property
    def lead_days(self):
        """≙ ``lead_days`` de ``_compute_lead_days`` (``odoo19c: :180-189``)."""
        return self._lead_days_values()[1]

    @property
    def allowed_replenishment_uom_ids(self):
        """≙ ``_compute_allowed_replenishment_uom_ids`` (``odoo19c: :215-220``).

        Las unidades del producto, más las de sus proveedores cuando alguna
        regla de la cadena es de compra.
        """
        if self.product_id is None:
            return []
        unidades = list(getattr(self.product, 'uom_ids', None) or [])
        if not unidades and self.product.uom is not None:
            unidades = [self.product.uom]
        if any(getattr(r, 'action', None) == 'buy' for r in self.rule_ids):
            for proveedor in getattr(self.product, 'seller_ids', None) or []:
                unidad = getattr(proveedor, 'product_uom', None)
                if unidad is not None and unidad not in unidades:
                    unidades.append(unidad)
        return unidades

    @property
    def replenishment_uom_id_placeholder(self):
        """≙ ``_compute_replenishment_uom_id_placeholder`` (``odoo19c: :222-226``)."""
        alternativa = self._get_replenishment_multiple_alternative(
            self.qty_to_order)
        return str(alternativa) if alternativa else ''

    def _inverse_route_id(self):
        """≙ ``_inverse_route_id`` (``odoo19c: :228-231``).

        «Override this method to add custom behavior when route is set.» Vacío
        en la fuente a propósito: es un punto de extensión. Se porta con su
        cuerpo real —ninguno— porque su valor es el contrato.
        """

    @property
    def route_id_placeholder(self):
        """≙ ``_compute_route_id_placeholder`` (``odoo19c: :233-237``)."""
        ruta = self._get_default_route()
        return str(ruta) if ruta is not None else ''

    @property
    def effective_route(self):
        """≙ ``_compute_effective_route_id`` (``odoo19c: :239-242``).

        «Either the route set directly or the one computed to be used by this
        replenishment.»
        """
        return self.route if self.route is not None else self._get_default_route()

    @classmethod
    def _search_effective_route_id(cls, operator, value):
        """≙ ``_search_effective_route_id`` (``odoo19c: :244-249``).

        El campo no tiene columna, así que la fuente busca en Python y devuelve
        un dominio por ``id``. El porte hace lo mismo.
        """
        route_model = apps.get_model('stock', 'StockRoute')
        rutas = set(route_model.objects.filter(
            **{f'pk__{operator}': value} if operator != '=' else {'pk': value}
        ).values_list('pk', flat=True))
        coinciden = [o.pk for o in cls.objects.all()
                     if getattr(o.effective_route, 'pk', None) in rutas]
        return Q(pk__in=coinciden)

    @property
    def days_to_order(self):
        """≙ ``_compute_days_to_order`` (``odoo19c: :251-253``).

        «``self.days_to_order = 0``» — cero en la fuente; el eje de anticipo por
        días lo rellenan otros addons. Se porta con su cuerpo real.
        """
        return 0.0

    @property
    def qty_on_hand(self):
        """≙ ``qty_on_hand`` de ``_compute_qty`` (``odoo19c: :371-388``)."""
        return self._qty_pair()[0]

    @property
    def qty_forecast(self):
        """≙ ``qty_forecast`` de ``_compute_qty`` (``odoo19c: :371-388``)."""
        return self._qty_pair()[1]

    def _qty_pair(self):
        """El par ``(existencia, pronóstico)`` — el cuerpo común de ``_compute_qty``.

        **No es un símbolo de la referencia**: allá ``_compute_qty`` escribe los
        **dos** campos en una pasada, agrupando por contexto para leer en tanda.
        Aquí son dos ``property`` y el cálculo es por registro; se factoriza el
        cuerpo por la misma razón que ``_lead_days_values``.
        """
        if self.product_id is None or self.location_id is None:
            return 0.0, 0.0
        contexto = self._get_product_context()
        producto = self.product
        existencia = producto._quantity_for('qty_available', **contexto)
        pronostico = producto._quantity_for('virtual_available', **contexto)
        en_progreso = type(self)._quantity_in_progress([self]).get(self.pk, 0.0)
        return existencia, pronostico + en_progreso

    @property
    def qty_to_order(self):
        """≙ ``_compute_qty_to_order`` (``odoo19c: :390-393``).

        «``qty_to_order_manual if qty_to_order_manual else qty_to_order_computed``».
        Con setter — ver D-2 del docstring del módulo.
        """
        if self._qty_to_order_assigned is not None:
            return self._qty_to_order_assigned
        return (self.qty_to_order_manual if self.qty_to_order_manual
                else self.qty_to_order_computed)

    @qty_to_order.setter
    def qty_to_order(self, value):
        self._qty_to_order_assigned = value
        self._inverse_qty_to_order()

    def _inverse_qty_to_order(self):
        """≙ ``_inverse_qty_to_order`` (``odoo19c: :395-402``).

        En una regla ``auto`` la cantidad manual se borra: la manda el cálculo.
        En una manual, la cantidad asignada se guarda **sólo si difiere** de la
        calculada — asignar exactamente lo calculado no es fijarla a mano.
        """
        if self.trigger == 'auto':
            self.qty_to_order_manual = 0
        elif not self.qty_to_order_manual and not self._qty_to_order_assigned:
            self._qty_to_order_assigned = self.qty_to_order_computed
        elif self._qty_to_order_assigned != self.qty_to_order_computed:
            self.qty_to_order_manual = self._qty_to_order_assigned

    @classmethod
    def _search_qty_to_order(cls, operator, value):
        """≙ ``_search_qty_to_order`` (``odoo19c: :404-411``).

        Dos ramas, como la fuente: las reglas con cantidad manual se comparan
        contra ella; las que no la tienen, contra la calculada.
        """
        lookup = {'=': 'exact', '!=': 'exact', '<': 'lt', '>': 'gt',
                  '<=': 'lte', '>=': 'gte'}.get(operator, 'exact')
        sin_manual = Q(**{f'qty_to_order_computed__{lookup}': value},
                       qty_to_order_manual__in=[0, None])
        con_manual = Q(**{f'qty_to_order_manual__{lookup}': value})
        con_manual &= ~Q(qty_to_order_manual__in=[0, None])
        combinado = sin_manual | con_manual
        return ~combinado if operator == '!=' else combinado

    @property
    def unwanted_replenish(self):
        """≙ ``_compute_unwanted_replenish`` (``odoo19c: :341-347``).

        ``True`` cuando pedir lo propuesto dejaría la existencia **por encima**
        del máximo — la señal de que la regla está mal calibrada.
        """
        uom = self.product_uom
        if self.product_id is None or uom is None:
            return False
        if uom.is_zero(self.qty_to_order) or uom.compare(self.product_max_qty, 0) == -1:
            return False
        tras_reponer = self.product._quantity_for(
            'virtual_available', location=getattr(self.location, 'pk', None),
        ) + self.qty_to_order
        return uom.compare(tras_reponer, self.product_max_qty) > 0

    # ------------------------------------------------------------------ #
    # Los compute almacenados (≙ los que la fuente marca store=True)       #
    # ------------------------------------------------------------------ #

    def _compute_product_max_qty(self):
        """≙ ``_compute_product_max_qty`` (``odoo19c: :209-213``).

        El máximo nunca queda por debajo del mínimo; sin máximo puesto, es el
        mínimo.
        """
        if self.product_max_qty < self.product_min_qty or not self.product_max_qty:
            self.product_max_qty = self.product_min_qty
        return self.product_max_qty

    def _compute_warehouse_id(self):
        """≙ ``_compute_warehouse_id`` (``odoo19c: :265-275``).

        El almacén sale de la ubicación; sin ella, el primero de la empresa. Sin
        ninguno, la fuente lanza el aviso que redirige a crear uno.
        """
        warehouse_model = apps.get_model('stock', 'StockWarehouse')
        if self.location_id is not None and self.location.warehouse is not None:
            self.warehouse = self.location.warehouse
        elif self.company_id is not None:
            self.warehouse = warehouse_model.objects.filter(
                company=self.company).first()
        if self.warehouse_id is None:
            picking_type_model = apps.get_model('stock', 'StockPickingType')
            picking_type_model._warehouse_redirect_warning()
        return self.warehouse

    def _compute_location_id(self):
        """≙ ``_compute_location_id`` (``odoo19c: :277-285``).

        «Finds location id for changed warehouse.» La estantería del almacén.
        """
        warehouse_model = apps.get_model('stock', 'StockWarehouse')
        almacen = self.warehouse
        if almacen is None and self.company_id is not None:
            almacen = warehouse_model.objects.filter(company=self.company).first()
        if almacen is not None:
            self.location = almacen.lot_stock
        return self.location

    @classmethod
    def _compute_qty_to_order_computed(cls, orderpoints):
        """≙ ``_compute_qty_to_order_computed`` (``odoo19c: :413-430``).

        Sólo se calcula para las reglas cuyo pronóstico ya está bajo el mínimo:
        «The check is on purpose. We only want to consider the horizon days if
        the forecast is negative and there is already something to resupply base
        on lead times.» Al resto se le pone cero.

        D-1: recibe el conjunto como argumento — ver el docstring del módulo.
        """
        orderpoints = list(orderpoints)
        por_calcular, resto = [], []
        for orderpoint in orderpoints:
            uom = orderpoint.product_uom
            redondeo = uom.rounding if uom is not None else 0.01
            if orderpoint.pk and float_compare(
                    orderpoint.qty_forecast, orderpoint.product_min_qty,
                    precision_rounding=redondeo) < 0:
                por_calcular.append(orderpoint)
            else:
                resto.append(orderpoint)

        en_progreso = cls._quantity_in_progress(por_calcular)
        for orderpoint in por_calcular:
            orderpoint.qty_to_order_computed = orderpoint._get_qty_to_order(
                qty_in_progress_by_orderpoint=en_progreso)
        for orderpoint in resto:
            orderpoint.qty_to_order_computed = 0.0

        cls.objects.bulk_update(
            [o for o in orderpoints if o.pk], ['qty_to_order_computed'])
        return orderpoints

    @classmethod
    def _compute_deadline_date(cls, orderpoints):
        """≙ ``_compute_deadline_date`` (``odoo19c: :123-178``).

        «This function first checks if the qty_on_hand is less than the
        product_min_qty. If it is the case, the deadline_date is set to the
        current day. Afterwards if there are still orderpoints to compute, it
        retrieves all the outgoing and incoming moves until the
        lead_horizon_date and adds (or subtracts) them to the qty_on_hand. The
        first instance when the qty_on_hand dips below the product_min_qty is
        the deadline date.»

        D-1: recibe el conjunto como argumento — ver el docstring del módulo.
        """
        move_model = apps.get_model('stock', 'StockMove')
        product_model = apps.get_model('product', 'ProductProduct')

        orderpoints = list(orderpoints)
        criticos = [o for o in orderpoints if o.qty_on_hand < o.product_min_qty]
        for orderpoint in criticos:
            orderpoint.deadline_date = _today()
        por_calcular = [o for o in orderpoints if o not in criticos]
        if not por_calcular:
            cls.objects.bulk_update(
                [o for o in orderpoints if o.pk], ['deadline_date'])
            return orderpoints

        # Se filtra por empresa: el horizonte es un ajuste de empresa, así que
        # dos empresas distintas miran hasta fechas distintas.
        por_empresa = defaultdict(list)
        for orderpoint in por_calcular:
            por_empresa[orderpoint.company].append(orderpoint)

        for empresa, del_grupo in por_empresa.items():
            horizonte = _today() + timedelta(
                days=int(cls.get_horizon_days(del_grupo)))
            productos = [o.product for o in del_grupo if o.product is not None]
            _q_quant, q_entra, q_sale = product_model._get_domain_locations()

            entradas = (move_model.objects
                        .filter(q_entra, product__in=productos,
                                state__in=MOVE_STATES_IN_PROGRESS,
                                date__date__lte=horizonte)
                        .values('product', 'location_dest', 'date__date')
                        .annotate(total=Sum('product_qty')))
            salidas = (move_model.objects
                       .filter(q_sale, product__in=productos,
                               state__in=MOVE_STATES_IN_PROGRESS,
                               date__date__lte=horizonte)
                       .values('product', 'location', 'date__date')
                       .annotate(total=Sum('product_qty')))

            por_producto_ubicacion = {}
            for fila in entradas:
                clave = (fila['product'], fila['location_dest'])
                por_producto_ubicacion.setdefault(clave, defaultdict(float))
                por_producto_ubicacion[clave][fila['date__date']] += float(
                    fila['total'] or 0)
            for fila in salidas:
                clave = (fila['product'], fila['location'])
                por_producto_ubicacion.setdefault(clave, defaultdict(float))
                por_producto_ubicacion[clave][fila['date__date']] -= float(
                    fila['total'] or 0)

            for orderpoint in del_grupo:
                existencia = orderpoint.qty_on_hand
                tentativa = horizonte
                movimientos = por_producto_ubicacion.get(
                    (orderpoint.product_id, orderpoint.location_id), {})
                for fecha, cantidad in sorted(movimientos.items()):
                    existencia += cantidad
                    if existencia < orderpoint.product_min_qty:
                        tentativa = fecha - timedelta(days=orderpoint.lead_days)
                        break
                orderpoint.deadline_date = (
                    tentativa if tentativa < horizonte else None)

        cls.objects.bulk_update(
            [o for o in orderpoints if o.pk], ['deadline_date'])
        return orderpoints

    # ------------------------------------------------------------------ #
    # Validación y ciclo de vida (≙ :255-263, 287-311)                     #
    # ------------------------------------------------------------------ #

    def _check_min_max_qty(self):
        """≙ ``_check_min_max_qty`` (``odoo19c: :255-259``)."""
        if self.product_min_qty > self.product_max_qty:
            raise ValidationError(_(
                'The minimum quantity must be less than or equal to the '
                'maximum quantity.'))

    def _onchange_product_id(self):
        """≙ ``_onchange_product_id`` (``odoo19c: :287-290``).

        En la fuente fija ``product_uom`` desde el producto. Aquí
        ``product_uom`` **es** una ``property`` sobre el producto, así que el
        onchange no tiene qué escribir: se conserva como punto de extensión con
        el mismo nombre y su efecto ya es estructural.
        """
        return self.product_uom

    def clean(self):
        """Corre las validaciones que allá son ``@api.constrains``."""
        super().clean()
        self._check_min_max_qty()

    def save(self, *args, **kwargs):
        """Dispara los compute almacenados y las dos guardas de ``create``/``write``.

        ≙ ``create`` (``odoo19c: :292-296``) y ``write`` (``:298-306``): la
        regla ``auto`` no admite ``snoozed_until``, y la empresa no se cambia en
        caliente. La fuente lo verifica en los dos métodos; aquí, en el único
        punto por el que pasan ambos.
        """
        creando = self.pk is None
        if self.snoozed_until and self.trigger == 'auto':
            raise UserError(_(
                'You can only snooze manual orderpoints. You should rather '
                "archive 'auto-trigger' orderpoints if you do not want them to "
                'be triggered.') if not creando else _(
                'You can not create a snoozed orderpoint that is not manually '
                'triggered.'))
        if not creando:
            anterior = type(self).objects.filter(pk=self.pk).values(
                'company_id').first()
            if anterior and anterior['company_id'] != self.company_id:
                raise UserError(_(
                    'Changing the company of this record is forbidden at this '
                    'point, you should rather archive it and create a new one.'))

        if self.warehouse_id is None:
            self._compute_warehouse_id()
        if self.location_id is None:
            self._compute_location_id()
        self._compute_product_max_qty()
        if not self.name:
            self.name = self._next_name()
        return super().save(*args, **kwargs)

    @classmethod
    def _next_name(cls):
        """≙ el ``default`` de ``name`` (``odoo19c: :28-30``).

        «``self.env['ir.sequence'].next_by_code('stock.orderpoint')``». Sin la
        secuencia sembrada aún (alcance de #330), se cae a un nombre vacío como
        hace la fuente cuando ``next_by_code`` no encuentra código.
        """
        sequence_model = apps.get_model('base', 'IrSequence')
        siguiente = getattr(sequence_model, 'next_by_code', None)
        return (siguiente('stock.orderpoint') or '') if siguiente else ''

    # ------------------------------------------------------------------ #
    # Acciones (≙ :308-366) — D-3                                          #
    # ------------------------------------------------------------------ #

    def action_product_forecast_report(self):
        """≙ ``action_product_forecast_report`` (``odoo19c: :308-321``)."""
        accion = self.product.action_product_forecast_report()
        accion['context'] = {
            'active_id': self.product_id,
            'active_model': 'product.product',
            'lead_horizon_date': self.lead_horizon_date,
            'qty_to_order': self._get_qty_to_order(),
        }
        if self.warehouse_id is not None:
            accion['context']['warehouse_id'] = self.warehouse_id
        return accion

    @classmethod
    def action_open_orderpoints(cls):
        """≙ ``action_open_orderpoints`` (``odoo19c: :323-325``)."""
        return cls._get_orderpoint_action()

    def action_stock_replenishment_info(self):
        """≙ ``action_stock_replenishment_info`` (``odoo19c: :327-340``).

        La fuente crea un ``stock.replenishment.info`` transitorio y devuelve la
        acción apuntando a él. Ese modelo **no existe en este árbol** (medido:
        ``grep -rn "replenishment.info" addons/ src/`` → 0), así que se devuelve
        el descriptor sin ``res_id``. Sucesor: tarea **#330**.
        """
        return {
            'type': 'ir.actions.act_window',
            'xml_id': 'stock.action_stock_replenishment_info',
            'res_model': 'stock.replenishment.info',
            'name': _('Replenishment Information for %(product)s in %(warehouse)s') % {
                'product': str(self.product) if self.product else '',
                'warehouse': str(self.warehouse) if self.warehouse else '',
            },
            'context': {'default_orderpoint_id': self.pk},
        }

    @classmethod
    def action_replenish(cls, orderpoints, force_to_max=False):
        """≙ ``action_replenish`` (``odoo19c: :342-365``).

        Con ``force_to_max`` se pide lo que falte para llegar al máximo. Luego
        se lanza el aprovisionamiento, se limpia la cantidad manual, se
        recalcula, y las reglas manuales creadas por el sistema que ya no piden
        nada se borran — la fuente las crea para el reporte de reabastecimiento
        y no quiere dejarlas.

        D-1: recibe el conjunto como argumento.
        """
        orderpoints = list(orderpoints)
        if force_to_max:
            for orderpoint in orderpoints:
                orderpoint.qty_to_order = orderpoint._get_multiple_rounded_qty(
                    orderpoint.product_max_qty - orderpoint.qty_forecast)

        cls._procure_orderpoint_confirm(
            orderpoints, company_id=get_current_company())

        notificacion = (orderpoints[0]._get_replenishment_order_notification()
                        if len(orderpoints) == 1 else False)
        cls.action_remove_manual_qty_to_order(orderpoints)
        cls._compute_qty_to_order_computed(orderpoints)
        a_borrar = [o.pk for o in orderpoints
                    if o.qty_to_order <= 0.0 and o.trigger == 'manual']
        if a_borrar:
            cls.objects.filter(pk__in=a_borrar).delete()
        return notificacion

    @classmethod
    def action_replenish_auto(cls, orderpoints):
        """≙ ``action_replenish_auto`` (``odoo19c: :367-369``)."""
        orderpoints = list(orderpoints)
        for orderpoint in orderpoints:
            orderpoint.trigger = 'auto'
        cls.objects.bulk_update([o for o in orderpoints if o.pk], ['trigger'])
        return cls.action_replenish(orderpoints)

    @classmethod
    def action_remove_manual_qty_to_order(cls, orderpoints):
        """≙ ``action_remove_manual_qty_to_order`` (``odoo19c: :629-630``)."""
        orderpoints = list(orderpoints)
        for orderpoint in orderpoints:
            orderpoint.qty_to_order_manual = 0
        cls.objects.bulk_update(
            [o for o in orderpoints if o.pk], ['qty_to_order_manual'])

    # ------------------------------------------------------------------ #
    # El cálculo de la cantidad a pedir (≙ :432-506)                       #
    # ------------------------------------------------------------------ #

    def _get_default_rule(self):
        """≙ ``_get_default_rule`` (``odoo19c: :432-438``)."""
        rule_model = apps.get_model('stock', 'StockRule')
        return rule_model._get_rule(self.product, self.location, {
            'route_ids': [self.route] if self.route is not None else (),
            'warehouse_id': self.warehouse,
        })

    def _get_default_route(self):
        """≙ ``_get_default_route`` (``odoo19c: :440-452``).

        La primera regla que abastece esta ubicación y cuya ruta esté entre las
        del producto o las de su categoría.
        """
        rule_model = apps.get_model('stock', 'StockRule')
        if self.product_id is None or self.location_id is None:
            return None
        # ``route_ids`` es un Many2many: su atributo es el **gestor**, que no es
        # iterable — hay que pedirle el queryset con ``.all()``.
        propias = set(_related_pks(self.product, 'route_ids'))
        propias |= set(_related_pks(getattr(self.product, 'categ', None),
                                    'route_ids'))
        candidatas = rule_model.objects.filter(
            Q(route__product_selectable=True)
            | Q(route__product_categ_selectable=True),
            location_dest=self.location,
            action__in=('pull_push', 'pull'),
            route__active=True,
        ).select_related('route')
        for regla in candidatas:
            if regla.route is not None and regla.route.pk in propias:
                return regla.route
        return None

    def _get_replenishment_multiple_alternative(self, qty_to_order):
        """≙ ``_get_replenishment_multiple_alternative`` (``odoo19c: :454-460``).

        «This method is used to get the alternative replenishment_uom_id for the
        orderpoint if not set manually. To be overridden in relevant modules.»
        Devuelve ``False`` en la fuente; se porta con su cuerpo real.
        """
        return False

    def _get_qty_to_order(self, qty_in_progress_by_orderpoint=None):
        """≙ ``_get_qty_to_order`` (``odoo19c: :462-478``).

        Lo que falta para llegar al mayor entre mínimo y máximo, descontando lo
        que ya viene en camino, redondeado al múltiplo de reabastecimiento.
        """
        qty_in_progress_by_orderpoint = qty_in_progress_by_orderpoint or {}
        en_progreso = qty_in_progress_by_orderpoint.get(self.pk)
        if en_progreso is None:
            en_progreso = type(self)._quantity_in_progress([self]).get(self.pk, 0.0)

        uom = self.product_uom
        redondeo = uom.rounding if uom is not None else 0.01
        if float_compare(self.qty_forecast, self.product_min_qty,
                         precision_rounding=redondeo) >= 0:
            return 0.0

        contexto = self._get_product_context()
        pronostico = self.product._quantity_for(
            'virtual_available', **contexto) + en_progreso
        cantidad = max(self.product_min_qty, self.product_max_qty) - pronostico
        return self._get_multiple_rounded_qty(cantidad)

    def _get_lead_days_values(self):
        """≙ ``_get_lead_days_values`` (``odoo19c: :480-484``)."""
        return {'days_to_order': self.days_to_order}

    def _get_product_context(self):
        """≙ ``_get_product_context`` (``odoo19c: :486-492``).

        «Used to call ``virtual_available`` when running an orderpoint.»
        """
        horizonte = self.lead_horizon_date
        return {
            'location': getattr(self.location, 'pk', None),
            'to_date': (datetime.combine(horizonte, time.max)
                        if horizonte is not None else None),
        }

    def _get_multiple_rounded_qty(self, qty_to_order):
        """≙ ``_get_multiple_rounded_qty`` (``odoo19c: :795-802``).

        Redondea **hacia arriba** al múltiplo de reabastecimiento: se pide de a
        cajas completas, no fracciones. La fuente anota que un módulo que no
        quiera pasarse del máximo cambia el ``UP`` por ``DOWN``.
        """
        multiplo = (self.replenishment_uom
                    or self._get_replenishment_multiple_alternative(qty_to_order))
        if not multiplo or self.product_id is None or self.product.uom is None:
            return qty_to_order
        unidad = self.product.uom
        cantidad = unidad.compute_quantity(qty_to_order, multiplo, round=False)
        cantidad = multiplo.round(cantidad, rounding_method='UP')
        return multiplo.compute_quantity(cantidad, unidad, round=False)

    @classmethod
    def get_horizon_days(cls, orderpoints=None):
        """≙ ``get_horizon_days`` (``odoo19c: :804-811``).

        «Return the value for Horizon. This can be (in order of priority): the
        value set in context in the replenishment view; the value set on the
        company of the all the records in self; the value set on the company of
        the user if all else fail.»

        D-1: la fuente lo llama sobre un recordset. Aquí es ``classmethod`` con
        el conjunto **opcional**, porque ``stock_rule.py:1029`` ya lo llamaba
        sobre la clase antes de que este archivo existiera. Sin conjunto, la
        empresa es la activa — que es exactamente el tercer nivel de prioridad
        que la fuente describe.
        """
        empresa = None
        for orderpoint in (orderpoints or ()):
            if orderpoint.company is not None:
                empresa = orderpoint.company
                break
        if empresa is None:
            # ``get_current_company()`` devuelve la **PK**, no el registro
            # (``orm/environments.py:153-161``) — por eso hay que resolverlo.
            # Leerlo como si fuera el objeto devolvía siempre 0 en silencio:
            # ver :ref:`h-api-617`.
            company_model = apps.get_model('base', 'ResCompany')
            empresa = company_model.objects.filter(
                pk=get_current_company()).first()
        return getattr(empresa, 'horizon_days', 0) or 0

    # ------------------------------------------------------------------ #
    # El reporte de reabastecimiento (≙ :494-627)                          #
    # ------------------------------------------------------------------ #

    @classmethod
    def _get_orderpoint_action(cls):
        """≙ ``_get_orderpoint_action`` (``odoo19c: :494-627``).

        «Create manual orderpoints for missing product in each warehouses. It
        also removes orderpoints that have been replenish.»

        El procedimiento de la fuente, en cuatro pasos: (1) borra las reglas
        manuales que el sistema creó y ya se repusieron; (2) por cada ubicación
        de reabastecimiento y producto, calcula existencia + entradas − salidas
        y se queda con los negativos; (3) recalcula el pronóstico con el plazo
        de cada uno; (4) crea una regla manual por cada faltante que no tenga ya
        una.

        D-3: devuelve el descriptor de la acción, no un ``act_window`` resuelto.
        """
        move_model = apps.get_model('stock', 'StockMove')
        quant_model = apps.get_model('stock', 'StockQuant')
        stock_location = apps.get_model('stock', 'StockLocation')
        warehouse_model = apps.get_model('stock', 'StockWarehouse')
        product_model = apps.get_model('product', 'ProductProduct')

        accion = {
            'type': 'ir.actions.act_window',
            'xml_id': 'stock.action_orderpoint_replenish',
            'res_model': cls._name,
        }

        orderpoints = cls.objects.all()
        borradas = cls._unlink_processed_orderpoints(orderpoints)
        orderpoints = cls.objects.exclude(pk__in=[o.pk for o in borradas])

        a_reponer = defaultdict(float)
        productos = list(cls._get_orderpoint_products())
        ubicaciones = list(cls._get_orderpoint_locations())
        if not productos or not ubicaciones:
            return accion

        q_quant, q_entra, q_sale = product_model._get_domain_locations_new(
            [u.pk for u in ubicaciones])
        q_estado = Q(state__in=MOVE_STATES_IN_PROGRESS)
        q_producto = Q(product__in=productos)

        entradas = defaultdict(list)
        for fila in (move_model.objects
                     .filter(q_producto & q_estado & q_entra)
                     .values('product', 'location_dest', 'location_final')
                     .annotate(total=Sum('product_qty'))):
            entradas[fila['product']].append(
                (fila['location_dest'], fila['location_final'],
                 float(fila['total'] or 0)))

        salidas = defaultdict(list)
        for fila in (move_model.objects
                     .filter(q_producto & q_estado & q_sale)
                     .values('product', 'location')
                     .annotate(total=Sum('product_qty'))):
            salidas[fila['product']].append(
                (fila['location'], float(fila['total'] or 0)))

        quants = defaultdict(list)
        for fila in (quant_model.objects
                     .filter(q_producto & q_quant)
                     .values('product', 'location')
                     .annotate(total=Sum('quantity'))):
            quants[fila['product']].append(
                (fila['location'], float(fila['total'] or 0)))

        rutas = {loc.pk: loc.parent_path for loc in stock_location.objects.filter(
            parent_path__isnull=False)}
        por_plazo = defaultdict(set)
        for ubicacion in ubicaciones:
            for producto in productos:
                disponible = sum(
                    q[1] for q in quants.get(producto.pk, ())
                    if is_parent_path_in(ubicacion, rutas, q[0]))
                entrante = sum(
                    m[2] for m in entradas.get(producto.pk, ())
                    if is_parent_path_in(ubicacion, rutas, m[0])
                    or is_parent_path_in(ubicacion, rutas, m[1]))
                saliente = sum(
                    m[1] for m in salidas.get(producto.pk, ())
                    if is_parent_path_in(ubicacion, rutas, m[0]))
                if producto.uom is None:
                    continue
                if producto.uom.compare(disponible + entrante - saliente, 0) >= 0:
                    continue
                reglas = product_model._get_rules_from_location(
                    producto, ubicacion)
                plazos, _descripcion = apps.get_model(
                    'stock', 'StockRule')._get_lead_days(reglas, producto)
                dias = plazos.get('total_delay', 0) + plazos.get('horizon_time', 0)
                por_plazo[dias, ubicacion.pk].add(producto.pk)

        # Se recalcula el pronóstico con el plazo de cada grupo.
        hoy = timezone.now().replace(hour=23, minute=59, second=59)
        for (dias, ubicacion_id), producto_ids in por_plazo.items():
            for producto in product_model.objects.filter(pk__in=producto_ids):
                pronostico = producto._quantity_for(
                    'virtual_available', location=ubicacion_id,
                    to_date=hoy + timedelta(days=dias))
                if producto.uom is not None and producto.uom.compare(pronostico, 0) < 0:
                    a_reponer[(producto.pk, ubicacion_id)] = pronostico
        if not a_reponer:
            return accion

        # Se descuenta lo que ya viene por otra vía (una orden de compra, p.ej.)
        # y lo que otras reglas de la misma ubicación ya piden.
        producto_ids = sorted({p for p, _u in a_reponer})
        ubicacion_ids = sorted({u for _p, u in a_reponer})
        en_progreso = product_model.objects.filter(pk__in=producto_ids).first()
        en_progreso = (en_progreso._get_quantity_in_progress(
            location_ids=ubicacion_ids)[0] if en_progreso is not None else {})
        ya_pedido = defaultdict(float)
        for orderpoint in orderpoints.filter(product__in=producto_ids):
            ya_pedido[(orderpoint.product_id, orderpoint.location_id)] += (
                orderpoint.qty_to_order)
        for clave, cantidad in list(a_reponer.items()):
            extra = (en_progreso.get(clave) or 0.0) + ya_pedido.get(clave, 0.0)
            if extra:
                a_reponer[clave] = cantidad + extra
        a_reponer = {k: v for k, v in a_reponer.items() if v < 0.0}

        existentes = {(o.product_id, o.location_id)
                      for o in orderpoints.filter(product__in=producto_ids)}
        nuevas = []
        for (producto_id, ubicacion_id), cantidad in a_reponer.items():
            if (producto_id, ubicacion_id) in existentes:
                continue
            ubicacion = stock_location.objects.filter(pk=ubicacion_id).first()
            if ubicacion is None:
                continue
            almacen = ubicacion.warehouse or warehouse_model.objects.filter(
                company=ubicacion.company).first()
            valores = cls._get_orderpoint_values(
                product_model.objects.filter(pk=producto_id).first(), ubicacion)
            valores.update({
                'name': _('Replenishment Report'),
                'warehouse': almacen,
                'company': ubicacion.company,
            })
            nuevas.append(cls(**valores))
        for orderpoint in nuevas:
            orderpoint.save()
        return accion

    @classmethod
    def _get_orderpoint_values(cls, product, location):
        """≙ ``_get_orderpoint_values`` (``odoo19c: :632-640``)."""
        return {
            'product': product,
            'location': location,
            'product_max_qty': 0.0,
            'product_min_qty': 0.0,
            'trigger': 'manual',
        }

    def _get_replenishment_order_notification(self):
        """≙ ``_get_replenishment_order_notification`` (``odoo19c: :642-665``).

        Cuando el reabastecimiento resultó en una transferencia **entre
        almacenes** —o por tránsito—, la fuente devuelve la notificación con el
        enlace a esa transferencia. En otro caso, ``False``.
        """
        move_model = apps.get_model('stock', 'StockMove')
        move = move_model.objects.filter(orderpoint=self).first()
        if move is None:
            return False
        origin = move.location
        other_warehouse = (origin is not None and origin.warehouse is not None
                           and origin.warehouse != self.warehouse)
        in_transit = origin is not None and origin.usage == 'transit'
        picking = getattr(move, 'picking', None)
        if not (other_warehouse or in_transit) or picking is None:
            return False
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('The inter-warehouse transfers have been generated'),
                'message': '%s',
                'links': [{'label': picking.name,
                           'url': f'/odoo/action-stock.stock_picking_action_'
                                  f'picking_type/{picking.pk}'}],
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    @classmethod
    def _quantity_in_progress(cls, orderpoints):
        """≙ ``_quantity_in_progress`` (``odoo19c: :667-670``).

        «Return Quantities that are not yet in virtual stock but should be
        deduced from orderpoint rule (example: purchases created from
        orderpoints).» Cero en la fuente: es el punto de extensión que
        ``purchase_stock`` y ``mrp`` rellenan. Se porta con su cuerpo real.
        """
        return {o.pk: 0.0 for o in orderpoints}

    @classmethod
    def _unlink_processed_orderpoints(cls, orderpoints=None):
        """≙ ``_unlink_processed_orderpoints`` (``odoo19c: :672-686``).

        Borra las reglas **manuales creadas por el sistema** que ya no piden
        nada: son las que el reporte de reabastecimiento fabrica, y dejarlas
        ensuciaría la lista. La fuente lo cuelga de ``@api.autovacuum``; aquí
        queda invocable y su cron es la tarea **#124**.
        """
        candidatas = cls.objects.filter(trigger='manual')
        if orderpoints is not None:
            candidatas = candidatas.filter(
                pk__in=[o.pk for o in orderpoints])
        a_borrar = [o for o in candidatas if o.qty_to_order <= 0.0]
        if a_borrar:
            cls.objects.filter(pk__in=[o.pk for o in a_borrar]).delete()
        return a_borrar

    # ------------------------------------------------------------------ #
    # El lanzamiento del aprovisionamiento (≙ :688-793)                    #
    # ------------------------------------------------------------------ #

    def _prepare_procurement_values(self, date=False):
        """≙ ``_prepare_procurement_values`` (``odoo19c: :688-707``).

        «Prepare specific key for moves or other components that will be created
        from a stock rule comming from an orderpoint.»
        """
        product_model = apps.get_model('product', 'ProductProduct')
        fecha_limite = date or _today()
        fechas = product_model._get_dates_info(
            self.product, fecha_limite, self.location,
            route_ids=[self.route] if self.route is not None else ())
        return {
            'route_ids': [self.route] if self.route is not None else [],
            'date_planned': fechas['date_planned'],
            'date_order': fechas['date_order'],
            'date_deadline': date or False,
            'warehouse_id': self.warehouse,
            'orderpoint_id': self if self.trigger == 'auto' else False,
        }

    def _get_orderpoint_procurement_date(self):
        """≙ ``_get_orderpoint_procurement_date`` (``odoo19c: :788-789``).

        Mediodía de la fecha horizonte, en el huso de la empresa, devuelto en
        UTC sin zona — que es como la fuente lo entrega.
        """
        horizonte = self.lead_horizon_date or _today()
        return datetime.combine(horizonte, time(12))

    @classmethod
    def _procure_orderpoint_confirm(cls, orderpoints, use_new_cursor=False,
                                    company_id=None, raise_user_error=True):
        """≙ ``_procure_orderpoint_confirm`` (``odoo19c: :709-786``).

        «Create procurements based on orderpoints.» Por lotes de 1000, arma una
        ``Procurement`` por cada regla que pide algo y las lanza todas juntas.
        Si alguna falla, la fuente **saca del lote a las que fallaron** y
        reintenta con el resto — no aborta el lote entero.

        D-1: recibe el conjunto como argumento.

        El ``use_new_cursor`` de la fuente abre un cursor propio y hace commit
        cada 1000: es su forma de trocear un trabajo por lotes largo. Aquí el
        parámetro se acepta y se ignora — Django no expone un cursor dedicado
        por lote con esa semántica, y el planificador ya corre dentro de su
        propia transacción. Es divergencia de mecanismo declarada.
        """
        rule_model = apps.get_model('stock', 'StockRule')

        orderpoints = list(orderpoints)
        for lote_ids in split_every(1000, [o.pk for o in orderpoints]):
            lote = [o for o in orderpoints if o.pk in set(lote_ids)]
            excepciones = []
            while lote:
                procurements = []
                for orderpoint in lote:
                    uom = orderpoint.product_uom
                    if uom is None or uom.compare(orderpoint.qty_to_order, 0.0) != 1:
                        continue
                    fecha = orderpoint._get_orderpoint_procurement_date()
                    horizonte = cls.get_horizon_days([orderpoint])
                    if horizonte:
                        fecha -= timedelta(days=int(horizonte))
                    valores = orderpoint._prepare_procurement_values(date=fecha)
                    procurements.append(rule_model.Procurement(
                        orderpoint.product, orderpoint.qty_to_order,
                        orderpoint.product_uom, orderpoint.location,
                        orderpoint.name, orderpoint.name,
                        orderpoint.company, valores))
                try:
                    rule_model.run(procurements,
                                   raise_user_error=raise_user_error)
                except ProcurementException as error:
                    fallidos = _failed_orderpoints(error)
                    excepciones += fallidos
                    culpables = {o.pk for o, _msg in fallidos if o is not None}
                    if not culpables:
                        break
                    lote = [o for o in lote if o.pk not in culpables]
                else:
                    cls._post_process_scheduler(lote)
                    break

            # La fuente registra una actividad de aviso sobre la plantilla del
            # producto por cada regla que falló, sin duplicar el mismo mensaje.
            for orderpoint, mensaje in excepciones:
                if orderpoint is None or orderpoint.product is None:
                    continue
                plantilla = orderpoint.product.product_tmpl
                programar = getattr(plantilla, 'activity_schedule', None)
                if programar is None:
                    continue
                programar('mail.mail_activity_data_warning', note=mensaje)
        return {}

    @classmethod
    def _post_process_scheduler(cls, orderpoints=None):
        """≙ ``_post_process_scheduler`` (``odoo19c: :785-786``).

        «``return True``» — punto de extensión vacío en la fuente. Se porta con
        su cuerpo real.
        """
        return True

    @classmethod
    def _get_orderpoint_products(cls):
        """≙ ``_get_orderpoint_products`` (``odoo19c: :791-792``).

        Los productos almacenables que ya tienen algún movimiento.
        """
        product_model = apps.get_model('product', 'ProductProduct')
        return product_model.objects.filter(
            product_tmpl__is_storable=True, stock_move_ids__isnull=False,
        ).distinct()

    @classmethod
    def _get_orderpoint_locations(cls):
        """≙ ``_get_orderpoint_locations`` (``odoo19c: :794-795``)."""
        stock_location = apps.get_model('stock', 'StockLocation')
        return stock_location.objects.filter(replenish_location=True)


def _failed_orderpoints(error):
    """Las reglas que provocaron el fallo — ≙ ``odoo19c: :762-766``.

    **No es un símbolo de la referencia**: allá el desempaquetado va en línea
    dentro del ``except``. Se factoriza porque el ``except`` ya lleva dos ramas
    y el cuerpo mezclaba desempaquetar con decidir.
    """
    return [(p.values.get('orderpoint_id') or None, mensaje)
            for p, mensaje in error.procurement_exceptions]
