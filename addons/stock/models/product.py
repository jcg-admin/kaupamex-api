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
import fields
import models
from django.apps import apps
from django.db.models import Q

from exceptions import UserError
from orm.method_chain import chain_method
from tools.mail import html2plaintext, is_html_empty
from tools.translate import _

from addons.product.models import ProductCategory, ProductProduct, ProductTemplate
from addons.product.models.product_template import TYPE_CONSU
from addons.uom.models.uom_uom import Uom

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
    descripcion = getattr(self.product_tmpl, 'description', None)
    return html2plaintext(descripcion) if not is_html_empty(descripcion) \
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
    heredadas, actual = set(), self.parent
    while actual is not None:
        heredadas.update(actual.route_ids.values_list('pk', flat=True))
        actual = actual.parent
    propias = set(self.route_ids.values_list('pk', flat=True))
    return StockRoute.objects.filter(pk__in=heredadas - propias)


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
    buscadas = {r.pk for r in routes}
    casan = [
        c.pk for c in cls.objects.all()
        if buscadas & set(c.total_route_ids.values_list('pk', flat=True))
    ]
    return cls.objects.filter(pk__in=casan)


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
    modelo = 'ProductTemplate' if active_model == 'product.template' else 'ProductProduct'
    registro = apps.get_model('product', modelo).objects.filter(pk=active_id).first()
    if registro is None:
        return cls.objects.all()
    categoria = registro.categ if modelo == 'ProductProduct' else registro.categ
    return cls.objects.filter(pk=categoria.pk) if categoria else cls.objects.none()


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
    mensaje = _(
        'No se puede cambiar el ratio de esta unidad de medida: ya hay '
        'productos con ella movidos o reservados.'
    )
    abiertos = ~Q(state__in=('cancel', 'done'))
    if StockMove.objects.filter(abiertos, product_uom=self).exists():
        raise UserError(mensaje)
    if StockMoveLine.objects.filter(abiertos, product_uom=self).exists():
        raise UserError(mensaje)
    if StockQuant.objects.filter(product__product_tmpl__uom=self).exclude(
            quantity=0).exists():
        raise UserError(mensaje)


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
    anterior = type(self).objects.filter(pk=self.pk).values(
        'relative_factor', 'relative_uom_id').first()
    if anterior and (anterior['relative_factor'] != self.relative_factor
                     or anterior['relative_uom_id'] != self.relative_uom_id):
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
    for nombre, etiqueta in (
        ('description_picking', 'Descripción en el albarán'),
        ('description_pickingout', 'Descripción en órdenes de entrega'),
        ('description_pickingin', 'Descripción en recepciones'),
    ):
        _add_if_absent(ProductTemplate, nombre, fields.Text(
            null=True, blank=True, verbose_name=etiqueta,
            help_text=f'Odoo {nombre}. La referencia lo declara traducible; '
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
