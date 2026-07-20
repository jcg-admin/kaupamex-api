"""Models — addons.wishlist.

``wishlist`` queda como **paquete controlador delgado** (views/urls/serializers)
de la lista de deseos. **No tiene modelos propios.**

El único modelo, ``WishlistItem``, se movió a su hogar fiel
``addons.website_sale_wishlist`` (``product.wishlist`` de Odoo lo provee el
módulo ``website_sale_wishlist``, no un módulo ``wishlist`` a secas). Los
consumidores importan ``WishlistItem`` desde ``addons.website_sale_wishlist.models``.
"""
