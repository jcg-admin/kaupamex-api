"""``product.supplierinfo`` — el precio de un proveedor para un producto.

Adaptación de ``addons/product/models/product_supplierinfo.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 119 líneas). Una fila responde: *"a
qué precio, en qué unidad, desde qué cantidad y con cuánto plazo me vende
**este** proveedor **este** producto"*. Es la tarifa de compra, la contraparte
de ``product.pricelist`` (que es la de venta).

Plantilla **y** variante, y por qué las dos
===========================================

La fila apunta a la **plantilla** (obligatorio) y opcionalmente a una
**variante**. No es redundancia: es el alcance del precio.

- Sólo plantilla → el precio vale para **todas** las variantes. Es el caso
  normal: el proveedor cotiza "camiseta", no "camiseta roja talla M".
- Plantilla + variante → el precio vale **sólo** para esa combinación. El
  ``help`` de la referencia lo dice al revés de como se lee al principio:
  *"If not set, the vendor price will apply to all variants"*.

La consecuencia es que **la variante manda sobre la plantilla** cuando ambas
encajan, y eso se ve en ``code_for`` más abajo: el bucle sigue buscando hasta
encontrar la entrada específica de la variante, y sólo entonces corta.

El orden es el que decide qué fila gana
=======================================

``_order = 'sequence, min_qty DESC, price, id'``. Leído en orden: el proveedor
con menos ``sequence`` primero; a igual secuencia, **la cantidad mínima mayor
primero** —porque comprar 100 sale más barato que comprar 10 y el escalón alto
debe evaluarse antes—; a igual cantidad, el precio menor. Invertir el
``DESC`` daría siempre el escalón de 1 unidad y el descuento por volumen no se
aplicaría nunca.

Divergencia declarada: ``price`` y ``discount`` son ``Monetary``
================================================================

La referencia declara los dos como ``Float``. Aquí son ``fields.Monetary``
—``DecimalField``— por el criterio de **comparabilidad** que H-API-168 fijó,
no por gusto:

1. Esta fila alimenta la línea de compra. ``purchase_order_line.price_unit``
   y ``purchase_order_line.discount`` ya son ``Monetary`` en este árbol
   (``purchase/models/purchase_order_line.py:38`` y ``:41``, medido) — con
   ``max_digits=5, decimal_places=2`` en el descuento, que es lo que se copia
   aquí. Un precio de proveedor en ``float`` al lado de la línea que lo
   consume redondearía distinto el mismo importe según por dónde se leyera.
2. ``Decimal * float`` **lanza** ``TypeError``. Con ``price`` en ``Decimal``,
   ``discount`` en ``float`` no es una inconsistencia estética: rompe
   ``price_discounted`` en tiempo de ejecución.

**El precio que la divergencia cobra** está en la conversión de unidad:
``Uom.compute_price`` multiplica por ``factor``, que es ``Float``
(``uom/models/uom_uom.py:104``), así que **no se le puede pasar un
``Decimal``**. ``price_discounted`` no lo llama: reconstruye el mismo ratio
(``to_unit.factor / self.factor``, verbatim de ``uom_uom.py:306-313``) como
``Decimal`` y multiplica. El dinero no sale de ``Decimal`` en ningún punto;
lo que se convierte es la **razón**, no el importe.

Dos hallazgos en la fuente, portados en consecuencia
====================================================

- **``_compute_price`` es código muerto.** Lleva su ``@api.depends`` y su
  bucle, pero **ningún campo lo declara**: ``price`` se declara
  ``fields.Float('Unit Price', min_display_digits=…, default=0.0)``, sin
  ``compute=``. El ORM nunca lo invoca. No se porta un método que la propia
  referencia no llama; se deja anotado para que nadie lo "restaure" creyendo
  que falta. Su intención —sembrar el precio de compra con el coste del
  producto— es un *default* de formulario, no una derivación.
- **``variant_seller_ids`` no es de variantes.** La plantilla declara
  ``seller_ids`` y ``variant_seller_ids`` (``product_template.py:126-127``)
  y **las dos** usan el mismo inverso ``product_tmpl_id``; sólo difieren en
  el ``depends_context=('company',)`` de la primera. En Django una FK da
  exactamente **un** ``related_name``, así que se declara ``seller_ids`` y
  ``variant_seller_ids`` queda como alias explícito sobre el mismo conjunto —
  preserva el nombre para quien lo llame sin fingir que filtra algo distinto.

Qué NO se porta, con su medición
================================

- **``_compute_product_id``**: lee ``self.env.get('default_product_id')``
  para presembrar la variante al abrir el formulario desde un producto. Es
  plomería del cliente web; el equivalente aquí es el ``initial`` del
  serializer.
- **``get_import_templates``**: devuelve la ruta de un ``.xls`` de ejemplo
  para el importador de Odoo. No hay importador XLS en este árbol
  (``grep -rn "get_import_templates" src/`` → **0** antes de este archivo).
- **``check_company=True``** como declaración: aquí es una comprobación
  explícita en ``clean()``. El atributo del campo no existe en Django, pero
  la invariante que expresa —proveedor, producto y tarifa de la **misma**
  compañía— sí, y es lo que se porta.
- **La comprobación de acceso de lectura** (``ir.model.access.check`` en
  ``_compute_product_code``): la autorización aquí es por capacidad (DEC-11),
  no por ACL de modelo. ``code_for`` recibe el interlocutor y devuelve el
  código; **quién puede preguntarlo** lo decide la vista.
"""
import decimal

import fields
import models
from django.core.exceptions import ValidationError

from addons.base.models.res_company import ResCompany
from addons.base.models.res_currency import ResCurrency
from addons.base.models.res_partner import ResPartner
from addons.base.models.timestamped_mixin import TimeStampedModel
from addons.product.models.product_product import ProductProduct
from addons.product.models.product_template import ProductTemplate
from addons.uom.models.uom_uom import Uom

#: Divisor del porcentaje de descuento. Constante nombrada porque el ``/ 100``
#: suelto de la fuente es lo que delata si alguien guarda ``0.15`` en vez de
#: ``15`` en el campo.
PERCENT_BASE = decimal.Decimal('100')


class ProductSupplierinfo(TimeStampedModel):
    """``product.supplierinfo`` — la tarifa de un proveedor.

    El nombre conserva la grafía de la referencia (``Supplierinfo``, con
    minúscula en la ``i``): es el nombre que buscan los ``grep`` de los
    archivos que la esperaban.
    """

    partner = fields.Many2one(
        ResPartner, on_delete=models.CASCADE, db_index=True,
        related_name='supplierinfo_ids', verbose_name='Proveedor',
        help_text='Odoo partner_id. Es el nombre por el que se muestra la '
                  'fila (_rec_name en la referencia).',
    )
    product_name = fields.Char(
        max_length=255, blank=True, default='',
        verbose_name='Nombre del producto para el proveedor',
        help_text='Se usa al imprimir una solicitud de presupuesto. Vacío = '
                  'se usa el nombre interno.',
    )
    product_code = fields.Char(
        max_length=64, blank=True, default='',
        verbose_name='Código del producto para el proveedor',
        help_text='Idem con la referencia: vacío = se usa la interna.')
    sequence = fields.Integer(
        default=1, verbose_name='Secuencia',
        help_text='Prioridad del proveedor en la lista. Menor gana.')
    product_uom = fields.Many2one(
        Uom, on_delete=models.PROTECT, null=True, blank=True,
        related_name='supplierinfo_ids', verbose_name='Unidad del proveedor',
        help_text='Unidad en que el proveedor cotiza, que puede no ser la del '
                  'producto. Odoo la calcula y almacena; aquí se siembra en '
                  'save() desde la variante o la plantilla.',
    )
    min_qty = fields.Float(
        default=0, verbose_name='Cantidad mínima',
        help_text='Cantidad a partir de la cual aplica este precio, expresada '
                  'en la unidad del proveedor.',
    )
    price = fields.Monetary(
        max_digits=16, decimal_places=2, default=0,
        verbose_name='Precio unitario',
        help_text='Precio de compra en la unidad del proveedor. Monetary, no '
                  'Float — ver el docstring del módulo.',
    )
    discount = fields.Monetary(
        max_digits=5, decimal_places=2, default=0,
        verbose_name='Descuento (%)',
        help_text='Porcentaje sobre el precio. Mismo tipo y precisión que '
                  'purchase_order_line.discount, que es quien lo consume.',
    )
    company = fields.Many2one(
        ResCompany, on_delete=models.CASCADE, null=True, blank=True,
        db_index=True, related_name='supplierinfo_ids', verbose_name='Compañía',
        help_text='Vacío = la tarifa sirve a todas las compañías.')
    currency = fields.Many2one(
        ResCurrency, on_delete=models.PROTECT, null=True, blank=True,
        related_name='supplierinfo_ids', verbose_name='Moneda',
        help_text='Moneda en que el proveedor cotiza. Requerido en la '
                  'referencia, con la de la compañía por defecto.',
    )
    date_start = fields.Date(
        null=True, blank=True, verbose_name='Fecha de inicio',
        help_text='Desde cuándo rige este precio.')
    date_end = fields.Date(
        null=True, blank=True, verbose_name='Fecha de fin',
        help_text='Hasta cuándo rige este precio.')
    product = fields.Many2one(
        ProductProduct, on_delete=models.CASCADE, null=True, blank=True,
        db_index=True, related_name='supplierinfo_ids',
        verbose_name='Variante de producto',
        help_text='Vacío = el precio aplica a TODAS las variantes de la '
                  'plantilla. Con valor, sólo a esa — y gana sobre la fila '
                  'de plantilla. El related_name no lo nombra la referencia.',
    )
    product_tmpl = fields.Many2one(
        ProductTemplate, on_delete=models.CASCADE, db_index=True,
        related_name='seller_ids', verbose_name='Plantilla de producto',
        help_text='Obligatorio. Odoo lo calcula desde la variante cuando sólo '
                  'se da ésta; aquí lo hace save().',
    )
    delay = fields.Integer(
        default=1, verbose_name='Plazo de entrega (días)',
        help_text='Días entre confirmar la compra y recibir la mercancía. El '
                  'planificador lo usa para calcular cuándo pedir.',
    )

    class Meta:
        db_table = 'product_supplierinfo'
        # Verbatim de _order: 'sequence, min_qty DESC, price, id'. El DESC de
        # min_qty es el que hace que el escalón por volumen se evalúe antes
        # que el de una unidad; invertirlo lo anularía.
        ordering = ['sequence', '-min_qty', 'price', 'id']
        verbose_name = 'Tarifa de proveedor'
        verbose_name_plural = 'Tarifas de proveedor'

    def __str__(self):
        return str(self.partner)

    # === INVARIANTES ======================================================

    def clean(self):
        """Las dos invariantes que la referencia declara sin escribir código.

        La primera es el ``@api.onchange('product_tmpl_id')``: si la variante
        deja de pertenecer a la plantilla, la fila apunta a dos productos
        distintos y su precio no significa nada. En la referencia el cliente
        web la limpia sola; aquí se rechaza, que es la versión de servidor de
        lo mismo — y la única que protege una escritura por API.

        La segunda es el ``check_company=True`` de tres campos: proveedor,
        producto y tarifa tienen que ser de la misma compañía. Django no tiene
        ese atributo, así que la comprobación es explícita.
        """
        super().clean()
        if self.product_id and self.product_tmpl_id \
                and self.product.product_tmpl_id != self.product_tmpl_id:
            raise ValidationError(
                'La variante no pertenece a la plantilla de esta tarifa.')
        if self.company_id:
            tmpl_company = getattr(self.product_tmpl, 'company_id', None)
            if tmpl_company and tmpl_company != self.company_id:
                raise ValidationError(
                    'El producto y la tarifa son de compañías distintas.')

    def save(self, *args, **kwargs):
        """``_sanitize_vals`` + ``_compute_product_uom_id``, en su sitio.

        La referencia reparte esto en tres piezas —un ``create``, un ``write``
        y un ``compute`` con ``precompute``— porque su ORM las necesita
        separadas. Aquí las tres ocurren en el único punto por el que pasa
        toda escritura, y hacen exactamente lo que hacían:

        - la plantilla se deduce de la variante cuando sólo se dio ésta
          (``_sanitize_vals``: sin ella la fila sería inguardable, porque
          ``product_tmpl_id`` es obligatorio);
        - la unidad del proveedor se siembra **sólo si está vacía**
          (``if not rec.product_uom_id`` de la fuente). Sembrarla siempre
          borraría la unidad que el proveedor realmente usa, que es el dato
          por el que el campo existe.
        """
        if self.product_id and not self.product_tmpl_id:
            self.product_tmpl = self.product.product_tmpl
        if not self.product_uom_id:
            source = self.product if self.product_id else self.product_tmpl
            self.product_uom = getattr(source, 'uom', None)
        super().save(*args, **kwargs)

    # === PRECIO ===========================================================

    @property
    def price_discounted(self):
        """``_compute_price_discounted`` — precio en la unidad del producto.

        Dos pasos, en el orden de la fuente: primero convertir de la unidad
        del proveedor a la del producto, después aplicar el descuento. Al
        revés daría lo mismo aquí, pero el orden es el que documenta qué
        significa el número: *"lo que cuesta una unidad de las nuestras"*.

        La conversión **no** llama a ``Uom.compute_price``: ese método
        multiplica por ``factor``, que es ``Float``, y ``Decimal * float``
        lanza ``TypeError``. Se reconstruye su ratio
        (``to_unit.factor / self.factor``, ``uom_uom.py:306-313``) en
        ``Decimal``, con sus mismos cortocircuitos.
        """
        price = self.price or decimal.Decimal(0)
        target = getattr(self.product if self.product_id else self.product_tmpl,
                         'uom', None)
        source = self.product_uom
        if price and target is not None and source is not None \
                and source != target:
            price = price * (
                decimal.Decimal(str(target.factor))
                / decimal.Decimal(str(source.factor))
            )
        discount = self.discount or decimal.Decimal(0)
        return price * (1 - discount / PERCENT_BASE)

    @property
    def product_variant_count(self):
        """``related='product_tmpl_id.product_variant_count'``."""
        return self.product_tmpl.product_variant_count

    # === SELECCIÓN ========================================================

    @classmethod
    def filtered_suppliers(cls, sellers, company, product):
        """``_get_filtered_supplier`` — las filas que sirven a esta compra.

        Tres condiciones, verbatim: la compañía encaja (o la fila es de
        todas), el proveedor está activo, y la fila no es específica de
        **otra** variante. La tercera es la que deja pasar las filas de
        plantilla junto a la de la variante pedida.

        Recibe el conjunto ya obtenido en vez de consultarlo: quien llama
        suele venir de ``product.seller_ids``, que ya está en memoria, y
        volver a la base sería una consulta por producto.
        """
        company_id = getattr(company, 'pk', company)
        product_id = getattr(product, 'pk', product)
        return [
            seller for seller in sellers
            if (not seller.company_id or seller.company_id == company_id)
            and getattr(seller.partner, 'active', True)
            and (not seller.product_id or seller.product_id == product_id)
        ]
