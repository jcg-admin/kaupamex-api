"""``stock.move.line`` — la línea de movimiento y sus dos fechas.

Adaptación de Odoo ``product_expiry/models/stock_move_line.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3) — atribución y aviso de
licencia preservados (DEC-KX-03).

Porte BLOQUEADO — 0 de 9 símbolos, y la causa es una sola
==========================================================

``odoo19c: addons/product_expiry/models/stock_move_line.py`` (62 líneas):
4 campos + 5 métodos, todos sobre ``stock.move.line``.

=========================================  =========================================
Símbolo de la referencia (línea)           Estado
=========================================  =========================================
``expiration_date`` (17-20, compute+store) bloqueado
``removal_date`` (21, compute+store)       bloqueado
``is_expired`` (22, related)               bloqueado
``use_expiration_date`` (23-24, related)   bloqueado
``_auto_init`` (26-36)                     bloqueado
``_compute_expiration_date`` (38-48)       bloqueado
``_compute_removal_date`` (50-58)          bloqueado
``_prepare_new_lot_vals`` (60-64)          bloqueado
=========================================  =========================================

**El modelo destino no existe.** Medido en este pase:

.. code-block:: text

   grep -rn "^class StockMoveLine" addons/ src/ --include=*.py   → 0
   ls addons/stock/models/                                        → 8 archivos,
       ninguno stock_move_line.py

No es una divergencia de diseño ni un recorte de alcance de este addon: los
nueve símbolos **extienden** ``stock.move.line``, un modelo del addon
``stock`` que aún no está portado. Colgar aquí una clase ``StockMoveLine``
propia sería inventar el modelo en el addon equivocado — exactamente el
defecto de forma que :ref:`h-api-350` registra, y la razón por la que este
mismo addon se reescribió (:ref:`h-api-576`).

Qué desbloquea el porte
-------------------------

``stock.move.line`` con, como mínimo, ``lot_id``, ``product_id``,
``picking_id`` y ``picking_type_use_create_lots`` — los cuatro campos que los
computes de este archivo navegan. Sucesor registrado: tarea **#274**
(``stock``: 17 archivos ausentes, 564 métodos y 272 campos medidos), donde
``stock_move_line.py`` es uno de los archivos del lote.

Cuando exista, este archivo se llena entero: los cuatro campos van por
``add_to_class``, los tres computes por función instalada, y ``_auto_init``
—que en la referencia crea las columnas a mano para no reventar la memoria al
computar 40 millones de líneas— se resuelve con una migración Django, que es
el mecanismo equivalente y no necesita el truco.
"""


def apply_product_expiry_extensions():
    """No-op declarado: no hay ``stock.move.line`` sobre el que colgar nada.

    Existe para que el archivo esté en ``_EXTENSIONES`` desde ahora y el día
    que ``stock.move.line`` aterrice sólo haya que llenar esta función — no
    recordar que hacía falta un archivo. Ver el docstring del módulo.
    """
    return None


__all__ = ['apply_product_expiry_extensions']
