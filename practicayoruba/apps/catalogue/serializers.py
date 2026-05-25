"""
Serializers — apps.catalogue

ProductListSerializer: para listas compactas (index, search results).
ProductDetailSerializer: para el detalle completo de un producto.
ProductSearchSerializer: para el endpoint de búsqueda avanzada.
CategoryWithCountSerializer: para el árbol de categorías con conteo.
"""
from decimal import Decimal
from django.db.models import Avg, Q
from django.utils import timezone
from rest_framework import serializers
from .models import Category, Product, ProductImage, ProductDiscount, ProductPriceHistory, SearchHistory


TAX_RATE = Decimal('0.16')  # 16% IVA


def _get_active_discount(product):
    \"\"\"Return the active ProductDiscount or None.\"\"\"
    now = timezone.now()
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
    \"\"\"Return discounted price string if an active discount exists, else None.\"\"\"
    discount = _get_active_discount(product)
    return str(discount.discounted_price) if discount else None


def _discount_block(product):
    \"\"\"Build discount dict or None for use in serializers.\"\"\"
    discount = _get_active_discount(product)
    if discount is None:
        return None
    return {
        'pct': float(discount.discount_pct),
        'original_price': float(product.price),
        'discounted_price': float(discount.discounted_price),
        'valid_from': discount.valid_from,
        'valid_until': discount.valid_until,
    }


def _availability(product):
    \"\"\"Return IN_STOCK or OUT_OF_STOCK.\"\"\"
    return 'IN_STOCK' if product.stock > 0 else 'OUT_OF_STOCK'


def _price_with_tax(product):
    \"\"\"Return price including 16% IVA.\"\"\"
    return float(product.price * (1 + TAX_RATE))


class ProductImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    image     = serializers.SerializerMethodField()

    class Meta:
        model  = ProductImage
        fields = ['id', 'image_url', 'image', 'alt_text', 'is_cover', 'order']

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url if obj.image else None

    def get_image(self, obj):
        return self.get_image_url(obj)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model  = Category
        fields = ['id', 'name', 'slug', 'parent']


class ProductListSerializer(serializers.ModelSerializer):
    cover_image_url  = serializers.SerializerMethodField()
    category_name    = serializers.CharField(source='category.name', read_only=True)
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

    def get_sale_price(self, obj):
        return _get_sale_price(obj)

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

    def get_cover_image_url(self, obj):
        request = self.context.get('request')
        cover = self._get_cover_image(obj)
        if cover and cover.image:
            return request.build_absolute_uri(cover.image.url) if request else cover.image.url
        return None

    def get_image(self, obj):
        request = self.context.get('request')
        cover = self._get_cover_image(obj)
        if cover and cover.image:
            return request.build_absolute_uri(cover.image.url) if request else cover.image.url
        return None

    def get_main_image(self, obj):
        request = self.context.get('request')
        cover = self._get_cover_image(obj)
        if cover and cover.image:
            return request.build_absolute_uri(cover.image.url) if request else cover.image.url
        return None

    def get_availability(self, obj):
        return _availability(obj)

    def get_variants_available(self, obj):
        return obj.variants.filter(is_active=True).exists()

    def get_discount(self, obj):
        return _discount_block(obj)


class ProductDetailSerializer(serializers.ModelSerializer):
    images          = ProductImageSerializer(many=True, read_only=True)
    category        = CategorySerializer(read_only=True)
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
            'category', 'images', 'is_active', 'is_published', 'is_featured',
            'stock', 'availability', 'discount',
            'reviews_summary', 'questions_count', 'related_products',
            'variants',
            'created_at', 'updated_at',
        ]

    def get_sale_price(self, obj):
        return _get_sale_price(obj)

    def get_price_with_tax(self, obj):
        return _price_with_tax(obj)

    def get_availability(self, obj):
        return _availability(obj)

    def get_discount(self, obj):
        return _discount_block(obj)

    def get_reviews_summary(self, obj):
        from apps.reviews.models import Review
        approved = Review.objects.filter(product=obj, status=Review.STATUS_APPROVED)
        count = approved.count()
        avg = approved.aggregate(avg=Avg('rating'))['avg']
        return {
            'average_rating': round(float(avg), 1) if avg is not None else None,
            'total_count': count,
        }

    def get_questions_count(self, obj):
        from apps.questions.models import ProductQuestion, QuestionStatus
        return ProductQuestion.objects.filter(
            product=obj, status=QuestionStatus.ANSWERED
        ).count()

    def get_related_products(self, obj):
        qs = (
            Product.objects
            .filter(category=obj.category, is_active=True, is_published=True)
            .exclude(pk=obj.pk)
            .order_by('?')[:4]
        )
        return ProductListSerializer(qs, many=True, context=self.context).data

    def get_variants(self, obj):
        from apps.chartsize.serializers import ProductVariantPublicSerializer
        qs = obj.variants.filter(is_active=True).select_related(
            'option', 'option__variant_type'
        ).order_by('option__variant_type__name', 'option__label')
        return ProductVariantPublicSerializer(qs, many=True).data


class ProductSearchSerializer(serializers.ModelSerializer):
    cover_image_url  = serializers.SerializerMethodField()
    category_name    = serializers.CharField(source='category.name', read_only=True)
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

    def get_sale_price(self, obj):
        return _get_sale_price(obj)

    def get_price_with_tax(self, obj):
        return _price_with_tax(obj)

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

    def get_highlighted_name(self, obj):
        q = self.context.get('search_term', '')
        if not q:
            return obj.name
        import re
        return re.sub(f'({re.escape(q)})', r'<em>\\1</em>', obj.name, flags=re.IGNORECASE)

    def get_availability(self, obj):
        return _availability(obj)

    def get_discount(self, obj):
        return _discount_block(obj)


class CategoryWithCountSerializer(serializers.ModelSerializer):
    product_count = serializers.SerializerMethodField()
    children      = serializers.SerializerMethodField()

    class Meta:
        model  = Category
        fields = ['id', 'name', 'slug', 'parent', 'product_count', 'children']

    def get_product_count(self, obj):
        if hasattr(obj, 'product_count'):
            return obj.product_count
        return obj.products.filter(is_active=True, is_published=True).count()

    def get_children(self, obj):
        return CategoryWithCountSerializer(obj.children.all(), many=True).data


class ProductAdminSerializer(serializers.ModelSerializer):
    images          = ProductImageSerializer(many=True, read_only=True)
    category        = CategorySerializer(read_only=True)
    category_id     = serializers.PrimaryKeyRelatedField(
        source='category', queryset=Category.objects.all(), required=False, allow_null=True,
    )
    sale_price      = serializers.SerializerMethodField()
    base_price      = serializers.DecimalField(
        source='price', max_digits=10, decimal_places=2, min_value=Decimal('0.01'), required=False,
    )
    price_with_tax  = serializers.SerializerMethodField()
    related_products = serializers.SerializerMethodField()
    discount        = serializers.SerializerMethodField()

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
            'category', 'category_id', 'images', 'is_active', 'is_published', 'is_featured',
            'stock', 'status', 'discount', 'related_products',
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
        return attrs

    def get_sale_price(self, obj):
        return _get_sale_price(obj)

    def get_price_with_tax(self, obj):
        return _price_with_tax(obj)

    def get_related_products(self, obj):
        return None

    def get_discount(self, obj):
        return _discount_block(obj)

    def _auto_slug(self, name):
        import uuid
        from django.utils.text import slugify
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
        return super().create(validated_data)

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


class CategoryAdminSerializer(serializers.ModelSerializer):
    parent_id = serializers.PrimaryKeyRelatedField(
        source='parent', queryset=Category.objects.all(), required=False, allow_null=True,
    )

    class Meta:
        model  = Category
        fields = ['id', 'name', 'slug', 'description', 'parent', 'parent_id', 'image', 'is_active']
        extra_kwargs = {'slug': {'required': False}, 'parent': {'read_only': True},
                        'description': {'max_length': 5000}}

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
