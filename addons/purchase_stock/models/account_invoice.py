r"""``account.move`` — la diferencia de precio anglosajona de la factura de
proveedor: NO PORTADA.

Adaptación de Odoo ``purchase_stock/models/account_invoice.py``
(``odoo19c: addons/purchase_stock/models/account_invoice.py``, 137 líneas,
LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Qué hace en la fuente: cuando se compra un producto valorado a **costo
estándar** y el proveedor factura un precio distinto del costo, el asiento de
la factura tiene que absorber la diferencia. Este archivo produce las dos
líneas de asiento que lo hacen (una a la cuenta de diferencia de precio, otra
correctora sobre la cuenta original) y las inyecta al contabilizar.

Los 5 símbolos de la fuente, con su desenlace
==============================================

*Métrica:* entradas del cuerpo de ``class AccountMove`` contadas por AST sobre
la fuente. Son **6** con ``_inherit``; **5** sin él, los cinco métodos, cero
campos.
*Ciega a:* lo que ``purchase`` (no este addon) le cuelga a ``account.move`` —
``purchase_id``, del que ``_compute_incoterm_location`` depende.

.. list-table::
   :header-rows: 1
   :widths: 40 18 42

   * - Símbolo (línea)
     - Desenlace
     - Medición
   * - ``_stock_account_prepare_anglo_saxon_in_lines_vals`` (``:12-108``)
     - **bloqueado**
     - 3 piezas ausentes, greppeadas abajo
   * - ``button_draft`` (``:110-111``)
     - **nada que portar** (degenerado en la fuente)
     - su cuerpo entero es ``return super().button_draft()``
   * - ``_post`` (``:113-117``)
     - **bloqueado por el anterior**
     - sólo existe para invocar al primero
   * - ``_stock_account_get_last_step_stock_moves`` (``:119-127``)
     - **bloqueado**
     - encadena un ``super()`` que no existe
   * - ``_compute_incoterm_location`` (``:129-137``)
     - **bloqueado**
     - el campo que escribe no existe en ``account.move``

Las mediciones, verbatim
=========================

.. code-block:: text

    grep -rn "anglo_saxon_accounting"  addons/ src/ --include=*.py  → 1
        (único hit: addons/l10n_mx/models/template_mx.py:112, una MENCIÓN en
         prosa dentro de un docstring que enumera campos NO portados)
    grep -rn "_eligible_for_stock_account"          addons/ src/    → 0
    grep -rn "property_price_difference_account_id" addons/ src/    → 0
    grep -rn "def _get_stock_moves"                 addons/ src/    → 0
    grep -rn "incoterm_location" addons/account/                    → 0

``_stock_account_prepare_anglo_saxon_in_lines_vals`` — las tres piezas
------------------------------------------------------------------------

1. ``move.company_id.anglo_saxon_accounting`` — el interruptor que decide si
   el método hace algo. Sin él, la primera condición del bucle
   (``odoo19c: :37``) no se puede evaluar: no es que dé ``False``, es que el
   atributo no existe.
2. ``line._eligible_for_stock_account()`` — el filtro de qué línea de factura
   participa en la valoración. Lo declara ``stock_account`` en la referencia;
   el ``stock_account`` de este árbol tiene dos archivos (``product_costing.py``,
   ``stock_valuation_layer.py``) y ninguno toca ``account.move.line``.
3. ``product.categ_id.property_price_difference_account_id`` — **la cuenta
   contable donde aterriza la diferencia**. Sin ella el método no tiene destino;
   la fuente misma hace ``continue`` cuando falta (``:55-56``), así que un
   puerto sin esa cuenta sería un método que nunca produce una línea. Eso es
   una superficie muerta, no un porte.

Y una cuarta, sobre el propio modelo: ``AccountMove`` de este árbol
(``addons/account/models/account_move.py``, 384 líneas) declara ``journal``,
``partner``, ``currency``, ``company`` y ``amount_total``, pero **no**
``invoice_line_ids`` ni ``fiscal_position_id``. El bucle de la fuente recorre
el primero y el mapeo de cuentas usa el segundo.

``button_draft`` — el símbolo que no aporta nada
--------------------------------------------------

Su cuerpo entero, verbatim de ``odoo19c: :110-111``::

    def button_draft(self):
        return super().button_draft()

Es un ``override`` que sólo llama al ``super()``. No añade condición, no
transforma el resultado, no registra nada. Portarlo aquí produciría un
``chain_method`` que envuelve una función para devolver exactamente lo que la
envuelta devuelve — coste sin efecto. **Se declara y no se porta**, que es
distinto de omitirlo en silencio.

(No se afirma por qué está en la fuente: podría ser residuo de una versión en
la que sí hacía algo, o un ancla para que otro addon encadene por encima. Es
un hallazgo del árbol de referencia, no una conclusión sobre él.)

``_post`` — bloqueado por el primero, y con un desajuste de nombre
--------------------------------------------------------------------

Su cuerpo es un ``create`` de las líneas que produce
``_stock_account_prepare_anglo_saxon_in_lines_vals`` antes de llamar al
``super()``. Sin el primero, no hay nada que crear.

Además, el punto de enganche difiere: este árbol declara ``AccountMove.post``
(``addons/account/models/account_move.py:354``), sin guion bajo y sin el
parámetro ``soft``. Cuando el primer método se desbloquee, el
``chain_method`` va sobre ``post``, no sobre ``_post`` — se deja escrito aquí
para que quien lo retome no encadene sobre un nombre inexistente y crea que
funcionó (el gate de porte compara nombres literales y sería ciego a eso,
:ref:`h-api-579`).

``_stock_account_get_last_step_stock_moves`` — el eslabón base falta
-----------------------------------------------------------------------

Su primera línea es ``rslt = super()._stock_account_get_last_step_stock_moves()``
y el ``super()`` lo declara ``stock_account`` allá. Aquí ese método no existe
en ningún archivo (0 hits). Instalar el segundo eslabón de una cadena sin
primer eslabón es el defecto de ``H-API-733``.

``_compute_incoterm_location`` — el campo que escribe no existe
-----------------------------------------------------------------

Escribe ``move.incoterm_location`` leyendo
``move.line_ids.purchase_line_id.order_id.incoterm_location``. Tres ausencias
encadenadas: el campo destino en ``account.move`` (0 hits en
``addons/account/``), ``purchase_line_id`` en ``account.move.line`` (lo declara
``purchase``, que no lo tiene), y el ``super()`` que la primera línea encadena.

**El campo origen SÍ se porta en este pase**: ``PurchaseOrder.incoterm_location``,
en ``purchase_order.py`` de este mismo addon. Lo que falta es el otro extremo
del puente, no el puente entero — por eso el desenlace es *bloqueado*, no
*divergencia*.

Lo que este archivo NO cierra
==============================

- **El eje de valoración anglosajona completo** (``anglo_saxon_accounting`` +
  ``_eligible_for_stock_account`` + la cuenta de diferencia de precio). Es el
  porte de ``stock_account`` sobre ``account.move``, que este lote no toca.
- **``account.move.invoice_line_ids`` y ``fiscal_position_id``**, del addon
  ``account``. Se registran aquí con su medición para que quien porte la
  factura de proveedor los encuentre nombrados.
"""
