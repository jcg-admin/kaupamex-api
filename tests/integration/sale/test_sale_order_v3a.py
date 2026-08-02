"""Tests — V3a unificación orders→sale (RETIRADO tras E5).

**Retirado** durante la reescritura post-disolución de ``orders``/``cart``/
``inventory``/``returns`` (rama ``feature/sanear-terminologia-l0-ecosistema``).

Este módulo probaba el **puente** V3a entre la venta canónica
(``sale.SaleOrder``) y un "espejo legacy" (``orders.Order``): ``Payment``
llevaba una FK ``order`` al espejo (obligatoria en V3a) y otra ``sale_order``
a la canónica; ``confirm_draft_order`` devolvía el **par** ``(canonical,
legacy)``; ``SaleOrder`` exponía ``legacy_order`` para ir del canónico al
espejo.

El addon ``orders`` (el espejo) se dio de baja por completo en E5
(``api@77bd1f0``). Verificado en el código real, no asumido:

1. ``confirm_draft_order`` ya **no devuelve un par** — devuelve la propia
   ``SaleOrder`` confirmada. Su propio docstring lo dice: *"Retorna la
   ``SaleOrder`` confirmada — ya no hay espejo que devolver"*
   (``src/addons/sale/services.py:310-311``), y el bloque final del cuerpo:
   *"el puente al espejo desapareció con el addon ``orders``"*
   (``src/addons/sale/services.py:396-397``).
2. ``Payment`` **no tiene** campo ``order`` — sólo ``sale_order``
   (``src/addons/payment/models/payment.py:56-62``, único ``ForeignKey`` del
   modelo hacia una orden). ``grep -n "order " src/addons/payment/models/
   payment.py`` → sin resultados de un segundo FK.
3. ``SaleOrder`` **no tiene** el atributo ``legacy_order``
   (``grep -rn "legacy_order" src/addons/sale/`` → vacío).

El contrato que este archivo SÍ seguía teniendo vigente — ``Payment.
sale_order`` NOT NULL/PROTECT, la canónica manda — está cubierto de forma
completa y actualizada en ``test_axis_anchor_e4pre.py``
(``TestPagoAncladoAlCanonico``), que ya declara explícitamente en su propio
docstring: *"Los tests que verificaban 'existe sin fila espejo' se
reescriben como 'el campo ya no existe' (``hasattr``)"* — exactamente el
reemplazo de este módulo. No hay contenido de este archivo que no tenga ya
un sucesor verificado.
"""
