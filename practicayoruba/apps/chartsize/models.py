"""
Models — apps.chartsize

Sprint 9 — UC-CHT-01, UC-CHT-02, UC-CHT-03, UC-CHT-04

Modelo CHARTSIZE: VariantType → VariantOption → ProductVariant
El diagrama canonico esta en modelo-chartsize.rst.
"""
from decimal import Decimal
from django.db import models
from apps.core.models import SoftDeleteModel, TimeStampedModel
from django.core.validators import MinValueValidator
from django.utils.text import slugify



class VariantType(TimeStampedModel, SoftDeleteModel):
    """
    Tipo de atributo de variante. Ej: 'Tamaño', 'Presentación'.
    Un producto puede tener uno o más tipos de variante.
    UC-CHT-03.

    Hereda de SoftDeleteModel (DEC-DOC-007). ``is_active`` representa
    visibilidad de NEGOCIO; ``is_deleted`` representa borrado LOGICO
    de SISTEMA y preserva el historial referenciado en ordenes pasadas.
    """
    product   = models.ForeignKey(
        'catalogue.Product', on_delete=models.CASCADE,
        related_name='variant_types',
    )
    name      = models.CharField(max_length=100,
                    verbose_name='Nombre del atributo')
    is_active = models.BooleanField(default=True)
    order     = models.PositiveSmallIntegerField(default=0, db_index=True,
                    verbose_name='Orden de presentacion')

    class Meta:
        db_table     = 'chartsize_variant_type'
        ordering     = ['order', 'name']
        unique_together = [('product', 'name')]
        verbose_name = 'Tipo de variante'

    def __str__(self):
        return f'{self.product.name} — {self.name}'


class VariantOption(TimeStampedModel, SoftDeleteModel):
    """
    Opcion dentro de un tipo de variante. Ej: 'Grande', '250ml'.
    UC-CHT-03.

    Hereda de SoftDeleteModel (DEC-DOC-007). Las opciones quedan
    referenciadas desde ProductVariant via CASCADE: un borrado fisico
    arruinaria el historial de pedidos. Preservar la fila con
    ``is_deleted=True`` permite que las consultas administrativas
    sigan reconstruyendo la variante exacta de cada orden pasada.
    """
    variant_type = models.ForeignKey(
        VariantType, on_delete=models.CASCADE,
        related_name='options',
    )
    label    = models.CharField(max_length=100, verbose_name='Etiqueta visible')
    slug     = models.SlugField(max_length=120, verbose_name='Slug URL')
    is_active = models.BooleanField(default=True)
    order    = models.PositiveSmallIntegerField(default=0, db_index=True)

    class Meta:
        db_table        = 'chartsize_variant_option'
        ordering        = ['order', 'label']
        unique_together = [('variant_type', 'label'), ('variant_type', 'slug')]
        verbose_name    = 'Opcion de variante'

    def __str__(self):
        return f'{self.variant_type.name}: {self.label}'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.label)
        super().save(*args, **kwargs)


class ProductVariant(TimeStampedModel, SoftDeleteModel):
    """
    Variante concreta de un producto. Combina producto + opcion de variante.
    UC-CHT-01, UC-CHT-03, UC-CHT-04.

    Hereda de SoftDeleteModel (DEC-DOC-007). ``is_active`` codifica la
    visibilidad de NEGOCIO (la variante ya no se ofrece); ``is_deleted``
    codifica el borrado LOGICO de SISTEMA. Mantener la fila preserva la
    coherencia de OrderItem / Cart histórico cuando referencian la
    variante por id.

    El SKU completo de la variante es: Product.sku + '-' + sku_suffix
    (si sku_suffix esta en blanco, se usa el SKU del producto directamente).

    effective_price(): retorna price_override si existe, o el precio base del
    producto. UC-CHT-04 (FR-CHT-04.02).
    """
    product        = models.ForeignKey(
        'catalogue.Product', on_delete=models.CASCADE,
        related_name='variants',
    )
    option         = models.OneToOneField(
        VariantOption, on_delete=models.CASCADE,
        related_name='variant',
    )
    sku_suffix     = models.CharField(max_length=20, blank=True, default='',
                         verbose_name='Sufijo SKU',
                         help_text='Se concatena a Product.sku. Ej: GRD → COL-001-GRD')
    price_override = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Precio diferenciado',
        help_text='Si esta en blanco, se usa el precio base del producto.',
    )
    stock          = models.PositiveIntegerField(default=0,
                         verbose_name='Stock de la variante')
    is_active      = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table     = 'chartsize_product_variant'
        ordering     = ['option__order', 'option__label']
        verbose_name = 'Variante de producto'

    def __str__(self):
        return f'{self.product.name} — {self.option.label}'

    @property
    def sku(self) -> str:
        """SKU completo de la variante."""
        if self.sku_suffix:
            return f'{self.product.sku}-{self.sku_suffix}'
        return self.product.sku

    def effective_price(self) -> Decimal:
        """
        Precio efectivo: price_override si existe, precio base del producto si no.
        FR-CHT-04.02.
        """
        return self.price_override if self.price_override is not None else self.product.price

    def is_available(self) -> bool:
        """True si la variante esta activa y tiene stock > 0."""
        return self.is_active and self.stock > 0
