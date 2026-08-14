r"""``stock.move`` — el movimiento sabe si su producto caduca.

Adaptación de Odoo ``product_expiry/models/stock_move.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3) — atribución y aviso de
licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 7 de la referencia, 1 aquí
=======================================================

``odoo19c: addons/product_expiry/models/stock_move.py`` (95 líneas):
1 campo + 6 métodos.

============================================  ==========================================
Símbolo de la referencia (línea)              Dónde queda en este puerto
============================================  ==========================================
``use_expiration_date`` (16-17, related)      property ``use_expiration_date``
``action_generate_lot_line_vals`` (19-28)     **bloqueado** — método base ausente
``_generate_serial_move_line_commands`` (30)  **bloqueado** — método base ausente
``_convert_string_into_field_data`` (41-52)   **bloqueado** — método base ausente
``_get_formating_options`` (54-85)            **bloqueado** — método base ausente
``_update_reserved_quantity`` (87-90)         **bloqueado** — método base ausente
``_get_available_quantity`` (92-95)           **bloqueado** — método base ausente
============================================  ==========================================

Lo que este archivo no cierra
===============================

Los seis métodos son **overrides**: no aportan comportamiento propio, inyectan
el contexto ``with_expiration`` o una fecha por defecto sobre un método de
``stock.move`` que aquí no existe. Medido en el mismo pase:

.. code-block:: text

   grep -rn "action_generate_lot_line_vals\|_generate_serial_move_line_commands\
   \|_convert_string_into_field_data\|_get_formating_options\
   \|_update_reserved_quantity" addons/ src/ --include=*.py
   → 0 en los cinco

``_get_available_quantity`` da 1 hit, pero es una **mención en un docstring**
de ``stock_quant.py``, no el método: el puerto de ``stock.move`` no lo declara.

No es una divergencia de diseño ni una decisión de alcance de este addon: es la
superficie de ``stock.move`` que aún no está portada. Encadenar sobre un método
inexistente instalaría una función suelta con nombre de override —una que nadie
llama y que ``chain_method`` no puede relevar—, que es peor que la ausencia
porque el gate de porte la contaría como presente.

Sucesor registrado: tarea **#274** (``stock``: 17 archivos ausentes, 564
métodos y 272 campos medidos). Los seis entran con el bloque de ``stock_move``
de esa tarea, en el mismo pase que sus métodos base.

Los tres primeros, además, dependen de ``stock.move.line``, que no existe como
modelo (ver ``stock_move_line.py`` de este mismo addon).
"""
from addons.stock.models import StockMove


def use_expiration_date(self):
    """≙ ``use_expiration_date`` (related a ``product_id``, ``:16-17``)."""
    producto = self.product
    return bool(producto is not None and producto.use_expiration_date)


def apply_product_expiry_extensions():
    """Cuelga ``use_expiration_date`` sobre ``stock.move``."""
    if not hasattr(StockMove, 'use_expiration_date'):
        StockMove.use_expiration_date = property(use_expiration_date)


__all__ = ['apply_product_expiry_extensions', 'use_expiration_date']
