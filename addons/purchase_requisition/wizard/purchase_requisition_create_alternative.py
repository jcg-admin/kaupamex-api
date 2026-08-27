"""``purchase.requisition.create.alternative`` — pedir la misma compra a otro
proveedor (Odoo ``purchase_requisition``).

Adaptación de Odoo
``purchase_requisition/wizard/purchase_requisition_create_alternative.py``
(``odoo19c: addons/purchase_requisition/wizard/
purchase_requisition_create_alternative.py``, 100 líneas, LGPL-3) —
atribución y aviso de licencia preservados (DEC-KX-03).

Qué es: desde una solicitud de cotización, abrir **otra igual** dirigida a uno
o varios proveedores distintos, para comparar. Copia opcionalmente los
productos y sus cantidades, y avisa de las advertencias que el proveedor o los
productos tengan configuradas.

Porte símbolo por símbolo — 2 de 8
====================================

*Métrica:* entradas del cuerpo de
``class PurchaseRequisitionCreateAlternative`` contadas por AST sobre la fuente,
descontando ``_name`` y ``_description``. Son **8**: 4 campos y 4 métodos.
*Ciega a:* si el asistente se comporta igual en ejecución.

.. list-table::
   :header-rows: 1
   :widths: 40 16 44

   * - Símbolo (línea)
     - Estado
     - Nota
   * - ``origin_po_id`` (``:11-13``)
     - portado
     - parámetro ``origin_po`` (D-1)
   * - ``partner_ids`` (``:14-16``)
     - portado
     - parámetro ``partners``
   * - ``copy_products`` (``:21-23``)
     - portado
     - parámetro ``copy_products``
   * - ``_get_alternative_line_value`` (``:90-100``)
     - portado
     - ``@classmethod``, con D-2
   * - ``purchase_warn_msg`` (``:17-20``)
     - **bloqueado**
     - ``groups=`` + el campo que lee
   * - ``_compute_purchase_warn_msg`` (``:25-40``)
     - **bloqueado**
     - ídem
   * - ``action_create_alternative`` (``:42-57``)
     - **bloqueado**
     - 5 campos de la orden ausentes
   * - ``_get_alternative_values`` (``:59-88``)
     - **bloqueado**
     - los mismos 5

Los dos bloqueos, medidos
==========================

**1 — el aviso del proveedor.** ``_compute_purchase_warn_msg`` lee dos campos
que no existen:

.. code-block:: text

    grep -rn "purchase_warn_msg"       addons/ src/ --include=*.py   → 0
    grep -rn "purchase_line_warn_msg"  addons/ src/ --include=*.py   → 0

Los declara ``purchase`` en la referencia sobre ``res.partner`` y
``product.template``. Y el campo del asistente lleva además
``groups="purchase.group_warning_purchase"``, el mismo mecanismo de
visibilidad por grupo que ``addons/hr_hourly_cost/models/hr_employee.py`` ya
declaró bloqueado: este stack autoriza por **capacidad** a nivel de vista DRF,
no por grupo a nivel de campo.

Sí existe la mitad que consulta el grupo — ``ResUsers.has_group``
(``src/addons/base/models/res_users.py:518``) —, así que el bloqueo es de los
**datos**, no del predicado.

**2 — la orden alternativa que se crearía.** ``_get_alternative_values`` arma
un diccionario con siete claves; **cinco no tienen campo destino** en la
``purchase.order`` de este árbol:

.. code-block:: text

    user_id · origin · currency_id · payment_term_id   (del addon `purchase`)
    property_purchase_currency_id · property_supplier_payment_term_id
                                                       (de `res.partner`)

Las dos que sí existen son ``date_order`` (``purchase``) y ``dest_address_id``
—que ``purchase_stock`` porta en este mismo lote como
``PurchaseOrder.dest_address``—. Crear la orden con dos de siete claves
produciría una alternativa incomparable con su original, que es lo contrario
de para lo que el asistente existe.

``action_create_alternative`` cae con él: su cuerpo entero es *crear con esos
valores y devolver el descriptor de la vista*. Además llama a
``order_line._compute_tax_id()`` (0 definiciones).

Divergencias declaradas
========================

**D-1 — los campos son parámetros.** ``TransientModel`` aquí es abstracto y
``managed = False`` (``src/orm/models_transient.py:29-36``): sin tabla. Mismo
idioma que los ocho asistentes de ``account`` y que el asistente hermano de
este addon.

**D-2 — ``_get_alternative_line_value`` conserva sus claves aunque tres no
tengan destino.** ``product_uom_id``, ``display_type`` y
``analytic_distribution`` no existen en la ``purchase.order.line`` de este
árbol. Se devuelven igualmente porque el diccionario es el **contrato** del
método —lo mismo que se decidió para
``PurchaseRequisitionLine._prepare_purchase_order_line``—: quien lo consuma
filtra lo que su modelo acepte, y el día que ``purchase`` complete su línea no
hay que volver a tocarlo.

Su condición final se conserva verbatim en intención: el nombre de la línea
**sólo** se copia cuando es una sección/nota o cuando el proveedor destino no
tiene descripción propia del producto. Copiarlo siempre pisaría la descripción
que ese proveedor usa para el mismo artículo.
"""
from orm.models_transient import TransientModel

#: ≙ los tres ``display_type`` que la fuente trata como texto libre
#: (``odoo19c: :99``): en ellos el nombre de la línea SIEMPRE se copia porque no
#: hay producto del que derivarlo.
TEXT_DISPLAY_TYPES = ('line_section', 'line_subsection', 'line_note')


class PurchaseRequisitionCreateAlternative(TransientModel):
    """``purchase.requisition.create.alternative`` — «Wizard to preset values
    for alternative PO»."""

    # Atributos de clase de modelo — los DOS que la fuente declara
    # (``odoo19c: :8-9``), verbatim.
    _name = 'purchase.requisition.create.alternative'
    _description = 'Wizard to preset values for alternative PO'

    class Meta:
        abstract = True
        managed = False

    @classmethod
    def _get_alternative_line_value(cls, order_line,
                                    product_tmpl_ids_with_description=()):
        """≙ ``_get_alternative_line_value`` (``odoo19c: :90-100``) — D-2.

        Los valores con los que se copia una línea a la orden alternativa.

        La condición del nombre es la parte que importa: se copia **sólo** si
        la línea es texto libre (sección, subsección, nota) o si el proveedor
        destino **no** tiene descripción propia de ese producto. Copiarlo en el
        otro caso pisaría el nombre que ese proveedor usa para el mismo
        artículo, que es justo lo que ``product.supplierinfo`` guarda.
        """
        product = order_line.product
        product_tmpl_id = product.product_tmpl_id if product is not None else None
        has_product_description = product_tmpl_id in set(
            product_tmpl_ids_with_description or ())
        display_type = getattr(order_line, 'display_type', None)

        vals = {
            'product_id': order_line.product_id,
            'product_qty': order_line.product_qty,
            'product_uom_id': getattr(order_line, 'product_uom_id', None),
            'display_type': display_type,
            'analytic_distribution': getattr(
                order_line, 'analytic_distribution', None),
        }
        if display_type in TEXT_DISPLAY_TYPES or not has_product_description:
            vals['name'] = order_line.name
        return vals
