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
``product_variant_count`` y ``product_variant_id`` — el segundo sólo tiene
sentido cuando la plantilla tiene **exactamente una** variante, que es el caso
del producto sin atributos.

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
  ``product_product.py``, ``seller_ids`` desde ``product_supplierinfo.py`` y
  ``combo_ids`` desde ``product_combo.py`` —que declara el M2M de su lado con
  el nombre de la fuente, sin tocar este archivo—.

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
- **``standard_price`` como ``compute``/``inverse``/``search``**: su valor
  sale de la valoración AVCO del inventario, que vive en ``stock_account``.
  Aquí se porta como **columna** —es el dato que alguien escribe cuando no hay
  valoración— y se declara que el cálculo automático no está.
- **``barcode`` con ``compute``/``inverse``/``search``**: el código de barras
  de la plantilla es el de su variante única. Se porta la **derivación**
  (propiedad), no el ``search`` — que en la referencia traduce el filtro a la
  tabla de variantes con su motor de dominios.
- **``_compute_currency_id`` / ``_compute_cost_currency_id``**: la moneda sale
  de la compañía. Se porta como propiedad; la de coste puede diferir cuando la
  compañía valora en otra divisa, y eso lo resuelve ``stock_account``.
- **La generación de variantes** (``_create_variant_ids``, ~200 líneas): crea
  el producto cartesiano de las líneas de atributo y sincroniza altas y bajas.
  Entra con ``product_product.py``, que es donde vive el modelo que crea.
"""
import fields
import models
from django.core.exceptions import ValidationError

from addons.base.models.image_mixin import ImageMixin
from addons.base.models.res_company import ResCompany
from addons.base.models.timestamped_mixin import TimeStampedModel
from addons.product.models.product_category import ProductCategory
from addons.product.models.product_document import ProductDocument
from addons.uom.models.uom_uom import Uom
from addons.website.models.mixins import WebsitePublishedMixin

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


class ProductTemplate(ImageMixin, WebsitePublishedMixin, TimeStampedModel):
    """``product.template`` — el producto del catálogo.

    **De dónde sale ``is_published``.** En la referencia no lo declara este
    modelo: lo añade ``website_sale`` reabriendo ``product.template`` con
    ``_inherit = [… 'website.published.multi.mixin' …]``
    (``odoo19c: website_sale/models/product_template.py:36-42``). Django no
    puede reabrir una clase de modelo, así que el mixin se hereda aquí — pero
    **el concepto sigue viviendo en ``website``**
    (``addons.website.models.mixins``), que es quien lo dueña en la
    referencia. La divergencia es de mecanismo (herencia en la definición vs.
    ``_inherit`` en tiempo de registro), no de reparto: un producto sigue
    existiendo en el ERP sin estar publicado en la tienda.
    """

    name = fields.Char(max_length=255, db_index=True, verbose_name='Nombre')
    sequence = fields.Integer(
        default=1, verbose_name='Secuencia',
        help_text='Orden al listar productos.')
    description = fields.Html(
        blank=True, default='', verbose_name='Descripción')
    description_purchase = fields.Text(
        blank=True, default='', verbose_name='Descripción de compra')
    description_sale = fields.Text(
        blank=True, default='', verbose_name='Descripción de venta',
        help_text='Se copia a cada pedido, albarán y factura del cliente.')
    type = fields.Selection(
        max_length=16, choices=TYPE_CHOICES, default=TYPE_CONSU,
        verbose_name='Tipo de producto')
    service_tracking = fields.Selection(
        max_length=16, choices=SERVICE_TRACKING_CHOICES, default='no',
        verbose_name='Crear al confirmar el pedido')
    categ = fields.Many2one(
        ProductCategory, on_delete=models.PROTECT, null=True, blank=True,
        db_index=True, related_name='product_tmpl_ids',
        verbose_name='Categoría de producto',
        help_text='Odoo categ_id. FK real: product.category ya está portado.',
    )
    company = fields.Many2one(
        ResCompany, on_delete=models.CASCADE, null=True, blank=True,
        db_index=True, related_name='product_tmpl_ids', verbose_name='Compañía',
        help_text='Vacío = producto compartido por todas las compañías.',
    )
    uom = fields.Many2one(
        Uom, on_delete=models.PROTECT, null=True, blank=True,
        related_name='product_tmpl_ids', verbose_name='Unidad de medida',
        help_text='Odoo uom_id. FK real: uom.uom ya está portado.',
    )
    list_price = fields.Monetary(
        max_digits=16, decimal_places=2, default=1,
        verbose_name='Precio de venta',
        help_text='Precio al que se vende al cliente. Monetary, no Float — '
                  'ver el docstring del módulo.',
    )
    standard_price = fields.Monetary(
        max_digits=16, decimal_places=2, default=0,
        verbose_name='Coste',
        help_text='Valor del producto. En la referencia lo calcula la '
                  'valoración AVCO del inventario; aquí es columna, y el '
                  'cálculo automático no está portado.',
    )
    volume = fields.Float(default=0, verbose_name='Volumen')
    weight = fields.Float(default=0, verbose_name='Peso')
    sale_ok = fields.Boolean(default=True, verbose_name='Se puede vender')
    purchase_ok = fields.Boolean(default=True, verbose_name='Se puede comprar')
    active = fields.Boolean(
        default=True, verbose_name='Activo',
        help_text='Desmarcar oculta el producto sin borrarlo.')
    color = fields.Integer(default=0, verbose_name='Índice de color')
    default_code = fields.Char(
        max_length=64, blank=True, default='', db_index=True,
        verbose_name='Referencia interna')
    is_favorite = fields.Boolean(default=False, verbose_name='Favorito')
    has_configurable_attributes = fields.Boolean(
        default=False, verbose_name='Producto configurable',
        help_text='Odoo lo calcula y almacena: verdadero si alguna línea de '
                  'atributo ofrece más de un valor.',
    )
    product_properties = fields.Json(
        default=dict, blank=True, verbose_name='Propiedades',
        help_text='Pares libres cuyo esquema declara '
                  'categ.product_properties_definition.',
    )

    class Meta:
        db_table = 'product_template'
        ordering = ['-is_favorite', 'name']
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'

    def __str__(self):
        return f'[{self.default_code}] {self.name}' if self.default_code \
            else self.name

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
                'Un servicio no se almacena: no tiene peso ni volumen.')
        if self.type == TYPE_COMBO and self.standard_price:
            raise ValidationError(
                'Un combo no tiene coste propio: lo aportan sus componentes.')

    def check_combo_has_no_attributes(self):
        """``_onchange_type`` — *"Combo products can't have attributes."*

        ``odoo19c: product_template.py:460-462`` (``odoo-tools@622ddc2aa5``).
        Un combo no describe un artículo con variaciones: describe un conjunto
        de elecciones. Darle atributos generaría el producto cartesiano de algo
        que no es un producto.

        **No es "un combo no tiene variantes".** Sin atributos la ficha tiene
        exactamente **una** variante — la que la línea de venta necesita para
        apuntar al combo. La confusión entre ambas reglas produjo H-API-190.

        Método y no ``clean()``: ``attribute_lines`` es una relación inversa, y
        Django persiste el padre antes que sus hijos. Mismo motivo que
        ``check_combo_choices`` y ``ProductCombo.check_has_items``.
        """
        if self.type != TYPE_COMBO:
            return
        lines = getattr(self, 'attribute_lines', None)
        if lines is not None and lines.exists():
            raise ValidationError(
                'Un producto combo no puede tener atributos: agrupa '
                'elecciones, no variaciones de un artículo.')

    def check_combo_choices(self):
        """Las dos invariantes de la referencia sobre ``combo_ids``.

        - ``_check_combo_ids_not_empty``: un producto de tipo combo tiene que
          ofrecer al menos una elección. Un menú sin elecciones no es un menú.
        - ``_check_sale_combo_ids``: si el combo se vende, **todo** producto
          ofrecido dentro de él tiene que ser vendible. Lo contrario permite
          armar un menú cuyo cliente elige algo que no está a la venta, y el
          error aparecería al confirmar el pedido, lejos de su causa.

        **Método, no ``clean()``**, por la misma razón que
        ``ProductCombo.check_has_items``: ``combo_ids`` es un M2M, y Django no
        deja poblarlo antes de que el registro exista. Exigirlo en ``clean()``
        haría imposible crear un producto combo. Se invoca tras adjuntar las
        elecciones.
        """
        if self.type != TYPE_COMBO:
            return
        combos = getattr(self, 'combo_ids', None)
        if combos is None or not combos.exists():
            raise ValidationError(
                'Un producto combo debe ofrecer al menos una elección.')
        if not self.sale_ok:
            return
        for combo in combos.all():
            items = getattr(combo, 'combo_item_ids', None)
            if items is not None and any(
                not item.product.sale_ok for item in items.all()
            ):
                raise ValidationError(
                    'Un combo a la venta no puede ofrecer productos que no '
                    'están a la venta.')

    # === DERIVADOS ========================================================

    @property
    def currency(self):
        """``_compute_currency_id`` — la moneda de la compañía del producto."""
        return getattr(self.company, 'currency', None)

    @property
    def cost_currency(self):
        """``_compute_cost_currency_id`` — la moneda en que se expresa el coste.

        Coincide con ``currency`` mientras no haya valoración de inventario en
        otra divisa; ese caso lo resuelve ``stock_account``, no portado.
        """
        return self.currency

    @property
    def uom_name(self):
        """``uom_name`` — ``related='uom_id.name'`` en la referencia."""
        return getattr(self.uom, 'name', '')

    @property
    def is_product_variant(self):
        """``_compute_is_product_variant`` — una plantilla **no** lo es.

        Devuelve siempre falso aquí y siempre verdadero en
        ``product.product``. Existe para que un mismo trozo de código pueda
        recibir cualquiera de los dos y saber cuál tiene.
        """
        return False

    @property
    def product_variant_count(self):
        """``product_variant_count`` — cuántas variantes tiene.

        Devuelve 0 mientras ``product.product`` no esté portado; llega solo
        por el ``related_name`` de aquel archivo, sin tocar éste.
        """
        variants = getattr(self, 'product_variant_ids', None)
        return variants.count() if variants is not None else 0

    @property
    def product_variant_id(self):
        """``_compute_product_variant_id`` — la variante única, si lo es.

        ``None`` cuando hay cero o más de una: pedir "la" variante de un
        producto con tres sólo puede ser un error de quien pregunta, y
        devolver una cualquiera lo escondería.
        """
        variants = getattr(self, 'product_variant_ids', None)
        if variants is None or variants.count() != 1:
            return None
        return variants.first()

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
    def barcode(self):
        """``_compute_barcode`` — el código de barras de la variante única."""
        variant = self.product_variant_id
        return getattr(variant, 'barcode', '') if variant is not None else ''

    @property
    def properties_definition(self):
        """El esquema de ``product_properties``, heredado de la categoría.

        La referencia lo declara en el propio campo
        (``definition='categ_id.product_properties_definition'``); aquí se lee
        por propiedad porque el vocabulario mapea ``Properties`` a
        ``JSONField``, que no lleva esa indirección.
        """
        return getattr(self.categ, 'product_properties_definition', None) or []
