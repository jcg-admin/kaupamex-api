"""Extensión ``sale_stock_product_expiry`` — caducidad en la línea de venta.

Adaptación de Odoo ``sale_stock_product_expiry/models/sale_order_line.py``
(``odoo19c:``, LGPL-3, ``auto_install``; **sólo existe en 19** — la fuente
es 19 sin desempate, medido en ``analisis-gap-sale-contra-ambos-arboles``).
Puente ``sale_stock`` + ``product_expiry``: ambos extremos existen aquí.

La fuente inyecta dos cosas en ``sale.order.line``:

- ``use_expiration_date`` (:9) — ``related='product_id.use_expiration_date'``.
  **Se porta** como :func:`use_expiration_date` — derivación en vivo, igual
  que el related de la fuente (no almacena).
- ``_read_qties`` (:11-16) — en el forecast de disponibilidad, para
  productos con caducidad usa ``free_qty`` fresco (excluye lotes vencidos)
  en vez del pronóstico cacheado. **No se porta**: opera sobre la
  maquinaria de forecast de ``sale_stock`` (``qty_forecast``/almacén por
  contexto), que este árbol no tiene — medido: 0 hits de
  ``free_qty``/``_read_qties`` en ``sale_stock``/``stock`` locales. La
  mitad entra cuando esa maquinaria aterrice (regla del puente aplicada a
  un método, mismo criterio que el M2O ``incoterm``).

Behavior-only (precedente ``sale_stock_margin``): sin tabla propia.
"""


def use_expiration_date(line) -> bool:
    """El ``related`` de la fuente: ¿el producto de la línea maneja caducidad?

    Lee la config de caducidad por su reverso ``expiry_config`` —
    ``product_expiry`` local la cuelga de la VARIANTE
    (``ProductExpiryConfig.product`` OneToOne a ``product.ProductProduct``),
    aunque la referencia la declare en la plantilla; se sigue al puerto, no
    a la memoria (H-API-293). Sin config, ``False`` — el related de un
    vacío es falsy.
    """
    if line.product is None:
        return False
    config = getattr(line.product, 'expiry_config', None)
    return bool(config and config.use_expiration_date)
