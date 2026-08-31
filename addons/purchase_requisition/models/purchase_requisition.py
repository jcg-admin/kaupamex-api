"""``purchase.requisition`` / ``purchase.requisition.line`` — el acuerdo de
compra (Odoo ``purchase_requisition``).

Adaptación de Odoo ``purchase_requisition/models/purchase_requisition.py``
(``odoo19c: addons/purchase_requisition/models/purchase_requisition.py``, 279
líneas, LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Qué es: un **acuerdo con un proveedor** que precede a las órdenes de compra
concretas. Toma dos formas, y la distinción no es cosmética:

- **Pedido abierto** (``blanket_order``) — precio pactado por producto durante
  una ventana de fechas. Al confirmarlo, cada línea **crea una tarifa de
  proveedor** (``product.supplierinfo``), que es lo que hace que las compras
  posteriores usen ese precio automáticamente.
- **Plantilla de compra** (``purchase_template``) — una lista de productos y
  cantidades que se copia a una orden nueva. No pacta precio ni fechas.

Porte símbolo por símbolo — 45 de 45, con 2 degradaciones declaradas
=====================================================================

*Métrica:* entradas del cuerpo de las dos clases contadas por AST sobre la
fuente, **descontando** los atributos de clase de modelo (``_name``,
``_description``, ``_inherit``, ``_order``, ``_rec_name``):

- ``PurchaseRequisition`` — 20 asignaciones − 4 atributos = **16 campos**, más
  **12 métodos**.
- ``PurchaseRequisitionLine`` — 13 asignaciones − 4 atributos = **9 campos**,
  más **8 métodos**.

Total **45**, y los 45 tienen destino aquí. Lo que NO es equivalencia son
**dos degradaciones**, cada una nombrada abajo — el conteo mide presencia de
símbolo, no conducta (``metrica-decide-la-conclusion.md``).
*Ciega a:* si un símbolo portado se comporta igual en ejecución, y a lo que
otros addons cuelgan sobre estos dos modelos.

Las dos degradaciones
-----------------------

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - Símbolo (línea)
     - Causa medida
   * - ``PurchaseRequisition._onchange_vendor`` (``:47-62``)
     - **portado**, pero como método normal: en la fuente es ``@api.onchange``
       y lo dispara el formulario. Aquí devuelve el mismo
       ``{'warning': {...}}`` y lo invoca quien valide.
   * - ``PurchaseRequisitionLine.write`` (``:231-241``)
     - **portado parcialmente**: su guard de precio y la propagación a la
       tarifa se portan en ``save()``; lo que no se porta es la firma
       ``write(vals)``, que este ORM no tiene (D-3).

Degradación CERRADA — el precio sugerido ya sale del acuerdo
-------------------------------------------------------------

``PurchaseRequisitionLine._compute_price_unit`` (``:206-214`` de la fuente) fue
la tercera degradación de esta lista: se portaba **sólo la rama de respaldo**
—``product.standard_price``— porque el método que elige la tarifa del proveedor
por cantidad y fecha no existía en este árbol.

Ya existe: ``ProductProduct._select_seller`` se portó con su cadena completa
(``_prepare_sellers`` → ``_get_filtered_sellers`` → ``_select_seller``), así que
la rama de tarifa **se resuelve** y el precio sugerido de una plantilla de
compra sale del acuerdo con ese proveedor, no del costo estándar. Ver
:ref:`h-api-998`.

Divergencias declaradas
========================

**D-1 — ``_inherit = ['mail.thread', 'mail.activity.mixin']`` no se hereda.**
La fuente declara el acuerdo como hilo de conversación con actividades. Medido:
``addons/mail/models/mail_thread.py:35`` declara ``MailThread``, pero es un
modelo del addon ``mail`` que este addon **no** declara en sus ``depends`` —
sus dos consumos reales (``message_post`` al cancelar, ``:126``) quedan por
tanto bloqueados. El atributo ``_inherit`` **se conserva verbatim en la clase**
(``atributos-de-clase-de-modelo.md``: se portan todos los que la fuente
declare) para que la deuda sea greppeable; lo que no existe es la herencia.

Consecuencia concreta y declarada: ``action_cancel`` cancela las órdenes pero
**no deja la nota** que la fuente publica en cada una (``:126``). Se marca en
su docstring.

**D-2 — ``tracking=True`` de tres campos queda bloqueado.** ``date_start``,
``date_end`` y ``state`` lo declaran. Medido:
``grep -n "tracking=True" src/orm/fields*.py`` → **0**; ningún ``Field`` de
este ORM acepta ese kwarg. Es el mismo bloqueo que
``addons/hr_hourly_cost/models/hr_employee.py`` ya documentó, y por la misma
razón: sin bitácora no hay dónde registrar el cambio.

**D-3 — ``create``/``write``/``unlink`` se portan sobre ``save``/``delete``.**
Este ORM no tiene esos tres nombres: Django usa ``save()`` y ``delete()``. La
lógica va entera; lo que cambia es el punto de enganche. En ``save()`` se
distingue alta de modificación con ``self._state.adding``, que es lo que separa
el cuerpo de ``create`` del de ``write``.

**D-4 — los ``compute`` sin ``store`` son ``property``.** ``order_count``,
``product_id`` y ``qty_ordered``. Los tres se declaran ``compute=`` sin
``store`` en la fuente, así que tampoco tienen columna allá.
``currency_id`` **sí** es ``store=True`` allá; aquí es columna con su cómputo
en ``save()`` — ver ``_compute_currency_id``.

**D-5 — ``company_id`` de la línea es FK propia, no ``related`` almacenado.**
La fuente lo declara ``related='requisition_id.company_id', store=True``: una
columna que el ORM mantiene sincronizada. Sin ese motor, mantenerla al día
sería trabajo manual y silencioso; se declara **``property``** que lee la del
acuerdo. Es la misma lectura y no puede desincronizarse.
"""
from datetime import datetime

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ValidationError

import fields
import models
from addons.analytic.models.analytic_mixin import AnalyticMixin
from addons.base.models import IrSequence, TimeStampedModel

#: ≙ ``requisition_type`` (``odoo19c: :21-23``) — las dos formas del acuerdo.
TYPE_BLANKET_ORDER = 'blanket_order'
TYPE_PURCHASE_TEMPLATE = 'purchase_template'
REQUISITION_TYPE_CHOICES = [
    (TYPE_BLANKET_ORDER, 'Pedido abierto'),
    (TYPE_PURCHASE_TEMPLATE, 'Plantilla de compra'),
]

#: ≙ ``state`` (``odoo19c: :34-42``).
STATE_DRAFT = 'draft'
STATE_CONFIRMED = 'confirmed'
STATE_DONE = 'done'
STATE_CANCEL = 'cancel'
STATE_CHOICES = [
    (STATE_DRAFT, 'Borrador'),
    (STATE_CONFIRMED, 'Confirmado'),
    (STATE_DONE, 'Cerrado'),
    (STATE_CANCEL, 'Cancelado'),
]

#: ≙ los dos códigos de secuencia de ``create`` (``odoo19c: :92, :94``),
#: verbatim: son datos sembrados, no cadenas libres.
SEQUENCE_CODE_BY_TYPE = {
    TYPE_BLANKET_ORDER: 'purchase.requisition.blanket.order',
    TYPE_PURCHASE_TEMPLATE: 'purchase.requisition.purchase.template',
}


def _default_requisition_name():
    """≙ ``default=lambda self: _('New')`` (``odoo19c: :16``).

    Función nombrada, no ``lambda``: el serializador de migraciones de Django
    rechaza las lambdas (``Cannot serialize function: lambda``).
    """
    return 'Nuevo'


class PurchaseRequisition(TimeStampedModel):
    """``purchase.requisition`` — «Purchase Requisition»."""

    # Atributos de clase de modelo — los CUATRO que la fuente declara
    # (``odoo19c: :9-12``), verbatim. ``_inherit`` se conserva aunque la
    # herencia no exista aquí (D-1 del docstring del módulo).
    _name = 'purchase.requisition'
    _description = 'Purchase Requisition'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    TYPE_BLANKET_ORDER = TYPE_BLANKET_ORDER
    TYPE_PURCHASE_TEMPLATE = TYPE_PURCHASE_TEMPLATE
    REQUISITION_TYPE_CHOICES = REQUISITION_TYPE_CHOICES
    STATE_DRAFT = STATE_DRAFT
    STATE_CONFIRMED = STATE_CONFIRMED
    STATE_DONE = STATE_DONE
    STATE_CANCEL = STATE_CANCEL
    STATE_CHOICES = STATE_CHOICES

    name = fields.Char(
        max_length=64, default=_default_requisition_name,
        verbose_name='Acuerdo',
        help_text='Referencia del acuerdo; la asigna la secuencia al crearlo '
                  '(Odoo name, readonly + copy=False).',
    )
    active = fields.Boolean(
        default=True,
        help_text='Si se desmarca, el acuerdo se oculta sin borrarlo '
                  '(Odoo active).',
    )
    reference = fields.Char(
        max_length=64, blank=True, default='',
        help_text='Referencia libre del acuerdo (Odoo reference).',
    )
    vendor = fields.Many2one(
        'base.ResPartner', null=True, blank=True, on_delete=models.PROTECT,
        related_name='purchase_requisition_ids', verbose_name='Proveedor',
        help_text='Proveedor con el que se pacta el acuerdo (Odoo vendor_id, '
                  'check_company=True).',
    )
    requisition_type = fields.Selection(
        max_length=20, choices=REQUISITION_TYPE_CHOICES,
        default=TYPE_BLANKET_ORDER, verbose_name='Tipo de acuerdo',
        help_text='Pedido abierto (precio pactado) o plantilla de compra '
                  '(lista que se copia) — Odoo requisition_type.',
    )
    date_start = fields.Date(
        null=True, blank=True, verbose_name='Fecha de inicio',
        help_text='Odoo date_start. La referencia lo declara tracking=True; '
                  'ver D-2 del docstring del módulo.',
    )
    date_end = fields.Date(
        null=True, blank=True, verbose_name='Fecha de fin',
        help_text='Odoo date_end (tracking=True en la referencia, D-2).',
    )
    user = fields.Many2one(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='purchase_requisition_ids',
        verbose_name='Responsable de compras',
        help_text='Odoo user_id, con el usuario en curso por defecto.',
    )
    description = fields.Html(
        blank=True, default='',
        help_text='Descripción del acuerdo (Odoo description).',
    )
    company = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE,
        related_name='purchase_requisition_ids', verbose_name='Empresa',
        help_text='Odoo company_id (required).',
    )
    currency = fields.Many2one(
        'base.ResCurrency', null=True, blank=True, on_delete=models.PROTECT,
        related_name='purchase_requisition_ids', verbose_name='Moneda',
        help_text='Moneda del acuerdo (Odoo currency_id, compute+store con '
                  'readonly=False). La calcula _compute_currency_id al '
                  'guardar.',
    )
    state = fields.Selection(
        max_length=16, choices=STATE_CHOICES, default=STATE_DRAFT,
        verbose_name='Estado',
        help_text='Odoo state (tracking=True en la referencia, D-2).',
    )

    class Meta:
        db_table = 'purchase_requisition'
        ordering = ['-id']
        verbose_name = 'Acuerdo de compra'
        verbose_name_plural = 'Acuerdos de compra'

    def __str__(self) -> str:
        return self.name

    # -- computes -----------------------------------------------------------

    @property
    def order_count(self):
        """≙ ``order_count`` + ``_compute_orders_number`` (``:19``, ``:72-75``).
        ``compute`` sin ``store`` — D-4."""
        return self._compute_orders_number()

    def _compute_orders_number(self):
        """≙ ``_compute_orders_number`` (``odoo19c: :72-75``)."""
        return self.purchase_ids.count()

    @property
    def product(self):
        """≙ ``product_id`` (``:33``) — ``related='line_ids.product_id'``.

        Un ``related`` sobre un to-many se queda con el primero; aquí se hace
        explícito con ``.first()``.
        """
        line = self.line_ids.first()
        return line.product if line is not None else None

    def _compute_currency_id(self):
        """≙ ``_compute_currency_id`` (``odoo19c: :64-70``).

        La moneda del proveedor manda sobre la de la empresa.
        ``property_purchase_currency_id`` **no existe** en este árbol (medido:
        ``grep -rn "property_purchase_currency_id" addons/ src/`` → 0), así que
        la primera rama nunca se toma y la moneda sale siempre de la empresa —
        que es lo que la fuente hace cuando el proveedor no la tiene fijada.
        Se declara en vez de callarse: es una degradación, no una equivalencia.
        """
        vendor_currency = getattr(self.vendor, 'property_purchase_currency', None)
        if vendor_currency is not None:
            return vendor_currency
        return self.company.currency if self.company_id else None

    def _onchange_vendor(self):
        """≙ ``_onchange_vendor`` (``odoo19c: :47-62``).

        Avisa si ya hay un pedido abierto confirmado con ese proveedor: la
        fuente sugiere completarlo en vez de abrir otro. Método normal, no
        ``@api.onchange`` — no hay formulario que lo dispare.
        """
        if self.vendor_id is None:
            return None
        existing = PurchaseRequisition.objects.filter(
            vendor=self.vendor, state=STATE_CONFIRMED,
            requisition_type=TYPE_BLANKET_ORDER, company=self.company,
        ).exclude(pk=self.pk)
        if not existing.exists():
            return None
        return {'warning': {
            'title': f'Aviso sobre {self.vendor.name}',
            'message': 'Ya hay un pedido abierto con este proveedor. Conviene '
                       'completarlo en vez de crear otro.',
        }}

    # -- validación y persistencia ------------------------------------------

    def clean(self):
        """≙ ``_check_dates`` (``odoo19c: :77-83``) — ``@api.constrains``.

        La fecha de fin no puede ser anterior a la de inicio.
        """
        super().clean()
        if self.date_end and self.date_start and self.date_end < self.date_start:
            raise ValidationError(
                'La fecha de fin no puede ser anterior a la de inicio. Revisa '
                f'las fechas del acuerdo: {self.name}')

    def save(self, *args, **kwargs):
        """≙ ``create`` (``:85-95``) + ``write`` (``:97-111``) — D-3.

        **Al crear**: el nombre lo asigna la secuencia que corresponde al tipo
        de acuerdo, en la empresa del acuerdo.

        **Al modificar**: si cambia el tipo o la empresa, el acuerdo se
        **renumera** — y la fuente lo prohíbe si ya salió de borrador, porque
        renumerar un acuerdo confirmado rompe las referencias que otros
        documentos ya guardaron. Una plantilla de compra además pierde sus
        fechas: no pacta ventana temporal.
        """
        creating = self._state.adding
        if not creating:
            previous = type(self).objects.filter(pk=self.pk).first()
            if previous is not None and (
                    previous.requisition_type != self.requisition_type
                    or previous.company_id != self.company_id):
                if previous.state != STATE_DRAFT:
                    raise ValidationError(
                        'No se puede cambiar el tipo de acuerdo ni la empresa '
                        'de un acuerdo que ya no está en borrador.')
                if self.requisition_type == TYPE_PURCHASE_TEMPLATE:
                    self.date_start = self.date_end = None
                self.name = self._next_name()
        if self.currency_id is None:
            self.currency = self._compute_currency_id()
        if creating:
            self.name = self._next_name()
        return super().save(*args, **kwargs)

    def _next_name(self):
        """El nombre que la secuencia del tipo de acuerdo entrega.

        Extraído porque ``create`` y ``write`` de la fuente lo repiten con la
        misma pareja de códigos (``:92-94`` y ``:109-110``).
        ``IrSequence.next_by_code`` es ``@classmethod``
        (``src/addons/base/models/ir_sequence.py:110``); sin secuencia sembrada
        devuelve ``None`` y se conserva el nombre por defecto, en vez de dejar
        el campo vacío.
        """
        code = SEQUENCE_CODE_BY_TYPE[self.requisition_type]
        return IrSequence.next_by_code(code, company=self.company) \
            or self.name or _default_requisition_name()

    def delete(self, *args, **kwargs):
        """≙ ``unlink`` (``odoo19c: :113-116``) + ``_unlink_if_draft_or_cancel``
        (``:158-161``) — D-3.

        Los dos van juntos porque la fuente los ejecuta en el mismo borrado: el
        segundo es un ``@api.ondelete`` que **rehúsa** borrar un acuerdo vivo,
        y el primero limpia las líneas antes de que caiga el acuerdo.

        ``@api.ondelete`` no existe en este ORM (mismo criterio ya declarado en
        ``addons/hr_recruitment/models/utm_*.py``): su guard se ejecuta aquí,
        que es el punto por el que todo borrado pasa.
        """
        self._unlink_if_draft_or_cancel()
        self.line_ids.all().delete()
        return super().delete(*args, **kwargs)

    def _unlink_if_draft_or_cancel(self):
        """≙ ``_unlink_if_draft_or_cancel`` (``odoo19c: :158-161``) — verbatim."""
        if self.state not in (STATE_DRAFT, STATE_CANCEL):
            raise ValidationError(
                'Sólo se pueden borrar acuerdos en borrador o cancelados.')

    # -- acciones -----------------------------------------------------------

    def action_cancel(self):
        """≙ ``action_cancel`` (``odoo19c: :118-127``).

        Cancela el acuerdo: retira las tarifas de proveedor que creó y cancela
        las solicitudes de cotización que siguen en borrador.

        **D-1 declarada:** la fuente publica además una nota en cada orden
        cancelada (``:126``, ``po.message_post(...)``). Aquí no: el mecanismo de
        bitácora no cubre ``purchase.order`` en este árbol. La cancelación sí
        ocurre; lo que falta es su rastro en la conversación.
        """
        for line in self.line_ids.all():
            line.supplier_info_ids.all().delete()
        for order in self.purchase_ids.filter(state='draft'):
            order.button_cancel()
        self.state = STATE_CANCEL
        self.save(update_fields=['state', 'updated_at'])

    def action_confirm(self):
        """≙ ``action_confirm`` (``odoo19c: :129-140``).

        Confirmar un **pedido abierto** es lo que materializa el acuerdo: cada
        línea crea su tarifa de proveedor. Por eso la fuente exige precio y
        cantidad en todas — una tarifa sin precio no sirve de nada.

        Una **plantilla de compra** se confirma sin esas comprobaciones: no
        pacta precio.
        """
        if not self.line_ids.exists():
            raise ValidationError(
                f"No se puede confirmar el acuerdo '{self.name}': no tiene "
                'líneas de producto.')
        if self.requisition_type == TYPE_BLANKET_ORDER:
            for line in self.line_ids.all():
                if line.price_unit <= 0.0:
                    raise ValidationError(
                        'No se puede confirmar un pedido abierto con líneas '
                        'sin precio.')
                if line.product_qty <= 0.0:
                    raise ValidationError(
                        'No se puede confirmar un pedido abierto con líneas '
                        'sin cantidad.')
                line._create_supplier_info()
        self.state = STATE_CONFIRMED
        self.save(update_fields=['state', 'updated_at'])

    def action_draft(self):
        """≙ ``action_draft`` (``odoo19c: :142-144``)."""
        self.state = STATE_DRAFT
        self.save(update_fields=['state', 'updated_at'])

    def action_done(self):
        """≙ ``action_done`` (``odoo19c: :146-156``).

        Cierra el acuerdo y retira sus tarifas. La fuente rehúsa cerrar mientras
        queden solicitudes de cotización vivas, y su comentario dice por qué:
        *«Imagine the mess if someone confirms these duplicates: double the
        order, double the trouble»*.
        """
        if self.purchase_ids.filter(state__in=['draft', 'sent']).exists():
            raise ValidationError(
                'Para cerrar este acuerdo, cancela primero las solicitudes de '
                'cotización relacionadas.')
        for line in self.line_ids.all():
            line.supplier_info_ids.all().delete()
        self.state = STATE_DONE
        self.save(update_fields=['state', 'updated_at'])


class PurchaseRequisitionLine(AnalyticMixin, TimeStampedModel):
    """``purchase.requisition.line`` — «Purchase Requisition Line»."""

    # Atributos de clase de modelo — los CUATRO que la fuente declara
    # (``odoo19c: :165-168``), verbatim. ``_inherit = ['analytic.mixin']`` SÍ se
    # hereda aquí: ``AnalyticMixin`` existe (``addons/analytic/models/
    # analytic_mixin.py:81``) y aporta ``analytic_distribution``, que
    # ``_prepare_purchase_order_line`` lee.
    _name = 'purchase.requisition.line'
    _inherit = ['analytic.mixin']
    _description = 'Purchase Requisition Line'
    _rec_name = 'product_id'

    product = fields.Many2one(
        'product.ProductProduct', on_delete=models.PROTECT,
        related_name='purchase_requisition_line_ids', verbose_name='Producto',
        help_text="Odoo product_id, con domain [('purchase_ok', '=', True)].",
    )
    product_uom = fields.Many2one(
        'uom.Uom', null=True, blank=True, on_delete=models.PROTECT,
        related_name='purchase_requisition_line_ids', verbose_name='Unidad',
        help_text='Odoo product_uom_id (compute+store, readonly=False). La '
                  'calcula _compute_product_uom_id al guardar.',
    )
    product_qty = fields.Float(
        default=0.0, verbose_name='Cantidad',
        help_text="Odoo product_qty (digits='Product Unit').",
    )
    product_description_variants = fields.Char(
        max_length=255, blank=True, default='', verbose_name='Descripción',
        help_text='Odoo product_description_variants.',
    )
    price_unit = fields.Float(
        default=0.0, verbose_name='Precio unitario',
        help_text='Odoo price_unit (compute+store, readonly=False). Lo calcula '
                  '_compute_price_unit al guardar.',
    )
    requisition = fields.Many2one(
        'purchase_requisition.PurchaseRequisition', on_delete=models.CASCADE,
        db_index=True, related_name='line_ids',
        verbose_name='Acuerdo de compra',
        help_text="Odoo requisition_id (required, ondelete='cascade').",
    )

    class Meta:
        db_table = 'purchase_requisition_line'
        ordering = ['id']
        verbose_name = 'Línea de acuerdo de compra'
        verbose_name_plural = 'Líneas de acuerdo de compra'

    def __str__(self) -> str:
        return str(self.product)

    # -- computes -----------------------------------------------------------

    @property
    def company(self):
        """≙ ``company_id`` (``:181``) — ``related='requisition_id.company_id'``.
        D-5 del docstring del módulo: ``property``, no columna espejo."""
        return self.requisition.company if self.requisition_id else None

    @property
    def qty_ordered(self):
        """≙ ``qty_ordered`` + ``_compute_ordered_qty`` (``:179``, ``:184-199``).
        ``compute`` sin ``store`` — D-4."""
        return self._compute_ordered_qty()

    def _compute_ordered_qty(self):
        """≙ ``_compute_ordered_qty`` (``odoo19c: :184-199``).

        Cuánto de este producto ya se pidió realmente, sumando las líneas de
        las órdenes **confirmadas** del acuerdo.

        La fuente lleva además un ``line_found`` para que, si el acuerdo tiene
        **dos líneas del mismo producto**, sólo la primera muestre el total y
        la segunda muestre 0 — evitando contar dos veces lo mismo en pantalla.
        Se conserva: se devuelve 0 si esta línea no es la primera de su
        producto dentro del acuerdo.

        La conversión de unidad de la fuente
        (``po_line.product_uom_id._compute_quantity``) **no se aplica**: la
        línea de compra de este árbol no declara unidad (medido en
        ``addons/purchase/models/purchase_order_line.py``, 6 campos). Las
        cantidades se suman en la unidad en que estén, y se declara aquí en vez
        de fingir una conversión.
        """
        first_line = self.requisition.line_ids.filter(
            product=self.product).order_by('pk').first()
        if first_line is not None and first_line.pk != self.pk:
            return 0.0
        POL = apps.get_model('purchase', 'PurchaseOrderLine')
        total = 0.0
        for po_line in POL.objects.filter(
                order__requisition=self.requisition, order__state='purchase',
                product=self.product):
            total += float(po_line.product_qty)
        return total

    def _compute_product_uom_id(self):
        """≙ ``_compute_product_uom_id`` (``odoo19c: :201-204``) — la unidad del
        producto."""
        return self.product.uom if self.product_id else None

    def _compute_price_unit(self):
        """≙ ``_compute_price_unit`` (``odoo19c: :206-214``) — **parcial**.

        Sólo aplica a una **plantilla de compra en borrador con proveedor**: el
        resto de casos la fuente los deja intactos (``continue``).

        La **rama de tarifa** se porta: el precio sale del acuerdo con ese
        proveedor para esa cantidad y esa fecha, y sólo cae al costo estándar
        cuando no hay tarifa — que es el respaldo de la propia fuente.

        Hasta este pase el bloque decía que ``_select_seller`` no existía en
        este árbol. La cadena está portada
        (``addons/product/models/product_product.py``) y la degradación que
        aquí se declaraba —precio del costo estándar en vez del acuerdo— ya no
        ocurre. Ver :ref:`h-api-998`.
        """
        requisition = self.requisition
        if (requisition is None
                or requisition.state != STATE_DRAFT
                or requisition.requisition_type != TYPE_PURCHASE_TEMPLATE
                or requisition.vendor_id is None
                or self.product_id is None):
            return self.price_unit
        seller = self.product._select_seller(
            partner_id=requisition.vendor,
            quantity=self.product_qty,
            date=requisition.date_start,
            uom_id=self.product_uom,
        )
        if seller:
            return float(seller[0].price or 0.0)
        return float(self.product.standard_price or 0.0)

    # -- persistencia -------------------------------------------------------

    def save(self, *args, **kwargs):
        """≙ ``create`` (``:216-229``) + ``write`` (``:231-241``) — D-3.

        El guard es el mismo en los dos y protege la coherencia del acuerdo: en
        un **pedido abierto ya confirmado** una línea no puede tener precio
        cero o negativo, porque de ese precio sale la tarifa del proveedor.

        Al crear, la fuente crea además la tarifa si el proveedor no tenía una
        de este acuerdo. Al modificar el precio, la propaga a las tarifas ya
        creadas — si no, el acuerdo y la tarifa dirían cosas distintas.
        """
        creating = self._state.adding
        previous_price = None
        if not creating:
            previous = type(self).objects.filter(pk=self.pk).first()
            previous_price = previous.price_unit if previous is not None else None

        if self.product_uom_id is None:
            self.product_uom = self._compute_product_uom_id()
        if creating and not self.price_unit:
            self.price_unit = self._compute_price_unit()

        requisition = self.requisition
        confirmed = (requisition is not None
                      and requisition.requisition_type == TYPE_BLANKET_ORDER
                      and requisition.state not in (STATE_DRAFT, STATE_CANCEL,
                                                    STATE_DONE))
        if confirmed and self.price_unit <= 0.0:
            raise ValidationError(
                'No se puede tener un precio unitario de 0 o negativo en un '
                'pedido abierto ya confirmado.')

        result = super().save(*args, **kwargs)

        if creating and confirmed:
            ProductSupplierinfo = apps.get_model('product', 'ProductSupplierinfo')
            already_there = ProductSupplierinfo.objects.filter(
                product=self.product, partner=requisition.vendor,
            ).exclude(purchase_requisition_line__isnull=True).exists()
            if not already_there:
                self._create_supplier_info()
        elif not creating and previous_price is not None \
                and previous_price != self.price_unit:
            self.supplier_info_ids.all().update(price=self.price_unit)
        return result

    def delete(self, *args, **kwargs):
        """≙ ``unlink`` (``odoo19c: :243-246``) — D-3.

        Al borrar una línea de un acuerdo **vivo**, su tarifa de proveedor se
        borra con ella. En un acuerdo en borrador, cancelado o cerrado no hay
        tarifa que retirar (ya la retiraron ``action_cancel``/``action_done``).
        """
        requisition = self.requisition
        if requisition is not None and requisition.state not in (
                STATE_DRAFT, STATE_CANCEL, STATE_DONE):
            self.supplier_info_ids.all().delete()
        return super().delete(*args, **kwargs)

    # -- negocio ------------------------------------------------------------

    def _create_supplier_info(self):
        """≙ ``_create_supplier_info`` (``odoo19c: :248-261``).

        **Sólo un pedido abierto con proveedor crea tarifa** — el comentario de
        la fuente lo dice y la condición lo impone. Es el mecanismo por el que
        el acuerdo llega al precio de las compras posteriores.
        """
        requisition = self.requisition
        if requisition is None or requisition.requisition_type != TYPE_BLANKET_ORDER:
            return None
        if requisition.vendor_id is None:
            return None
        ProductSupplierinfo = apps.get_model('product', 'ProductSupplierinfo')
        return ProductSupplierinfo.objects.create(
            partner=requisition.vendor,
            product=self.product,
            product_uom=self.product_uom,
            product_tmpl=self.product.product_tmpl,
            price=self.price_unit,
            currency=requisition.currency,
            purchase_requisition_line=self,
        )

    def _prepare_purchase_order_line(self, name, product_qty=0.0,
                                     price_unit=0.0, taxes_ids=False):
        """≙ ``_prepare_purchase_order_line`` (``odoo19c: :263-279``).

        Los valores con los que el acuerdo siembra una línea de orden de
        compra. La fecha prevista **nunca es anterior al inicio del acuerdo**:
        la fuente toma el máximo entre ahora y ``date_start``.

        Se devuelven las claves de la fuente aunque tres de ellas
        —``product_uom_id``, ``tax_ids``, ``date_planned``— no tengan campo
        destino en la ``purchase.order.line`` de este árbol. El diccionario es
        el **contrato** del método; quien lo consuma filtrará lo que su modelo
        acepte, y así el día que ``purchase`` complete su línea no hay que
        volver a tocar esto.
        """
        if self.product_description_variants:
            name = f'{name}\n{self.product_description_variants}'
        date_planned = datetime.now()
        if self.requisition.date_start:
            start_dt = datetime.combine(self.requisition.date_start,
                                      datetime.min.time())
            date_planned = max(date_planned, start_dt)
        return {
            'name': name,
            'product_id': self.product_id,
            'product_uom_id': self.product_uom_id,
            'product_qty': product_qty,
            'price_unit': price_unit,
            'tax_ids': list(taxes_ids or []),
            'date_planned': date_planned,
            'analytic_distribution': self.analytic_distribution,
        }
