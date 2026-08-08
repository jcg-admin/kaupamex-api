"""Fábrica de catálogo (``product.template`` + ``product.product``) para tests.

Post-disolución de ``catalogue``/``chartsize`` (H-API-212 y hermanas): el
catálogo canónico separa ficha (``ProductTemplate``, precio/nombre/categoría)
de variante (``ProductProduct``, lo que de verdad vende una línea de venta —
``odoo19c: addons/sale/models/sale_order_line.py:83-88``). El viejo
``catalogue.Product`` (plano: ``name``/``slug``/``sku``/``price``/``stock``/
``is_active``/``is_published``/``categories``) no tiene un único sucesor —
sus campos se reparten entre la ficha y la variante, y el ``stock`` se
**deriva** de ``stock.quant`` en vez de ser una columna (odoo19c:
``stock/models/stock_quant.py:119-122``).

Esta fábrica reconstruye el atajo que los tests necesitan: un producto SIN
atributos (una ficha, una variante), con su stock inicial si se pide.
"""
from decimal import Decimal

from addons.product.models import ProductCategory, ProductProduct, ProductTemplate
from addons.stock.models import StockLocation, StockQuant
from addons.stock.services import InventoryService

ZERO = Decimal('0.00')


def make_category(name='Categoría de prueba', **kwargs):
    """``product.category`` mínima (Odoo ``ProductCategory``)."""
    kwargs.setdefault('name', name)
    return ProductCategory.objects.create(**kwargs)


def default_internal_location():
    """Ubicación interna por defecto — misma que ``InventoryService.restore``
    usa para no depender de que el árbol de ubicaciones ya esté sembrado."""
    location, _ = StockLocation.objects.get_or_create(
        name='WH/Stock', defaults={'usage': StockLocation.USAGE_INTERNAL},
    )
    return location


def set_stock(product, quantity):
    """Fija el stock a la mano de ``product`` (paridad con el viejo
    ``Product.stock = N``). Usa el helper canónico del propio modelo."""
    return StockQuant.set_on_hand(
        product, default_internal_location(), Decimal(quantity))


def make_product(name='Producto de prueba', price=Decimal('100.00'),
                  stock=None, default_code='', active=True, categ=None,
                  barcode='', standard_price=None, weight=None, volume=None,
                  **tmpl_kwargs):
    """Crea una ficha + su variante única (sin atributos, sin combinación).

    :param price: ``ProductTemplate.list_price`` (Odoo ``list_price``).
    :param stock: si no es ``None``, crea/fija un ``stock.quant`` en la
        ubicación interna por defecto con esa cantidad a la mano.
    :param standard_price: costo — va a la **variante**
        (``ProductProduct.standard_price``), que la sobreescribe respecto de
        la ficha (odoo19c: ``product_product.py:144-148``). ``None`` deja el
        default (``0``) de la variante.
    :param weight: peso — va a la **variante** (``ProductProduct.weight``,
        que también sobreescribe a la ficha, misma razón que
        ``standard_price`` — odoo19c: ``product_product.py:154-156``). Lo
        que se mueve y se envía es la variante, así que
        ``stock_landed_costs`` lo lee de ahí. ``None`` deja el default (``0``).
    :param volume: ídem ``weight``, para ``ProductProduct.volume``.
    :param tmpl_kwargs: kwargs adicionales para ``ProductTemplate.objects.create``
        (p. ej. ``type=ProductTemplate.TYPE_SERVICE``).
    :returns: la **variante** (``product.ProductProduct``) — es la que
        ``SaleOrderLine``/``PurchaseOrderLine``/``StockQuant`` referencian.
    """
    tmpl = ProductTemplate.objects.create(
        name=name, list_price=Decimal(price), active=active, categ=categ,
        **tmpl_kwargs,
    )
    variant_kwargs = {}
    if standard_price is not None:
        variant_kwargs['standard_price'] = Decimal(standard_price)
    if weight is not None:
        variant_kwargs['weight'] = weight
    if volume is not None:
        variant_kwargs['volume'] = volume
    variant = ProductProduct.objects.create(
        product_tmpl=tmpl, default_code=default_code, active=active,
        barcode=barcode, **variant_kwargs,
    )
    if stock is not None:
        set_stock(variant, stock)
    return variant


def get_stock(product) -> Decimal:
    """Stock disponible del producto (paridad de lectura con el viejo
    ``Product.stock``). ``SUM(quantity - reserved_quantity)`` sobre sus quants."""
    return InventoryService.available_quantity(product)
