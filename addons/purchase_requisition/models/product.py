"""``product.supplierinfo`` / ``product.product`` — la tarifa que nace de un
acuerdo (Odoo ``purchase_requisition``).

Adaptación de Odoo ``purchase_requisition/models/product.py``
(``odoo19c: addons/purchase_requisition/models/product.py``, 22 líneas,
LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Qué añade: el enlace que cierra el círculo del **pedido abierto**. Confirmar un
acuerdo crea tarifas de proveedor (``PurchaseRequisitionLine._create_supplier_info``);
este archivo es el campo que recuerda **de qué línea de acuerdo** salió cada
tarifa. Sin él, cancelar el acuerdo no sabría qué tarifas retirar.

Porte símbolo por símbolo — 2 de 3
====================================

*Métrica:* entradas del cuerpo de las dos clases contadas por AST sobre la
fuente, descontando ``_inherit``. Son **3**: 2 campos en
``ProductSupplierinfo``, 1 método en ``ProductProduct``.

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Símbolo (línea)
     - Estado
   * - ``purchase_requisition_line_id`` (``:17``)
     - portado — campo ``purchase_requisition_line`` (FK indexada)
   * - ``purchase_requisition_id`` (``:16``)
     - portado — ``property`` (era ``related=``)
   * - ``ProductProduct._prepare_sellers`` (``:23-28``)
     - **bloqueado**

``_prepare_sellers`` — el bloqueo, medido
==========================================

.. code-block:: text

    grep -rn "def _prepare_sellers" addons/ src/ --include=*.py   → 0

Encadena un ``super()._prepare_sellers(params=params)`` que no existe en este
árbol. Lo declara ``product`` en la referencia; el ``product`` de este árbol
resuelve la selección de proveedor con
``ProductSupplierinfo.filtered_suppliers``
(``addons/product/models/product_supplierinfo.py:302-322``), que es **otro
mecanismo**: filtra por empresa, proveedor activo y variante, y no acepta el
``params`` con la orden de compra del que este método depende.

Lo que el método hace, para quien lo retome: **excluye de la lista de
proveedores las tarifas que pertenecen a OTRO acuerdo**. Sin él, una orden de
compra ligada al acuerdo A podría tomar el precio pactado en el acuerdo B —
que es exactamente lo que un pedido abierto existe para impedir. Es una regla
de negocio real, no un filtro de conveniencia; se declara bloqueada con su
consecuencia nombrada.

Sucesor: el porte de ``_prepare_sellers`` pertenece al addon ``product``; este
archivo es su puntero.

Divergencia declarada
======================

**``purchase_requisition_id`` es ``property``.** La fuente lo declara
``related='purchase_requisition_line_id.requisition_id'`` **sin** ``store``, así
que tampoco tiene columna allá: es la navegación de dos saltos desde la tarifa
hasta el acuerdo. Aquí es exactamente eso.
"""
import fields
import models
from orm.model_classes import extend_model


def purchase_requisition(self):
    """≙ ``purchase_requisition_id`` (``odoo19c: :16``) — «Agreement».

    ``related='purchase_requisition_line_id.requisition_id'``: el acuerdo del
    que salió esta tarifa, a través de su línea.
    """
    if self.purchase_requisition_line_id is None:
        return None
    return self.purchase_requisition_line.requisition


def apply_purchase_requisition_product_extensions():
    """Cuelga sobre ``product.ProductSupplierinfo`` lo que
    ``purchase_requisition`` le añade — ≙ ``_inherit``.

    ``product.ProductProduct`` NO recibe nada: su único símbolo
    (``_prepare_sellers``) está bloqueado, con su medición en el docstring del
    módulo.
    """
    extend_model(
        'product', 'ProductSupplierinfo',
        campos={
            'purchase_requisition_line': fields.Many2one(
                'purchase_requisition.PurchaseRequisitionLine',
                null=True, blank=True, on_delete=models.CASCADE,
                db_index=True, related_name='supplier_info_ids',
                verbose_name='Línea de acuerdo',
                help_text='Línea del acuerdo de compra que creó esta tarifa '
                          '(Odoo purchase_requisition_line_id). El inverso es '
                          '``line.supplier_info_ids``.',
            ),
        },
        propiedades={'purchase_requisition': purchase_requisition},
    )
