"""Tests — E5/R5: retirado, ``update_shipping_method`` ya no existe.

Este módulo verificaba que dos escritores de producción poblaran
``SaleOrder.carrier`` — la canónica — a la par del espejo
``orders.Order.shipping_method`` (:ref:`analisis-retiro-addon-orders-e5`):
el flujo admin vía ``orders.services.update_shipping_method`` y el checkout
express. Ambos supuestos quedaron sin sujeto:

1. ``update_shipping_method`` está **DEPRECADO desde 2026-07-07**
   (comentario vigente en ``src/addons/delivery/models/__init__.py:288``):
   el comprador ya no elige transportista — el envío se deriva por zona —,
   así que ese escritor no existe en ningún addon
   (``grep -rn "def update_shipping_method" src/`` → vacío).
2. El retiro del addon espejo ``orders`` (SOL-098, ``api@77bd1f0``) quitó
   el segundo hogar (``orders.Order.shipping_method``) al que el
   write-through apuntaba: ``SaleOrder.carrier`` es hoy el **único** lugar
   donde vive el transportista de una venta — no hay nada con lo que
   sincronizarlo.

El guard que este archivo protegía —no permitir desactivar un método de
envío con órdenes activas— ya consulta el campo canónico directamente:
``active_sale_orders().filter(carrier=instance)``
(``src/addons/settings_app/views.py:275``). Esa consulta ya no depende de
ningún write-through: ``carrier`` se puebla al crear/confirmar la venta
(``SaleOrder.objects.create(carrier=...)`` / ``tests/factories/
order_factory.py::make_order``), no por un paso posterior de
sincronización. Su cobertura vive en la suite de ``settings_app``, no aquí.

No queda ningún caso vigente en este módulo: los dos tests originales
(``test_update_shipping_method_escribe_ambos_lados`` y
``test_la_canonica_es_consultable_por_metodo_de_envio``) ejercían
exclusivamente ``update_shipping_method``, que ya no existe. Se documenta
la razón del retiro en vez de dejar un test que pase por vacío o que
referencie una función inexistente.
"""
