"""
Models — apps.catalogue

Sprints 4-9. Refactorizado en sprint de infraestructura: herencia-modelos-django
  Product       → TimeStampedModel (refactor puro, sin migración)
  Category      → TimeStampedModel (migración 0006: ADD created_at + updated_at)
  SearchHistory → TimeStampedModel (migración 0006: RENAME searched_at→updated_at + ADD created_at)
                  API mantiene el campo como 'searched_at' via source='updated_at' en serializer.
  ProductImage  → TimeStampedModel (migración 0006: ADD created_at + updated_at)
"""
import threading
from decimal import Decimal
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from apps.core.models import SoftDeleteModel, TimeStampedModel
from apps.catalogue.utils import category_upload_path, product_image_upload_path




class Category(TimeStampedModel):
    """Categoría del catálogo con árbol jerárquico. UC-CAT-04/05/06."""
    name        = models.CharField(max_length=100, unique=True)
    slug        = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, default='')
    parent      = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='children',
    )
    image       = models.ImageField(upload_to=category_upload_path, null=True, blank=True)
    is_active   = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table     = 'catalogue_category'
        ordering     = ['name']
        verbose_name = 'Categoría'

    def __str__(self):
        return self.name

    def would_create_cycle(self, new_parent) -> bool:
        """
        Verifica si asignar new_parent como padre crearía un ciclo en el árbol.
        Retorna True si hay ciclo (no permitido), False si es seguro.
        """
        if new_parent is None:
            return False
        if new_parent.pk == self.pk:
            return True
        # Verificar si self es ancestro de new_parent
        ancestor = new_parent
        while ancestor.parent_id is not None:
            if ancestor.parent_id == self.pk:
                return True
            ancestor = ancestor.parent
        return False

    def get_descendants_ids(self):
        """
        Retorna el set de PKs de esta categoría y todos sus descendientes activos.
        FR-CAT-04.02: incluye la propia categoría (self) y todos sus hijos recursivos.
        """
        ids = {self.pk}
        queue = list(self.children.filter(is_active=True).values_list('pk', flat=True))
        while queue:
            child_id = queue.pop()
            ids.add(child_id)
            queue.extend(
                Category.objects.filter(parent_id=child_id, is_active=True)
                .values_list('pk', flat=True)
            )
        return ids


class Product(TimeStampedModel, SoftDeleteModel):
    """Producto del catálogo. UC-CAT-01/02/09/10/11/12.

    Hereda de SoftDeleteModel (DEC-DOC-007): el borrado fisico esta
    prohibido — se preserva historial via ``is_deleted`` + ``deleted_at``.
    """
    name              = models.CharField(max_length=200)
    slug              = models.SlugField(max_length=220, unique=True)
    sku               = models.CharField(max_length=50, unique=True, db_index=True)
    description       = models.TextField(blank=True, default='')
    short_description = models.TextField(max_length=300, blank=True, default='')
    categories        = models.ManyToManyField(
        Category, related_name='products', blank=False,
    )
    price             = models.DecimalField(max_digits=10, decimal_places=2)
    # Costo unitario — dato sensible de negocio. Solo se expone vía serializers
    # admin; NUNCA en la API pública de catálogo (ver Gestión de costos).
    cost              = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0'))],
    )
    stock             = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    is_active         = models.BooleanField(default=True, db_index=True)
    is_published      = models.BooleanField(default=False, db_index=True)
    is_featured       = models.BooleanField(default=False, db_index=True)
    # Columna auxiliar para búsqueda fulltext (MariaDB usa FULLTEXT INDEX, no tsvector)
    # El índice FULLTEXT real está en la migración 0002 sobre name+description+short_description
    search_vector     = models.TextField(null=True, blank=True)

    class Meta:
        db_table     = 'catalogue_product'
        ordering     = ['-created_at']
        verbose_name = 'Producto'

    def __str__(self):
        return self.name

    @property
    def margin(self):
        """Margen bruto unitario: ``price - cost`` (sobre el precio base, no
        el precio con descuento). Retorna ``None`` si ``cost`` es nulo."""
        if self.cost is None:
            return None
        return self.price - self.cost

    @property
    def margin_pct(self):
        """Margen porcentual: ``(price - cost) / price * 100`` sobre el precio
        base. Retorna ``None`` si ``cost`` es nulo o ``price`` es cero
        (guarda contra división por cero)."""
        if self.cost is None or not self.price:
            return None
        return (self.price - self.cost) / self.price * Decimal('100')


class SearchHistory(TimeStampedModel):
    """
    Historial de búsquedas del usuario. UC-SRCH-03.
    Upsert por (user, term): cada búsqueda actualiza updated_at.

    H-INH-002: el campo fue renombrado de searched_at a updated_at
    internamente. La API mantiene el nombre 'searched_at' via
    source='updated_at' en SearchHistorySerializer (backward compatible).
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='search_history',
    )
    term = models.CharField(max_length=200)

    class Meta:
        db_table     = 'catalogue_search_history'
        constraints  = [
            models.UniqueConstraint(
                fields=['user', 'term'],
                name='unique_search_history_user_term',
            )
        ]
        ordering     = ['-updated_at']
        verbose_name = 'Historial de búsqueda'

    def __str__(self):
        return f'{self.user.username}: "{self.term}"'

    @classmethod
    def record(cls, user, term: str) -> None:
        """
        Crea o actualiza el registro de búsqueda.
        Mantiene un máximo de 20 términos por usuario eliminando el más antiguo.
        """
        obj, created = cls.objects.get_or_create(
            user=user, term=term,
            defaults={},
        )
        if not created:
            # Forzar actualización de updated_at (auto_now)
            obj.save(update_fields=['updated_at'])

        def trim():
            qs = cls.objects.filter(user=user).order_by('updated_at')
            count = qs.count()
            if count > 20:
                oldest_ids = list(qs.values_list('pk', flat=True)[:count - 20])
                cls.objects.filter(pk__in=oldest_ids).delete()

        # Ejecutar trim de forma síncrona para garantizar consistencia
        # El costo es mínimo: 1 COUNT + 1 DELETE cuando count > 20
        trim()


class ProductDiscount(TimeStampedModel, SoftDeleteModel):
    """
    Product-level discount (UC-DASH-01..04).

    Hereda de SoftDeleteModel (DEC-DOC-007). Coexisten dos semánticas:

    - ``is_active`` / ``deactivated_at`` / ``deactivated_by``:
      desactivacion de NEGOCIO (el admin marca la promocion como
      no-aplicable; sigue listada en reportes y en el historial de
      precios aplicados a las ordenes pasadas).
    - ``is_deleted`` / ``deleted_at``: borrado LOGICO de SISTEMA.
      Fuera del manager por defecto pero recuperable via
      ``ProductDiscount.all_objects`` para auditoria.

    Distinto de Voucher (apps.voucher): no tiene codigo y se aplica
    automaticamente al render del producto en catalogo. Una sola
    promocion activa por producto a la vez (la mas reciente con
    valid_from <= now <= valid_until y is_active=True).

    Status derivado:
      CURRENT  — is_active y valid_from <= now y (valid_until None o now <= valid_until)
      FUTURE   — is_active y now < valid_from
      EXPIRED  — is_active y valid_until y now > valid_until
      INACTIVE — is_active=False (no expuesto en filtros UI)
    """
    product       = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='discounts',
    )
    discount_pct  = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01')),
                    MaxValueValidator(Decimal('100.00'))],
        help_text='Porcentaje de descuento (0.01 - 100).',
    )
    valid_from    = models.DateTimeField(db_index=True)
    valid_until   = models.DateTimeField(null=True, blank=True, db_index=True)
    is_active     = models.BooleanField(default=True, db_index=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    deactivated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='deactivated_product_discounts',
    )
    created_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='created_product_discounts',
    )

    class Meta:
        db_table     = 'catalogue_product_discount'
        ordering     = ['-created_at']
        verbose_name = 'Descuento de producto'
        indexes = [
            models.Index(fields=['product', 'is_active']),
        ]

    def __str__(self):
        return f'{self.product.sku} -{self.discount_pct}% ({self.status})'

    @property
    def status(self) -> str:
        if not self.is_active:
            return 'INACTIVE'
        now = timezone.now()
        if now < self.valid_from:
            return 'FUTURE'
        if self.valid_until and now > self.valid_until:
            return 'EXPIRED'
        return 'CURRENT'

    @property
    def discounted_price(self) -> Decimal:
        original = self.product.price
        factor = (Decimal('100.00') - self.discount_pct) / Decimal('100')
        return (original * factor).quantize(Decimal('0.01'))


class AttributeAxis(TimeStampedModel):
    """Eje de clasificación de atributos: Orisha, Color, Material, etc. ADR-012 EJE 2."""
    name          = models.CharField(max_length=100, unique=True)
    slug          = models.SlugField(unique=True)
    is_filterable = models.BooleanField(default=True)
    display_order = models.IntegerField(default=0)
    is_active     = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'catalogue_attribute_axis'
        ordering = ['display_order', 'name']
        verbose_name = 'Eje de atributo'

    def __str__(self):
        return self.name


class AttributeValue(TimeStampedModel):
    """Valor de un eje de atributo. Jerarquía opcional vía parent (ej. Yemayá → caminos)."""
    axis          = models.ForeignKey(
        AttributeAxis, on_delete=models.CASCADE, related_name='values',
    )
    value         = models.CharField(max_length=100)
    slug          = models.SlugField()
    parent        = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='children',
    )
    display_order = models.IntegerField(default=0)

    class Meta:
        db_table     = 'catalogue_attribute_value'
        constraints  = [
            models.UniqueConstraint(
                fields=['axis', 'value'],
                name='unique_attribute_value_axis_value',
            ),
            models.UniqueConstraint(
                fields=['axis', 'slug'],
                name='unique_attribute_value_axis_slug',
            ),
        ]
        ordering     = ['axis', 'display_order', 'value']
        verbose_name = 'Valor de atributo'

    def __str__(self):
        return f'{self.axis.name}: {self.value}'

    def would_create_cycle(self, new_parent) -> bool:
        """
        Returns True if assigning new_parent would create a cycle in the
        value hierarchy. Used before setting self.parent to reject invalid
        assignments (e.g. Yemayá → parent Mayelewo → parent Yemayá).
        """
        if new_parent is None:
            return False
        if new_parent.pk == self.pk:
            return True
        ancestor = new_parent
        while ancestor.parent_id is not None:
            if ancestor.parent_id == self.pk:
                return True
            ancestor = ancestor.parent
        return False


class ProductAttribute(models.Model):
    """Asociación Product ↔ AttributeValue. ADR-012 EJE 2."""
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='attributes',
    )
    value   = models.ForeignKey(
        AttributeValue, on_delete=models.CASCADE, related_name='products',
    )

    class Meta:
        db_table     = 'catalogue_product_attribute'
        constraints  = [
            models.UniqueConstraint(
                fields=['product', 'value'],
                name='unique_product_attribute',
            )
        ]
        indexes      = [
            models.Index(fields=['value']),
            models.Index(fields=['product', 'value']),
        ]
        verbose_name = 'Atributo de producto'

    def __str__(self):
        return f'{self.product.sku} — {self.value}'


class ProductImage(TimeStampedModel):
    """Imagen asociada a un producto. UC-CAT-09."""
    product  = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image    = models.ImageField(upload_to=product_image_upload_path)
    alt_text = models.CharField(max_length=200, blank=True, default='')
    order    = models.PositiveSmallIntegerField(default=0)
    is_cover = models.BooleanField(default=False)

    class Meta:
        db_table     = 'catalogue_product_image'
        ordering     = ['order', 'id']
        verbose_name = 'Imagen de producto'

    def __str__(self):
        return f'{self.product.name} — imagen {self.order}'


class ProductPriceHistory(TimeStampedModel):
    """
    Historial de cambios de precio de productos. UC-CAT-10 (RNF 6.3).
    Creado en cada mutación de Product.price vía admin manual o CSV sync.
    """
    MANUAL     = 'MANUAL'
    PRICE_SYNC = 'PRICE_SYNC'
    SOURCE_CHOICES = [
        (MANUAL,     'Ajuste manual'),
        (PRICE_SYNC, 'Sincronización CSV'),
    ]

    product    = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='price_history',
    )
    old_price  = models.DecimalField(max_digits=10, decimal_places=2)
    new_price  = models.DecimalField(max_digits=10, decimal_places=2)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='product_price_changes',
    )
    source     = models.CharField(
        max_length=20, choices=SOURCE_CHOICES, default=MANUAL,
    )

    class Meta:
        db_table     = 'catalogue_product_price_history'
        ordering     = ['-created_at']
        verbose_name = 'Historial de precio'

    def __str__(self):
        return f'{self.product.sku}: {self.old_price}→{self.new_price}'
