"""``purchase.order.group`` / ``purchase.order`` / ``purchase.order.line`` — la
orden que nace de un acuerdo, y sus alternativas (Odoo
``purchase_requisition``).

Adaptación de Odoo ``purchase_requisition/models/purchase.py``
(``odoo19c: addons/purchase_requisition/models/purchase.py``, 322 líneas,
LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Qué añade, y son dos ejes independientes:

1. **El acuerdo como origen.** Una orden puede venir de un
   ``purchase.requisition``, y entonces hereda su proveedor, su moneda, sus
   condiciones y sus líneas.
2. **Las alternativas.** Se piden varias cotizaciones para lo mismo, a
   proveedores distintos, y se comparan. El agrupador de ese conjunto es
   ``purchase.order.group`` — un modelo cuya única razón de ser es sostener el
   grupo, como su propia descripción dice: *«Technical model to group PO for
   call to tenders»*.

Porte símbolo por símbolo — 12 de 22
=====================================

*Métrica:* entradas del cuerpo de las tres clases contadas por AST sobre la
fuente, descontando los atributos de clase de modelo. ``PurchaseOrderGroup``:
1 campo + 1 método. ``PurchaseOrder``: 4 campos + 10 métodos.
``PurchaseOrderLine``: 2 campos + 4 métodos. Total **22**.
*Ciega a:* si un símbolo portado se comporta igual en ejecución.

.. note::

   **Corregido — tarea #266.** Esta cabecera decía *"8 de 22"*, contando
   **filas de la tabla** en vez de **símbolos**: la fila de
   ``PurchaseOrderGroup`` bundlea dos (``order_ids`` + ``write``), así que 8
   filas eran **9** símbolos, no 8. Verificado por AST sobre los
   ``extend_model(...)`` de este archivo:
   ``campos={requisition, purchase_group}`` + ``propiedades={requisition_type,
   alternative_po_ids}`` + ``metodos={get_tender_best_lines,
   action_clear_quantities}`` + ``button_confirm`` (vía ``luego``) = 7, más
   los 2 propios de ``PurchaseOrderGroup`` = **9**. Esta tarea añade
   ``price_total_cc``, ``company_currency_id`` y ``_compute_price_total_cc``
   (los tres de ``PurchaseOrderLine``): **12 de 22**.

Lo portado
------------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Símbolo (línea)
     - Forma aquí
   * - ``PurchaseOrderGroup`` (``:10-20``)
     - **modelo propio**, con su ``order_ids`` y su ``delete`` auto-implosivo
   * - ``PurchaseOrder.requisition_id`` (``:26``)
     - campo ``requisition``
   * - ``PurchaseOrder.purchase_group_id`` (``:29``)
     - campo ``purchase_group``
   * - ``PurchaseOrder.requisition_type`` (``:27``)
     - ``property`` (era ``related=``)
   * - ``PurchaseOrder.alternative_po_ids`` (``:30-34``)
     - ``property`` (era ``related=`` sobre el grupo)
   * - ``PurchaseOrder.button_confirm`` (``:95-110``)
     - ``chain_method`` — la guarda de alternativas abiertas
   * - ``PurchaseOrder.get_tender_best_lines`` (``:192-235``)
     - método homónimo — D-3a CERRADA (tarea #266), D-3b sigue abierta
   * - ``PurchaseOrderLine.action_clear_quantities`` (``:295-308``)
     - método homónimo, con D-4
   * - ``PurchaseOrderLine.price_total_cc`` (``:257``)
     - campo homónimo — tarea #266, Causa D CERRADA
   * - ``PurchaseOrderLine.company_currency_id`` (``:258``)
     - ``property`` (era ``related=`` sin ``store``) — tarea #266
   * - ``PurchaseOrderLine._compute_price_total_cc`` (``:260-263``)
     - método homónimo, invocado en ``save()`` — tarea #266

Lo NO portado, por causa
--------------------------

**Causa A — parcialmente cerrada por la tarea #266; sigue bloqueando.** Decía:
*"la orden de compra de este árbol tiene cinco campos… sin ``company_id``,
``currency_id``, ``user_id``, ``origin``, ``payment_term_id``,
``fiscal_position_id`` ni ``date_planned`` no hay dónde escribir"*.
``company_id`` y ``currency_id`` **ya existen** — se portaron en
``api: addons/purchase/models/purchase_order.py`` (tarea #266). De los ocho
campos que ``_onchange_requisition_id`` escribe (``:36-93``), cinco tienen
ya dónde escribir —``partner_id``, ``note``, ``date_order``, ``company_id``,
``currency_id``— y **tres siguen sin campo**: ``fiscal_position_id``,
``payment_term_id``, ``origin``. Esos tres —ninguno del alcance de la tarea
#266— siguen bloqueando ``_onchange_requisition_id`` (``:36-93``), ``create``
(``:112-129``) y ``write`` (``:131-160``) — los dos últimos además publican
en la bitácora.

*Métrica:* comparación por AST de los ocho ``self.<campo> = …`` de
``_onchange_requisition_id`` contra los campos declarados en
``api: addons/purchase/models/purchase_order.py`` tras la tarea #266.
*Ciega a:* si portar los tres restantes exige también ``account.fiscal
.position``/``account.payment.term`` con receptor propio — no medido en
este pase.

**Causa B — el método al que encadenan no existe.** Medido sobre ``addons/`` +
``src/``:

.. code-block:: text

    def _prepare_grouped_data   → 0
    def _merge_po_post_process  → 0
    def _merge_alternative_po   → 0
    def _compute_price_unit_and_date_planned_and_name → 0
    def _select_seller          → 0

Caen ``_prepare_grouped_data`` (``:236-238``), ``_merge_po_post_process``
(``:240-242``), ``_merge_alternative_po`` (``:244-247``) y
``_compute_price_unit_and_date_planned_and_name`` (``:261-292``).

**Causa C — ``env.ref`` de una vista XML.** ``action_create_alternative``
(``:162-172``) y ``action_compare_alternative_lines`` (``:174-190``) resuelven
un ``view_id`` sembrado por datos XML. Este árbol no siembra vistas (misma
ausencia que ``_for_xml_id``, 0 definiciones). Los dos son descriptores de
acción para el cliente web de Odoo, no lógica de negocio.

**Causa D — CERRADA (tarea #266).** Decía: *"la cabecera de
``purchase.order`` es un esqueleto — ``price_total_cc`` (``:257``) y
``company_currency_id`` (``:258``) más su ``_compute_price_total_cc``
(``:260-263``) dividen el subtotal entre ``order_id.currency_rate``, y ese
campo no existía"*. Se cerró portando la cabecera —``company_id``,
``currency_id``, ``currency_rate``— en
``api: addons/purchase/models/purchase_order.py`` (docstring del módulo, con
la tabla de forma de cada campo) y, en este archivo, los tres símbolos de
``PurchaseOrderLine`` que dependían de ella: ``price_total_cc``,
``company_currency_id`` (``@property``) y ``_compute_price_total_cc``.

**Divergencia de tipo heredada de la cabecera.** La fuente declara
``currency_field="company_currency_id"`` en ``price_total_cc`` —
``fields.Monetary`` en este ORM no acepta ``currency_field=`` porque no hay
columna de moneda por campo (mismo mecanismo que ``HrEmployee.hourly_cost``,
``api: addons/hr_hourly_cost/models/hr_employee.py:32-39``); la moneda ya se
resuelve por ``company_currency_id``, que es exactamente lo que
``currency_field=`` apuntaba a hacer.

**Causa E — depende de lo anterior.** ``action_choose`` (``:310-322``) llama a
``action_clear_quantities`` sobre las líneas de las alternativas, y necesita
``line.state`` — que la línea de este árbol no declara (lo declara la orden).
Se porta ``action_clear_quantities`` **con** esa divergencia (D-4) y
``action_choose`` **no**, porque su filtro cruza tres campos ausentes.

Divergencias declaradas
========================

**D-1 — ``alternative_po_ids`` es ``property``, no ``related`` escribible.** La
fuente lo declara ``related='purchase_group_id.order_ids', readonly=False``: se
lee del grupo y **escribirlo crea o deshace el grupo** (esa es la lógica de
``write``, ``:143-150``). Aquí es sólo lectura; la escritura vive en
``PurchaseOrderGroup``, que es donde el dato realmente está. Quien quiera
enlazar dos órdenes crea o amplía el grupo — una operación explícita en vez de
un efecto lateral de asignar un campo.

**D-2 — ``purchase.order.group`` sí se declara como modelo.** Es un modelo
propio de este addon (``_name`` nuevo), no una extensión, y su tabla no
depende de nada ausente: una clave primaria y el reverso de
``purchase.order.purchase_group_id``. Su ``write`` auto-implosivo se porta
sobre ``delete``… al revés: se porta como un método ``_implode_if_alone`` que
el llamador invoca tras enlazar, porque en la fuente lo dispara ``write`` sobre
el propio grupo y aquí el enlace se escribe en la **orden**, no en el grupo.

**D-3a — CERRADA (tarea #266).** Decía: *"``get_tender_best_lines`` compara
por subtotal de línea, no por ``price_total_cc``… el resultado sólo es
correcto si todas las alternativas están en la misma moneda"*. Con la Causa D
cerrada, ``get_tender_best_lines`` compara por ``line.price_total_cc`` —moneda
de la empresa—, igual que la fuente (``odoo19c: :197-217``): dos cotizaciones
en divisas distintas ya son comparables. Test discriminante:
``tests/unit/purchase_requisition/test_get_tender_best_lines_currency.py::
TestGetTenderBestLinesD3a::
test_prefers_the_cheaper_line_in_company_currency_not_the_smaller_raw_number``
— dos alternativas del mismo producto, una en pesos y otra en dólares con un
número crudo menor pero equivalente a más pesos al convertir; con
``PurchaseOrder._compute_currency_rate`` neutralizado a 1.0 fijo (control del
sub-patrón D de ``metrica-decide-la-conclusion.md``,
``scripts/evidence/neutering-purchase-currency-rate-266-*.txt``) el mismo
caso cae — de 1 passed a 1 failed.

**D-3b — sigue abierta.** La comparación por fecha (``:220-223``,
``date_planned``) queda fuera: ``date_planned`` **no existe** en
``purchase.order.line`` de este árbol —campo distinto de los tres que la
tarea #266 porta (``company_id``/``currency_id``/``currency_rate``)—. El
método sigue devolviendo la tripleta de la fuente con la lista de mejores
fechas **vacía**, para que su contrato no cambie. Condición de cierre:
portar ``date_planned`` a la línea (bloqueo medido, no "no se puede";
sucesor: nueva tarea a abrir cuando se porte ``date_planned``, aún sin
número).

**D-4 — ``action_clear_quantities`` no filtra por estado de línea.** La fuente
excluye las líneas ``cancel``/``purchase``; aquí el estado vive en la **orden**
(``purchase.order.state``), así que el filtro se aplica sobre ``line.order``.
Es la misma intención —no tocar lo ya comprometido— sobre el campo que sí
existe.
"""
from collections import defaultdict

from decimal import Decimal

import fields
import models
from addons.base.models import TimeStampedModel
from orm.environments import get_context
from orm.method_chain import chain_method
from orm.model_classes import extend_model


class PurchaseOrderGroup(TimeStampedModel):
    """``purchase.order.group`` — «Technical model to group PO for call to
    tenders»."""

    # Atributos de clase de modelo — los DOS que la fuente declara
    # (``odoo19c: :11-12``), verbatim.
    _name = 'purchase.order.group'
    _description = 'Technical model to group PO for call to tenders'

    class Meta:
        db_table = 'purchase_order_group'
        ordering = ['id']
        verbose_name = 'Grupo de órdenes de compra'
        verbose_name_plural = 'Grupos de órdenes de compra'

    def __str__(self) -> str:
        return f'grupo #{self.pk}'

    def implode_if_alone(self):
        """≙ ``write`` (``odoo19c: :16-20``) — D-2 del docstring del módulo.

        El comentario de la fuente es la regla entera: *«when len(POs) == 1,
        only linking PO to itself at this point => self implode (delete)
        group»*. Un grupo de una sola orden no agrupa nada.

        En la fuente lo dispara ``write`` sobre el grupo, porque allá el enlace
        se escribe en ``group.order_ids``. Aquí el enlace vive en
        ``purchase.order.purchase_group``, así que quien lo escriba invoca
        este método después. Devuelve ``True`` si el grupo se borró.
        """
        if self.order_ids.count() <= 1:
            self.delete()
            return True
        return False


# --- purchase.order --------------------------------------------------------

def requisition_type(self):
    """≙ ``requisition_type`` (``odoo19c: :27``) —
    ``related='requisition_id.requisition_type'``, sin columna."""
    return self.requisition.requisition_type if self.requisition_id else None


def alternative_po_ids(self):
    """≙ ``alternative_po_ids`` (``odoo19c: :30-34``) — D-1 del docstring.

    «Other potential purchase orders for purchasing products». El dominio de la
    fuente excluye la propia orden y se queda con las que siguen abiertas; se
    conserva, con los dos estados abiertos que esta ``purchase.order`` declara
    (``draft``, ``sent`` — no hay ``to approve`` en este árbol).
    """
    model = type(self)
    if self.purchase_group_id is None:
        return model.objects.none()
    return (model.objects
            .filter(purchase_group=self.purchase_group)
            .exclude(pk=self.pk)
            .filter(state__in=[model.STATE_DRAFT, model.STATE_SENT]))


def button_confirm(self):
    """≙ ``button_confirm`` (``odoo19c: :95-110``).

    Si la orden tiene alternativas todavía abiertas, la fuente **no confirma**:
    devuelve el descriptor del asistente que pregunta qué hacer con ellas
    (mantenerlas o cancelarlas). Es una guarda real, no un aviso: confirmar sin
    resolver las alternativas deja solicitudes vivas que nadie va a cerrar.

    ``get_context().get('skip_alternative_check')`` es la escotilla que el
    propio asistente usa al volver — se conserva con el mismo nombre.

    Devolver el descriptor **corta la cadena** (``chain_method`` sólo cede al
    método previo cuando el resultado es ``None``), que es exactamente el
    ``return`` temprano de la fuente. Cuando no hay alternativas abiertas
    devuelve ``None`` y la confirmación real la hace el método previo.

    **Divergencia:** la fuente resuelve la vista del asistente con
    ``env.ref(...)`` y la mete en ``views``; aquí no hay vistas XML sembradas,
    así que el descriptor lleva el modelo y el contexto pero no el ``view_id``.
    """
    open_orders = list(self.alternative_po_ids)
    if not open_orders:
        return None
    if get_context().get('skip_alternative_check'):
        return None
    return {
        'name': '¿Qué hacemos con las otras solicitudes de cotización?',
        'type': 'ir.actions.act_window',
        'view_mode': 'form',
        'res_model': 'purchase.requisition.alternative.warning',
        'target': 'new',
        'context': {
            'default_alternative_po_ids': [po.pk for po in open_orders],
            'default_po_ids': [self.pk],
        },
    }


def get_tender_best_lines(self):
    """≙ ``get_tender_best_lines`` (``odoo19c: :192-235``).

    Entre esta orden y sus alternativas, marca por producto: la línea de mejor
    **subtotal**, la de mejor **fecha** y la de mejor **precio unitario**. Son
    tres criterios distintos a propósito — el subtotal más bajo puede venir de
    una cantidad menor, y el precio unitario lo desempata.

    Los empates **acumulan**: la fuente usa ``|=`` para que dos líneas con el
    mismo precio queden ambas marcadas. Se conserva.

    D-3a CERRADA (tarea #266): compara con ``price_total_cc`` —moneda de la
    empresa— en vez de ``price_subtotal()``, igual que la fuente
    (``odoo19c: :197-217``). Ya no exige que las alternativas compartan
    divisa. D-3b sigue abierta: la lista de mejores fechas sale **vacía**
    porque ``date_planned`` no existe en la línea de este árbol — ver
    docstring del módulo.
    """
    best_subtotal = defaultdict(list)
    best_unit_price = defaultdict(list)
    orders = [self] + list(self.alternative_po_ids)

    for order_rec in orders:
        if order_rec.state in (type(self).STATE_CANCEL, type(self).STATE_PURCHASE):
            continue
        for line in order_rec.order_line.all():
            if not line.product_qty or not line.price_total_cc:
                continue
            subtotal = line.price_total_cc
            unit_price = subtotal / line.product_qty
            key = line.product_id

            if not best_subtotal[key]:
                best_subtotal[key] = [line]
                best_unit_price[key] = [line]
                continue

            current_subtotal = best_subtotal[key][0].price_total_cc
            reference_line = best_unit_price[key][0]
            current_unit_price = (reference_line.price_total_cc
                               / reference_line.product_qty)
            if current_subtotal > subtotal:
                best_subtotal[key] = [line]
            elif current_subtotal == subtotal:
                best_subtotal[key].append(line)
            if current_unit_price > unit_price:
                best_unit_price[key] = [line]
            elif current_unit_price == unit_price:
                best_unit_price[key].append(line)

    best_price_ids = {l.pk for lines in best_subtotal.values() for l in lines}
    best_price_unit_ids = {l.pk for lines in best_unit_price.values() for l in lines}
    # D-3b: sin ``date_planned`` en la línea no hay mejor fecha que calcular.
    best_date_ids = []
    return list(best_price_ids), best_date_ids, list(best_price_unit_ids)


def company_currency_id(self):
    """≙ ``company_currency_id`` (``odoo19c: :258``) —
    ``related="company_id.currency_id"``, sin ``store``.

    Divergencia de mecanismo: ``currency_field=`` de ``price_total_cc`` no
    tiene receptor en ``fields.Monetary`` — ver docstring del módulo (mismo
    criterio que ``HrEmployee.hourly_cost``).
    """
    return self.company_id.currency if self.company_id_id else None


def _compute_price_total_cc(self):
    """≙ ``_compute_price_total_cc`` (``odoo19c: :260-263``).

    Divide el subtotal de la línea entre la tasa de la orden — de ahí que
    ``PurchaseOrder.currency_rate`` sea ``fields.Monetary`` (``Decimal``) y
    no ``fields.Float`` como en la fuente: ``Decimal / float`` levanta
    ``TypeError`` en Python (ver docstring de
    ``api: addons/purchase/models/purchase_order.py``).
    """
    order = self.order_id
    rate = order.currency_rate if order is not None and order.currency_rate else Decimal('1.0')
    self.price_total_cc = (self.price_subtotal() / rate).quantize(Decimal('0.01'))


def save_price_total_cc(self, previous, *args, **kwargs):
    """Recompila ``price_total_cc`` antes de persistir — este ORM no dispara
    ``@api.depends`` (tarea #191).

    Instalado con ``wrap_method`` (no ``chain_method``): la previa llega **en
    la mano**, ligada al receptor, porque necesito mutar ``update_fields`` y
    pasárselo yo mismo — con ``chain_method`` la mutación de ``kwargs`` no
    llega a la previa (cada llamada con ``**kwargs`` empaqueta un ``dict``
    nuevo en el frame receptor; medido al escribir esto, no supuesto). La
    previa es ``PurchaseOrderLine.save()`` de ``purchase`` (sincroniza
    ``company_id``) y, tras ella, el ``save()`` de Django.
    """
    self._compute_price_total_cc()
    update_fields = kwargs.get('update_fields')
    if update_fields is not None and 'price_total_cc' not in update_fields:
        kwargs['update_fields'] = [*update_fields, 'price_total_cc']
    return previous(*args, **kwargs)


# --- purchase.order.line ---------------------------------------------------

def action_clear_quantities(self):
    """≙ ``action_clear_quantities`` (``odoo19c: :295-308``) — D-4 del docstring.

    Pone a cero las cantidades de las líneas que **todavía se pueden tocar**, y
    avisa si alguna quedó sin limpiar por estar ya comprometida.

    D-4: la fuente filtra por ``line.state``; aquí el estado vive en la orden,
    así que el filtro es ``self.order.state``. Misma intención, sobre el campo
    que existe.

    Es un método de **instancia** en este puerto y de recordset en la fuente:
    quien limpie varias líneas itera. El aviso de «algunas no se limpiaron» lo
    devuelve la línea que no se pudo limpiar, que es la información útil.
    """
    order = self.order_id
    if order is not None and order.state in (type(order).STATE_CANCEL,
                                             type(order).STATE_PURCHASE):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Algunas no se limpiaron',
                'message': 'Algunas cantidades no se pusieron a cero porque su '
                           'estado ya no es el de una solicitud de cotización.',
                'sticky': False,
            },
        }
    self.product_qty = 0
    self.save(update_fields=['product_qty', 'updated_at'])
    return False


def _install_order(model):
    chain_method(model, 'button_confirm', button_confirm)


def apply_purchase_requisition_purchase_extensions():
    """Cuelga sobre ``purchase.PurchaseOrder`` y ``purchase.PurchaseOrderLine``
    lo que ``purchase_requisition`` les añade — ≙ los dos ``_inherit``.

    ``PurchaseOrderGroup`` NO va aquí: es un modelo propio de este addon y se
    declara en el cuerpo del módulo, no por extensión.
    """
    extend_model(
        'purchase', 'PurchaseOrder',
        campos={
            'requisition': fields.Many2one(
                'purchase_requisition.PurchaseRequisition',
                null=True, blank=True, on_delete=models.SET_NULL,
                db_index=True, related_name='purchase_ids',
                verbose_name='Acuerdo',
                help_text='Acuerdo de compra del que nace esta orden '
                          '(Odoo requisition_id).',
            ),
            'purchase_group': fields.Many2one(
                'purchase_requisition.PurchaseOrderGroup',
                null=True, blank=True, on_delete=models.SET_NULL,
                db_index=True, related_name='order_ids',
                verbose_name='Grupo de alternativas',
                help_text='Grupo que reúne esta orden con sus alternativas '
                          '(Odoo purchase_group_id).',
            ),
        },
        propiedades={
            'requisition_type': requisition_type,
            'alternative_po_ids': alternative_po_ids,
        },
        metodos={'get_tender_best_lines': get_tender_best_lines},
        luego=_install_order,
    )

    extend_model(
        'purchase', 'PurchaseOrderLine',
        campos={
            'price_total_cc': fields.Monetary(
                null=True, blank=True, max_digits=12, decimal_places=2,
                default=Decimal('0.00'),
                verbose_name='Subtotal en moneda de la empresa',
                help_text='Odoo price_total_cc ("Company Subtotal", compute, '
                          "store=True, currency_field='company_currency_id' "
                          '— sin receptor aquí, ver docstring del módulo). '
                          '``price_subtotal`` / ``order_id.currency_rate``.',
            ),
        },
        propiedades={'company_currency_id': company_currency_id},
        metodos={
            'action_clear_quantities': action_clear_quantities,
            '_compute_price_total_cc': _compute_price_total_cc,
        },
        overrides={'save': save_price_total_cc},
    )
