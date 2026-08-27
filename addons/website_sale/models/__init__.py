"""Modelos de ``website_sale`` — espejo de ``addons/website_sale/models/``.

La referencia declara aquí **26 archivos**, casi todos extensiones de modelos
que pertenecen a otros addons (``product_template.py``, ``product_product.py``,
``delivery_carrier.py``, ``account_move.py``…). Ése es exactamente su papel:
``website_sale`` es el **puente** entre la tienda y el ERP, así que su carpeta
de modelos está llena de extensiones, no de modelos propios.

Portados por ahora — **5 de 26**:

``product_template.py``
    Publica el producto en la tienda.
``website.py``
    La política de recuperación de carrito del sitio y el equipo de venta al
    que se atribuyen sus pedidos (tareas **#258** y **#568**).
``sale_order.py``
    El carrito abandonado y su recuperación (tarea **#258**).
``crm_team.py``
    El contador de carritos abandonados del equipo (tarea **#568**). 4 de sus
    5 símbolos; el quinto es navegación y declara su arista.
``res_config_settings.py``
    Declarado **no portado** con su medición (tarea **#278**): la pantalla de
    ajustes es capa de presentación y ``ResConfigSettings`` es abstracto.
    Quinto caso idéntico del árbol.

Sólo ``website.py`` y ``sale_order.py`` declaran modelos con tabla, así que son
los únicos que se **importan** aquí: es lo que hace que Django los registre.
Los otros tres no declaran ninguno —cuelgan símbolos sobre modelos ajenos, o no
cuelgan nada— y por eso no aparecen abajo; su cableado vive donde corresponde,
en ``WebsiteSaleConfig.ready()``. ``res_config_settings.py`` no se cablea
siquiera: es sólo docstring, y una llamada no-op sería cableado muerto.

Las demás llegan con su superficie.
"""
from .sale_order import WebsiteSaleOrderInfo
from .website import WebsiteSaleSettings

__all__ = ['WebsiteSaleOrderInfo', 'WebsiteSaleSettings']
