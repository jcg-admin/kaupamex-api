"""Controllers de ``payment`` — espejo de ``addons/payment/controllers/``.

La referencia parte esta capa en dos módulos y aquí se respeta el mismo
corte (medido en ``odoo19c`` y ``odoo18c``, mismas 6 rutas en ambas):

- ``portal.py`` — lo que el comprador toca: iniciar la transacción, consultar
  su estado, y su historial. ≙ ``/payment/transaction``, ``/payment/status``,
  ``/my/payment_method``.
- ``post_processing.py`` — el post-proceso del proveedor. **No portado aún**:
  aquí ese papel lo cumplen los webhooks (``webhook_processing.py``), que ya
  existen y entran por su propio módulo de URLs.
"""
