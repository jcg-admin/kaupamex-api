"""Modelo ``SaleOrderLine`` — addon ``sale``.

Adaptación fiel de Odoo ``sale.order.line`` (``sale/models/sale_order_line.py``):
``product_id``/``product_uom_qty``/``price_unit``/``discount`` +
``price_subtotal``/``price_tax``/``price_total`` computados y **redondeados por
línea** (``_compute_amount``, sale_order_line.py:852). Precios IVA-incluido (MX):
el total de línea es ``price_unit*qty*(1-discount/100)`` y el IVA se extrae con la
tasa vigente, cuantizando por línea (equivale a ``_round_base_lines_tax_details``).
"""
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
import fields
import models

from addons.analytic.models.analytic_mixin import AnalyticMixin
from addons.base.models import TimeStampedModel
from addons.base_setup.settings_access import get_setting
from addons.stock.services import InventoryService

from .sale_order import SaleOrder


class SaleOrderLine(AnalyticMixin, TimeStampedModel):
    """``sale.order.line`` — una línea de la orden/carrito."""

    # -- atributos de clase del modelo -------------------------------------
    # ≙ ``odoo19c: sale/models/sale_order_line.py:13-27``. Los SEIS que la
    # fuente declara, más los dos objetos de tabla
    # (``atributos-de-clase-de-modelo.md``: se portan TODOS los que la fuente
    # declare, verbatim, y no sustituyen a su forma Django).

    #: ≙ ``_name = 'sale.order.line'`` (``:13``). Lo consume
    #: ``orm.registry.MODELS_BY_ODOO_NAME``, que es lo que permite a
    #: ``extend_model('sale.order.line', …)`` resolver por nombre.
    _name = 'sale.order.line'

    #: ≙ ``_inherit = ['analytic.mixin']`` (``:14``). El mixin existe en este
    #: árbol (``addons/analytic/models/analytic_mixin.py``) y se declara además
    #: como **base** de la clase, que es como este stack expresa la herencia.
    #: Con él la línea gana ``analytic_distribution`` y la sanitización de
    #: porcentajes de su ``save()`` — el docstring de aquel archivo lo anticipa
    #: por su nombre: *"un futuro consumidor (``sale.order.line``,
    #: ``account.move.line``) lo herede sin reabrir este addon"*.
    _inherit = ['analytic.mixin']

    #: ≙ ``_description = "Sales Order Line"`` (``:15``). No sustituye a
    #: ``Meta.verbose_name``, que va en español.
    _description = 'Sales Order Line'

    #: ≙ ``_rec_names_search = ['name', 'order_id.name']`` (``:16``). Aquí es
    #: atributo y no propiedad —la fuente tampoco la hace propiedad en este
    #: modelo, a diferencia de ``sale.order``— y el segundo término se escribe
    #: con la travesía de Django (``order__name``) porque el símbolo de la FK
    #: sigue en forma A: su paso a forma C es la tarea #986.
    _rec_names_search = ['name', 'order__name']

    #: ≙ ``_order = 'order_id, sequence, id'`` (``:17``), y ``Meta.ordering`` lo
    #: deriva término a término. El primer término se escribe ``order`` por lo
    #: mismo que la línea de arriba.
    _order = 'order_id, sequence, id'

    #: ≙ ``_check_company_auto = True`` (``:18``). NO es decorativo: lo lee
    #: ``CheckCompanyMixin.save`` (``orm/models.py``), que ``TimeStampedModel``
    #: ya hereda, y dispara ``_check_company()`` sobre los campos marcados
    #: ``check_company=True`` — aquí ``product`` y ``tax_ids``, como allá.
    _check_company_auto = True

    # Los dos objetos de tabla de la fuente (``:20-27``) NO se declaran en este
    # bloque, y la razón es medida, no de alcance: ninguna fila los podría
    # satisfacer hoy. ``product_uom_id`` nace NULL en toda fila existente, y
    # ``product_uom_qty`` —``PositiveIntegerField`` con ``MinValueValidator(1)``
    # aquí, ``Float`` allá— no admite el 0 que la segunda restricción exige de
    # una línea de sección. Un CHECK que nadie puede violar es el sub-patrón D
    # de ``metrica-decide-la-conclusion.md``: pasa sin discriminar. Van con las
    # dos correcciones de forma que habilitan, en la tarea **#987**.

    # -- vocabularios de la fuente ------------------------------------------
    # Las tres enumeraciones que ``fields.Selection`` de la fuente declara en
    # línea. Aquí van como constantes de clase, igual que ``SaleOrder.STATES``:
    # así el consumidor las nombra en vez de teclear la cadena.

    #: ≙ el ``selection`` de ``display_type`` (``odoo19c: :64-68``).
    DISPLAY_LINE_SECTION    = 'line_section'
    DISPLAY_LINE_SUBSECTION = 'line_subsection'
    DISPLAY_LINE_NOTE       = 'line_note'
    DISPLAY_TYPES = (
        (DISPLAY_LINE_SECTION,    'Sección'),
        (DISPLAY_LINE_SUBSECTION, 'Subsección'),
        (DISPLAY_LINE_NOTE,       'Nota'),
    )

    #: ≙ el ``selection`` de ``qty_delivered_method`` (``odoo19c: :219-221``).
    #: La fuente enumera DOS —``manual`` y ``analytic``— y su ``help`` describe
    #: cuatro: los otros dos (``timesheet``, ``stock_move``) los añaden
    #: ``sale_timesheet`` y ``sale_stock`` por extensión, no este archivo.
    QTY_DELIVERED_MANUAL   = 'manual'
    QTY_DELIVERED_ANALYTIC = 'analytic'
    QTY_DELIVERED_METHODS = (
        (QTY_DELIVERED_MANUAL,   'Manual'),
        (QTY_DELIVERED_ANALYTIC, 'Analítico, desde gastos'),
    )

    #: ≙ el ``selection`` de ``invoice_status`` (``odoo19c: :263-268``). El
    #: tercer valor lleva un ESPACIO, no un guion bajo: es ``'to invoice'`` en
    #: la fuente y se porta verbatim — es el valor que viaja a la columna.
    INVOICE_UPSELLING = 'upselling'
    INVOICE_INVOICED  = 'invoiced'
    INVOICE_TO_INVOICE = 'to invoice'
    INVOICE_NOTHING   = 'no'
    INVOICE_STATUSES = (
        (INVOICE_UPSELLING,  'Oportunidad de venta adicional'),
        (INVOICE_INVOICED,   'Facturada por completo'),
        (INVOICE_TO_INVOICE, 'Por facturar'),
        (INVOICE_NOTHING,    'Nada que facturar'),
    )

    order           = fields.Many2one(
        'sale.SaleOrder', on_delete=models.CASCADE, related_name='order_line',
        help_text='Odoo order_id.',
    )
    product         = fields.Many2one(
        'product.ProductProduct', on_delete=models.PROTECT,
        related_name='sale_order_lines', help_text='Odoo product_id.',
    )
    name            = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Descripción de la línea (Odoo name).',
    )
    product_uom_qty = models.PositiveIntegerField(
        default=1, validators=[MinValueValidator(1)],
        help_text='Cantidad (Odoo product_uom_qty).',
    )
    price_unit      = fields.Monetary(
        max_digits=12, decimal_places=2, help_text='Odoo price_unit (IVA incl.).',
    )
    discount        = fields.Monetary(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        help_text='Descuento % de la línea (Odoo discount).',
    )
    # ------------------------------------------------------------------
    # E1-bis — marcadores de línea NO-producto (H-API-24 / H-API-30).
    #
    # Los importes que no son de producto (envío, descuento de cupón) hoy son
    # escalares que nunca llegan a ``order_line``, así que ``amount_total``
    # los excluye por construcción. La forma fiel los materializa como líneas
    # y los marca para poder distinguirlas:
    #
    # - ``is_delivery`` ≙ Odoo ``delivery/models/sale_order_line.py:9``.
    # - ``is_reward``   ≙ la línea de recompensa de ``sale_loyalty`` (precio
    #   negativo).
    #
    # Ambos marcadores nacen juntos por decisión del ejecutor (2026-07-28):
    # envío y descuento comparten mecanismo en el monolito modular, y comparten
    # la misma causa raíz. Son marcadores, NO un tipo de línea: la línea sigue
    # siendo una ``sale.order.line`` normal y entra a los totales como
    # cualquier otra.
    # ------------------------------------------------------------------
    is_delivery     = fields.Boolean(
        default=False, db_index=True,
        help_text='La línea representa el costo de envío (Odoo is_delivery).',
    )
    is_reward       = fields.Boolean(
        default=False, db_index=True,
        help_text='La línea representa un descuento/recompensa (precio negativo).',
    )
    sequence        = models.IntegerField(
        default=10, db_index=True,
        help_text='Orden de la línea dentro de la orden (Odoo sequence).',
    )

    # === Campos de la referencia que faltaban =============================
    # ≙ ``odoo19c: sale/models/sale_order_line.py:34-333``. La fuente declara
    # **67** campos; medidos por AST y clasificados por si llevan columna:
    # 7 ya estaban (``order_id``/``sequence``/``product_id``/``name``/
    # ``product_uom_qty``/``price_unit``/``discount``), **33** llevan columna y
    # faltaban, y 27 no la llevan (``One2many`` inverso, ``store=False``
    # explícito, o ``compute``/``related`` sin ``store=True``).
    #
    # De esos 33 entran aquí **30**. Los tres restantes —``price_subtotal``,
    # ``price_tax`` y ``price_total``— hoy existen como MÉTODO en este archivo
    # y su paso a campo almacenado arrastra sus llamadas: medido, 30 sitios en
    # 14 archivos. Es el bloque siguiente, no una omisión.
    #
    # Las FK nuevas van en **forma C** de ADR-029: símbolo verbatim de la
    # fuente —con su sufijo ``_id``— más ``db_column`` fijando la columna al
    # mismo nombre. Sin el ``db_column`` Django escribiría ``…_id_id``.

    # -- copia desnormalizada de la orden ----------------------------------
    # La fuente las declara ``related='order_id.…'`` con ``store=True`` y
    # ``precompute=True``: son columnas propias de la línea, pobladas desde la
    # orden al crearla. Aquí son FK reales por la misma razón — que la línea
    # se pueda consultar y agrupar sin recorrer la orden en cada fila.
    company_id = fields.Many2one(
        'base.ResCompany', on_delete=models.PROTECT,
        db_column='company_id', null=True, blank=True, db_index=True,
        related_name='sale_order_lines', verbose_name='Empresa',
        help_text='Odoo company_id (related order_id.company_id, store, '
                  'index, precompute). La empresa que vende.',
    )
    currency_id = fields.Many2one(
        'base.ResCurrency', on_delete=models.PROTECT,
        db_column='currency_id', null=True, blank=True,
        related_name='+', verbose_name='Divisa',
        help_text='Odoo currency_id (related order_id.currency_id, store, '
                  'precompute). La divisa en que se expresan los importes.',
    )
    order_partner_id = fields.Many2one(
        'base.ResPartner', on_delete=models.PROTECT,
        db_column='order_partner_id', null=True, blank=True, db_index=True,
        related_name='+', verbose_name='Cliente',
        help_text='Odoo order_partner_id ("Customer", related '
                  'order_id.partner_id, store, index, precompute).',
    )
    salesman_id = fields.Many2one(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        db_column='salesman_id', null=True, blank=True,
        related_name='+', verbose_name='Comercial',
        help_text='Odoo salesman_id ("Salesperson", related order_id.user_id, '
                  'store, precompute).',
    )
    state = fields.Selection(
        max_length=10, choices=SaleOrder.STATES, null=True, blank=True,
        db_index=True, verbose_name='Estado de la orden',
        help_text='Odoo state ("Order Status", related order_id.state, store, '
                  'precompute, copy=False). El vocabulario es el de la orden.',
    )

    # -- lógica de línea propia de la fuente -------------------------------
    display_type = fields.Selection(
        max_length=16, choices=DISPLAY_TYPES, null=True, blank=True,
        verbose_name='Tipo de despliegue',
        help_text='Odoo display_type. Si tiene valor, la línea NO es una venta '
                  'sino una sección, subsección o nota del documento.',
    )
    is_downpayment = fields.Boolean(
        default=False, verbose_name='Es anticipo',
        help_text='Odoo is_downpayment ("Is a down payment"). Los anticipos se '
                  'crean al facturar desde el pedido; no se copian al '
                  'duplicarlo.',
    )
    is_expense = fields.Boolean(
        default=False, verbose_name='Es gasto',
        help_text='Odoo is_expense ("Is expense"). Verdadero si la línea viene '
                  'de un gasto o de una factura de proveedor.',
    )

    # -- configuración del producto ----------------------------------------
    product_no_variant_attribute_value_ids = fields.Many2many(
        'product.ProductTemplateAttributeValue', blank=True,
        db_table='sale_order_line_product_no_variant_rel',
        related_name='sale_order_lines_no_variant',
        verbose_name='Valores extra',
        help_text='Odoo product_no_variant_attribute_value_ids ("Extra '
                  'Values"): los valores de atributo cuyo create_variant es '
                  'no_variant — no generan variante pero sí precio extra.',
    )
    product_uom_id = fields.Many2one(
        'uom.Uom', on_delete=models.PROTECT,
        db_column='product_uom_id', null=True, blank=True,
        related_name='sale_order_lines', verbose_name='Unidad',
        help_text='Odoo product_uom_id ("Unit", compute+store con '
                  'readonly=False). La unidad en que se vende esta línea.',
    )
    linked_line_id = fields.Many2one(
        'sale.SaleOrderLine', on_delete=models.CASCADE,
        db_column='linked_line_id', null=True, blank=True, db_index=True,
        related_name='linked_line_ids', verbose_name='Línea enlazada',
        help_text='Odoo linked_line_id ("Linked Order Line"). La línea de la '
                  'que ésta depende — una opción de un combo, por ejemplo. Su '
                  'inverso ES el One2many linked_line_ids de la fuente.',
    )
    virtual_id = fields.Char(
        max_length=64, blank=True, default='', verbose_name='Id virtual',
        help_text='Odoo virtual_id. Identifica la línea ANTES de que la base '
                  'le dé un id — mientras el documento se edita en el cliente.',
    )
    linked_virtual_id = fields.Char(
        max_length=64, blank=True, default='', verbose_name='Id virtual enlazado',
        help_text='Odoo linked_virtual_id. El enlace a otra línea por su '
                  'virtual_id, para cuando ninguna de las dos tiene id todavía.',
    )
    combo_item_id = fields.Many2one(
        'product.ProductComboItem', on_delete=models.PROTECT,
        db_column='combo_item_id', null=True, blank=True,
        related_name='sale_order_lines', verbose_name='Elemento del combo',
        help_text='Odoo combo_item_id. El elemento del combo que esta línea '
                  'materializa.',
    )

    # -- impuestos y precio -------------------------------------------------
    tax_ids = fields.Many2many(
        'account.AccountTax', blank=True,
        db_table='sale_order_line_tax_rel',
        related_name='sale_order_lines', verbose_name='Impuestos',
        help_text='Odoo tax_ids ("Taxes", compute+store con readonly=False, '
                  'check_company). Los impuestos que gravan esta línea.',
    )
    technical_price_unit = fields.Monetary(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Precio unitario técnico',
        help_text='Odoo technical_price_unit. El precio antes de que el '
                  'usuario lo altere a mano; sirve para detectar el cambio.',
    )
    price_reduce_taxexcl = fields.Monetary(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Precio con descuento sin impuestos',
        help_text='Odoo price_reduce_taxexcl ("Price Reduce Tax excl", '
                  'compute+store, precompute).',
    )
    price_reduce_taxinc = fields.Monetary(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Precio con descuento con impuestos',
        help_text='Odoo price_reduce_taxinc ("Price Reduce Tax incl", '
                  'compute+store, precompute).',
    )
    customer_lead = fields.Monetary(
        max_digits=16, decimal_places=4, default=Decimal('0.0000'),
        verbose_name='Plazo de entrega',
        help_text='Odoo customer_lead ("Lead Time", compute+store con '
                  'readonly=False, required, precompute). Días entre la '
                  'confirmación del pedido y el envío al cliente.',
    )

    # -- entrega y facturación ---------------------------------------------
    qty_delivered_method = fields.Selection(
        max_length=16, choices=QTY_DELIVERED_METHODS, null=True, blank=True,
        verbose_name='Método de cantidad entregada',
        help_text='Odoo qty_delivered_method ("Method to update delivered '
                  'qty", compute+store, precompute). Cómo se obtiene la '
                  'cantidad entregada: a mano o desde gastos analíticos.',
    )
    qty_delivered = fields.Monetary(
        max_digits=16, decimal_places=4, default=Decimal('0.0000'),
        verbose_name='Cantidad entregada',
        help_text='Odoo qty_delivered ("Delivery Quantity", compute+store con '
                  'readonly=False, copy=False).',
    )
    qty_invoiced = fields.Monetary(
        max_digits=16, decimal_places=4, default=Decimal('0.0000'),
        verbose_name='Cantidad facturada',
        help_text='Odoo qty_invoiced ("Invoiced Quantity", compute+store).',
    )
    qty_to_invoice = fields.Monetary(
        max_digits=16, decimal_places=4, default=Decimal('0.0000'),
        verbose_name='Cantidad por facturar',
        help_text='Odoo qty_to_invoice ("Quantity To Invoice", compute+store).',
    )
    invoice_lines = fields.Many2many(
        'account.AccountMoveLine', blank=True,
        db_table='sale_order_line_invoice_rel',
        related_name='sale_line_ids', verbose_name='Líneas de factura',
        help_text='Odoo invoice_lines ("Invoice Lines", relation '
                  'sale_order_line_invoice_rel, copy=False). Las líneas de '
                  'factura que facturan esta línea de pedido.',
    )
    invoice_status = fields.Selection(
        max_length=16, choices=INVOICE_STATUSES, null=True, blank=True,
        verbose_name='Estado de facturación',
        help_text='Odoo invoice_status ("Invoice Status", compute+store).',
    )
    untaxed_amount_invoiced = fields.Monetary(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Importe facturado sin impuestos',
        help_text='Odoo untaxed_amount_invoiced ("Untaxed Invoiced Amount", '
                  'compute+store).',
    )
    untaxed_amount_to_invoice = fields.Monetary(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Importe por facturar sin impuestos',
        help_text='Odoo untaxed_amount_to_invoice ("Untaxed Amount To '
                  'Invoice", compute+store).',
    )

    # -- datos técnicos y secciones ----------------------------------------
    extra_tax_data = fields.Json(
        null=True, blank=True, default=dict, verbose_name='Datos extra de impuesto',
        help_text='Odoo extra_tax_data. Campo técnico con los datos que el '
                  'motor de cálculo de impuestos necesita conservar.',
    )
    collapse_prices = fields.Boolean(
        default=False, verbose_name='Colapsar precios',
        help_text='Odoo collapse_prices ("Collapse Prices", copy=True). Si los '
                  'precios de las líneas de esta sección se ocultan en el '
                  'reporte y en el portal.',
    )
    collapse_composition = fields.Boolean(
        default=False, verbose_name='Colapsar composición',
        help_text='Odoo collapse_composition ("Collapse Composition", '
                  'copy=True). Si las líneas de esta sección se ocultan en el '
                  'reporte y en el portal.',
    )

    class Meta:
        db_table     = 'sale_order_line'
        verbose_name = 'Línea de orden de venta'
        # ≙ ``odoo19c: sale/models/sale_order_line.py:17`` — ``_order =
        # 'order_id, sequence, id'``. No es cosmética: sin ORDER BY el motor
        # devuelve las filas en el orden que le conviene, y PostgreSQL no
        # promete el de la PK. MariaDB lo daba de hecho, así que dos caminos
        # que leían las mismas líneas coincidían por suerte del
        # almacenamiento — hasta que dejaron de coincidir (H-API-312).
        #
        # ``sequence`` viene con el orden: es lo que hace que el usuario pueda
        # reordenar líneas sin depender del id de inserción, y es la razón por
        # la que la referencia no ordena sólo por ``id``.
        ordering     = ['order', 'sequence', 'id']

    def __str__(self):
        return f'{self.name or self.product_id} ×{self.product_uom_qty}'

    # ------------------------------------------------------------------
    # Disparo del recálculo de la orden (H-API-30) — equivalente Django del
    # ``@api.depends('order_line.price_subtotal', ...)`` que Odoo declara en
    # ``SaleOrder.amount_untaxed/tax/total`` (sale/models/sale_order.py:232-234).
    # En la referencia el motor de dependencias de Odoo dispara
    # ``_compute_amounts`` sólo cuando cambia un campo del que depende; Django
    # no tiene ese motor, así que aquí se dispara en **cada** ``save()``/
    # ``delete()`` de la línea, sin distinguir qué campo cambió. El costo es
    # un recompute redundante ocasional (p. ej. renombrar la línea sin tocar
    # precio/cantidad) — no hay recursión: ``_compute_amounts`` guarda la
    # ORDEN (``SaleOrder.save``, sin overridear), nunca vuelve a tocar la línea.
    #
    # **Alcance del disparo — sólo mutaciones a nivel instancia.** Un
    # ``QuerySet.filter(...).delete()`` (o ``.update()``) no pasa por aquí:
    # Django hace DELETE/UPDATE en bloque sin invocar el ``delete()``/``save()``
    # de cada fila. Los llamadores que borran líneas en bloque
    # (``delivery.set_delivery_line``, ``sale_loyalty.set_reward_line``,
    # ``sale_product_matrix.SaleOrderMatrix.apply``, ``sale.services.
    # clear_draft_items``) llaman a ``order._compute_amounts()`` explícitamente
    # tras el borrado en bloque — ver el docstring de cada uno.
    # ------------------------------------------------------------------
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.order._compute_amounts()

    def delete(self, *args, **kwargs):
        order = self.order
        result = super().delete(*args, **kwargs)
        order._compute_amounts()
        return result

    # Desglose por línea — de sale.order.line._compute_amount (sale_order_line.py:852).
    def price_total(self) -> Decimal:
        gross = (self.price_unit * self.product_uom_qty
                 * (Decimal('1') - self.discount / Decimal('100')))
        return gross.quantize(Decimal('0.01'))

    def price_tax(self) -> Decimal:
        rate = get_setting('iva_rate')
        return (self.price_total() * rate / (1 + rate)).quantize(Decimal('0.01'))

    def price_subtotal(self) -> Decimal:
        return self.price_total() - self.price_tax()

    # ------------------------------------------------------------------
    # V2 unificación orders→sale: la línea del draft (carrito) necesita el
    # estado VIVO del catálogo. En Odoo ``website_sale`` recalcula el precio
    # del carrito contra la pricelist vigente; aquí el vigente es
    # ``ProductProduct.lst_price`` — el de la ficha más el extra de los
    # valores de atributo de la variante (odoo19c:
    # ``product/models/product_product.py``).
    #
    # El eje ``variant`` desapareció: ``product`` **es** la variante
    # (H-API-213). La existencia se deriva de ``stock.quant`` vía
    # ``InventoryService``, no de una columna del producto (odoo19c:
    # ``stock/models/stock_quant.py:119-122``).
    # ------------------------------------------------------------------
    def current_price(self) -> Decimal:
        """Precio vigente del catálogo (Odoo ``lst_price``)."""
        return self.product.lst_price

    def is_available(self) -> bool:
        """Paridad con la guardia histórica de carrito (H-CICLO42-01)."""
        if not self.product.active:
            return False
        return self.available_stock() >= self.product_uom_qty

    def available_stock(self) -> Decimal:
        return InventoryService.available_quantity(self.product)
