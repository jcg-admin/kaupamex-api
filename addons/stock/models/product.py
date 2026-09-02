"""``product.template`` / ``product.product`` — la superficie que ``stock`` cuelga.

Adaptación de Odoo ``stock/models/product.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Porte por bloques — dos clases cerradas de cuatro
==================================================

Medido sobre ``odoo19c: addons/stock/models/product.py`` (1393 líneas):
4 clases con **58 campos y 83 métodos**.

.. list-table:: Estado por clase
   :header-rows: 1

   * - Clase de la referencia
     - Campos
     - Métodos
     - Estado
   * - ``ProductCategory`` (:1278-1338)
     - 7
     - 4
     - **CERRADA** en este pase
   * - ``UomUom`` (:1341-1393)
     - 2
     - 2
     - **CERRADA** en este pase
   * - ``ProductProduct`` (:47-815)
     - 20
     - 43
     - parcial — el motor de cantidades, bloque siguiente
   * - ``ProductTemplate`` (:817-1276)
     - 29
     - 34
     - parcial — ídem

*Métrica:* campos y métodos declarados en el cuerpo de cada clase, por AST.
*Ciega a:* si un símbolo nuestro **hace** lo que hace el suyo — el conteo no
distingue un alias de Django de un porte real.

**Las dos clases cerradas se eligieron primero por dependencia, no por
tamaño.** ``ProductCategory.total_route_ids`` y ``ProductProduct.route_ids``
son lo que ``stock.warehouse.orderpoint._compute_rules`` consulta
(``odoo19c: stock/models/stock_orderpoint.py:196``), así que el orderpoint
—tarea **#257**— no se puede portar antes que ellas. El motor de cantidades
(``_compute_quantities_dict`` y su familia de dominios) es el bloque que sigue,
y va con el resto de la tarea **#330**.

Dos de los siete campos de ``ProductCategory`` **ya existían** como accesor
inverso de Django y no se redeclaran: ``route_ids`` lo genera
``StockRoute.categ_ids`` y ``putaway_rule_ids`` lo genera
``StockPutawayRule.category``. La referencia los escribe del lado de la
categoría porque su ORM no genera el inverso; declararlos aquí crearía dos
columnas para una sola relación.

Por qué ``tracking`` vive aquí y no en ``product_expiry``
----------------------------------------------------------

Porque es donde la referencia lo declara: ``odoo19c: stock/models/product.py:842``.
``product_expiry`` lo **lee** (``if tracking == 'none': use_expiration_date =
False``) pero no lo declara — colgarlo desde el satélite pondría el símbolo en
el addon equivocado, que es la clase de defecto que :ref:`h-api-350` registra
(el porte que entrega todos los símbolos con la forma y el sitio cambiados).

Divergencia declarada — los dos ``compute`` se invocan a mano
--------------------------------------------------------------

La referencia declara ``is_storable`` y ``tracking`` como campos
**almacenados con compute** (``compute='compute_is_storable'`` y
``compute='_compute_tracking'``, ambos ``store=True, readonly=False,
precompute=True``): su ORM los recalcula cuando cambia la dependencia y el
valor queda editable. Aquí son campos almacenados con default y sus dos
computes se portan como métodos que el consumidor invoca — el motor de
``@api.depends`` no existe todavía (tarea **#191**).

El texto anterior de esta sección decía que ``_compute_tracking`` estaba
bloqueado porque dependía de ``is_storable``/``type``, «dos campos de este
mismo archivo que aún no están portados». Ya lo están —``is_storable`` en este
pase, ``type`` desde ``product.template``— así que el compute entró con ellos,
que es la condición que ese texto fijaba.
"""
import operator as py_operator
from collections import defaultdict
from datetime import date, datetime, time, timedelta

import fields
import models
from django.apps import apps
from django.db.models import Count, Q, Sum
from django.utils import timezone

from exceptions import UserError
from orm.domains import FALSE_DOMAIN, OR
from orm.environments import get_current_companies
from orm.method_chain import chain_method
from tools.barcode import check_barcode_encoding
from tools.mail import html2plaintext, is_html_empty
from tools.translate import _

from addons.product.models import ProductCategory, ProductProduct, ProductTemplate
from addons.product.models.product_template import TYPE_CONSU, TYPE_SERVICE
from addons.uom.models.uom_uom import Uom

#: ≙ ``PY_OPERATORS`` (``odoo19c: stock/models/product.py:18-27``). El
#: buscador de un campo calculado compara en Python, no en SQL, así que la
#: fuente mapea el operador de dominio a su función. Verbatim.
PY_OPERATORS = {
    '<': py_operator.lt,
    '>': py_operator.gt,
    '<=': py_operator.le,
    '>=': py_operator.ge,
    '=': py_operator.eq,
    '!=': py_operator.ne,
    'in': lambda elem, container: elem in container,
    'not in': lambda elem, container: elem not in container,
}

#: ≙ ``tracking`` (``odoo19c: stock/models/product.py:842-848``). El
#: vocabulario es el de la referencia, verbatim y en el mismo orden.
TRACKING_CHOICES = [
    ('serial', 'Por número de serie único'),
    ('lot', 'Por lotes'),
    ('none', 'Por cantidad'),
]

#: ≙ ``packaging_reserve_method`` (``odoo19c: stock/models/product.py:1302-1306``).
#: Vocabulario verbatim y en el mismo orden que la fuente.
PACKAGING_RESERVE_METHOD_CHOICES = [
    ('full', 'Reservar sólo empaques completos'),
    ('partial', 'Reservar empaques parciales'),
]


def _add_if_absent(model, name, field):
    """Añade el campo sólo si el modelo no lo tiene ya — ver ``account_fleet``."""
    if not any(f.name == name for f in model._meta.get_fields()):
        model.add_to_class(name, field)


def tracking(self):
    """≙ ``product.product.tracking`` — delegado al template.

    Mismo idioma que ``categ``/``uom``/``type`` en
    ``api: addons/product/models/product_product.py``: la variante expone por
    property lo que el template declara como columna.
    """
    return self.product_tmpl.tracking


def lot_sequence(self):
    """≙ ``product.product.lot_sequence_id`` — delegado al template.

    Mismo idioma que ``tracking``/``is_storable``: la variante expone por
    property lo que el template declara como columna. Lo consume
    ``stock.lot._compute_name``.
    """
    return self.product_tmpl.lot_sequence


def is_storable(self):
    """≙ ``product.product.is_storable`` — delegado al template.

    Mismo idioma que ``tracking``: la variante expone por property lo que el
    template declara como columna.
    """
    return self.product_tmpl.is_storable


def compute_is_storable(self):
    """≙ ``compute_is_storable`` (``odoo19c: stock/models/product.py:898-899``).

    «``self.filtered(lambda t: t.type != 'consu' and t.is_storable).is_storable
    = False``» — sólo un **bien** (``consu``) puede llevar existencias; un
    servicio o un combo no, y si alguien lo marcó se desmarca.

    El nombre va **sin** guion bajo porque la referencia lo declara así
    (``compute='compute_is_storable'``, ``:826``): es de los pocos ``compute``
    que expone en público, y el porte conserva su visibilidad
    (``porte-completo-no-parcial.md``, H-API-581).
    """
    if self.type != TYPE_CONSU and self.is_storable:
        self.is_storable = False


def _compute_tracking(self):
    """≙ ``_compute_tracking`` (``odoo19c: stock/models/product.py:1080-1082``).

    «``self.filtered(lambda t: not t.is_storable and t.tracking != 'none')
    .tracking = 'none'``» — sin existencias que rastrear no hay trazabilidad
    que declarar.

    Estaba **bloqueado** hasta este pase: el docstring de arriba decía que
    depende de ``is_storable``/``type``, «dos campos de este mismo archivo que
    aún no están portados». Ya lo están, así que el compute entra con ellos —
    que es exactamente lo que ese texto anticipaba.
    """
    if not self.is_storable and self.tracking != 'none':
        self.tracking = 'none'


def _get_description(self, picking_type):
    """≙ ``_get_description`` (``odoo19c: stock/models/product.py:319-329``).

    Descripción del producto según el tipo de operación: en una **salida**
    siempre manda el nombre; en el resto se intenta la descripción larga y,
    si está vacía, se cae al nombre.

    El guion bajo se conserva porque la fuente lo declara así
    (``porte-completo-no-parcial.md``, H-API-581).
    """
    if getattr(picking_type, 'code', None) == 'outgoing':
        return self.display_name
    description = getattr(self.product_tmpl, 'description', None)
    return html2plaintext(description) if not is_html_empty(description) \
        else self.display_name


def _get_picking_description(self, picking_type):
    """≙ ``_get_picking_description`` (``odoo19c: stock/models/product.py:331-339``).

    La descripción **específica de la operación**: recepción, entrega o
    interna. Sin tipo de operación no hay descripción que elegir.
    """
    tmpl = self.product_tmpl
    return {
        'incoming': tmpl.description_pickingin,
        'outgoing': tmpl.description_pickingout,
        'internal': tmpl.description_picking,
    }.get(getattr(picking_type, 'code', None), '')


# === ``product.category`` — la superficie de rutas y de retiro ==============
#
# ≙ ``ProductCategory`` (``odoo19c: stock/models/product.py:1278-1338``): 7
# campos y 4 métodos. Dos de los siete —``route_ids`` y ``putaway_rule_ids``—
# **ya existen** como accesor inverso: los declaran ``StockRoute.categ_ids``
# (``related_name='route_ids'``) y ``StockPutawayRule.category``
# (``related_name='putaway_rule_ids'``). No se redeclaran; la referencia los
# escribe del lado de la categoría porque su ORM no genera el inverso.


def parent_route_ids(self):
    """≙ ``parent_route_ids`` (``odoo19c: :1295-1296``, compute ``:1310-1318``).

    Las rutas que la categoría **hereda** de sus ancestros, menos las que ella
    misma declara: subir por la cadena de padres acumulando ``route_ids`` y
    restar las propias.
    """
    StockRoute = apps.get_model('stock', 'StockRoute')
    inherited, current = set(), self.parent
    while current is not None:
        inherited.update(current.route_ids.values_list('pk', flat=True))
        current = current.parent
    own = set(self.route_ids.values_list('pk', flat=True))
    return StockRoute.objects.filter(pk__in=inherited - own)


def total_route_ids(self):
    """≙ ``total_route_ids`` (``odoo19c: :1297-1299``, compute ``:1325-1328``).

    «``category.route_ids | category.parent_route_ids``» — todo lo que aplica a
    la categoría, propio y heredado.
    """
    StockRoute = apps.get_model('stock', 'StockRoute')
    ids = set(self.route_ids.values_list('pk', flat=True))
    ids |= set(self.parent_route_ids.values_list('pk', flat=True))
    return StockRoute.objects.filter(pk__in=ids)


def _search_total_route_ids(cls, routes):
    """≙ ``_search_total_route_ids`` (``odoo19c: :1320-1323``).

    La referencia filtra en memoria porque ``total_route_ids`` no está
    almacenado; aquí igual — se recorre el árbol de categorías y se devuelve el
    queryset de las que casan. El guion bajo se conserva
    (``porte-completo-no-parcial.md``, H-API-581).
    """
    wanted = {r.pk for r in routes}
    matching = [
        c.pk for c in cls.objects.all()
        if wanted & set(c.total_route_ids.values_list('pk', flat=True))
    ]
    return cls.objects.filter(pk__in=matching)


def _search_filter_for_stock_putaway_rule(cls, active_model=None, active_id=None):
    """≙ ``_search_filter_for_stock_putaway_rule`` (``odoo19c: :1330-1338``).

    El pseudo-campo ``filter_for_stock_putaway_rule`` no se almacena: existe
    sólo para acotar el desplegable de categorías al abrir una regla de
    colocación **desde un producto**. Sin producto en contexto no acota nada.

    Divergencia declarada: allá el contexto llega por ``self.env.context``;
    aquí se pasa explícito, porque este árbol no tiene el contexto implícito
    del ORM de la fuente.
    """
    if active_model not in ('product.template', 'product.product') or not active_id:
        return cls.objects.all()
    model_name = 'ProductTemplate' if active_model == 'product.template' else 'ProductProduct'
    record = apps.get_model('product', model_name).objects.filter(pk=active_id).first()
    if record is None:
        return cls.objects.all()
    category = record.categ if model_name == 'ProductProduct' else record.categ
    return cls.objects.filter(pk=category.pk) if category else cls.objects.none()


# === ``uom.uom`` — el tipo de paquete y la guarda del factor =================
#
# ≙ ``UomUom`` (``odoo19c: stock/models/product.py:1341-1393``): 2 campos y 2
# métodos.


def uom_route_ids(self):
    """≙ ``route_ids`` (``odoo19c: :1345``, ``related='package_type_id.route_ids'``).

    Las rutas se propagan desde el tipo de paquete; sin tipo, no hay rutas.
    """
    StockRoute = apps.get_model('stock', 'StockRoute')
    if self.package_type_id is None:
        return StockRoute.objects.none()
    return self.package_type.route_ids.all()


def check_factor_not_in_use(self):
    """≙ la guarda de ``write`` (``odoo19c: :1347-1373``).

    El ratio de una unidad **no se cambia** si ya hay movimientos abiertos o
    existencias apoyados en él: reescribirlo reinterpretaría cantidades ya
    registradas. Los tres consumidores que la fuente consulta son los mismos
    aquí — movimiento, línea de movimiento y quant.

    Divergencia de forma declarada: la referencia lo hace dentro de ``write``
    porque su ORM escribe en lote y ahí ve el ``vals``. Aquí la comparación
    "cambió el factor" la hace el llamador, y esta guarda responde a la
    pregunta que sigue: *¿esta unidad está en uso?* La invoca ``Uom.save()``
    cuando detecta el cambio, que es donde el árbol pone sus reglas de negocio
    (mismo criterio que ``clean_business``).
    """
    StockMove = apps.get_model('stock', 'StockMove')
    StockMoveLine = apps.get_model('stock', 'StockMoveLine')
    StockQuant = apps.get_model('stock', 'StockQuant')
    message = _(
        'No se puede cambiar el ratio de esta unidad de medida: ya hay '
        'productos con ella movidos o reservados.'
    )
    open_moves = ~Q(state__in=('cancel', 'done'))
    if StockMove.objects.filter(open_moves, product_uom=self).exists():
        raise UserError(message)
    if StockMoveLine.objects.filter(open_moves, product_uom=self).exists():
        raise UserError(message)
    if StockQuant.objects.filter(product__product_tmpl__uom=self).exclude(
            quantity=0).exists():
        raise UserError(message)


def save_guarding_factor(self, *args, **kwargs):
    """Instala la guarda del factor en el camino de escritura de ``uom.uom``.

    ≙ el ``write`` que ``stock`` superpone a ``uom.uom``
    (``odoo19c: :1347-1373``): la referencia extiende el método porque su ORM
    encadena por ``_inherit``; aquí lo hace ``chain_method``, que es el
    ``super()`` que este idioma no tiene. Devolver ``None`` cede el relevo al
    ``save`` previo (el de ``addons/uom``).

    **Divergencia declarada — dos claves protegidas, no tres.** La fuente
    protege ``factor``, ``relative_factor`` y ``relative_uom_id``. Aquí
    ``factor`` **no es una clave de escritura**: ``Uom.save`` lo deriva de la
    cadena de factores relativos en cada guardado y lo repropaga a los hijos
    (``addons/uom/models/uom_uom.py:197-215``). Incluirlo dispararía la guarda
    en cada hijo repropagado —cantidades que nadie cambió— que es un falso
    positivo que la referencia no tiene: allá el ORM recalcula el compute sin
    pasar por ``write``.
    """
    if self.pk is None:
        return None
    # Los dos lados de la comparación tienen que estar en el MISMO eje.
    # ``values('relative_uom_id')`` devuelve la clave ajena en crudo; el
    # atributo homónimo, desde ADR-029, es el **registro**. El eje crudo del
    # símbolo ``relative_uom_id`` es su ``attname``, que Django construye
    # añadiendo otro ``_id``. Comparar el crudo contra el registro da siempre
    # distinto y dispara la guarda en cada repropagación (H-API-882).
    previous = type(self).objects.filter(pk=self.pk).values(
        'relative_factor', 'relative_uom_id').first()
    if previous and (previous['relative_factor'] != self.relative_factor
                     or previous['relative_uom_id'] != self.relative_uom_id_id):
        self.check_factor_not_in_use()
    return None


def _adjust_uom_quantities(self, qty, quant_uom):
    """≙ ``_adjust_uom_quantities`` (``odoo19c: :1375-1393``).

    Cuando la unidad del aprovisionamiento no es la del quant, o se propaga la
    unidad de origen (``stock.propagate_uom = '1'``) o se convierte a la del
    quant. En ambos casos el redondeo es ``HALF-UP``, verbatim de la fuente.

    Nombre nuestro del convertidor: ``compute_quantity``. La referencia lo
    declara ``_compute_quantity``; la despromoción es preexistente en el addon
    ``uom`` y entra en el barrido de la tarea **#337**, no se corrige aquí para
    no mezclar un rename de API con este porte.
    """
    SystemParameter = apps.get_model('base', 'SystemParameter')
    if SystemParameter.get_param('stock.propagate_uom') != '1':
        return (self.compute_quantity(qty, quant_uom, rounding_method='HALF-UP'),
                quant_uom)
    return (self.compute_quantity(qty, self, rounding_method='HALF-UP'), self)


# === el motor de cantidades (``odoo19c: :146-536``) =========================
#
# Es el bloque del que cuelgan los cinco campos de cantidad de la referencia
# —``qty_available``, ``virtual_available``, ``free_qty``, ``incoming_qty`` y
# ``outgoing_qty``— y sus cinco buscadores. Tres divergencias declaradas, todas
# de mecanismo:
#
# 1. **El contexto se vuelve parámetros.** La referencia lee once claves de
#    ``self.env.context`` (``location``, ``warehouse_id``, ``lot_id``,
#    ``owner_id``, ``package_id``, ``from_date``, ``to_date``, ``strict``,
#    ``skip_in_progress``, ``owners``, ``with_expiration``). Aquí
#    ``orm.environments`` sólo lleva el canal del dato (``get_current_companies``)
#    y el de elevación, no un diccionario libre, así que cada clave es un
#    argumento con nombre. Es el mismo idioma que ya usa ``StockQuant._gather``.
# 2. **``Domain`` → ``Q``.** La clase ``Domain`` de ``odoo/orm/domains.py`` no
#    está portada (tarea **#356**); ``orm.domains`` es su espejo sobre ``Q``,
#    que es el tipo que el ORM de destino consume.
# 3. **El CTE recursivo → ``parent_path``.** La referencia arma un
#    ``WITH RECURSIVE descendants`` y su propio comentario dice por qué: evitar
#    que el ORM inyecte «un montón de ids de ubicación» en la consulta. Aquí la
#    ruta materializada ya existe (``stock_location.py``, ``compute_parent_path``)
#    y un ``parent_path__startswith`` da el mismo conjunto sin subconsulta — es
#    el idioma que ``stock_location.py:412,444`` ya usa.


def _descendants_q(locations, prefix):
    """``Q`` que matchea las ubicaciones del conjunto y toda su descendencia.

    ``prefix`` es la ruta al campo de ubicación desde el modelo que se
    consulta (``'location'`` para el quant y para el origen del movimiento,
    ``'location_dest'`` para el destino).
    """
    paths = [loc.parent_path for loc in locations if loc.parent_path]
    if not paths:
        return FALSE_DOMAIN
    return OR([Q(**{f'{prefix}__parent_path__startswith': r}) for r in paths])


def _get_domain_locations_new(cls, location_ids, strict=False,
                              skip_in_progress=False):
    """≙ ``_get_domain_locations_new`` (``odoo19c: :394-462``).

    Devuelve la terna ``(q_quant_loc, q_move_in_loc, q_move_out_loc)``: el
    filtro sobre existencias, sobre movimientos que ENTRAN al conjunto y sobre
    los que SALEN de él.
    """
    StockLocation = apps.get_model('stock', 'StockLocation')
    location_ids = list(location_ids or ())
    if not location_ids:
        return (FALSE_DOMAIN,) * 3

    if strict:
        loc_domain = Q(location__in=location_ids)
        dest_loc_domain = Q(location_dest__in=location_ids)
        dest_loc_domain_out = ~Q(location_dest__in=location_ids)
        return (loc_domain, dest_loc_domain & ~loc_domain,
                loc_domain & dest_loc_domain_out)

    locations = list(StockLocation.objects.filter(pk__in=location_ids))
    loc_domain = _descendants_q(locations, 'location')
    dest_done = _descendants_q(locations, 'location_dest')

    # El destino final sólo tiene sentido en la parte de la cadena que aún no
    # está hecha, así que la referencia parte la condición por estado.
    dest_in_progress = (
        (Q(location_final__isnull=False) & _descendants_q(locations, 'location_final'))
        | (Q(location_final__isnull=True) & dest_done)
    )
    done = Q(state='done')
    dest_loc_domain = (done & dest_done) | (~done & dest_in_progress)
    dest_loc_domain_out = (done & ~dest_done) | (~done & ~dest_in_progress)

    if skip_in_progress:
        return (loc_domain, dest_done & ~loc_domain, loc_domain & ~dest_done)

    return (loc_domain, dest_loc_domain & ~loc_domain,
            loc_domain & dest_loc_domain_out)


def _get_domain_locations(cls, location=None, warehouse=None, strict=False,
                          skip_in_progress=False):
    """≙ ``_get_domain_locations`` (``odoo19c: :341-392``).

    Resuelve el conjunto de ubicaciones a partir de ubicación y/o almacén y
    delega en ``_get_domain_locations_new``. Cada argumento acepta un id, un
    nombre (búsqueda ``icontains``, ≙ el ``ilike`` sobre ``_rec_name``) o una
    lista de cualquiera de los dos.

    Sin ninguno de los dos, el conjunto son las ubicaciones vista de los
    almacenes de las empresas activadas — ≙ ``self.env.companies``.
    """
    StockLocation = apps.get_model('stock', 'StockLocation')
    StockWarehouse = apps.get_model('stock', 'StockWarehouse')

    def _search_ids(model_name, name_field, values):
        ids, names = set(), []
        for item in values:
            if isinstance(item, int):
                ids.add(item)
            else:
                names.append(Q(**{f'{name_field}__icontains': item}))
        if names:
            ids |= set(model_name.objects.filter(OR(names))
                       .values_list('pk', flat=True))
        return ids

    if location is not None and not isinstance(location, (list, tuple, set)):
        location = [location]
    if warehouse is not None and not isinstance(warehouse, (list, tuple, set)):
        warehouse = [warehouse]

    if warehouse:
        w_ids = _search_ids(StockWarehouse, 'name', warehouse)
        view_ids = set(StockWarehouse.objects.filter(pk__in=w_ids)
                        .exclude(view_location__isnull=True)
                        .values_list('view_location_id', flat=True))
        if location:
            l_ids = _search_ids(StockLocation, 'complete_name', location)
            parents = [p for p in StockLocation.objects
                      .filter(pk__in=view_ids)
                      .values_list('parent_path', flat=True) if p]
            location_ids = {
                loc.pk for loc in StockLocation.objects.filter(pk__in=l_ids)
                if loc.parent_path
                and any(loc.parent_path.startswith(p) for p in parents)
            }
        else:
            location_ids = view_ids
    elif location:
        location_ids = _search_ids(StockLocation, 'complete_name', location)
    else:
        companies = get_current_companies()
        warehouses = StockWarehouse.objects.exclude(view_location__isnull=True)
        if companies:
            warehouses = warehouses.filter(company_id__in=companies)
        location_ids = set(warehouses.values_list('view_location_id', flat=True))

    return cls._get_domain_locations_new(
        location_ids, strict=strict, skip_in_progress=skip_in_progress)


def _compute_quantities_dict(cls, products, lot=None, owner=None, package=None,
                             from_date=None, to_date=None, owners=None,
                             with_expiration=None, location=None,
                             warehouse=None, strict=False,
                             skip_in_progress=False):
    """≙ ``_compute_quantities_dict`` (``odoo19c: :164-268``).

    Devuelve ``{pk: {qty_available, free_qty, incoming_qty, outgoing_qty,
    virtual_available}}`` para los productos dados.

    **Divergencia declarada — ``_origin``.** La fuente distingue el registro
    persistido de su borrador de onchange (``product._origin.id``) y devuelve
    ceros para los que aún no existen en base. Aquí no hay borradores: un
    modelo de Django o tiene ``pk`` o no está en el queryset, así que la rama
    se colapsa a la comprobación de que el producto aparezca en algún agregado.
    """
    StockMove = apps.get_model('stock', 'StockMove')
    StockQuant = apps.get_model('stock', 'StockQuant')

    records = [p for p in products if p.pk is not None]
    ids = [p.pk for p in records]
    zeros = dict.fromkeys(
        ['qty_available', 'free_qty', 'incoming_qty', 'outgoing_qty',
         'virtual_available'], 0.0)
    if not ids:
        return {}

    q_quant_loc, q_move_in_loc, q_move_out_loc = cls._get_domain_locations(
        location=location, warehouse=warehouse, strict=strict,
        skip_in_progress=skip_in_progress)

    q_quant = Q(product_id__in=ids) & q_quant_loc
    q_move_in = Q(product_id__in=ids) & q_move_in_loc
    q_move_out = Q(product_id__in=ids) & q_move_out_loc

    # Sólo ``to_date`` mira al pasado: es el que corresponde a qty_available.
    cutoff = _to_cutoff_datetime(to_date)
    dates_in_the_past = bool(cutoff and cutoff < timezone.now())

    if lot is not None:
        q_quant &= Q(lot=lot)
        q_move_in &= Q(move_line_ids__lot=lot)
        q_move_out &= Q(move_line_ids__lot=lot)
    if owner is not None:
        q_quant &= Q(owner=owner)
        q_move_in &= Q(restrict_partner=owner)
        q_move_out &= Q(restrict_partner=owner)
    if owners is not None:
        if owners:
            q_quant &= Q(owner__in=owners)
            q_move_in &= Q(move_line_ids__owner__in=owners)
            q_move_out &= Q(move_line_ids__owner__in=owners)
        else:
            q_quant &= Q(owner__isnull=True)
            q_move_in &= Q(move_line_ids__owner__isnull=True)
            q_move_out &= Q(move_line_ids__owner__isnull=True)
    if package is not None:
        q_quant &= Q(package=package)

    q_move_in_done, q_move_out_done = q_move_in, q_move_out
    if from_date:
        q_move_in &= Q(date__gte=from_date)
        q_move_out &= Q(date__gte=from_date)
    if cutoff:
        q_move_in &= Q(date__lte=cutoff)
        q_move_out &= Q(date__lte=cutoff)

    pending = ('waiting', 'confirmed', 'assigned', 'partially_available')
    moves_in = _sum_by_product(
        StockMove.objects.filter(q_move_in, state__in=pending), 'product_qty')
    moves_out = _sum_by_product(
        StockMove.objects.filter(q_move_out, state__in=pending), 'product_qty')

    quants = {
        row['product']: (float(row['q'] or 0), float(row['r'] or 0))
        for row in StockQuant.objects.filter(q_quant).values('product')
        .annotate(q=Sum('quantity'), r=Sum('reserved_quantity'))
    }

    # Existencias ya caducadas y sin reservar: no cuentan como disponibles.
    expired = {}
    if with_expiration:
        expired = {
            row['product']: float(row['q'] or 0) - float(row['r'] or 0)
            for row in StockQuant.objects
            .filter(q_quant, lot__removal_date__lte=with_expiration)
            .values('product').annotate(q=Sum('quantity'),
                                        r=Sum('reserved_quantity'))
        }

    # Para mirar al pasado se deshacen los movimientos hechos DESPUÉS del
    # corte, convirtiendo cada uno desde su propia unidad de medida.
    moves_in_past, moves_out_past = defaultdict(float), defaultdict(float)
    if dates_in_the_past:
        for bucket, query in ((moves_in_past, q_move_in_done),
                              (moves_out_past, q_move_out_done)):
            for move in (StockMove.objects
                         .filter(query, state='done', date__gt=cutoff)
                         .select_related('product__product_tmpl__uom',
                                         'product_uom')):
                bucket[move.product_id] += _in_product_uom(move)

    res = {}
    for record in records:
        pk = record.pk
        if not any(pk in table for table in
                   (quants, moves_in, moves_out, moves_in_past, moves_out_past,
                    expired)):
            res[pk] = dict(zeros)
            continue
        on_hand, reserved = quants.get(pk, (0.0, 0.0))
        if dates_in_the_past:
            on_hand = on_hand - moves_in_past.get(pk, 0.0) + moves_out_past.get(pk, 0.0)
        expired_qty = expired.get(pk, 0.0)
        uom = record.uom
        incoming = _round_to(uom, moves_in.get(pk, 0.0))
        outgoing = _round_to(uom, moves_out.get(pk, 0.0))
        res[pk] = {
            'qty_available': _round_to(uom, on_hand),
            'free_qty': _round_to(uom, on_hand - reserved - expired_qty),
            'incoming_qty': incoming,
            'outgoing_qty': outgoing,
            'virtual_available': _round_to(
                uom, on_hand + incoming - outgoing - expired_qty),
        }
    return res


def _to_cutoff_datetime(to_date):
    """``to_date`` como instante: una fecha desnuda vale hasta su último tic.

    ≙ el bloque ``datetime.combine(to_date.date(), time.max)`` de la fuente
    (``odoo19c: :169-174``), que distingue una fecha de un instante para que
    «hasta el día D» incluya el día D entero.
    """
    if not to_date:
        return None
    if isinstance(to_date, str):
        to_date = (datetime.fromisoformat(to_date) if len(to_date) > 10
                   else datetime.combine(date.fromisoformat(to_date), time.max))
    elif isinstance(to_date, datetime):
        pass
    elif isinstance(to_date, date):
        to_date = datetime.combine(to_date, time.max)
    if timezone.is_naive(to_date):
        to_date = timezone.make_aware(to_date)
    return to_date


def _in_product_uom(move):
    """La cantidad del movimiento expresada en la unidad del producto.

    ≙ ``uom._compute_quantity(quantity, product.uom_id)`` (``odoo19c: :231``).
    Misma divergencia que ``_round_to``: la fuente convierte sin guarda porque
    allá ``product_uom`` y ``uom_id`` son obligatorios; aquí los dos son
    nulables, y sin unidad de origen o de destino no hay conversión que hacer.
    """
    qty = float(move.quantity or 0)
    origin, target = move.product_uom, move.product.uom
    if origin is None or target is None:
        return qty
    return origin.compute_quantity(qty, target)


def _round_to(uom, value):
    """Redondea a la unidad del producto; sin unidad, no hay a qué redondear.

    **Divergencia declarada.** La fuente escribe ``product.uom_id.round(...)``
    sin guarda porque allá ``uom_id`` es obligatorio y trae default
    (``odoo19c: product/models/product_template.py``). Aquí
    ``ProductTemplate.uom`` es nulable, así que un producto sin unidad haría
    reventar el motor con ``AttributeError`` — un fallo que la referencia no
    puede tener. Sin unidad se devuelve el valor crudo.
    """
    return uom.round(value) if uom is not None else float(value)


def _sum_by_product(queryset, field):
    """≙ ``_read_group(dominio, ['product_id'], ['<campo>:sum'])``."""
    return {row['product']: float(row['total'] or 0)
            for row in queryset.values('product').annotate(total=Sum(field))}


def _compute_quantities(cls, products, **kwargs):
    """≙ ``_compute_quantities`` (``odoo19c: :151-162``).

    Un servicio no lleva existencias, así que sale del cálculo y recibe ceros.
    """
    storable = [p for p in products if p.type != TYPE_SERVICE]
    res = cls._compute_quantities_dict(storable, **kwargs)
    zeros = dict.fromkeys(
        ['qty_available', 'free_qty', 'incoming_qty', 'outgoing_qty',
         'virtual_available'], 0.0)
    return {p.pk: res.get(p.pk, dict(zeros)) for p in products
            if p.pk is not None}


def _quantity_for(self, key, **kwargs):
    """El valor de un campo de cantidad para ESTE producto.

    Las cinco ``property`` de cantidad lo llaman sin contexto; el planificador
    de reabastecimiento lo llama **con** contexto (``location``, ``to_date``:
    ``stock_orderpoint._get_product_context``), así que además de ayudante de
    módulo se cuelga de ``ProductProduct`` como método ligado — hasta #277 no
    se colgaba y ``_run_scheduler_tasks`` moría con ``AttributeError`` en el
    primer orderpoint.
    """
    return type(self)._compute_quantities([self], **kwargs).get(
        self.pk, {}).get(key, 0.0)


def qty_available(self):
    """≙ ``qty_available`` (``odoo19c: :52-66``) — existencias a la mano."""
    return _quantity_for(self, 'qty_available')


def virtual_available(self):
    """≙ ``virtual_available`` (``:69-79``) — a la mano + entrante − saliente."""
    return _quantity_for(self, 'virtual_available')


def free_qty(self):
    """≙ ``free_qty`` (``:81-91``) — a la mano menos lo reservado."""
    return _quantity_for(self, 'free_qty')


def incoming_qty(self):
    """≙ ``incoming_qty`` (``:93-102``) — entradas planificadas."""
    return _quantity_for(self, 'incoming_qty')


def outgoing_qty(self):
    """≙ ``outgoing_qty`` (``:104-113``) — salidas planificadas."""
    return _quantity_for(self, 'outgoing_qty')


def _year_ago():
    """Un año atrás — ≙ ``fields.Datetime.now() - relativedelta(years=1)``."""
    now = timezone.now()
    try:
        return now.replace(year=now.year - 1)
    except ValueError:            # 29 de febrero en año no bisiesto
        return now.replace(year=now.year - 1, day=28)


def _count_done_lines_by_code(cls, products, code):
    """Líneas de movimiento cerradas del último año, por tipo de albarán.

    **Divergencia declarada.** La fuente filtra por ``picking_code``, que su
    ORM resuelve en SQL porque un ``related`` es una columna consultable.
    Aquí ``StockMoveLine.picking_code`` **sí está portado**
    (``addons/stock/models/stock_move_line.py:477-480``) pero como
    ``property`` de Python: se evalúa por instancia y el ORM no puede
    empujarlo al ``WHERE``. El filtro recorre la relación —
    ``picking__picking_type__code``— que es la misma travesía que el
    ``related`` declara, escrita donde la consulta la puede usar.
    """
    StockMoveLine = apps.get_model('stock', 'StockMoveLine')
    filas = (StockMoveLine.objects
             .filter(product__in=products, state='done',
                     picking__picking_type__code=code, date__gte=_year_ago())
             .values('product').annotate(total=Count('pk')))
    return {row['product']: row['total'] for row in filas}


def _compute_nbr_moves(cls, products):
    """≙ ``_compute_nbr_moves`` (``odoo19c: :292-309``).

    Devuelve ``{pk: (entradas, salidas)}`` — el par que la fuente reparte
    entre ``nbr_moves_in`` y ``nbr_moves_out``.
    """
    products = list(products)
    entradas = _count_done_lines_by_code(cls, products, 'incoming')
    salidas = _count_done_lines_by_code(cls, products, 'outgoing')
    return {p.pk: (entradas.get(p.pk, 0), salidas.get(p.pk, 0))
            for p in products}


def nbr_moves_in(self):
    """≙ ``nbr_moves_in`` — recepciones cerradas del último año."""
    return type(self)._compute_nbr_moves([self]).get(self.pk, (0, 0))[0]


def nbr_moves_out(self):
    """≙ ``nbr_moves_out`` — entregas cerradas del último año."""
    return type(self)._compute_nbr_moves([self]).get(self.pk, (0, 0))[1]


def show_on_hand_qty_status_button(self):
    """≙ ``_compute_show_qty_status_button`` (``odoo19c: :117-121``)."""
    template = self.product_tmpl
    return bool(template and getattr(template, 'is_storable', False))


def show_forecasted_qty_status_button(self):
    """≙ el segundo campo del mismo compute (``odoo19c: :117-121``)."""
    template = self.product_tmpl
    return bool(template and getattr(template, 'is_storable', False))


def show_qty_update_button(self):
    """≙ ``_compute_show_qty_update_button`` (``odoo19c: :123-126``)."""
    template = self.product_tmpl
    return bool(template and _should_open_product_quants(template))


def valid_ean(self):
    """≙ ``_compute_valid_ean`` (``odoo19c: :128-133``)."""
    if not self.barcode:
        return False
    return check_barcode_encoding(self.barcode.rjust(14, '0'), 'gtin14')


def _should_open_product_quants(template):
    """≙ ``_should_open_product_quants`` de ``product.template``.

    La fuente abre el ajuste de existencias sólo para un producto que las
    lleva; para el resto el botón no tiene destino.
    """
    return bool(getattr(template, 'is_storable', False))


def get_components(self):
    """≙ ``get_components`` (``odoo19c: :311-313``)."""
    return [self.pk]


def _get_quantity_in_progress(self, location_ids=(), warehouse_ids=()):
    """≙ ``_get_quantity_in_progress`` (``odoo19c: :707-708``).

    La fuente devuelve dos mapas vacíos: es el punto de extensión que
    ``purchase_stock`` y ``mrp`` rellenan con sus pedidos en curso. Se porta
    con su cuerpo real —vacío— porque su valor es el contrato, no el cálculo.
    """
    return defaultdict(float), defaultdict(float)


def _get_only_qty_available(cls, products):
    """≙ ``_get_only_qty_available`` (``odoo19c: :735-745``).

    Sólo la existencia física, sin tocar los movimientos: la fuente lo separa
    justamente para no pagar el ``_read_group`` sobre ``stock.move``.
    """
    StockQuant = apps.get_model('stock', 'StockQuant')
    products = list(products)
    q_quant_loc = cls._get_domain_locations()[0]
    filas = (StockQuant.objects
             .filter(q_quant_loc, product__in=products)
             .values('product').annotate(total=Sum('quantity')))
    actuales = defaultdict(float)
    actuales.update({row['product']: float(row['total'] or 0) for row in filas})
    return actuales


def _filter_to_unlink(cls, products):
    """≙ ``_filter_to_unlink`` (``odoo19c: :747-751``).

    Un producto con lotes registrados no se borra: la fuente lo excluye del
    conjunto antes de delegar en su superclase.
    """
    StockLot = apps.get_model('stock', 'StockLot')
    products = list(products)
    with_lot = set(StockLot.objects.filter(product__in=products)
                   .values_list('product_id', flat=True))
    return [p for p in products if p.pk not in with_lot]


def _count_returned_sn_products(cls, sn_lot, or_domains=()):
    """≙ ``_count_returned_sn_products`` (``odoo19c: :753-758``)."""
    StockMoveLine = apps.get_model('stock', 'StockMoveLine')
    domain = cls._count_returned_sn_products_domain(sn_lot, or_domains)
    if domain is None:
        return 0
    return StockMoveLine.objects.filter(domain).count()


def _count_returned_sn_products_domain(cls, sn_lot, or_domains=()):
    """≙ ``_count_returned_sn_products_domain`` (``odoo19c: :760-768``).

    Sin las ramas que aportan los addons de venta y compra, la fuente
    devuelve ``None`` y el contador sale 0 — el punto de extensión sigue
    siendo el mismo aquí.
    """
    or_domains = list(or_domains or ())
    if not or_domains:
        return None
    return (Q(lot=sn_lot, quantity=1, state='done')) & OR(or_domains)


def filter_has_routes(cls, products):
    """≙ ``filter_has_routes`` (``odoo19c: :796-805``).

    Un producto tiene ruta si la declara él o si la hereda de su categoría —
    y lo segundo exige el recorrido de padres que ``total_route_ids`` ya
    resuelve.
    """
    salida = []
    for product in products:
        if product.route_ids.exists():
            salida.append(product)
            continue
        categoria = getattr(product, 'categ', None)
        if categoria is not None and categoria.total_route_ids.exists():
            salida.append(product)
    return salida


def _get_rules_from_location(cls, product, location, route_ids=(),
                             seen_rules=None):
    """≙ ``_get_rules_from_location`` (``odoo19c: :710-725``).

    Sube por la cadena de reglas hasta la que abastece contra existencias.
    La guarda del bucle infinito es de la fuente, no un añadido.
    """
    StockRule = apps.get_model('stock', 'StockRule')
    seen_rules = list(seen_rules or ())
    warehouse = getattr(location, 'warehouse', None)
    rule = StockRule._get_rule(product, location, {
        'route_ids': route_ids,
        'warehouse_id': warehouse,
    })
    if rule is not None and rule in seen_rules:
        raise UserError(
            _('Configuración de regla inválida: la regla %s provoca un bucle '
              'infinito.') % rule)
    if rule is None:
        return seen_rules
    seen_rules = seen_rules + [rule]
    if (rule.procure_method == 'make_to_stock'
            or rule.action not in ('pull_push', 'pull')):
        return seen_rules
    return cls._get_rules_from_location(
        product, rule.location_src, seen_rules=seen_rules)


def _get_dates_info(cls, product, date, location, route_ids=()):
    """≙ ``_get_dates_info`` (``odoo19c: :727-733``)."""
    StockRule = apps.get_model('stock', 'StockRule')
    rules = cls._get_rules_from_location(product, location, route_ids=route_ids)
    delays, _unused = StockRule._get_lead_days(rules, product)
    return {
        'date_planned': date,
        'date_order': date - timedelta(days=delays.get('purchase_delay', 0)),
    }


def _uom_change_is_blocked(product, to_uom):
    """Las dos consultas con que la fuente veta el cambio de unidad.

    ≙ los dos ``_read_group`` de ``_update_uom`` (``odoo19c: :770-794``):
    si el producto ya tiene movimientos o líneas en OTRA unidad, el cambio
    reinterpretaría cantidades ya registradas.
    """
    StockMove = apps.get_model('stock', 'StockMove')
    StockMoveLine = apps.get_model('stock', 'StockMoveLine')
    actual = product.uom
    usadas = set(StockMove.objects.filter(product=product)
                 .exclude(product_uom__isnull=True)
                 .values_list('product_uom_id', flat=True))
    usadas |= set(StockMoveLine.objects.filter(product=product)
                  .exclude(product_uom__isnull=True)
                  .values_list('product_uom_id', flat=True))
    ajenas = {u for u in usadas if actual is None or u != actual.pk}
    return sorted(ajenas)


def _update_uom(self, to_uom):
    """≙ ``_update_uom`` (``odoo19c: :770-794``)."""
    StockMove = apps.get_model('stock', 'StockMove')
    StockMoveLine = apps.get_model('stock', 'StockMoveLine')
    ajenas = _uom_change_is_blocked(self, to_uom)
    if ajenas:
        raise UserError(
            _('Ya se usaron otras unidades de medida para este producto, así '
              'que el cambio de unidad no puede hacerse. Si quiere cambiarla, '
              'archive el producto y cree uno nuevo.'))
    StockMove.objects.filter(product=self).update(product_uom=to_uom)
    StockMoveLine.objects.filter(product=self).update(product_uom=to_uom)


def _trigger_uom_warning(self):
    """≙ ``_trigger_uom_warning`` (``odoo19c: :807-814``)."""
    StockMove = apps.get_model('stock', 'StockMove')
    return StockMove.objects.filter(product=self).exists()


def _onchange_tracking(self):
    """≙ ``_onchange_tracking`` (``odoo19c: :551-556``).

    Devuelve el aviso, no lo levanta: la fuente lo entrega como ``warning``
    para que la capa de presentación decida. Aquí lo consume el serializer.
    """
    if self.tracking != 'none' and self.qty_available > 0:
        return _('Tiene existencias sin número de lote o de serie. Puede '
                 'asignárselos con un ajuste de inventario.')
    return None


def _search_product_quantity(cls, operator, value, field, **kwargs):
    """≙ ``_search_product_quantity`` (``odoo19c: :492-496``).

    La fuente rechaza aquí el mismo par de casos, y por la misma razón: sin un
    número que comparar, o con un operador que no es de orden, la búsqueda no
    tiene significado sobre una cantidad calculada.
    """
    if field not in ('qty_available', 'virtual_available', 'incoming_qty',
                     'outgoing_qty', 'free_qty'):
        raise UserError(_('Búsqueda no soportada sobre el campo %s.') % field)
    if operator not in PY_OPERATORS:
        raise UserError(_('Operador no soportado: %s.') % operator)
    if not isinstance(value, (float, int)):
        raise UserError(_('El valor a comparar debe ser un número.'))
    return cls._search_qty_available_new(operator, value, field, **kwargs)


def _search_qty_available_new(cls, operator, value, field, lot=None, owner=None,
                              package=None, location=None, warehouse=None,
                              strict=False):
    """≙ ``_search_qty_available_new`` (``odoo19c: :498-536``).

    Devuelve el ``Q`` que acota a los productos cuyo campo de cantidad cumple
    la comparación. La fuente calcula el campo para el universo de productos
    con existencias o movimientos y filtra en Python — no hay columna que
    comparar en SQL, y aquí tampoco: el campo es una ``property``.
    """
    StockMove = apps.get_model('stock', 'StockMove')
    StockQuant = apps.get_model('stock', 'StockQuant')
    cls = cls

    q_quant_loc, q_move_in_loc, q_move_out_loc = cls._get_domain_locations(
        location=location, warehouse=warehouse, strict=strict)
    candidates = set(
        StockQuant.objects.filter(q_quant_loc)
        .values_list('product_id', flat=True))
    candidates |= set(
        StockMove.objects.filter(q_move_in_loc | q_move_out_loc)
        .values_list('product_id', flat=True))
    if not candidates:
        return FALSE_DOMAIN

    records = list(cls.objects.filter(pk__in=candidates))
    values = cls._compute_quantities(
        records, lot=lot, owner=owner, package=package, location=location,
        warehouse=warehouse, strict=strict)
    compare = PY_OPERATORS[operator]
    matches = [pk for pk, row in values.items()
                if compare(row.get(field, 0.0), value)]
    return Q(pk__in=matches) if matches else FALSE_DOMAIN


def _search_qty_available(cls, operator, value, **kwargs):
    """≙ ``_search_qty_available`` (``odoo19c: :464-475``).

    El atajo de la fuente: preguntar por «cantidad distinta de cero» no
    necesita el motor — basta con quién tiene un quant. Se conserva porque es
    la búsqueda más frecuente y la que más costaría calcular entera.
    """
    if operator in ('=', '!=') and value == 0 and not kwargs:
        StockQuant = apps.get_model('stock', 'StockQuant')
        with_stock = set(StockQuant.objects.exclude(quantity=0)
                             .values_list('product_id', flat=True))
        if operator == '=':
            return ~Q(pk__in=with_stock)
        return Q(pk__in=with_stock)
    return cls._search_product_quantity(operator, value, 'qty_available',
                                        **kwargs)


def _search_virtual_available(cls, operator, value, **kwargs):
    """≙ ``_search_virtual_available`` (``odoo19c: :477-479``)."""
    return cls._search_product_quantity(operator, value, 'virtual_available',
                                        **kwargs)


def _search_incoming_qty(cls, operator, value, **kwargs):
    """≙ ``_search_incoming_qty`` (``odoo19c: :481-483``)."""
    return cls._search_product_quantity(operator, value, 'incoming_qty',
                                        **kwargs)


def _search_outgoing_qty(cls, operator, value, **kwargs):
    """≙ ``_search_outgoing_qty`` (``odoo19c: :485-487``)."""
    return cls._search_product_quantity(operator, value, 'outgoing_qty',
                                        **kwargs)


def _search_free_qty(cls, operator, value, **kwargs):
    """≙ ``_search_free_qty`` (``odoo19c: :489-490``)."""
    return cls._search_product_quantity(operator, value, 'free_qty', **kwargs)


def product_route_ids(self):
    """≙ ``product.product.route_ids`` — delegado al template.

    La fuente lo obtiene por ``_inherits``: el M2M vive en ``product.template``
    (``StockRoute.product_ids``, ``related_name='route_ids'``) y la variante lo
    lee a través de la delegación. Mismo idioma que ``categ``/``uom``/``type``
    en ``api: addons/product/models/product_product.py``.
    """
    return self.product_tmpl.route_ids


def get_total_routes(self):
    """≙ ``get_total_routes`` (``odoo19c: :315-317``).

    «``self.route_ids | self.categ_id.total_route_ids``» — las rutas propias
    (las de su plantilla, por delegación) más las que hereda de su categoría.
    """
    StockRoute = apps.get_model('stock', 'StockRoute')
    ids = set(self.route_ids.values_list('pk', flat=True))
    category = self.categ
    if category is not None:
        ids |= set(category.total_route_ids.values_list('pk', flat=True))
    return StockRoute.objects.filter(pk__in=ids)


def apply_stock_product_extensions():
    """Cuelga ``is_storable`` y ``tracking`` sobre ``product.template``.

    La llama ``StockConfig.ready()``; los tests la invocan explícitamente
    (mismo criterio que ``account_fleet``).
    """
    _add_if_absent(ProductTemplate, 'is_storable', fields.Boolean(
        default=False,
        help_text='Lleva existencias en almacén (Odoo is_storable, '
                  '«Track Inventory»).',
    ))
    _add_if_absent(ProductTemplate, 'tracking', fields.Selection(
        choices=TRACKING_CHOICES, max_length=16, default='none',
        help_text='Trazabilidad del producto almacenable (Odoo tracking).',
    ))
    if not hasattr(ProductTemplate, 'compute_is_storable'):
        ProductTemplate.compute_is_storable = compute_is_storable
    if not hasattr(ProductTemplate, '_compute_tracking'):
        ProductTemplate._compute_tracking = _compute_tracking
    if not hasattr(ProductProduct, 'tracking'):
        ProductProduct.tracking = property(tracking)
    if not hasattr(ProductProduct, 'is_storable'):
        ProductProduct.is_storable = property(is_storable)

    # ≙ ``description_picking`` / ``description_pickingout`` /
    # ``description_pickingin`` (``odoo19c: stock/models/product.py:856-858``).
    # Los declara ``product.template``; los consume ``_get_picking_description``.
    for name, label in (
        ('description_picking', 'Descripción en el albarán'),
        ('description_pickingout', 'Descripción en órdenes de entrega'),
        ('description_pickingin', 'Descripción en recepciones'),
    ):
        _add_if_absent(ProductTemplate, name, fields.Text(
            null=True, blank=True, verbose_name=label,
            help_text=f'Odoo {name}. La referencia lo declara traducible; '
                      'el almacenamiento jsonb de translate=True es la tarea #333.',
        ))
    if not hasattr(ProductProduct, '_get_description'):
        ProductProduct._get_description = _get_description
    if not hasattr(ProductProduct, '_get_picking_description'):
        ProductProduct._get_picking_description = _get_picking_description

    # --- ``product.category`` (``odoo19c: :1278-1338``) --------------------
    _add_if_absent(ProductCategory, 'removal_strategy', fields.Many2one(
        'stock.ProductRemoval', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='categ_ids',
        verbose_name='Estrategia de retiro forzada',
        help_text='Estrategia que se aplica sin importar la ubicación de '
                  'origen (Odoo removal_strategy_id). La consume '
                  'StockQuant._get_removal_strategy, que ya la leía.',
    ))
    _add_if_absent(ProductCategory, 'packaging_reserve_method', fields.Selection(
        max_length=16, choices=PACKAGING_RESERVE_METHOD_CHOICES,
        default='partial', verbose_name='Reserva de empaques',
        help_text='full: no reserva empaques parciales; partial: sí '
                  '(Odoo packaging_reserve_method).',
    ))
    if not hasattr(ProductCategory, 'parent_route_ids'):
        ProductCategory.parent_route_ids = property(parent_route_ids)
    if not hasattr(ProductCategory, 'total_route_ids'):
        ProductCategory.total_route_ids = property(total_route_ids)
    if not hasattr(ProductCategory, '_search_total_route_ids'):
        ProductCategory._search_total_route_ids = classmethod(
            _search_total_route_ids)
    if not hasattr(ProductCategory, '_search_filter_for_stock_putaway_rule'):
        ProductCategory._search_filter_for_stock_putaway_rule = classmethod(
            _search_filter_for_stock_putaway_rule)

    # --- ``uom.uom`` (``odoo19c: :1341-1393``) ----------------------------
    _add_if_absent(Uom, 'package_type', fields.Many2one(
        'stock.StockPackageType', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='uom_ids',
        verbose_name='Tipo de paquete',
        help_text='Tipo de paquete del que esta unidad propaga sus rutas '
                  '(Odoo package_type_id).',
    ))
    if not hasattr(Uom, 'route_ids'):
        Uom.route_ids = property(uom_route_ids)
    if not hasattr(Uom, 'check_factor_not_in_use'):
        Uom.check_factor_not_in_use = check_factor_not_in_use
    if not hasattr(Uom, '_adjust_uom_quantities'):
        Uom._adjust_uom_quantities = _adjust_uom_quantities
    chain_method(Uom, 'save', save_guarding_factor)

    # --- el motor de cantidades (``odoo19c: :146-536``) --------------------
    for name, function in (
        ('_get_domain_locations', _get_domain_locations),
        ('_get_domain_locations_new', _get_domain_locations_new),
        ('_compute_quantities_dict', _compute_quantities_dict),
        ('_compute_quantities', _compute_quantities),
        ('_search_product_quantity', _search_product_quantity),
        ('_search_qty_available_new', _search_qty_available_new),
        ('_search_qty_available', _search_qty_available),
        ('_search_virtual_available', _search_virtual_available),
        ('_search_incoming_qty', _search_incoming_qty),
        ('_search_outgoing_qty', _search_outgoing_qty),
        ('_search_free_qty', _search_free_qty),
    ):
        if not hasattr(ProductProduct, name):
            setattr(ProductProduct, name, classmethod(function))
    for name, function in (
        ('qty_available', qty_available),
        ('virtual_available', virtual_available),
        ('free_qty', free_qty),
        ('incoming_qty', incoming_qty),
        ('outgoing_qty', outgoing_qty),
    ):
        if not hasattr(ProductProduct, name):
            setattr(ProductProduct, name, property(function))
    if not hasattr(ProductProduct, 'route_ids'):
        ProductProduct.route_ids = property(product_route_ids)
    if not hasattr(ProductProduct, 'get_total_routes'):
        ProductProduct.get_total_routes = get_total_routes

    # ≙ ``lot_sequence_id`` (``odoo19c: stock/models/product.py:849-851``), que
    # la referencia declara sobre ``product.template``. Es el campo TÉCNICO del
    # que ``stock.lot._compute_name`` saca el nombre cuando el usuario no lo
    # escribe: sin él, ese compute no tiene de dónde numerar.
    #
    # El sufijo ``_id`` se retira como en todo el árbol; queda ``lot_sequence``,
    # que no colisiona con nada de ``product.template``.
    _add_if_absent(ProductTemplate, 'lot_sequence', fields.Many2one(
        'base.IrSequence', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='lot_product_tmpls', verbose_name='Secuencia de lote/serie',
        help_text='Secuencia que genera los números de lote/serie de este '
                  'producto (Odoo lot_sequence_id). Campo técnico.',
    ))
    if not hasattr(ProductProduct, 'lot_sequence'):
        ProductProduct.lot_sequence = property(lot_sequence)

    # --- el resto de ``product.product`` (``odoo19c: :292-814``) -----------
    _add_if_absent(ProductProduct, 'lot_properties_definition', fields.Json(
        null=True, blank=True, default=None,
        verbose_name='Definición de propiedades de lote',
        help_text='Esquema de las propiedades que llevan los lotes de este '
                  'producto (Odoo lot_properties_definition).',
    ))
    for name, function in (
        ('_compute_nbr_moves', _compute_nbr_moves),
        ('_get_only_qty_available', _get_only_qty_available),
        ('_filter_to_unlink', _filter_to_unlink),
        ('_count_returned_sn_products', _count_returned_sn_products),
        ('_count_returned_sn_products_domain', _count_returned_sn_products_domain),
        ('filter_has_routes', filter_has_routes),
        ('_get_rules_from_location', _get_rules_from_location),
        ('_get_dates_info', _get_dates_info),
    ):
        if not hasattr(ProductProduct, name):
            setattr(ProductProduct, name, classmethod(function))
    for name, function in (
        ('nbr_moves_in', nbr_moves_in),
        ('nbr_moves_out', nbr_moves_out),
        ('show_on_hand_qty_status_button', show_on_hand_qty_status_button),
        ('show_forecasted_qty_status_button', show_forecasted_qty_status_button),
        ('show_qty_update_button', show_qty_update_button),
        ('valid_ean', valid_ean),
    ):
        if not hasattr(ProductProduct, name):
            setattr(ProductProduct, name, property(function))
    for name, function in (
        ('_quantity_for', _quantity_for),
        ('get_components', get_components),
        ('_get_quantity_in_progress', _get_quantity_in_progress),
        ('_update_uom', _update_uom),
        ('_trigger_uom_warning', _trigger_uom_warning),
        ('_onchange_tracking', _onchange_tracking),
    ):
        if not hasattr(ProductProduct, name):
            setattr(ProductProduct, name, function)
