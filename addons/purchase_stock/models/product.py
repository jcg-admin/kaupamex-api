"""``product.template`` / ``product.product`` / ``product.supplierinfo`` — la
demanda mensual y la cantidad sugerida de compra (Odoo ``purchase_stock``).

Adaptación de Odoo ``purchase_stock/models/product.py``
(``odoo19c: addons/purchase_stock/models/product.py``, 330 líneas, LGPL-3) —
atribución y aviso de licencia preservados (DEC-KX-03).

Qué añade: el producto aprende a decir **cuánto se mueve al mes** y, a partir de
ahí, **cuánto habría que comprar**. La ventana sobre la que se mide (30 días,
una semana, un año, el mismo trimestre del año pasado…) es una elección del
usuario, y el mismo mecanismo sirve para las tres preguntas: demanda mensual,
cantidad sugerida y precio estimado de esa sugerencia.

Porte símbolo por símbolo — 9 de 19
=====================================

*Métrica:* entradas del cuerpo de las tres clases contadas por AST sobre la
fuente. Con ``_inherit`` son 22; sin él **19**: 6 campos y 13 métodos
(1 en ``ProductTemplate``, 11 + 4 campos en ``ProductProduct``, 4 + 2 campos en
``ProductSupplierinfo``).
*Ciega a:* si un símbolo portado se comporta igual en ejecución — mide
presencia, no conducta.

.. list-table::
   :header-rows: 1
   :widths: 42 14 44

   * - Símbolo (línea)
     - Estado
     - Nota
   * - ``ProductTemplate._onchange_buy_route`` (``:16-31``)
     - portado
     - devuelve el aviso; no lo dispara un evento de formulario
   * - ``ProductProduct.monthly_demand`` (``:38``)
     - portado
     - ``property``
   * - ``ProductProduct.suggested_qty`` (``:39``)
     - portado
     - ``property``; su ``search=`` queda bloqueado
   * - ``_compute_monthly_demand`` (``:107-134``)
     - portado
     - agregación por ORM en vez de ``_read_group``
   * - ``_get_monthly_demand_moves_location_domain`` (``:136-162``)
     - portado
     - ``Domain`` verbatim, incluidas las dos ramas
   * - ``_get_monthly_demand_range`` (``:221-246``)
     - portado
     - sin ``relativedelta`` — ver divergencia D-1
   * - ``_compute_suggested_quantity`` (``:42-60``)
     - portado
     - las dos ramas de la fuente
   * - ``get_total_routes`` (``:248-253``)
     - portado
     - ``chain_method`` con ``combine`` de conjuntos
   * - ``ProductSupplierinfo._compute_display_name`` (``:290-298``)
     - portado
     - f-string en vez de ``formatLang`` (D-2)
   * - ``purchase_order_line_ids`` (``:37``)
     - **divergencia**
     - ya existe con otro nombre — ver abajo
   * - ``suggest_estimated_price`` + su compute (``:40``, ``:62-78``)
     - **bloqueado**
     - ``grep -rn "_select_seller" addons/ src/`` → 0
   * - ``_search_product_with_suggested_quantity`` (``:80-89``)
     - **bloqueado**
     - ``search_fetch``/``filtered_domain`` sobre un campo sin columna
   * - ``_compute_quantities`` (``:91-93``)
     - **nada que portar**
     - su cuerpo es ``return super()._compute_quantities()``
   * - ``_compute_quantities_dict`` (``:95-105``)
     - **bloqueado por mecanismo**
     - modifica un argumento ANTES del ``super()`` — ver D-3
   * - ``_get_quantity_in_progress`` (``:164-185``)
     - **bloqueado**
     - la línea de compra no tiene ``product_uom_id`` ni ``state``
   * - ``_get_lines_domain`` (``:187-219``)
     - **bloqueado**
     - es el dominio del anterior; sin él no tiene llamador
   * - ``last_purchase_date`` + su compute (``:259``, ``:263-279``)
     - **bloqueado**
     - ``PurchaseOrder.partner`` apunta a un usuario, no a ``res.partner``
   * - ``show_set_supplier_button`` + su compute (``:260-261``, ``:281-288``)
     - portado
     - ``property``, lee el punto de pedido del contexto
   * - ``action_set_supplier`` (``:300-330``)
     - **bloqueado**
     - ``product.replenish`` no está portado (ver ``wizard/``)

Divergencias declaradas
========================

**D-1 — sin ``dateutil.relativedelta``.** La fuente usa ``relativedelta`` en
``_get_monthly_demand_range`` y ``_compute_quantities_dict``. Medido:
``grep -in dateutil pyproject.toml uv.lock`` → vacío; no es dependencia de este
proyecto. El desplazamiento por meses y años se calcula con aritmética de
calendario, con la misma semántica que ``relativedelta``: mismo día del mes
destino, recortado al último día cuando no existe. Es el mismo criterio y casi
el mismo código que ``addons/base_automation/models/base_automation.py:165``
(``advance_date``), que este archivo cita en vez de re-derivar.

**D-2 — ``formatLang`` no existe en este árbol.** Medido: 0 definiciones (los 6
hits de ``grep -rn formatLang`` son menciones en docstrings de ``account`` que
declaran exactamente esta misma divergencia). El nombre para mostrar del
proveedor usa una f-string con el símbolo de la moneda, que es lo que
``formatLang`` produce sin el formato por locale.

**D-3 — ``_compute_quantities_dict`` no se puede encadenar.** La fuente
**modifica el argumento ``to_date`` antes** de llamar al ``super()``.
``chain_method`` ejecuta la función nueva y, si devuelve ``None``, ejecuta la
previa **con los argumentos originales** (``src/orm/method_chain.py:158-168``):
no hay forma de reescribir un argumento en el camino. Instalarlo produciría un
método que ignora en silencio la ventana de la sugerencia — un resultado
plausible y equivocado, que es peor que la ausencia. Sucesor: cuando
``chain_method`` admita un ``combine`` sobre los argumentos de entrada (hoy
sólo lo admite sobre el resultado), este método se porta sin cambios.

**D-4 — ``purchase_order_line_ids`` ya existe con otro nombre.** La fuente lo
declara ``One2many('purchase.order.line', 'product_id')``. Aquí ese reverso ya
lo produce ``PurchaseOrderLine.product``, declarado con
``related_name='purchase_order_lines'``
(``addons/purchase/models/purchase_order_line.py:27-30``). Colgar un segundo
accesor sobre la misma relación sería un alias sin dato nuevo, y la regla de
colisiones de esta tanda lo prohíbe expresamente. Quien busque el nombre de la
fuente lo encuentra aquí.

Nota sobre ``_onchange_buy_route``
====================================

En la fuente es ``@api.onchange``: el cliente web lo dispara al marcar una
casilla y muestra el diccionario ``{'warning': ...}`` que devuelve. Aquí no hay
formulario que lo dispare, así que se porta como **método normal** con el mismo
nombre y el mismo valor de retorno: quien valide un producto —una vista DRF, un
comando— lo invoca y decide qué hacer con el aviso. Es la misma traducción que
``stock`` ya hizo con ``_onchange_tracking``
(``addons/stock/models/product.py``).
"""
import calendar
from datetime import datetime, timedelta

from django.apps import apps
from django.db.models import Sum

from addons.product.models import ProductSupplierinfo, ProductTemplate
from orm.domains import Domain, to_q
from orm.environments import get_context
from orm.method_chain import chain_method
from orm.model_classes import extend_model

#: ≙ ``'buy'`` — el valor de ``stock.rule.action`` que este addon añade. Se
#: declara aquí como literal y no se importa de ``stock_rule.py`` del mismo
#: addon para no crear un ciclo de imports entre dos módulos hermanos.
ACTION_BUY = 'buy'


# --- aritmética de calendario (D-1) ----------------------------------------

def _shift_months(value, count):
    """≙ ``value - relativedelta(months=count)`` cuando ``count`` es negativo.

    Misma semántica que ``relativedelta``: conserva el día del mes y lo recorta
    al último día del mes destino cuando ese día no existe (31 de marzo menos
    un mes → 28 o 29 de febrero). Copiado en espíritu de
    ``addons/base_automation/models/base_automation.py:181-187``.
    """
    total = value.month - 1 + count
    year = value.year + total // 12
    month = total % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


# --- product.template ------------------------------------------------------

def _onchange_buy_route(self):
    """≙ ``_onchange_buy_route`` (``odoo19c: :16-31``).

    Avisa cuando el producto tiene la ruta «Comprar» marcada pero no es
    comprable — una combinación que deja al reabastecimiento sin salida.
    Devuelve el mismo diccionario ``{'warning': {...}}`` de la fuente, o
    ``None`` cuando no hay nada que avisar.
    """
    if self.purchase_ok:
        return None
    StockRule = apps.get_model('stock', 'StockRule')
    buy_route_ids = set(
        StockRule.objects
        .filter(action=ACTION_BUY, picking_type__code='incoming', active=True)
        .values_list('route', flat=True)
    )
    if not buy_route_ids:
        return None
    own_route_ids = set(self.route_ids.values_list('pk', flat=True))
    if buy_route_ids & own_route_ids:
        return {'warning': {
            'title': '¡Atención!',
            'message': 'Este producto tiene marcada la ruta «Comprar» pero no '
                       'es comprable.',
        }}
    return None


# --- product.product: la demanda mensual -----------------------------------

def _get_monthly_demand_range(self, based_on):
    """≙ ``_get_monthly_demand_range`` (``odoo19c: :221-246``).

    La ventana temporal sobre la que se mide la demanda, según lo que el
    usuario haya elegido. Las cinco ramas de la fuente, en su mismo orden, sin
    ``relativedelta`` (D-1).
    """
    start_date = limit_date = datetime.now()

    if not based_on or based_on in ('actual_demand', '30_days'):
        start_date = start_date - timedelta(days=30)
    elif based_on == 'one_week':
        start_date = start_date - timedelta(weeks=1)
    elif based_on == 'three_months':
        start_date = _shift_months(start_date, -3)
    elif based_on == 'one_year':
        start_date = _shift_months(start_date, -12)
    else:
        # Periodo relativo al año pasado: el mes homólogo, o el siguiente,
        # o el subsiguiente; y el trimestre cuando se pide.
        today = datetime.now()
        start_date = datetime(year=today.year - 1, month=today.month, day=1)
        if based_on == 'last_year_m_plus_1':
            start_date = _shift_months(start_date, 1)
        elif based_on == 'last_year_m_plus_2':
            start_date = _shift_months(start_date, 2)
        if based_on == 'last_year_quarter':
            limit_date = _shift_months(start_date, 3)
        else:
            limit_date = _shift_months(start_date, 1)

    return start_date, limit_date


def _get_monthly_demand_moves_location_domain(self):
    """≙ ``_get_monthly_demand_moves_location_domain`` (``odoo19c: :136-162``).

    El comentario de la fuente es la parte que no hay que perder: cuentan como
    demanda los movimientos que **salen** del almacén elegido hacia un cliente
    o a producción, y los que van a **otro** almacén (un central que surte a
    sus tiendas). Las devoluciones no cuentan: vuelven a las existencias.

    ``location_dest_usage`` de la fuente es un campo relacionado allá; aquí es
    una ``property`` sin columna, así que el dominio navega la relación
    (``location_dest.usage``) — misma condición, expresada sobre la columna que
    sí existe.
    """
    warehouse_id = get_context().get('warehouse_id')
    # ≙ ``['!', ('move_dest_ids.origin_returned_move_id', '=', False)]`` —
    # excluye los movimientos cuyo destino es una devolución.
    non_return = ~Domain('move_dest_ids.origin_returned_move', '=', False)
    if not warehouse_id:
        return Domain.AND([
            Domain.OR([
                Domain('location_dest.usage', 'in', ['customer', 'production']),
                Domain('location_final.usage', 'in', ['customer', 'production']),
            ]),
            non_return,
        ])
    return Domain.AND([
        Domain('location.warehouse', '=', warehouse_id),
        Domain.OR([
            Domain('location_dest.warehouse', '!=', warehouse_id),
            Domain('location_final.warehouse', '!=', warehouse_id),
        ]),
        Domain('location_dest.usage', '!=', 'inventory'),   # excluye el desecho
        non_return,
    ])


def _compute_monthly_demand(self):
    """≙ ``_compute_monthly_demand`` (``odoo19c: :107-134``).

    Suma la cantidad movida en la ventana y la normaliza a un mes. El divisor
    de la fuente se conserva verbatim: 12 para un año, 3 para tres meses o el
    trimestre del año pasado, y ``7 / (365.25 / 12)`` para una semana.

    ``_read_group`` de la fuente → agregación del ORM de Django. La fuente
    agrupa por producto porque opera sobre un *recordset*; aquí una instancia
    es un registro, así que basta el ``Sum`` sobre su propio filtro.
    """
    based_on = get_context().get('suggest_based_on', '30_days')
    start_date, limit_date = self._get_monthly_demand_range(based_on)

    StockMove = apps.get_model('stock', 'StockMove')
    move_domain = Domain.AND([
        Domain('product', '=', self.pk),
        Domain('state', 'in',
               ['assigned', 'confirmed', 'partially_available', 'done']),
        Domain('date', '>=', start_date),
        Domain('date', '<', limit_date),
        self._get_monthly_demand_moves_location_domain(),
    ])
    total = (StockMove.objects
             .filter(to_q(move_domain, StockMove))
             .aggregate(total=Sum('product_qty'))['total'] or 0)

    factor = 1
    if based_on == 'one_year':
        factor = 12
    elif based_on in ('three_months', 'last_year_quarter'):
        factor = 3
    elif based_on == 'one_week':
        factor = 7 / (365.25 / 12)
    return total / factor


def monthly_demand(self):
    """≙ ``monthly_demand`` (``odoo19c: :38``) — ``compute`` sin ``store``."""
    return self._compute_monthly_demand()


def _compute_suggested_quantity(self):
    """≙ ``_compute_suggested_quantity`` (``odoo19c: :42-60``).

    Las dos ramas de la fuente:

    - ``actual_demand`` — se sugiere cubrir el déficit previsto
      (``virtual_available`` negativo), ajustado por el porcentaje elegido.
    - cualquier otra base — se sugiere la demanda mensual proyectada sobre los
      días de horizonte, **menos** lo que ya hay a la mano y lo que ya viene en
      camino.

    ``float_round(..., rounding_method='UP')`` de la fuente es un redondeo
    hacia arriba a entero: aquí ``math.ceil`` sobre el mismo valor, con el
    mismo ``max(..., 0)`` que impide sugerir cantidades negativas.
    """
    ctx = get_context()
    based_on = ctx.get('suggest_based_on')
    percent = ctx.get('suggest_percent', 0)

    if based_on == 'actual_demand':
        if self.virtual_available >= 0:
            return 0
        qty = -self.virtual_available * percent / 100
        return max(-(-qty // 1), 0)      # ceil sin importar math

    if based_on:
        demand = self.monthly_demand
        if demand <= 0:
            return 0
        # 7 días / (365.25 días/año / 12 meses/año) = 0.23 meses
        monthly_ratio = ctx.get('suggest_days', 0) / (365.25 / 12)
        qty = demand * monthly_ratio * percent / 100
        qty -= max(self.qty_available, 0) + max(self.incoming_qty, 0)
        return max(-(-qty // 1), 0)

    return 0


def suggested_qty(self):
    """≙ ``suggested_qty`` (``odoo19c: :39``) — ``compute`` sin ``store``.

    Su ``search='_search_product_with_suggested_quantity'`` queda **bloqueado**:
    el campo no tiene columna y el mecanismo de búsqueda sobre computados sin
    almacenar (``search_fetch`` + ``filtered_domain``) no existe en este árbol
    (medido: ``grep -rn "def search_fetch" addons/ src/`` → 0 definiciones).
    """
    return self._compute_suggested_quantity()


def get_total_routes(self):
    """≙ ``get_total_routes`` (``odoo19c: :248-253``).

    Un producto con proveedores gana además las rutas de compra. Se instala con
    un ``combine`` propio porque **acumula** sobre el resultado del ``super()``
    (``routes |= buy_routes``): con el relevo por defecto perdería las rutas
    propias y las de la categoría, que es lo que el ``super()`` aporta.
    """
    if not self.product_tmpl.seller_ids.exists():
        return None
    StockRoute = apps.get_model('stock', 'StockRoute')
    route_ids = (apps.get_model('stock', 'StockRule').objects
                 .filter(action=ACTION_BUY)
                 .values_list('route', flat=True))
    return StockRoute.objects.filter(pk__in=set(route_ids))


def _union_routes(new, previous):
    """``combine`` de ``get_total_routes`` — ≙ el ``|=`` de la fuente.

    Los dos lados son *querysets* del mismo modelo; se unen por clave primaria
    para no depender de que ``QuerySet.union`` conserve la posibilidad de
    filtrar después (no la conserva).
    """
    if new is None:
        return previous
    if previous is None:
        return new
    ids = set(new.values_list('pk', flat=True))
    ids |= set(previous.values_list('pk', flat=True))
    return new.model.objects.filter(pk__in=ids)


# --- product.supplierinfo --------------------------------------------------

def display_name(self):
    """≙ ``_compute_display_name`` (``odoo19c: :290-298``).

    ``Proveedor (min_qty unidad - precio)``. Con
    ``use_simplified_supplier_name`` en el contexto, la fuente cede al
    ``super()`` y muestra sólo el nombre del contacto; esa rama se conserva.

    D-2 del docstring: ``formatLang`` no existe aquí, así que el precio se
    formatea con f-string más el símbolo de la moneda.
    """
    if get_context().get('use_simplified_supplier_name'):
        return self.partner.display_name if self.partner_id else ''
    currency = getattr(self.currency, 'symbol', '') if self.currency_id else ''
    uom = self.product_uom.name if self.product_uom_id else ''
    return (f'{self.partner.display_name if self.partner_id else ""} '
            f'({self.min_qty} {uom} - {currency}{self.price})')


def show_set_supplier_button(self):
    """≙ ``_compute_show_set_supplier_button`` (``odoo19c: :281-288``).

    El botón «fijar proveedor» se oculta cuando este proveedor **ya es** el del
    punto de pedido que se está mirando. El id del punto de pedido llega por
    contexto, igual que en la fuente (``orderpoint_id`` o
    ``default_orderpoint_id``).
    """
    ctx = get_context()
    orderpoint_id = ctx.get('orderpoint_id', ctx.get('default_orderpoint_id'))
    if not orderpoint_id:
        return True
    Orderpoint = apps.get_model('stock', 'StockWarehouseOrderpoint')
    orderpoint = Orderpoint.objects.filter(pk=orderpoint_id).first()
    if orderpoint is None:
        return True
    return orderpoint.supplier_id != self.pk


def apply_purchase_stock_product_extensions():
    """Cuelga sobre ``product.template``/``product.product``/
    ``product.supplierinfo`` lo que ``purchase_stock`` les añade — ≙ ``_inherit``.

    ``ProductTemplate`` y ``ProductSupplierinfo`` se importan al top y reciben
    ``setattr`` directo (mismo idioma que ``addons/stock/models/product.py``);
    ``ProductProduct`` va por ``extend_model`` porque además del método
    necesita el ``chain_method`` con ``combine``, que sólo la escotilla
    ``luego=`` permite.
    """
    if not hasattr(ProductTemplate, '_onchange_buy_route'):
        ProductTemplate._onchange_buy_route = _onchange_buy_route
    if not hasattr(ProductSupplierinfo, 'display_name'):
        ProductSupplierinfo.display_name = property(display_name)
    if not hasattr(ProductSupplierinfo, 'show_set_supplier_button'):
        ProductSupplierinfo.show_set_supplier_button = property(
            show_set_supplier_button)

    extend_model(
        'product', 'ProductProduct',
        propiedades={
            'monthly_demand': monthly_demand,
            'suggested_qty': suggested_qty,
        },
        metodos={
            '_compute_monthly_demand': _compute_monthly_demand,
            '_compute_suggested_quantity': _compute_suggested_quantity,
            '_get_monthly_demand_range': _get_monthly_demand_range,
            '_get_monthly_demand_moves_location_domain':
                _get_monthly_demand_moves_location_domain,
        },
        luego=_install_get_total_routes,
    )


def _install_get_total_routes(model):
    """``get_total_routes`` necesita ``combine`` — escotilla ``luego=``."""
    chain_method(model, 'get_total_routes', get_total_routes,
                 combine=_union_routes)
