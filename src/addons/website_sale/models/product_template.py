"""Extensión de ``product.template`` para la tienda — ≙ ``_inherit``.

Origen
======

``odoo19c: website_sale/models/product_template.py:34-42`` reabre
``product.template`` y le añade, entre otros, el mixin de publicación::

    class ProductTemplate(models.Model):
        _name = 'product.template'
        _inherit = [
            'rating.mixin',
            'product.template',
            'website.seo.metadata',
            'website.published.multi.mixin',
            'website.searchable.mixin',
        ]

Lo que importa de esa declaración no es la lista, es **quién la escribe**:
la escribe ``website_sale``, no ``product``. Medido en la referencia
(``odoo-tools@622ddc2a``):

===============  ===============================================
Addon            ``depends``
===============  ===============================================
``product``      ``base``, ``mail``, ``uom`` — **no** ``website``
``website_sale`` ``website``, ``sale``, ``website_payment``, …
===============  ===============================================

La única aparición de la cadena ``website`` en ``product/models/`` es un
comentario (``product_pricelist.py:353``). El producto **no sabe** que existe
un sitio web; es el escaparate quien lo publica.

Cómo se hace en Django
======================

Django **sí** permite reabrir un modelo ya definido: ``ModelBase.add_to_class``
es un ``classmethod`` (``django/db/models/base.py:391``) y funciona en
runtime — medido: añadir un campo a ``ProductTemplate`` después de definida lo
deja registrado en ``_meta`` con su columna SQL.

La restricción real es **otra**, y también está medida: el autodetector
atribuye la migración al ``app_label`` del **modelo**, no al addon que
contribuye el campo. Es decir, la columna se crea desde
``product/migrations/``, se use la vía que se use. Eso no se puede replicar de
la referencia —allá desinstalar ``website_sale`` retira la columna— y se
declara como divergencia de plataforma.

Lo que **sí** se preserva es lo que importa para SRP y Open/Closed: el código
de ``product`` no menciona al sitio, y quien decide publicar es este archivo.
"""
from addons.product.models import ProductTemplate
from addons.website.models.mixins import WebsitePublishedMixin


def apply_website_extensions():
    """Aplica al producto las extensiones de la tienda.

    Se invoca desde ``WebsiteSaleConfig.ready()``: en tiempo de import el
    registro de modelos aún no está poblado.
    """
    WebsitePublishedMixin.apply_to(ProductTemplate)
