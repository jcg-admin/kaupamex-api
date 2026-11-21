"""``product.template`` — el producto tal como se cataloga y se vende.

Adaptación de ``addons/product/models/product_template.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 1598 líneas). Es el archivo que
sostiene el addon: la plantilla es **el producto** para el catálogo, el precio
y la descripción; sus **variantes** (``product.product``) son las
combinaciones concretas de atributos que se almacenan y se venden.

Plantilla y variante — la distinción que hay que tener clara al leer
====================================================================

Una camiseta es **una** plantilla; "camiseta roja talla M" es **una variante**.
La plantilla lleva lo común —nombre, categoría, precio de lista, unidad—; la
variante lleva lo que distingue una combinación de otra y es lo que apunta un
movimiento de stock o una línea de pedido.

La referencia lo refuerza con dos campos que este archivo porta:
``product_variant_count`` y ``product_variant_id`` — el segundo es la primera
variante; quien exige una sola lo comprueba con el primero, como la fuente.

Divergencia declarada: el precio es ``Monetary``, no ``Float``
==============================================================

La referencia declara ``list_price`` y ``standard_price`` como ``Float``.
Aquí son ``fields.Monetary`` —``DecimalField`` en este vocabulario— y la
divergencia es **decidida**, no heredada por descuido:

1. Es la convención medida de este árbol: ``grep -rn "fields\\.Monetary"
   src/addons/`` → **56** usos, incluidos ``sale_order_line.price_unit`` y
   ``purchase_order_line.price_unit``. Un precio de producto en ``Float`` al
   lado de una línea de venta en ``Decimal`` produciría redondeos distintos
   para el mismo importe según por dónde se lea.
2. Un ``float`` binario no representa ``0.10`` exactamente. Para dinero eso no
   es un detalle de presentación: se acumula.

Se declara aquí porque H-API-168 fijó el criterio — divergir de la referencia
es legítimo cuando se decide y se dice; lo que no vale es introducirlo en
silencio.

Qué NO se porta, con su medición
================================

- **``_inherit = ['mail.thread', 'mail.activity.mixin']``** — el producto es
  un hilo de mensajería en la referencia. ``image.mixin`` **sí** se hereda
  (``ImageMixin`` existe en ``base``), junto a ``TimeStampedModel``: heredar
  sólo el mixin de imagen **borraría las marcas de tiempo**, que es el defecto
  que H-API-147 registró al portar ``res_partner``.
- **Los campos que apuntan a modelos aún sin portar**: **ninguno**. Los
  reversos llegaron **casi todos por ``related_name``**, igual que
  ``report_paperformat.report_ids`` (H-API-164): ``product_tag_ids`` desde
  ``product_tag.py``, ``pricelist_rule_ids`` desde
  ``product_pricelist_item.py``, ``product_variant_ids`` desde
  ``product_product.py`` y ``seller_ids`` desde ``product_supplierinfo.py``.
  ``combo_ids`` sí se declara aquí, como en la fuente.

  La predicción falló **dos veces**, y en direcciones distintas:

  1. No cubría que uno llegara **con un gemelo** — ver ``variant_seller_ids``
     abajo.
  2. Daba por hecho que ``product_document_ids`` llegaría también por
     ``related_name``. **No podía**: la fuente lo declara ``One2many`` sobre
     ``inverse_name='res_id'`` con ``domain=[('res_model', '=', self._name)]``
     (``odoo19c: product_template.py:164-168``), es decir por **referencia
     genérica**, no por FK. Se porta como propiedad de consulta abajo. Ver
     H-API-193.

``variant_seller_ids`` — dos One2many sobre el mismo inverso
============================================================

La referencia declara ``seller_ids`` y ``variant_seller_ids`` en líneas
consecutivas (``product_template.py:126-127``) y **las dos** apuntan al mismo
campo inverso, ``product_tmpl_id``. Sólo difieren en el
``depends_context=('company',)`` de la primera; el nombre de la segunda
promete un filtro por variante que su declaración no hace.

En Django una FK da exactamente **un** ``related_name``, así que el gemelo no
puede existir como campo. Se conserva como **propiedad alias** sobre el mismo
conjunto: el nombre sigue disponible para quien lo llame, y el docstring dice
que no filtra nada — que es la verdad de la fuente, no una simplificación.
- **``currency_id`` / ``cost_currency_id``**: campos calculados sin columna,
  como en la fuente. La moneda de ``res.company`` se llama aquí ``currency``.
- **La generación de variantes** (``_create_variant_ids``, ~200 líneas): crea
  el producto cartesiano de las líneas de atributo y sincroniza altas y bajas.
  Entra con ``product_product.py``, que es donde vive el modelo que crea.
"""

import itertools

import api
import fields
import models
from django.apps import apps
from django.core.exceptions import ValidationError
from orm.domains import Domain

from addons.base.models.image_mixin import ImageMixin
from addons.base.models.ir_config_parameter import SystemParameter
from addons.base.models.ir_model import IrModelData
from addons.base.models.res_company import ResCompany
from addons.base.models.timestamped_mixin import TimeStampedModel
from addons.product.models.product_category import ProductCategory
from addons.product.models.product_document import ProductDocument
from addons.uom.models.uom_uom import Uom
from exceptions import UserError
from tools.translate import _

#: Claves de contexto que afectan al precio calculado — verbatim de la fuente.
#: Se conservan aunque el cálculo de precio viva en ``product.pricelist``:
#: nombran **de qué depende** un precio, que es lo que se olvida al portar.
PRICE_CONTEXT_KEYS = ['pricelist', 'quantity', 'uom', 'date']

TYPE_CONSU = 'consu'
TYPE_SERVICE = 'service'
TYPE_COMBO = 'combo'
#: ``type`` — los tres tipos de la referencia, verbatim. ``consu`` es material
#: tangible; ``service`` no lo es; ``combo`` agrupa otros productos.
TYPE_CHOICES = [
    (TYPE_CONSU, 'Bienes'),
    (TYPE_SERVICE, 'Servicio'),
    (TYPE_COMBO, 'Combo'),
]

#: ``service_tracking`` — la referencia declara sólo ``no`` en ``product``;
#: los addons de venta y proyecto añaden sus valores. Se copia esa base.
SERVICE_TRACKING_CHOICES = [('no', 'Nada')]


def _get_default_uom_id():
    """≙ ``ProductTemplate._get_default_uom_id`` (``odoo19c:
    addons/product/models/product_template.py:34-36``): la unidad,
    ``uom.product_uom_unit``.

    DIVERGENCIA DE MECANISMO declarada, la de ``_get_default_color``: Django
    serializa un ``default`` callable por su ruta de import, así que queda a
    nivel de módulo y sin ``self``. Registrada en
    ``scripts/divergencias_declaradas.txt``.
    """
    return IrModelData._xmlid_to_res_id('uom.product_uom_unit')


class ProductTemplate(models.BaseModel, ImageMixin, TimeStampedModel):
    """``product.template`` — el producto del catálogo."""

    #: Los atributos de clase de la fuente
    #: (``odoo19c: product_template.py:19-24, 180``). Sin ``_name`` el modelo
    #: no entra en ``MODELS_BY_NAME``, y ``ensure_inherits`` no encuentra el
    #: comodelo del ``_inherits`` de ``product.product``.
    _name = 'product.template'
    #: ≙ ``_inherit`` (``:20``), verbatim. ``image.mixin`` es la base
    #: ``ImageMixin`` de arriba; el hilo de mensajes no está cableado.
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _description = 'Product'
    #: ≙ ``_order`` (``:22``); ``Meta.ordering`` lo expresa en Django.
    _order = 'is_favorite desc, name'
    #: ≙ ``_check_company_auto = True`` (``:23``): ``CheckCompanyMixin`` (por
    #: ``TimeStampedModel``) lo lee al guardar.
    _check_company_auto = True
    #: ≙ ``_check_company_domain`` (``:24``); ``classmethod`` porque aquí se
    #: invoca sobre la clase.
    _check_company_domain = classmethod(models.check_company_domain_parent_of)

    name = fields.Char(max_length=255, db_index=True, verbose_name='Nombre')
    sequence = fields.Integer(
        default=1,
        verbose_name='Secuencia',
        help_text='Orden al listar productos.',
    )
    description = fields.Html(
        blank=True, default='', verbose_name='Descripción'
    )
    description_purchase = fields.Text(
        blank=True, default='', verbose_name='Descripción de compra'
    )
    description_sale = fields.Text(
        blank=True,
        default='',
        verbose_name='Descripción de venta',
        help_text='Se copia a cada pedido, albarán y factura del cliente.',
    )
    type = fields.Selection(
        max_length=16,
        choices=TYPE_CHOICES,
        default=TYPE_CONSU,
        verbose_name='Tipo de producto',
    )
    #: ≙ ``combo_ids`` (``odoo19c: addons/product/models/
    #: product_template.py:66-70``): las elecciones del menú.
    combo_ids = fields.Many2many(
        'product.ProductCombo',
        relation='product_combo_product_template_rel',
        column1='product_template_id',
        column2='product_combo_id',
        string="Combo Choices",
        check_company=True,
        blank=True,
        related_name='+',
    )
    service_tracking = fields.Selection(
        max_length=16,
        choices=SERVICE_TRACKING_CHOICES,
        default='no',
        verbose_name='Crear al confirmar el pedido',
    )
    #: ≙ ``categ_id`` (``odoo19c: addons/product/models/
    #: product_template.py:81``) en forma C.
    categ_id = fields.Many2one(
        ProductCategory,
        db_column='categ_id',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_index=True,
        related_name='product_tmpl_ids',
        verbose_name='Categoría de producto',
        help_text='Odoo categ_id. FK real: product.category ya está portado.',
    )
    #: ≙ ``company_id`` (``odoo19c: addons/product/models/
    #: product_template.py:124``) en forma C.
    company_id = fields.Many2one(
        ResCompany,
        db_column='company_id',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_index=True,
        related_name='product_tmpl_ids',
        verbose_name='Compañía',
        help_text='Vacío = producto compartido por todas las compañías.',
    )
    # ≙ ``uom_id`` (``odoo19c: :118-121``): ``default`` la unidad y
    # ``required`` (``blank=False``). La columna sigue admitiendo nulo hasta
    # que las filas sin unidad se rellenen
    # (``product-uom-uom-extension-0397``).
    uom_id = fields.Many2one(
        Uom,
        db_column='uom_id',
        on_delete=models.PROTECT,
        default=_get_default_uom_id,
        null=True,
        blank=False,
        related_name='product_tmpl_ids',
        verbose_name='Unidad de medida',
        help_text='Odoo uom_id. FK real: uom.uom ya está portado.',
    )
    uom_ids = fields.Many2many(
        Uom,
        blank=True,
        related_name='packaging_product_tmpl_ids',
        db_table='product_template_uom_rel',
        verbose_name='Empaquetados',
        help_text=(
            'Odoo uom_ids ("Packagings"): unidades adicionales con las '
            'que este producto se puede vender. La fuente excluye la '
            'unidad base por dominio; aquí lo hace quien las consume.'
        ),
    )
    #: ≙ ``currency_id`` (``odoo19c: addons/product/models/
    #: product_template.py:88-89``): calculado, sin columna.
    currency_id = fields.Many2one(
        'base.ResCurrency', 'Currency', compute='_compute_currency_id',
        store=False, related_name='+',
    )
    #: ≙ ``cost_currency_id`` (``:90-91``): calculado, sin columna.
    cost_currency_id = fields.Many2one(
        'base.ResCurrency', 'Cost Currency',
        compute='_compute_cost_currency_id', store=False, related_name='+',
    )
    #: ≙ ``product_variant_count`` (``odoo19c: addons/product/models/
    #: product_template.py:148-149``): calculado, sin columna.
    product_variant_count = fields.Integer(
        '# Product Variants', compute='_compute_product_variant_count',
        store=False,
    )
    list_price = fields.Monetary(
        max_digits=16,
        decimal_places=2,
        default=1,
        verbose_name='Precio de venta',
        help_text=(
            'Precio al que se vende al cliente. Monetary, no Float — '
            'ver el docstring del módulo.'
        ),
    )
    #: ≙ ``standard_price`` (``odoo19c: addons/product/models/
    #: product_template.py:100-106``): el de la variante única, sin columna.
    standard_price = fields.Monetary(
        compute='_compute_standard_price',
        inverse='_set_standard_price',
        search='_search_standard_price',
        store=False,
        max_digits=16,
        decimal_places=2,
        verbose_name='Coste',
    )
    #: ≙ ``volume`` y ``weight`` (``:108-113``): los de la variante única,
    #: almacenados.
    volume = fields.Float(
        compute='_compute_volume', inverse='_set_volume', store=True,
        default=0, verbose_name='Volumen')
    weight = fields.Float(
        compute='_compute_weight', inverse='_set_weight', store=True,
        default=0, verbose_name='Peso')
    sale_ok = fields.Boolean(default=True, verbose_name='Se puede vender')
    purchase_ok = fields.Boolean(default=True, verbose_name='Se puede comprar')
    active = fields.Boolean(
        default=True,
        verbose_name='Activo',
        help_text='Desmarcar oculta el producto sin borrarlo.',
    )
    color = fields.Integer(default=0, verbose_name='Índice de color')
    #: ≙ ``default_code`` (``:153-155``): el de la variante única,
    #: almacenado.
    default_code = fields.Char(
        compute='_compute_default_code',
        inverse='_set_default_code',
        store=True,
        max_length=64,
        blank=True,
        null=True,
        db_index=True,
        verbose_name='Referencia interna',
    )
    #: ≙ ``barcode`` (``:152``): el de la variante única, sin columna.
    barcode = fields.Char(
        compute='_compute_barcode',
        inverse='_set_barcode',
        search='_search_barcode',
        store=False,
        max_length=64,
        verbose_name='Código de barras',
    )
    is_favorite = fields.Boolean(default=False, verbose_name='Favorito')
    has_configurable_attributes = fields.Boolean(
        default=False,
        verbose_name='Producto configurable',
        help_text=(
            'Odoo lo calcula y almacena: verdadero si alguna línea de '
            'atributo ofrece más de un valor.'
        ),
    )
    product_properties = fields.Json(
        default=dict,
        blank=True,
        verbose_name='Propiedades',
        help_text=(
            'Pares libres cuyo esquema declara '
            'categ.product_properties_definition.'
        ),
    )

    class Meta:
        db_table = 'product_template'
        ordering = ['-is_favorite', 'name']
        indexes = [
            # ≙ ``_is_favorite_index = models.Index('(is_favorite) WHERE
            # is_favorite IS TRUE')`` (``:180``). El nombre de la fuente pasa
            # de los 30 caracteres de ``models.E034``, que detiene
            # ``migrate``: se acota como los demás índices declarados.
            models.Index(fields=['is_favorite'],
                         condition=models.Q(is_favorite=True),
                         name=fields.table_index_name('product_template',
                                                      'is_favorite')),
        ]
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'

    def __str__(self):
        return (
            f'[{self.default_code}] {self.name}'
            if self.default_code
            else self.name
        )

    def clean(self):
        """Las invariantes que la referencia impone sobre el tipo.

        Un **combo** agrupa otros productos: no tiene coste propio ni unidad
        de medida que lo describa. Un **servicio** no se almacena, así que su
        peso y volumen no significan nada — la referencia los oculta en el
        formulario; aquí se rechaza escribirlos, que es la versión de
        servidor de lo mismo.
        """
        super().clean()
        if self.type == TYPE_SERVICE and (self.weight or self.volume):
            raise ValidationError(
                'Un servicio no se almacena: no tiene peso ni volumen.'
            )
        if self.type == TYPE_COMBO and self.standard_price:
            raise ValidationError(
                'Un combo no tiene coste propio: lo aportan sus componentes.'
            )

    def check_combo_has_no_attributes(self):
        """``_onchange_type`` — *"Combo products can't have attributes."*

        ``odoo19c: product_template.py:460-462`` (``odoo-tools@622ddc2aa5``).
        Un combo no describe un artículo con variaciones: describe un conjunto
        de elecciones. Darle atributos generaría el producto cartesiano de algo
        que no es un producto.

        **No es "un combo no tiene variantes".** Sin atributos la ficha tiene
        exactamente **una** variante — la que la línea de venta necesita para
        apuntar al combo. La confusión entre ambas reglas produjo H-API-190.

        Método y no ``clean()``: ``attribute_line_ids`` es una relación
        inversa, y Django persiste el padre antes que sus hijos.
        """
        if self.type != TYPE_COMBO:
            return
        lines = getattr(self, 'attribute_line_ids', None)
        if lines is not None and lines.exists():
            raise ValidationError(
                'Un producto combo no puede tener atributos: agrupa '
                'elecciones, no variaciones de un artículo.'
            )

    @api.constrains('type', 'combo_ids')
    def _check_combo_ids_not_empty(self):
        """≙ ``_check_combo_ids_not_empty``
        (``odoo19c: product_template.py:490-493``)."""
        for template in self:
            if template.type == 'combo' and not template.combo_ids:
                raise ValidationError(_(
                    "A combo product must contain at least 1 combo choice."))

    @api.constrains('type', 'combo_ids', 'sale_ok')
    def _check_sale_combo_ids(self):
        """≙ ``_check_sale_combo_ids``
        (``odoo19c: product_template.py:496-507``)."""
        for template in self:
            if (
                template.type == 'combo'
                and template.sale_ok
                and any(
                    not product.sale_ok for product in
                    template.combo_ids.combo_item_ids.product_id
                )
            ):
                raise ValidationError(_(
                    "A sellable combo product can only contain sellable "
                    "products."))

    @api.depends('company_id')
    def _compute_currency_id(self):
        """≙ ``_compute_currency_id``
        (``odoo19c: product_template.py:257-260``).

        La moneda de la compañía del producto o, sin compañía, la de la
        compañía principal. La moneda de ``res.company`` se llama aquí
        ``currency``; la principal la resuelve ``ResCompany.get_main_company``.
        """
        main_company = ResCompany.get_main_company()
        main_currency = getattr(main_company, 'currency', None)
        for template in self:
            company = template.company_id
            template.currency_id = (
                (company.currency if company else None) or main_currency
            )

    @api.depends('company_id')
    @api.depends_context('company')
    def _compute_cost_currency_id(self):
        """≙ ``_compute_cost_currency_id``
        (``odoo19c: product_template.py:264-267``).

        La de la compañía del producto o, sin compañía, la de la empresa
        **activa**, no la principal.
        """
        env_company = self.env.company
        env_currency = env_company.currency if env_company else None
        for template in self:
            company = template.company_id
            template.cost_currency_id = (
                (company.currency if company else None) or env_currency
            )

    @property
    def uom_name(self):
        """``uom_name`` — ``related='uom_id.name'`` en la referencia."""
        return getattr(self.uom_id, 'name', '')

    def _get_attributes_extra_price(self):
        """≙ ``_get_attributes_extra_price`` (``odoo19c: addons/product/
        models/product_template.py:732``)."""
        self.ensure_one()

        return sum(self.env.context.get('current_attributes_price_extra', []))

    def _price_compute(self, price_type, uom=None, currency=None,
                       company=None, date=False):
        """≙ ``_price_compute`` (``odoo19c: addons/product/models/
        product_template.py:737``): el precio de ``price_type`` por
        plantilla, en la unidad y la moneda pedidas."""
        company = company or self.env.company
        date = date or fields.Date.context_today(self)

        self = self.with_company(company)
        if price_type == 'standard_price':
            # standard_price field can only be seen by users in
            # base.group_user. Thus, in order to compute the sale price from
            # the cost for users not in this group. We fetch the standard
            # price as the superuser
            self = self.sudo()

        prices = dict.fromkeys(self.ids, 0.0)
        for template in self:
            # ``Monetary`` es aquí un ``DecimalField``: el precio se lleva a
            # ``float``, el tipo con que la fuente lo calcula.
            price = float(template[price_type] or 0.0)
            price_currency = template.currency_id
            if price_type == 'standard_price':
                if not price and template.product_variant_ids:
                    price = float(
                        template.product_variant_ids[0].standard_price)
                price_currency = template.cost_currency_id
            elif price_type == 'list_price':
                price += template._get_attributes_extra_price()

            if uom:
                price = template.uom_id._compute_price(price, uom)

            # Convert from current user company currency to asked one
            # This is right cause a field cannot be in more than one currency
            if currency:
                price = price_currency._convert(price, currency, company,
                                                date)

            prices[template.id] = price
        return prices

    @property
    def is_product_variant(self):
        """``_compute_is_product_variant`` — una plantilla **no** lo es.

        Devuelve siempre falso aquí y siempre verdadero en
        ``product.product``. Existe para que un mismo trozo de código pueda
        recibir cualquiera de los dos y saber cuál tiene.
        """
        return False

    @api.depends('product_variant_ids.product_tmpl_id')
    def _compute_product_variant_count(self):
        """≙ ``_compute_product_variant_count``
        (``odoo19c: product_template.py:413-415``)."""
        for template in self:
            template.product_variant_count = len(template.product_variant_ids)

    @property
    def product_variant_id(self):
        """≙ ``_compute_product_variant_id`` (``odoo19c:
        addons/product/models/product_template.py:247-249``): la primera
        variante, ``product_variant_ids[:1]``. Quien exige una sola lo
        comprueba con ``product_variant_count``, como la fuente."""
        return self.product_variant_ids[:1]

    @property
    def product_document_ids(self):
        """Los documentos de esta ficha (``product_template.py:164-168``).

        **No** es un ``related_name``, y no puede serlo: el documento apunta
        por referencia genérica (``res_model``+``res_id``), no por FK.
        ``ProductDocument.for_record`` aplica el mismo filtro que el ``domain``
        de la fuente. Ver H-API-193.
        """
        return ProductDocument.for_record(self)

    @property
    def product_document_count(self):
        """``_compute_product_document_count`` — cuántos documentos tiene."""
        return self.product_document_ids.count()

    @property
    def variant_seller_ids(self):
        """El gemelo de ``seller_ids`` — el **mismo** conjunto, no un filtro.

        Su nombre sugiere "las tarifas específicas de variante", pero la
        referencia lo declara sobre el inverso ``product_tmpl_id``, igual que
        ``seller_ids``. Se conserva el nombre porque hay código que lo llama;
        filtrarlo aquí "porque el nombre lo dice" cambiaría el comportamiento
        de la fuente en silencio, que es lo contrario de portar.

        Quien quiera de verdad las tarifas de una variante concreta tiene
        ``ProductProduct.supplierinfo_ids``.
        """
        return self.seller_ids

    @property
    def properties_definition(self):
        """El esquema de ``product_properties``, heredado de la categoría.

        La referencia lo declara en el propio campo
        (``definition='categ_id.product_properties_definition'``); aquí se lee
        por propiedad porque el vocabulario mapea ``Properties`` a
        ``JSONField``, que no lleva esa indirección.
        """
        return getattr(
            self.categ_id, 'product_properties_definition', None) or []

    # -- unidad de peso / longitud / volumen leída del parámetro de sistema --
    #
    # ≙ los seis ayudantes de ``odoo19c:
    # product/models/product_template.py:354-403``.
    # Son ``@api.model``: no dependen de la instancia, así que aquí son
    # ``classmethod``. Los consume ``stock.package.type`` (etiquetas de alto,
    # ancho y peso) y ``stock.storage.category`` (etiqueta de peso máximo).

    @classmethod
    def get_weight_uom_id_from_ir_config_parameter(cls):
        """≙ ``_get_weight_uom_id_from_ir_config_parameter`` (``:354-364``).

        El peso se interpreta en kilogramos salvo que el parámetro
        ``product.weight_in_lbs`` valga ``'1'``, en cuyo caso son libras.
        """
        if SystemParameter.get_param('product.weight_in_lbs') == '1':
            return IrModelData.ref(
                'uom.product_uom_lb', raise_if_not_found=False
            )
        return IrModelData.ref('uom.product_uom_kgm', raise_if_not_found=False)

    @classmethod
    def get_length_uom_id_from_ir_config_parameter(cls):
        """≙ ``_get_length_uom_id_from_ir_config_parameter`` (``:367-377``).

        Milímetros por defecto; pies si ``product.volume_in_cubic_feet`` es
        ``'1'``. La referencia reutiliza a propósito el parámetro del volumen:
        quien mide en pies cúbicos mide en pies.
        """
        if SystemParameter.get_param('product.volume_in_cubic_feet') == '1':
            return IrModelData.ref(
                'uom.product_uom_foot', raise_if_not_found=False
            )
        return IrModelData.ref(
            'uom.product_uom_millimeter', raise_if_not_found=False
        )

    @classmethod
    def get_volume_uom_id_from_ir_config_parameter(cls):
        """≙ ``_get_volume_uom_id_from_ir_config_parameter`` (``:380-390``)."""
        if SystemParameter.get_param('product.volume_in_cubic_feet') == '1':
            return IrModelData.ref(
                'uom.product_uom_cubic_foot', raise_if_not_found=False
            )
        return IrModelData.ref(
            'uom.product_uom_cubic_meter', raise_if_not_found=False
        )

    @classmethod
    def get_weight_uom_name_from_ir_config_parameter(cls):
        """≙ ``_get_weight_uom_name_from_ir_config_parameter`` (``:392-394``).

        Devuelve ``''`` si la unidad no está sembrada — la referencia devuelve
        el ``display_name`` de un recordset vacío, que también es ``''``.
        """
        unidad = cls.get_weight_uom_id_from_ir_config_parameter()
        return str(unidad) if unidad is not None else ''

    @classmethod
    def get_length_uom_name_from_ir_config_parameter(cls):
        """
        ≙ ``_get_length_uom_name_from_ir_config_parameter`` (``:396-398``).
        """
        unidad = cls.get_length_uom_id_from_ir_config_parameter()
        return str(unidad) if unidad is not None else ''

    @classmethod
    def get_volume_uom_name_from_ir_config_parameter(cls):
        """
        ≙ ``_get_volume_uom_name_from_ir_config_parameter`` (``:400-402``).
        """
        unidad = cls.get_volume_uom_id_from_ir_config_parameter()
        return str(unidad) if unidad is not None else ''

    # === GENERACIÓN DE VARIANTES =========================================
    # ≙ ``odoo19c: addons/product/models/product_template.py:567-591,
    # 770-1128``. Diseño: ``designs/product-template-variant-generation.md``.

    @api.model_create_multi
    def create(self, vals_list):
        """≙ ``create`` (``:567-583``): genera las variantes de cada plantilla
        salvo con ``create_product_product=False`` en el contexto, y copia a
        la variante creada los campos que comparten plantilla y variante.
        """
        templates = super().create(vals_list)
        if self.env.context.get("create_product_product", True):
            templates._create_variant_ids()

        # This is needed to set given values to first variant after creation
        for template, vals in zip(templates, vals_list):
            related_vals = {}
            for field_name in self._get_related_fields_variant_template():
                if vals.get(field_name) and not template[field_name]:
                    related_vals[field_name] = vals[field_name]
            if related_vals:
                template.write(related_vals)

        return templates

    def write(self, vals):
        """≙ las ramas de variantes de ``write`` (``:585-596``): regenera al
        cambiar las líneas o al reactivar una plantilla sin variantes, y
        archiva las variantes al archivar la plantilla.

        También el cambio de unidad de las variantes (``:586-588``) y
        ``combo_ids`` al dejar de ser combo (``:604-606``). La invalidación de
        las imágenes de la variante (``:597-603``) espera a que la variante
        las declare (sucesor ``product-variant-images-0122``).
        """
        if 'uom_id' in vals:
            # ``filtered(...).product_variant_ids`` sobre varias plantillas
            # espera la rama multi-registro de los relacionales
            # (TASK-API-0401): se recorre plantilla a plantilla.
            for template in self.filtered(
                    lambda template: template.uom_id.id != vals['uom_id']):
                template.product_variant_ids.with_context(
                    skip_uom_conversion=True)._update_uom(vals['uom_id'])
        res = super().write(vals)
        if (self.env.context.get("create_product_product", True)
                and 'attribute_line_ids' in vals
                or (vals.get('active')
                    and len(self.product_variant_ids) == 0)):
            self._create_variant_ids()
        if 'active' in vals and not vals.get('active'):
            # ``mapped('product_variant_ids')`` sobre varias plantillas espera
            # la rama multi-registro de los relacionales (TASK-API-0401): se
            # recorre plantilla a plantilla, con el mismo efecto.
            for template in self.with_context(active_test=False):
                template.product_variant_ids.write(
                    {'active': vals.get('active')})
        for product_template in self:
            if "type" in vals and vals.get("type") != "combo":
                product_template.combo_ids = False
        return res

    def _create_variant_ids(self):
        """≙ ``_create_variant_ids`` (``:770-870``)."""
        if not self:
            return
        self.env.flush_all()
        Product = self.env["product.product"]

        variants_to_create = []
        variants_to_activate = Product
        variants_to_unlink = Product

        for tmpl_id in self:
            lines_without_no_variants = (
                tmpl_id.valid_product_template_attribute_line_ids
                ._without_no_variant_attributes())

            all_variants = tmpl_id.with_context(
                active_test=False).product_variant_ids.sorted(
                lambda p: (p.active, -p.id))

            current_variants_to_create = []
            current_variants_to_activate = Product

            # adding an attribute with only one value should not recreate
            # product; write this attribute on every product to make sure we
            # don't lose them
            single_value_lines = lines_without_no_variants.filtered(
                lambda ptal: len(
                    ptal.product_template_value_ids._only_active()) == 1)
            if single_value_lines:
                for variant in all_variants:
                    combination = (
                        variant.product_template_attribute_value_ids
                        | single_value_lines.product_template_value_ids
                        ._only_active())
                    # Do not add single value if the resulting combination
                    # would be invalid anyway.
                    if (
                        len(combination) == len(lines_without_no_variants)
                        and combination.attribute_line_id
                        == lines_without_no_variants
                        # Update only if necessary to prevent a cache
                        # invalidation
                        and variant.product_template_attribute_value_ids
                        != combination
                    ):
                        variant.product_template_attribute_value_ids = (
                            combination)

            # Set containing existing `product.template.attribute.value`
            # combination
            existing_variants = {
                variant.product_template_attribute_value_ids: variant
                for variant in all_variants
            }

            # Determine which product variants need to be created based on
            # the attribute configuration. If any attribute is set to
            # generate variants dynamically, skip the process.
            if not tmpl_id.has_dynamic_attributes():
                # Iterator containing all possible combinations, used to
                # avoid MemoryError in case of a huge number of combinations.
                all_combinations = itertools.product(*[
                    ptal.product_template_value_ids._only_active()
                    for ptal in lines_without_no_variants
                ])
                # For each possible variant, create if it doesn't exist yet.
                for combination in (
                        tmpl_id._filter_combinations_impossible_by_config(
                            all_combinations, ignore_no_variant=True)):
                    if combination in existing_variants:
                        current_variants_to_activate += existing_variants[
                            combination]
                    else:
                        current_variants_to_create.append(
                            tmpl_id._prepare_variant_values(combination))
                        variant_limit = SystemParameter.get_param(
                            'product.dynamic_variant_limit', 1000)
                        if len(current_variants_to_create) > int(
                                variant_limit):
                            raise UserError(_(
                                'The number of variants to generate is above'
                                ' allowed limit. You should either not'
                                ' generate variants for each combination or'
                                ' generate them on demand from the sales'
                                ' order. To do so, open the form view of'
                                ' attributes and change the mode of *Create'
                                ' Variants*.'))
                variants_to_create += current_variants_to_create
                variants_to_activate += current_variants_to_activate

            elif existing_variants:
                variants_combinations = [
                    variant.product_template_attribute_value_ids
                    for variant in existing_variants.values()]
                current_variants_to_activate += Product.concat(*[
                    existing_variants[possible_combination]
                    for possible_combination in
                    tmpl_id._filter_combinations_impossible_by_config(
                        variants_combinations, ignore_no_variant=True)
                ])
                variants_to_activate += current_variants_to_activate

            variants_to_unlink += all_variants - current_variants_to_activate

        if variants_to_activate:
            # Only activate variants whose template is active
            variants_to_activate.filtered(
                lambda v: v.product_tmpl_id.active).write({'active': True})
        if variants_to_create:
            Product.create(variants_to_create)
        if variants_to_unlink:
            variants_to_unlink._unlink_or_archive()
            # prevent change if exclusion deleted template by deleting last
            # variant
            if self.exists() != self:
                raise UserError(_(
                    "This configuration of product attributes, values, and"
                    " exclusions would lead to no possible variant. Please"
                    " archive or delete your product directly if intended."))
        # ``product.combo.item`` es todavía modelo de Django: el ``search`` +
        # ``unlink`` de la fuente es su consulta y su borrado.
        ProductComboItem = apps.get_model('product', 'ProductComboItem')
        for variant in variants_to_unlink:
            # Unlink all combo items which reference unlinked variants.
            ProductComboItem.objects.filter(product_id=variant.id).delete()

        # prefetched o2m have to be reloaded (because of active_test)
        self.env.flush_all()
        self.env.invalidate_all()
        return True

    def _prepare_variant_values(self, combination):
        """≙ ``_prepare_variant_values`` (``:872-878``)."""
        self.ensure_one()
        return {
            'product_tmpl_id': self.id,
            'product_template_attribute_value_ids': [
                (6, 0, combination.ids)],
            'active': self.active,
        }

    def has_dynamic_attributes(self):
        """≙ ``has_dynamic_attributes`` (``:880-888``)."""
        self.ensure_one()
        # ``product.attribute`` es todavía modelo de Django: el recordset de
        # sus filas por las líneas (``lines.attribute_id``) se recorre línea a
        # línea, con la misma condición.
        return any(
            line.attribute_id.create_variant == 'dynamic'
            for line in self.valid_product_template_attribute_line_ids)

    @property
    def valid_product_template_attribute_line_ids(self):
        """≙ ``valid_product_template_attribute_line_ids`` (``:135-136``) con
        su cómputo (``:890-900``): las líneas con al menos un valor."""
        return self.attribute_line_ids.filtered(lambda ptal: ptal.value_ids)

    def _get_own_attribute_exclusions(self, combination_ids=None):
        """≙ ``_get_own_attribute_exclusions`` (``:990-1031``): por cada
        valor de la plantilla, los valores que excluye."""
        self.ensure_one()
        product_template_attribute_values = (
            self.valid_product_template_attribute_line_ids
            .product_template_value_ids)
        result = {}

        domain_ptav = [('ptav_active', '=', True)]

        if combination_ids:
            domain_ptav = Domain.OR([
                domain_ptav,
                [('id', 'in', combination_ids)]
            ])

        domain_ptav = Domain.AND([
            domain_ptav,
            [('id', 'in', product_template_attribute_values.ids)],
        ])

        exclusion_ids_by_ptav = dict(
            self.env['product.template.attribute.exclusion']._read_group(
                domain=[
                    ('product_template_attribute_value_id', 'any',
                     domain_ptav),
                    ('product_tmpl_id', '=', self.id),
                ],
                groupby=['product_template_attribute_value_id'],
                aggregates=['id:recordset'],
            ))

        for ptav in product_template_attribute_values:
            if (ptav.ptav_active
                    or combination_ids and ptav.id in combination_ids):
                if exclusions := exclusion_ids_by_ptav.get(ptav):
                    result[ptav.id] = exclusions.value_ids.filtered(
                        lambda x: x.ptav_active).ids
                else:
                    result[ptav.id] = []

        return result

    def _filter_combinations_impossible_by_config(
            self, combination_tuples, ignore_no_variant=False):
        """≙ ``_filter_combinations_impossible_by_config`` (``:1076-1111``):
        «Filter combination_tuples according to the config of attributes on
        the template.»"""
        self.ensure_one()
        attribute_lines = self.valid_product_template_attribute_line_ids
        attribute_lines_active_values = (
            attribute_lines.product_template_value_ids._only_active())
        if ignore_no_variant:
            attribute_lines = attribute_lines._without_no_variant_attributes()
        attribute_lines_without_multi = attribute_lines.filtered(
            lambda line: line.attribute_id.display_type != 'multi')
        exclusions = self._get_own_attribute_exclusions()
        for combination_tuple in combination_tuples:
            combination = self.env['product.template.attribute.value'].concat(
                *combination_tuple)
            combination_without_multi = combination.filtered(
                lambda line: line.attribute_line_id.attribute_id.display_type
                != 'multi')
            if (len(combination_without_multi)
                    != len(attribute_lines_without_multi)):
                # number of attribute values passed is different than the
                # configuration of attributes on the template
                continue
            if (attribute_lines_without_multi
                    != combination_without_multi.attribute_line_id):
                # combination has different attributes than the ones
                # configured on the template
                continue
            if not (attribute_lines_active_values >= combination):
                # combination has different values than the ones configured
                # on the template
                continue
            if exclusions:
                # exclude if the current value is in an exclusion, and the
                # value excluding it is also in the combination
                combination_ids = set(combination.ids)
                combination_excluded_ids = set(itertools.chain(*[
                    exclusions.get(ptav_id) for ptav_id in combination.ids]))
                if combination_ids & combination_excluded_ids:
                    continue
            yield combination

    def _is_combination_possible_by_config(
            self, combination, ignore_no_variant=False):
        """≙ ``_is_combination_possible_by_config`` (``:1113-1127``)."""
        self.ensure_one()
        # Returns False on StopIteration. Empty combination should return
        # True.
        return isinstance(next(self._filter_combinations_impossible_by_config(
            [combination], ignore_no_variant), False), models.BaseModel)

    # === CAMPOS LEÍDOS DE LA VARIANTE ÚNICA ===============================
    # ≙ ``odoo19c: addons/product/models/product_template.py:269-351,
    # 436-442,509-511``. Diseño: ``designs/product-template-crud.md``.

    def _compute_template_field_from_variant_field(self, fname,
                                                   default=False):
        """≙ ``_compute_template_field_from_variant_field`` (``:269-290``):
        el valor de la variante única, o ``default`` con varias o ninguna.
        """
        for template in self:
            variant_count = len(template.product_variant_ids)
            if variant_count == 1:
                template[fname] = template.product_variant_ids[fname]
            elif (variant_count == 0
                    and self.env.context.get("active_test", True)):
                # If the product has no active variants, retry without the
                # active_test.
                template_ctx = template.with_context(active_test=False)
                template_ctx._compute_template_field_from_variant_field(
                    fname, default=default)
            else:
                template[fname] = default

    def _set_product_variant_field(self, fname):
        """≙ ``_set_product_variant_field`` (``:292-310``): propaga el valor
        a la variante única, o a la única archivada."""
        for template in self:
            count = len(template.product_variant_ids)
            if count == 1:
                template.product_variant_ids[fname] = template[fname]
            elif count == 0:
                archived_variants = self.with_context(
                    active_test=False).product_variant_ids
                if len(archived_variants) == 1:
                    archived_variants[fname] = template[fname]

    @api.depends_context('company')
    @api.depends('product_variant_ids.standard_price')
    def _compute_standard_price(self):
        """≙ ``_compute_standard_price`` (``:311-314``)."""
        # Depends on force_company context because standard_price is
        # company_dependent on the product_product.
        self._compute_template_field_from_variant_field('standard_price')

    def _set_standard_price(self):
        """≙ ``_set_standard_price`` (``:316-317``)."""
        self._set_product_variant_field('standard_price')

    def _search_standard_price(self, operator, value):
        """≙ ``_search_standard_price`` (``:319-320``)."""
        return [('product_variant_ids.standard_price', operator, value)]

    @api.depends('product_variant_ids.volume')
    def _compute_volume(self):
        """≙ ``_compute_volume`` (``:322-324``)."""
        self._compute_template_field_from_variant_field('volume')

    def _set_volume(self):
        """≙ ``_set_volume`` (``:326-327``)."""
        self._set_product_variant_field('volume')

    @api.depends('product_variant_ids.weight')
    def _compute_weight(self):
        """≙ ``_compute_weight`` (``:329-331``)."""
        self._compute_template_field_from_variant_field('weight')

    def _set_weight(self):
        """≙ ``_set_weight`` (``:333-334``)."""
        self._set_product_variant_field('weight')

    @api.depends('product_variant_ids.barcode')
    def _compute_barcode(self):
        """≙ ``_compute_barcode`` (``:339-341``)."""
        self._compute_template_field_from_variant_field('barcode')

    def _search_barcode(self, operator, value):
        """≙ ``_search_barcode`` (``:343-347``)."""
        subquery = self.with_context(active_test=False)._search([
            ('product_variant_ids.barcode', operator, value),
        ])
        return [('id', 'in', subquery)]

    def _set_barcode(self):
        """≙ ``_set_barcode`` (``:349-350``)."""
        self._set_product_variant_field('barcode')

    @api.depends('product_variant_ids.default_code')
    def _compute_default_code(self):
        """≙ ``_compute_default_code`` (``:436-438``)."""
        self._compute_template_field_from_variant_field('default_code')

    def _set_default_code(self):
        """≙ ``_set_default_code`` (``:440-441``)."""
        self._set_product_variant_field('default_code')

    def _get_related_fields_variant_template(self):
        """≙ ``_get_related_fields_variant_template`` (``:509-511``)."""
        return ['barcode', 'default_code', 'standard_price', 'volume',
                'weight', 'product_properties']
