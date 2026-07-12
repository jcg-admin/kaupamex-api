"""
Serializers — apps.catalogue

ProductListSerializer: para listas compactas (index, search results).
ProductDetailSerializer: para el detalle completo de un producto.
ProductSearchSerializer: para el endpoint de búsqueda avanzada.
CategoryWithCountSerializer: para el árbol de categorías con conteo.
"""
import os
import random
import re
import uuid
from decimal import Decimal
from django.db import IntegrityError
from django.db.models import Avg, Q
from django.utils import timezone
from django.utils.text import slugify
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from apps.chartsize.serializers import ProductVariantPublicSerializer
from apps.questions.models import ProductQuestion, QuestionStatus
from apps.reviews.models import Review
from apps.settings_app.models import SiteSettings
from .models import Category, Product, ProductImage, ProductDiscount, ProductPriceHistory, SearchHistory


def _get_active_discount(product):
    """Return the active ProductDiscount or None.

    Reads from the prefetch cache when 'discounts' has been prefetched,
    avoiding an extra query per product in list views (API-1).
    """
    now = timezone.now()
    cache = getattr(product, '_prefetched_objects_cache', {})
    if 'discounts' in cache:
        candidates = [
            d for d in cache['discounts']
            if d.is_active
            and d.valid_from <= now
            and (d.valid_until is None or d.valid_until >= now)
        ]
        return max(candidates, key=lambda d: d.created_at, default=None)
    return (
        ProductDiscount.objects
        .filter(
            product=product,
            is_active=True,
            valid_from__lte=now,
        )
        .filter(Q(valid_until__isnull=True) | Q(valid_until__gte=now))
        .order_by('-created_at')
        .first()
    )


def _get_sale_price(product):
    """Return discounted price string if an active discount exists, else None."""
    discount = _get_active_discount(product)
    return str(discount.discounted_price) if discount else None


def _discount_block(product):
    """Build discount dict or None for use in serializers."""
    discount = _get_active_discount(product)
    if discount is None:
        return None
    # H-CICLO48-04: usar str() sobre Decimal en lugar de float() evita
    # errores de punto flotante en precios (ej. 1999.9999999 en vez de 2000).
    return {
        'pct': str(discount.discount_pct),
        'original_price': str(product.price),
        'discounted_price': str(discount.discounted_price),
        'valid_from': discount.valid_from,
        'valid_until': discount.valid_until,
    }


def _availability(product):
    """Return IN_STOCK or OUT_OF_STOCK."""
    return 'IN_STOCK' if product.stock > 0 else 'OUT_OF_STOCK'


def _price_with_tax(product):
    """Return price including IVA as Decimal string (no float rounding errors).

    H-CICLO49-01: usa SiteSettings.get_current().iva_rate en lugar de la
    constante TAX_RATE = Decimal('0.16') hardcodeada. Si el admin cambia
    la tasa IVA en Configuracion del sitio, el precio_con_IVA del catalogo
    queda desincronizado con el precio de las variantes (chartsize serializers
    usan SiteSettings). La inconsistencia producir discrepancias visibles en
    comparadores de precios. Se delega al mismo origen de verdad.
    """
    # H-CICLO48-04: Decimal * Decimal evita los errores de punto flotante que
    # producen valores como 1159.9999999999998 en lugar de 1160.00.
    iva = SiteSettings.get_current().iva_rate
    return str((product.price * (1 + iva)).quantize(Decimal('0.01')))


class ProductImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    image     = serializers.SerializerMethodField()

    class Meta:
        model  = ProductImage
        fields = ['id', 'image_url', 'image', 'alt_text', 'is_cover', 'order']

    @extend_schema_field(OpenApiTypes.STR)
    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url if obj.image else None

    @extend_schema_field(OpenApiTypes.STR)
    def get_image(self, obj):
        return self.get_image_url(obj)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model  = Category
        fields = ['id', 'name', 'slug', 'parent']


class ProductListSerializer(serializers.ModelSerializer):
    cover_image_url  = serializers.SerializerMethodField()
    # UC-CAT-13: M2M — return first category name for UI backwards compat.
    category_name    = serializers.SerializerMethodField()
    sale_price       = serializers.SerializerMethodField()
    base_price       = serializers.DecimalField(source='price', max_digits=10, decimal_places=2, read_only=True)
    price_with_tax   = serializers.SerializerMethodField()
    image            = serializers.SerializerMethodField()
    main_image       = serializers.SerializerMethodField()
    availability     = serializers.SerializerMethodField()
    variants_available = serializers.SerializerMethodField()
    discount         = serializers.SerializerMethodField()

    class Meta:
        model  = Product
        fields = [
            'id', 'name', 'slug', 'sku', 'base_price', 'price_with_tax',
            'sale_price', 'category_name', 'cover_image_url',
            'image', 'main_image',
            'is_active', 'is_published', 'is_featured',
            'availability', 'variants_available', 'discount',
            'stock',
        ]

    @extend_schema_field(OpenApiTypes.STR)
    def get_category_name(self, obj):
        prefetched = getattr(obj, '_prefetched_objects_cache', {}).get('categories')
        if prefetched is not None:
            cats = list(prefetched)
            return cats[0].name if cats else None
        first = obj.categories.order_by('id').first()
        return first.name if first else None

    @extend_schema_field(OpenApiTypes.STR)
    def get_sale_price(self, obj):
        return _get_sale_price(obj)

    @extend_schema_field(OpenApiTypes.STR)
    def get_price_with_tax(self, obj):
        return _price_with_tax(obj)

    def _get_cover_image(self, obj):
        # H-CICLO31-04: evitar N+1 usando el prefetch `images` cuando la vista
        # ya hizo prefetch_related('images'). La llamada a obj.images.filter(…)
        # dispara 1 query por producto en listas; con el prefetch en memoria solo
        # se itera la lista en Python.
        prefetched = getattr(obj, '_prefetched_objects_cache', {}).get('images')
        if prefetched is not None:
            images_list = list(prefetched)
            cover = next((img for img in images_list if img.is_cover), None)
            if not cover and images_list:
                cover = images_list[0]
            return cover
        # Fallback para acceso unitario (detail view): query directa.
        cover = obj.images.filter(is_cover=True).first()
        if not cover:
            cover = obj.images.first()
        return cover

    @extend_schema_field(OpenApiTypes.STR)
    def get_cover_image_url(self, obj):
        request = self.context.get('request')
        cover = self._get_cover_image(obj)
        if cover and cover.image:
            return request.build_absolute_uri(cover.image.url) if request else cover.image.url
        return None

    @extend_schema_field(OpenApiTypes.STR)
    def get_image(self, obj):
        request = self.context.get('request')
        cover = self._get_cover_image(obj)
        if cover and cover.image:
            return request.build_absolute_uri(cover.image.url) if request else cover.image.url
        return None

    @extend_schema_field(OpenApiTypes.STR)
    def get_main_image(self, obj):
        request = self.context.get('request')
        cover = self._get_cover_image(obj)
        if cover and cover.image:
            return request.build_absolute_uri(cover.image.url) if request else cover.image.url
        return None

    @extend_schema_field(OpenApiTypes.STR)
    def get_availability(self, obj):
        return _availability(obj)

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_variants_available(self, obj):
        cache = getattr(obj, '_prefetched_objects_cache', {})
        if 'variants' in cache:
            return any(v.is_active for v in cache['variants'])
        return obj.variants.filter(is_active=True).exists()

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_discount(self, obj):
        return _discount_block(obj)


class ProductDetailSerializer(serializers.ModelSerializer):
    images          = ProductImageSerializer(many=True, read_only=True)
    categories      = CategorySerializer(many=True, read_only=True)
    sale_price      = serializers.SerializerMethodField()
    base_price      = serializers.DecimalField(source='price', max_digits=10, decimal_places=2, read_only=True)
    price_with_tax  = serializers.SerializerMethodField()
    availability    = serializers.SerializerMethodField()
    discount        = serializers.SerializerMethodField()
    reviews_summary = serializers.SerializerMethodField()
    questions_count = serializers.SerializerMethodField()
    related_products = serializers.SerializerMethodField()
    variants        = serializers.SerializerMethodField()

    class Meta:
        model  = Product
        fields = [
            'id', 'name', 'slug', 'sku', 'description', 'short_description',
            'base_price', 'price_with_tax', 'sale_price',
            'categories', 'images', 'is_active', 'is_published', 'is_featured',
            'stock', 'availability', 'discount',
            'reviews_summary', 'questions_count', 'related_products',
            'variants',
            'created_at', 'updated_at',
        ]

    @extend_schema_field(OpenApiTypes.STR)
    def get_sale_price(self, obj):
        return _get_sale_price(obj)

    @extend_schema_field(OpenApiTypes.STR)
    def get_price_with_tax(self, obj):
        return _price_with_tax(obj)

    @extend_schema_field(OpenApiTypes.STR)
    def get_availability(self, obj):
        return _availability(obj)

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_discount(self, obj):
        return _discount_block(obj)

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_reviews_summary(self, obj):
        approved = Review.objects.filter(product=obj, status=Review.STATUS_APPROVED)
        count = approved.count()
        avg = approved.aggregate(avg=Avg('rating'))['avg']
        return {
            'average_rating': round(float(avg), 1) if avg is not None else None,
            'total_count': count,
        }

    @extend_schema_field(OpenApiTypes.INT)
    def get_questions_count(self, obj):
        return ProductQuestion.objects.filter(
            product=obj, status=QuestionStatus.ANSWERED
        ).count()

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_related_products(self, obj):
        # order_by('?') triggers a full-table filesort on MariaDB — too slow on
        # large catalogs.  Instead, fetch a slightly larger deterministic pool
        # and shuffle at the application level (O(n) Python vs O(n log n) SQL).
        # UC-CAT-13: filter by shared categories (any overlap) instead of single FK.
        pool = list(
            Product.objects
            .filter(categories__in=obj.categories.all(), is_active=True, is_published=True)
            .exclude(pk=obj.pk)
            .prefetch_related('images', 'discounts', 'variants', 'categories')
            .order_by('-id')
            .distinct()[:20]
        )
        random.shuffle(pool)
        qs = pool[:4]
        return ProductListSerializer(qs, many=True, context=self.context).data

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_variants(self, obj):
        qs = obj.variants.filter(is_active=True).select_related(
            'option', 'option__variant_type'
        ).order_by('option__variant_type__name', 'option__label')
        return ProductVariantPublicSerializer(qs, many=True).data


class ProductSearchSerializer(serializers.ModelSerializer):
    cover_image_url  = serializers.SerializerMethodField()
    # UC-CAT-13: M2M — return first category name for UI backwards compat.
    category_name    = serializers.SerializerMethodField()
    sale_price       = serializers.SerializerMethodField()
    base_price       = serializers.DecimalField(source='price', max_digits=10, decimal_places=2, read_only=True)
    price_with_tax   = serializers.SerializerMethodField()
    highlighted_name = serializers.SerializerMethodField()
    availability     = serializers.SerializerMethodField()
    discount         = serializers.SerializerMethodField()

    class Meta:
        model  = Product
        fields = [
            'id', 'name', 'slug', 'sku', 'base_price', 'price_with_tax',
            'sale_price', 'category_name', 'cover_image_url',
            'stock', 'availability', 'discount', 'highlighted_name',
            'is_featured',
        ]

    @extend_schema_field(OpenApiTypes.STR)
    def get_category_name(self, obj):
        prefetched = getattr(obj, '_prefetched_objects_cache', {}).get('categories')
        if prefetched is not None:
            cats = list(prefetched)
            return cats[0].name if cats else None
        first = obj.categories.order_by('id').first()
        return first.name if first else None

    @extend_schema_field(OpenApiTypes.STR)
    def get_sale_price(self, obj):
        return _get_sale_price(obj)

    @extend_schema_field(OpenApiTypes.STR)
    def get_price_with_tax(self, obj):
        return _price_with_tax(obj)

    @extend_schema_field(OpenApiTypes.STR)
    def get_cover_image_url(self, obj):
        request = self.context.get('request')
        # H-CICLO31-04: mismo patrón anti-N+1 que ProductListSerializer.
        prefetched = getattr(obj, '_prefetched_objects_cache', {}).get('images')
        if prefetched is not None:
            images_list = list(prefetched)
            cover = next((img for img in images_list if img.is_cover), None)
            if not cover and images_list:
                cover = images_list[0]
        else:
            cover = obj.images.filter(is_cover=True).first()
            if not cover:
                cover = obj.images.first()
        if cover and cover.image:
            return request.build_absolute_uri(cover.image.url) if request else cover.image.url
        return None

    @extend_schema_field(OpenApiTypes.STR)
    def get_highlighted_name(self, obj):
        q = self.context.get('search_term', '')
        if not q:
            return obj.name
        return re.sub(f'({re.escape(q)})', r'<em>\\1</em>', obj.name, flags=re.IGNORECASE)

    @extend_schema_field(OpenApiTypes.STR)
    def get_availability(self, obj):
        return _availability(obj)

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_discount(self, obj):
        return _discount_block(obj)


class CategoryWithCountSerializer(serializers.ModelSerializer):
    product_count = serializers.SerializerMethodField()
    children      = serializers.SerializerMethodField()

    class Meta:
        model  = Category
        fields = ['id', 'name', 'slug', 'parent', 'product_count', 'children']

    @extend_schema_field(OpenApiTypes.INT)
    def get_product_count(self, obj):
        if hasattr(obj, 'product_count'):
            return obj.product_count
        return obj.products.filter(is_active=True, is_published=True).count()

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_children(self, obj):
        return CategoryWithCountSerializer(obj.children.all(), many=True).data


class ProductAdminSerializer(serializers.ModelSerializer):
    images          = ProductImageSerializer(many=True, read_only=True)
    categories      = CategorySerializer(many=True, read_only=True)
    # UC-CAT-13: write via category_ids (list of PKs); read via categories (list of objects).
    category_ids    = serializers.PrimaryKeyRelatedField(
        source='categories', many=True, queryset=Category.objects.all(), required=False,
    )
    sale_price      = serializers.SerializerMethodField()
    base_price      = serializers.DecimalField(
        source='price', max_digits=10, decimal_places=2, min_value=Decimal('0.01'), required=False,
    )
    price_with_tax  = serializers.SerializerMethodField()
    related_products = serializers.SerializerMethodField()
    discount        = serializers.SerializerMethodField()

    # Gestión de costos — dato sensible: SOLO en el serializer admin.
    # `cost` es escribible; `margin`/`margin_pct` son read-only (calculados).
    cost            = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal('0'),
        required=False, allow_null=True,
    )
    margin          = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True,
    )
    margin_pct      = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True,
    )

    stock = serializers.IntegerField(min_value=0, required=False)

    # H-CICLO23-05: campo virtual `status` para compatibilidad con el formulario
    # del admin de UI. El formulario envía `status: 'PUBLICADO'|'BORRADOR'` pero
    # el modelo almacena `is_active` + `is_published`. Sin este campo el valor
    # enviado por la UI era ignorado silenciosamente por DRF, dejando el producto
    # siempre en BORRADOR (is_published=False) sin importar lo que el admin elija.
    #
    # Mapeo:
    #   PUBLICADO → is_active=True, is_published=True
    #   BORRADOR  → is_active=True, is_published=False  (default)
    status = serializers.ChoiceField(
        choices=['PUBLICADO', 'BORRADOR'],
        required=False,
        write_only=True,
        help_text='PUBLICADO activa el producto y lo publica; BORRADOR lo mantiene inactivo.',
    )

    class Meta:
        model  = Product
        fields = [
            'id', 'name', 'slug', 'sku', 'description', 'short_description',
            'base_price', 'price_with_tax', 'sale_price',
            'cost', 'margin', 'margin_pct',
            'categories', 'category_ids', 'images', 'is_active', 'is_published', 'is_featured',
            'stock', 'weight_kg', 'status', 'discount', 'related_products',
            'created_at', 'updated_at',
        ]
        extra_kwargs = {'slug': {'required': False}, 'name': {'required': True},
                        'description': {'max_length': 10000}, 'short_description': {'max_length': 500}}

    def validate_sku(self, value):
        return value.upper() if value else value

    def validate(self, attrs):
        if not self.instance and 'price' not in attrs:
            raise serializers.ValidationError({'base_price': 'Este campo es requerido.'})
        # H-CICLO23-05: expandir `status` virtual a `is_active` / `is_published`
        # antes de llegar a create/update. DRF no sabe nada de `status`
        # en el modelo, así que hay que convertirlo aquí.
        status_value = attrs.pop('status', None)
        if status_value == 'PUBLICADO':
            attrs['is_active'] = True
            attrs['is_published'] = True
        elif status_value == 'BORRADOR':
            attrs['is_active'] = True
            attrs['is_published'] = False
        # H-CICLO62-01: impedir publicar un producto sin imágenes.
        # Un producto publicado sin imagen aparece con imagen rota en el
        # catálogo (cover_image=None). La validación se aplica tanto al
        # path status='PUBLICADO' como a is_published=True directo.
        publishing = attrs.get('is_published', False)
        if publishing and self.instance and not self.instance.images.exists():
            raise serializers.ValidationError({
                'is_published': (
                    'No se puede publicar un producto sin imágenes. '
                    'Sube al menos una imagen antes de publicar.'
                ),
            })
        return attrs

    @extend_schema_field(OpenApiTypes.STR)
    def get_sale_price(self, obj):
        return _get_sale_price(obj)

    @extend_schema_field(OpenApiTypes.STR)
    def get_price_with_tax(self, obj):
        return _price_with_tax(obj)

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_related_products(self, obj):
        return None

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_discount(self, obj):
        return _discount_block(obj)

    def _auto_slug(self, name):
        base = slugify(name)
        # H-CICLO24-06: slugify() retorna cadena vacía para nombres que solo
        # contienen caracteres no-ASCII sin transliteración (p.ej. caracteres
        # CJK, emojis, cadenas solo con símbolos como "!!!"). En ese caso,
        # un slug vacío causaría IntegrityError por violación del NOT NULL +
        # UNIQUE en la columna, y el bucle while quedaría en estado indefinido
        # (slug='' siempre existiría). Se genera un fallback con prefijo + uuid.
        if not base:
            base = f'producto-{uuid.uuid4().hex[:8]}'
        slug = base
        n = 1
        while Product.objects.filter(slug=slug).exclude(
            pk=self.instance.pk if self.instance else None
        ).exists():
            slug = f'{base}-{n}'
            n += 1
        return slug

    def create(self, validated_data):
        if 'slug' not in validated_data or not validated_data.get('slug'):
            validated_data['slug'] = self._auto_slug(validated_data['name'])
        # H-CICLO56-03: guard against the TOCTOU race between _auto_slug's
        # .exists() check and the INSERT.  Two concurrent requests may both
        # pass the uniqueness loop with the same candidate slug and then one
        # will hit IntegrityError.  Retry once with a fresh uuid-suffixed slug
        # to handle this without surfacing a 500 to the caller.
        # H-CICLO59-01: the retry only fixes slug conflicts.  If the original
        # IntegrityError was caused by a duplicate SKU (concurrent request that
        # slipped past the view-level _check_sku_unique() TOCTOU window), the
        # retry will raise again on the same SKU constraint.  Catch that second
        # IntegrityError and surface it as a 400 ValidationError instead of a
        # 500 Internal Server Error.
        try:
            return super().create(validated_data)
        except IntegrityError:
            validated_data['slug'] = (
                f"{validated_data['slug']}-{uuid.uuid4().hex[:6]}"
            )
            try:
                return super().create(validated_data)
            except IntegrityError:
                raise serializers.ValidationError(
                    {'sku': 'Ya existe un producto con ese SKU (conflicto concurrente).'}
                )

    def validate_slug(self, value):
        # H-CICLO20-06: validar unicidad del slug en update antes de llegar
        # al DB. Sin esta validación un slug duplicado causa IntegrityError
        # (500) en lugar de ValidationError (400) cuando el admin edita un
        # producto y envía un slug ya ocupado por otro producto.
        if value:
            qs = Product.objects.filter(slug=value)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    f'El slug "{value}" ya está en uso por otro producto.'
                )
        return value

    def update(self, instance, validated_data):
        # H-CICLO70-06: slug must be immutable after creation.  Changing a
        # product slug breaks all existing bookmarks, shared links and any
        # external system that cached the URL.  Strip slug from PATCH/PUT
        # payloads so the backend silently ignores it even if a client sends
        # it.  Creation still generates a slug via _auto_slug().
        validated_data.pop('slug', None)
        return super().update(instance, validated_data)


class AutocompleteSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Product
        fields = ['id', 'name', 'slug']


class SearchHistorySerializer(serializers.ModelSerializer):
    searched_at = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model  = SearchHistory
        fields = ['id', 'term', 'searched_at']


_CATEGORY_IMAGE_MAX_MB = 5
_CATEGORY_IMAGE_ALLOWED_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
_CATEGORY_IMAGE_ALLOWED_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}


class _ParentStubSerializer(serializers.ModelSerializer):
    """Minimal representation of a parent category for admin list/detail."""
    class Meta:
        model  = Category
        fields = ['id', 'name']


class CategoryAdminSerializer(serializers.ModelSerializer):
    # H-CICLO67-03: `parent` was serialized as a raw PK integer (read_only FK).
    # AdminCategoriesPage.jsx reads `c.parent?.name` to display the parent
    # category name in the table — a plain integer has no `.name` property so
    # the column always rendered `—`.  Replace with a nested stub that exposes
    # {id, name}, keeping `parent_id` as the write-side writable FK field.
    parent = _ParentStubSerializer(read_only=True)
    parent_id = serializers.PrimaryKeyRelatedField(
        source='parent', queryset=Category.objects.all(), required=False, allow_null=True,
    )

    class Meta:
        model  = Category
        fields = ['id', 'name', 'slug', 'description', 'parent', 'parent_id', 'image', 'is_active', 'order']
        extra_kwargs = {'slug': {'required': False},
                        'description': {'max_length': 5000}}

    def validate_image(self, value):
        """Validate category image size and content-type."""
        if value is None:
            return value
        if value.size > _CATEGORY_IMAGE_MAX_MB * 1024 * 1024:
            raise serializers.ValidationError(
                f'La imagen no puede superar {_CATEGORY_IMAGE_MAX_MB} MB.'
            )
        ext = os.path.splitext(value.name or '')[1].lower()
        if ext not in _CATEGORY_IMAGE_ALLOWED_EXTS:
            raise serializers.ValidationError(
                f'Extensión no permitida: {ext or "(sin extensión)"}. '
                f'Usa JPEG, PNG, WebP o GIF.'
            )
        content_type = getattr(value, 'content_type', '') or ''
        if content_type and content_type.split(';')[0].strip() not in _CATEGORY_IMAGE_ALLOWED_TYPES:
            raise serializers.ValidationError(
                f'Tipo de contenido no permitido: {content_type}. '
                f'Usa image/jpeg, image/png, image/webp o image/gif.'
            )
        return value

    def validate(self, attrs):
        new_parent = attrs.get('parent', self.instance.parent if self.instance else None)
        if self.instance and new_parent is not None:
            if self.instance.would_create_cycle(new_parent):
                raise serializers.ValidationError({
                    'parent_id': 'Esta asignación crearía un ciclo en la jerarquía.',
                    'codigo_error': 'CYCLE_IN_HIERARCHY',
                })
        return attrs


class ProductPriceHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model  = ProductPriceHistory
        fields = ['id', 'old_price', 'new_price', 'source', 'changed_by', 'created_at']
