"""``product.product`` — la variante: lo que se almacena, se compra y se vende.

Adaptación de ``addons/product/models/product_product.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 1197 líneas). Si ``product.template``
es la ficha —"camiseta"—, esto es "camiseta roja talla M": la combinación
concreta de valores de atributo que apunta un movimiento de stock, una línea
de pedido o una capa de valoración.

``_inherits`` **no** es la herencia multi-tabla de Django
=========================================================

La referencia declara ``_inherits = {'product.template': 'product_tmpl_id'}``
— *delegación*: la variante lee los campos de su ficha de forma transparente.
La traducción tentadora es la herencia multi-tabla de Django
(``class ProductProduct(ProductTemplate)``), que también delega y también
genera un enlace al padre.

**Sería un error grave, y silencioso.** La herencia multi-tabla de Django crea
un ``OneToOneField(parent_link=True)``: **una** fila hija por fila padre. La
``_inherits`` de Odoo es un **Many2one** —``product_tmpl_id`` está declarado
así, explícitamente, en la línea 42 de la fuente— y todo el modelo depende de
que **muchas** variantes cuelguen de una ficha. Con la herencia de Django,
"camiseta" admitiría exactamente una variante y el addon entero perdería su
razón de ser, sin ningún error: las escrituras fallarían por clave duplicada
mucho después, en otro sitio.

Así que aquí es una **FK real** más **delegación por propiedad** para los
campos de la ficha que la referencia expone en la variante (``name``, ``categ``,
``uom``, ``list_price``, ``type``…). Es más verboso y es lo que hace la fuente.

Los tres campos que **la variante sobreescribe**
================================================

No todo se delega. La referencia redeclara tres campos en la variante, y
saberlo importa porque el valor de la ficha **deja de aplicar**:

- ``standard_price`` — el coste es por variante (y ``company_dependent``): dos
  tallas de la misma camiseta pueden costar distinto.
- ``volume`` y ``weight`` — el envío se calcula sobre lo que se mueve, que es
  la variante.

``combination_indices`` — la clave de la combinación
====================================================

Es ``store=True`` e indexado, y su cálculo es
``','.join(str(i) for i in sorted(self.ids))`` sobre los valores de atributo
(``product_template_attribute_value.py:166-167``). Dos detalles que se pierden
al reescribirlo:

- **``sorted``**: sin ordenar, la misma combinación elegida en distinto orden
  daría claves distintas y la búsqueda de "¿existe ya esta variante?" fallaría
  creando duplicados.
- **almacenado**: existe para poder **buscar** una combinación en una consulta
  en vez de recorrer las variantes en Python.

Qué NO se porta, con su medición
================================

- **``_inherit = ['mail.thread', 'mail.activity.mixin']``** — mismo criterio
  que ``product_template.py``.
- **``price_extra`` / ``lst_price``** como columnas: en la referencia son
  ``compute`` sin ``store``. Aquí son propiedades — ``price_extra`` suma el
  extra de los valores de atributo, y ``lst_price`` es el precio de la ficha
  más ese extra. La conversión de unidad que ``lst_price`` hace por contexto
  (``depends_context=('uom',)``) **no** se porta: este archivo no conoce el
  contexto de la petición, y la conversión ya la sabe hacer ``Uom``.
- **``code`` / ``partner_ref``** — **cerrados**, con un cambio de forma. La
  referencia los declara ``compute`` con ``@api.depends_context('partner_id')``:
  el mismo producto muestra un código distinto según **quién** pregunta, y ese
  "quién" viaja en el contexto de la petición. Aquí no hay ese contexto, así
  que la clave del contexto pasa a ser un **argumento**: ``code_for(partner)``
  y ``partner_ref_for(partner)``. No es una degradación — es la misma
  dependencia, escrita donde se puede ver. El gate de acceso de lectura sobre
  ``product.supplierinfo`` no viaja con ellos: la autorización aquí es por
  capacidad (DEC-11) y la decide la vista, no el modelo.
- **``_check_barcode_uniqueness``** — **cerrado**. La referencia exige el
  código único y compartido con el de los empaquetados, porque la
  nomenclatura GS1 usa el mismo patrón para los dos. La unicidad de esta tabla
  está en su ``UniqueConstraint``; la mitad cruzada la aporta
  ``product_uom.py``, que ya está portado y comprueba en su ``clean()`` que
  ninguna variante use el código. El destino estaba fechado y se cumplió sin
  tocar este archivo.
- **``product_document_ids``**: reverso hacia ``product_document.py``, aún sin
  portar. Aparece solo cuando ese archivo declare su ``related_name``, sin
  tocar éste — igual que ``report_paperformat.report_ids`` (H-API-164).
  ``product_uom_ids``, ``pricelist_rule_ids`` y
  ``additional_product_tag_ids`` **ya llegaron** así, desde
  ``product_uom.py``, ``product_pricelist_item.py`` y ``product_tag.py``
  respectivamente — ninguno necesitó una línea aquí.
"""
import fields
import models
from django.core.exceptions import ValidationError

from addons.base.models.timestamped_mixin import TimeStampedModel
from addons.product.models.product_template import ProductTemplate
from addons.product.models.product_template_attribute_value import (
    ProductTemplateAttributeValue,
)

#: Separador de la clave de combinación, verbatim de ``_ids2str``.
COMBINATION_SEPARATOR = ','


class ProductProduct(TimeStampedModel):
    """``product.product`` — una combinación concreta de la ficha."""

    product_tmpl = fields.Many2one(
        ProductTemplate, on_delete=models.CASCADE, db_index=True,
        related_name='product_variant_ids', verbose_name='Ficha de producto',
        help_text='Odoo product_tmpl_id. FK real, NO herencia multi-tabla: '
                  'muchas variantes por ficha. Ver el docstring del módulo.',
    )
    default_code = fields.Char(
        max_length=64, blank=True, default='', db_index=True,
        verbose_name='Referencia interna')
    barcode = fields.Char(
        max_length=64, blank=True, default='', db_index=True,
        verbose_name='Código de barras',
        help_text='Número de artículo internacional. Único por compañía.',
    )
    active = fields.Boolean(
        default=True, verbose_name='Activo',
        help_text='Desmarcar oculta la variante sin borrarla.')
    combination_indices = fields.Char(
        max_length=255, blank=True, default='', db_index=True,
        verbose_name='Índices de la combinación',
        help_text='Ids de los valores de atributo, ORDENADOS y separados por '
                  'coma. Almacenado para poder buscar una combinación en una '
                  'consulta.',
    )
    product_template_attribute_values = fields.Many2many(
        ProductTemplateAttributeValue, blank=True,
        db_table='product_variant_combination',
        related_name='product_variant_ids',
        verbose_name='Valores de atributo',
    )
    # Los tres que la variante SOBREESCRIBE — el valor de la ficha no aplica.
    standard_price = fields.Monetary(
        max_digits=16, decimal_places=2, default=0, verbose_name='Coste',
        help_text='Coste POR VARIANTE: dos tallas pueden costar distinto. '
                  'Sobreescribe el de la ficha.',
    )
    volume = fields.Float(
        default=0, verbose_name='Volumen',
        help_text='Sobreescribe el de la ficha: el envío se calcula sobre lo '
                  'que se mueve.',
    )
    weight = fields.Float(
        default=0, verbose_name='Peso',
        help_text='Sobreescribe el de la ficha, por la misma razón.')

    class Meta:
        db_table = 'product_product'
        ordering = ['default_code', 'id']
        verbose_name = 'Variante de producto'
        verbose_name_plural = 'Variantes de producto'
        constraints = [
            # ``_check_barcode_uniqueness`` — la mitad que cabe en la tabla.
            # La otra mitad (que tampoco lo use un empaquetado) la aporta
            # ``product_uom.clean()``, que ya está portado.
            models.UniqueConstraint(
                fields=['barcode'],
                condition=~models.Q(barcode=''),
                name='product_product_barcode_uniq',
            ),
        ]

    def __str__(self):
        return f'[{self.default_code}] {self.display_name}' \
            if self.default_code else self.display_name

    # === DELEGACIÓN A LA FICHA ===========================================
    # La ``_inherits`` de la referencia hace esto transparente; aquí es
    # explícito, que es el precio de no poder usar la herencia de Django.

    @property
    def name(self):
        """El nombre de la ficha (delegado por ``_inherits``)."""
        return self.product_tmpl.name

    @property
    def categ(self):
        """La categoría de la ficha."""
        return self.product_tmpl.categ

    @property
    def uom(self):
        """La unidad de medida de la ficha."""
        return self.product_tmpl.uom

    @property
    def type(self):
        """El tipo de producto de la ficha."""
        return self.product_tmpl.type

    @property
    def company(self):
        """La compañía de la ficha."""
        return self.product_tmpl.company

    @property
    def list_price(self):
        """El precio de catálogo de la ficha, **sin** el extra de la variante.

        El precio que se cobra es ``lst_price``, que suma el extra. Se
        conservan los dos nombres de la referencia porque distinguen
        exactamente eso.
        """
        return self.product_tmpl.list_price

    @property
    def is_product_variant(self):
        """``_compute_is_product_variant`` — aquí siempre verdadero.

        La contraparte de la propiedad homónima de ``ProductTemplate``, que
        siempre devuelve falso. Existen para que un mismo código pueda recibir
        cualquiera de los dos y saber cuál tiene.
        """
        return True

    # === COMBINACIÓN =====================================================

    @staticmethod
    def build_combination_indices(attribute_values):
        """``_ids2str`` — la clave de una combinación.

        Los ids **ordenados** y unidos por coma. El ``sorted`` no es estética:
        sin él, la misma combinación elegida en distinto orden daría claves
        distintas y la comprobación de "¿existe ya esta variante?" crearía
        duplicados.
        """
        ids = sorted(
            getattr(value, 'pk', value) for value in attribute_values)
        return COMBINATION_SEPARATOR.join(str(pk) for pk in ids)

    def refresh_combination_indices(self):
        """``_compute_combination_indices`` — recalcula desde los valores."""
        self.combination_indices = self.build_combination_indices(
            self.product_template_attribute_values.all())
        return self.combination_indices

    @property
    def display_name(self):
        """``_get_combination_name`` — nombre de la ficha más su combinación.

        La referencia **excluye** los valores de líneas con un solo valor: si
        todas las camisetas son de algodón, poner "(Algodón)" en cada variante
        no distingue nada y sólo alarga el nombre. Se conserva ese filtro.
        """
        base = self.product_tmpl.name
        parts = [
            str(value)
            for value in self.product_template_attribute_values.all()
            if getattr(value, 'is_distinguishing', True)
        ]
        return f'{base} ({", ".join(parts)})' if parts else base

    # === PRECIO ===========================================================

    @property
    def price_extra(self):
        """``_compute_product_price_extra`` — suma del extra de los atributos.

        Un valor de atributo puede encarecer la variante (talla XXL, madera
        noble). Es la suma, no el máximo: los extras se acumulan.
        """
        return sum(
            (getattr(value, 'price_extra', 0) or 0)
            for value in self.product_template_attribute_values.all()
        )

    @property
    def lst_price(self):
        """``_compute_product_lst_price`` — precio de catálogo **más** el extra.

        La conversión de unidad que la referencia hace por contexto no se
        porta; ver el docstring del módulo.
        """
        return self.list_price + self.price_extra

    # === IDENTIFICACIÓN ANTE UN PROVEEDOR =================================
    # ``_compute_product_code`` y ``_compute_partner_ref`` de la referencia,
    # con el ``partner_id`` del contexto convertido en argumento.

    def code_for(self, partner):
        """``_compute_product_code`` — el código con que **este** proveedor
        conoce la variante.

        El bucle **no corta en la primera coincidencia**, y eso es el corazón
        del método: recorre las tarifas del proveedor quedándose con la última
        que encaja, y sólo rompe cuando encuentra la que es específica de esta
        variante. Así una fila de plantilla ("camiseta = REF-100") queda
        pisada por la de la variante ("camiseta roja M = REF-100-RM") cuando
        existe, y se ignora la que es específica de **otra** variante.

        Sin proveedor, o sin tarifa suya, devuelve la referencia interna.
        """
        code = self.default_code
        partner_id = getattr(partner, 'pk', partner)
        if not partner_id:
            return code
        for seller in self.product_tmpl.seller_ids.all():
            if seller.partner_id != partner_id:
                continue
            if seller.product_id and seller.product_id != self.pk:
                continue        # tarifa específica de otra variante
            code = seller.product_code or self.default_code
            if seller.product_id == self.pk:
                break           # específica de ésta: manda y termina
        return code

    def partner_ref_for(self, partner):
        """``_compute_partner_ref`` — cómo se nombra la variante ante él.

        ``[CÓDIGO] Nombre``, donde las dos mitades salen de la tarifa del
        proveedor si la tiene. El ``for/else`` de la fuente se conserva tal
        cual: sin tarifa suya, el nombre es el de siempre — no una versión
        vacía del formato.
        """
        partner_id = getattr(partner, 'pk', partner)
        for seller in self.product_tmpl.seller_ids.all():
            if seller.partner_id != partner_id:
                continue
            name = seller.product_name or self.default_code or self.name
            code = self.code_for(partner)
            return f'[{code}] {name}' if code else name
        return self.display_name

    def clean(self):
        """La variante no puede colgar de una ficha de tipo combo.

        Un combo agrupa otros productos: no tiene variantes propias, y
        permitirlas daría una combinación de atributos sobre algo que no es
        un artículo.
        """
        super().clean()
        if self.product_tmpl_id and self.product_tmpl.type == 'combo':
            raise ValidationError(
                'Un combo no tiene variantes: sus componentes las tienen.')
