"""URLs del checkout del escaparate — ``website_sale``.

Montado en ``config/urls.py``::

    path('api/v2/checkout/', include((
        'addons.website_sale.controllers.checkout_urls', 'checkout'),
        namespace='checkout_v2'))

Módulo aparte de ``urls.py`` (carrito) y ``shop_urls.py`` (vitrina) porque
cuelga de su propio prefijo. Los tres son de la misma familia; lo que cambia
es el momento del flujo que sirven.
"""
from django.urls import path

from addons.website_sale.controllers.payment import express_checkout

app_name = 'checkout'

urlpatterns = [
    path('express/', express_checkout, name='checkout-express'),
]
