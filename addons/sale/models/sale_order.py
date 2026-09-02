"""Modelo ``SaleOrder`` — addon ``sale``.

Adaptación fiel del módulo Odoo ``sale`` (``sale/models/sale_order.py``). En
Odoo **no existe un modelo "cart"**: el carrito es un ``sale.order`` con
``state='draft'`` (``website_sale``) y la orden confirmada es ``state='sale'``.
Este addon es el modelo canónico que **absorbe** la divergencia ``cart`` +
``orders`` (ver ``analisis-unificar-cart-order-sale``).

Fidelidad de scope: se portan los campos comerciales core de ``sale.order``
(``name``/``partner_id``/``state``/``date_order``/``order_line`` + amounts). Los
estados de *fulfillment* (enviado/entregado) y *pago* (pagado) NO viven aquí — en
Odoo están en ``stock.picking`` y ``payment.transaction``/``account.move``; se
integran en sus addons (``inventory``/``logistics``/``payments``).
"""
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
import api
import fields
import models
from django.db import connection, transaction
from django.utils import timezone

from exceptions import UserError
from orm.environments import get_context
from tools.sql import SQL
from tools.translate import _

from addons.account.models.account_document_import_mixin import (
    AccountDocumentImportMixin)
from addons.account.services import create_invoice_from_sale_order
from addons.base.models import IrSequence, TimeStampedModel
from addons.base.models.ir_rule import RuleScopedManager
from addons.mail.models import MailThread
from addons.mail.models.mail_activity_mixin import MailActivityMixin
from addons.portal.models.portal_mixin import PortalMixin
from addons.product.models.product_catalog_mixin import ProductCatalogMixin
from addons.product.models.product_pricelist import ProductPricelist
from addons.utm.models.utm_mixin import UtmMixin


def _next_sale_name() -> str:
    """Referencia SO vía ``ir.sequence`` ``code='sale.order'`` (Odoo
    ``sale/models/sale_order.py:1010`` — ``next_by_code('sale.order')``;
    secuencia ``seq_sale_order``: prefix ``S``, padding 5 → ``S00001``,
    ``sale/data/ir_sequence_data.xml``). El seed es idempotente en el punto
    de uso — análogo del data record ``noupdate`` — para no depender del
    mecanismo de seeds del proyecto (H-API-22). ``select_for_update``
    serializa la lectura-incremento; el atomic anidado lo hace válido
    aunque el llamador no tenga transacción abierta.
    """
    with transaction.atomic():
        seq = IrSequence.objects.select_for_update().filter(
            code='sale.order').first()
        if seq is None:
            seq = IrSequence.objects.create(
                name='Sales Order', code='sale.order', prefix='S', padding=5)
        return seq.next_by_id()


#: ≙ ``INVOICE_STATUS`` (``odoo19c: sale/models/sale_order.py:19-24``). Los
#: **valores** son idénticos a los de la fuente —incluido el ``'to invoice'``
#: con espacio, que es lo que viaja y se compara—; las etiquetas van en
#: español por ``redaccion-tecnica-es.md``.
INVOICE_STATUS = [
    ('upselling', 'Oportunidad de venta adicional'),
    ('invoiced', 'Facturado por completo'),
    ('to invoice', 'Por facturar'),
    ('no', 'Nada que facturar'),
]

#: ≙ ``SALE_ORDER_STATE`` (``odoo19c: :26-31``). Mismos cuatro valores que la
#: clase ya declaraba en ``STATES``; se sube a constante de módulo porque ahí
#: es donde la fuente lo declara, y porque un consumidor externo puede
#: importarlo sin instanciar el modelo.
SALE_ORDER_STATE = [
    ('draft', 'Cotización'),
    ('sent', 'Cotización enviada'),
    ('sale', 'Orden de venta'),
    ('cancel', 'Cancelada'),
]

#: ≙ ``domain=[('type', '=', 'sale')]`` de ``journal_id`` (``odoo19c:
#: sale/models/sale_order.py:141``). Django no declara el dominio en el campo;
#: se nombra como constante para que quien filtre candidatos la importe en vez
#: de reescribirla. Mismo criterio que ``SALE_DISCOUNT_PRODUCT_DOMAIN`` de
#: ``res_company.py``.
SALE_JOURNAL_DOMAIN = {'type': 'sale'}

#: ≙ ``domain="['|', ('company_id','=',False), ('company_id','=',company_id)]"``
#: de ``payment_term_id`` y ``pricelist_id`` (``:180,189``): los de la empresa
#: del pedido o los compartidos. Es un invocable porque el segundo término
#: depende del pedido.
def payment_term_domain(order):
    """Los plazos de pago admisibles para ``order``."""
    return models.Q(company__isnull=True) | models.Q(company=order.company)


#: ≙ el mismo dominio, aplicado a la tarifa (``:191``).
pricelist_domain = payment_term_domain

#: ≙ ``domain="[('payment_type','=','inbound'), ('company_id','=',company_id)]"``
#: de ``preferred_payment_method_line_id`` (``:184``).
def preferred_payment_method_domain(order):
    """Las líneas de método de pago entrantes de la empresa de ``order``."""
    return models.Q(payment_type='inbound') & models.Q(company=order.company)


#: ≙ el grupo que acota el vendedor en ``user_id`` (``:211-214``):
#: ``all_group_ids in [group_sale_salesman]``, ``share = False`` y la empresa
#: del pedido. El nombre del grupo se conserva verbatim.
SALESPERSON_GROUP = 'sales_team.group_sale_salesman'

#: Centinela: la instancia no se cargó de la base, así que no hay valor
#: anterior de ``company`` contra el cual comparar. Distinto de ``None``, que
#: sí es un valor legítimo (orden sin empresa).
_EMPRESA_NO_CARGADA = object()


def _compute_is_expired_default(order) -> bool:
    """≙ ``_compute_is_expired`` (``odoo19c: sale_order.py:758-764``).

    Cuerpo exacto de la referencia: cotización/enviada con vigencia vencida.
    ``NonStored.resolve_default`` llama a este invocable con la instancia
    porque acepta un parámetro (mismo protocolo que
    ``account_fleet/models/account_move.py::_compute_need_vehicle``).

    Usa la fecha del **servidor** a propósito: la referencia compara contra
    ``fields.Date.today()`` aquí y contra ``fields.Date.context_today(self)``
    en ``_compute_validity_date``. Esa asimetría se conserva — ver el
    docstring de ``SaleOrder._compute_validity_date``.
    """
    return bool(
        order.state in (order.STATE_DRAFT, order.STATE_SENT)
        and order.validity_date
        and order.validity_date < timezone.now().date()
    )


# --- los invocables de los campos no almacenados -------------------------
# ``fields.NonStored`` toma su valor de un ``default=`` que puede ser un
# invocable; ``NonStored.resolve_default`` le pasa la instancia cuando su firma
# acepta un parámetro. Cada uno de los siguientes porta el cuerpo del
# ``_compute_*`` homónimo de la referencia — mismo nombre, mismo cálculo.
#
# Viven a nivel de módulo y no como método porque el descriptor se declara en el
# cuerpo de la clase y necesita el invocable ya definido. Es la misma forma que
# ``_compute_is_expired_default`` estrenó arriba.


def _compute_has_archived_products(order) -> bool:
    """≙ ``_compute_has_archived_products`` (``odoo19c: sale_order.py:343-348``).

    Cuerpo exacto: ``any(not product.active for product in
    order.order_line.product_id)``. Aquí el recorrido va por el
    ``related_name='order_line'`` de :class:`SaleOrderLine`, y el producto de
    una línea puede ser nulo (línea de sección o de nota), así que se descarta
    antes de leerle ``active`` — en la fuente ese caso no llega porque
    ``order_line.product_id`` es un recordset que ya excluye los vacíos.
    """
    return any(
        not line.product.active
        for line in order.order_line.all()
        if line.product_id is not None
    )


def _compute_has_active_pricelist(order) -> bool:
    """≙ ``_compute_has_active_pricelist`` (``odoo19c: :468-473``).

    Cuerpo exacto: existe alguna tarifa activa de la empresa del pedido o sin
    empresa. El ``('company_id', 'in', (False, order.company_id.id))`` de la
    fuente es aquí ``company__in=(None, order.company_id)``: en este ORM el
    ``False`` de un Many2one vacío se escribe ``None``.
    """
    return ProductPricelist.objects.filter(
        models.Q(company__isnull=True) | models.Q(company=order.company),
        active=True,
    ).exists()


def _compute_tax_country(order):
    """≙ ``_compute_tax_country_id`` (``odoo19c: :767-772``).

    Cuerpo exacto: si la posición fiscal declara RFC propio en la región que
    mapea, el país fiscal es el de esa posición; si no, el de la empresa.

    La fuente lo marca ``compute_sudo=True`` con su razón escrita en el propio
    campo — *«Avoid access error on fiscal position when reading a sale order
    with company != user.company_ids»* (``:315``). Aquí la lectura de la
    posición fiscal no pasa por el gestor acotado por reglas de fila, así que
    no hay error de acceso que evitar: se lee la FK ya resuelta.
    """
    position = order.fiscal_position_id
    if position is not None and position.foreign_vat:
        return position.country
    return order.company.account_fiscal_country if order.company_id else None


def _compute_type_name(order) -> str:
    """≙ ``_compute_type_name`` (``odoo19c: :815-820``).

    Cuerpo exacto: ``draft``/``sent``/``cancel`` son una cotización; el resto,
    una orden de venta. La fuente lo declara ``@api.depends_context('lang')``
    porque el texto es traducible — aquí lo cubre ``_()``, que resuelve contra
    el idioma activo en el momento de leerlo.
    """
    if order.state in (SaleOrder.STATE_DRAFT, SaleOrder.STATE_SENT,
                       SaleOrder.STATE_CANCEL):
        return _('Cotización')
    return _('Orden de venta')


def _compute_duplicated_orders(order):
    """≙ ``_compute_duplicated_order_ids`` (``odoo19c: :692-697``).

    Cuerpo fiel: sólo un pedido en borrador busca duplicados; los demás
    devuelven vacío. La fuente lo resuelve sobre un recordset entero
    (``draft_orders._fetch_duplicate_orders()``); aquí el descriptor se evalúa
    por instancia, así que se consulta con esa sola.

    Devuelve un ``QuerySet`` y no una lista de ids porque quien lo consuma
    querrá el pedido, no su clave — es lo que la fuente entrega al declararlo
    ``Many2many(comodel_name='sale.order')``.
    """
    if order.state != SaleOrder.STATE_DRAFT:
        return SaleOrder.objects.none()
    duplicados = SaleOrder.fetch_duplicate_orders([order])
    return SaleOrder.objects.filter(pk__in=duplicados.get(order.pk, ()))


class SaleOrder(PortalMixin, ProductCatalogMixin, MailThread,
                MailActivityMixin, UtmMixin, AccountDocumentImportMixin,
                TimeStampedModel):
    """``sale.order`` — cotización/carrito (draft) → orden de venta (sale).

    Hereda ``MailThread`` igual que ``sale.order`` hereda ``mail.thread`` en la
    referencia (``odoo19x sale/models/sale_order.py:23``). El mixin es abstracto
    y **no agrega columnas** —el hilo se materializa en ``mail_message`` /
    ``mail_followers`` por el par polimórfico—, así que la herencia no genera
    migración.

    Por qué importa para el cut-over: en la referencia la bitácora de la venta
    es ``tracking=True`` sobre ``state`` (``:81``), no una tabla lateral. El
    espejo ``orders.Order`` sí era un hilo; la canónica no lo era, de modo que
    retirar ``orders`` habría perdido la capacidad.

    Equivalencia de nombre con la referencia
    ========================================

    Las FK pierden el sufijo ``_id`` porque Django lo repone en la columna:
    ``partner = fields.Many2one(...)`` escribe ``partner_id``, que es
    exactamente el nombre de la fuente. Es la convención dominante del árbol —
    medido por AST sobre ``addons/**/models/*.py``: **495** declaraciones
    relacionales sin sufijo contra **98** con él.

    *Métrica:* declaraciones ``fields.Many2one``/``fields.Many2many`` en el
    cuerpo de una clase, según su nombre termine o no en ``_id``/``_ids``.
    *Ciega a:* los campos que ``extend_model`` cuelga desde otro addon, que no
    viven en el cuerpo de ninguna clase, y a ``src/addons/base``.

    Los que además cambian de forma, no sólo de sufijo:

    ==============================  =========================================
    Referencia                      Aquí
    ==============================  =========================================
    ``create_date`` (:85)           ``created_at`` de ``TimeStampedModel``,
                                    ya con el ``index=True`` que la fuente
                                    añade al sobreescribirlo
    ``order_line`` (:226)           el reverso de ``SaleOrderLine.order``,
                                    cuyo ``related_name`` es ``order_line``
                                    — un ``One2many`` de la fuente es un
                                    ``related_name`` aquí
                                    (``orm/fields_relational.py:73``)
    ``invoice_ids`` (:238)          ``invoice``, FK 1:1 — divergencia
                                    preexistente; la fuente calcula un M2M
                                    desde las líneas
    ``campaign_id``/``medium_id``/  los declara ``UtmMixin``, del que esta
    ``source_id`` (:283-285)        clase ahora hereda. La fuente sólo los
                                    redeclara para fijar
                                    ``ondelete='set null'``, y el mixin ya
                                    lo declara así
    ``access_token``                lo declara ``PortalMixin``, del que esta
                                    clase ahora hereda
    ==============================  =========================================
    """

    # -- atributos de clase del modelo -------------------------------------
    # ≙ ``odoo19c: sale/models/sale_order.py:34-49``. Los cinco que la fuente
    # declara, más los dos objetos de tabla y la propiedad ``_rec_names_search``
    # (``atributos-de-clase-de-modelo.md``: se portan TODOS los que la fuente
    # declare, verbatim, y no sustituyen a su forma Django).

    #: ≙ ``_name = 'sale.order'`` (``:35``). Cierra la mitad de cabecera de la
    #: tarea #574. Lo consume ``orm.registry.MODELS_BY_ODOO_NAME``, que es lo
    #: que permite a ``extend_model('sale.order', …)`` resolver por nombre.
    _name = 'sale.order'

    #: ≙ ``_inherit`` (``:36``). Los seis mixins de la fuente, en su orden, y
    #: los seis existen en este árbol — se declaran además como **bases** de la
    #: clase, que es como este stack expresa la herencia. La lista se conserva
    #: verbatim porque es el contrato que un addon posterior lee para saber qué
    #: ganchos puede esperar.
    _inherit = ['portal.mixin', 'product.catalog.mixin', 'mail.thread',
                'mail.activity.mixin', 'utm.mixin',
                'account.document.import.mixin']

    #: ≙ ``_description = "Sales Order"`` (``:37``). No sustituye a
    #: ``Meta.verbose_name``, que va en español.
    _description = 'Sales Order'

    #: ≙ ``_order = 'date_order desc, id desc'`` (``:38``), y ``Meta.ordering``
    #: lo deriva: ``['-date_order', '-id']``.
    #:
    #: La derivación es mecánica —cada término ``<campo> desc`` es un ``-campo``
    #: de Django, en el mismo orden— y sólo fue posible al portar el
    #: ``default=fields.Datetime.now`` del campo: mientras ``date_order`` era
    #: NULL en los borradores, ordenar por él los habría agrupado en un bloque
    #: de NULL. Los dos cambios van juntos a propósito.
    _order = 'date_order desc, id desc'

    #: ≙ ``_check_company_auto = True`` (``:39``). NO es decorativo: lo lee
    #: ``CheckCompanyMixin.save`` (``orm/models.py:856``), que ``TimeStampedModel``
    #: ya hereda, y dispara ``_check_company()`` sobre los campos marcados
    #: ``check_company=True``.
    _check_company_auto = True

    @property
    def _rec_names_search(self):
        """≙ la propiedad homónima de la fuente (``odoo19c: :45-49``).

        Se porta como **propiedad**, igual que allá: el conjunto de campos por
        los que se busca depende del contexto de la petición, no de la clase.
        Con ``sale_show_partner_name`` activo la búsqueda también mira el
        nombre del cliente.

        El contexto se lee de ``env.context`` en la fuente; aquí se toma del
        contexto del hilo de petición, que es el equivalente de este stack.
        """
        if get_context().get('sale_show_partner_name'):
            return ['name', 'partner__name']
        return ['name']

    # Odoo SALE_ORDER_STATE (sale/models/sale_order.py:70, default 'draft').
    STATE_DRAFT  = 'draft'    # cotización / carrito (website_sale)
    STATE_SENT   = 'sent'     # cotización enviada
    STATE_SALE   = 'sale'     # orden de venta confirmada
    STATE_CANCEL = 'cancel'
    STATES = [
        (STATE_DRAFT,  'Cotización'),
        (STATE_SENT,   'Cotización enviada'),
        (STATE_SALE,   'Orden de venta'),
        (STATE_CANCEL, 'Cancelada'),
    ]

    # DEC-003: ``TimeStampedModel`` deja ``created_at`` sin índice y encarga a
    # cada modelo declararlo "por volumen (inventario, órdenes)". El espejo lo
    # declaraba y la canónica no lo heredó al retirarlo, aunque es ella la que
    # se ordena por fecha en el panel del comprador y en el admin.
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    # ``name`` NULL mientras es borrador (Odoo lo asigna al crear vía secuencia;
    # aquí se asigna al confirmar). UNIQUE admite múltiples NULL en SQL.
    name       = fields.Char(
        max_length=20, unique=True, null=True, blank=True, db_index=True,
        help_text='Referencia SO (Odoo sale.order.name). NULL en borrador.',
    )
    partner    = fields.Many2one(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='sale_orders',
        help_text='Cliente (Odoo partner_id). NULL en carrito anónimo.',
    )
    cart_token = models.UUIDField(
        unique=True, null=True, blank=True, db_index=True,
        help_text='Carrito anónimo — draft sin partner (paridad cart.cart_token).',
    )
    state      = fields.Selection(
        max_length=10, choices=STATES, default=STATE_DRAFT, db_index=True,
    )
    #: ≙ ``date_order`` (``odoo19c: sale/models/sale_order.py:92-96``), con sus
    #: tres atributos: ``required=True``, ``copy=False`` y
    #: ``default=fields.Datetime.now``.
    #:
    #: **Nace con la orden, no con la confirmación.** La ayuda de la fuente lo
    #: dice entera —*«Creation date of draft/sent orders, Confirmation date of
    #: confirmed orders»*—: es una sola columna que significa dos cosas según
    #: el estado, no una fecha que aparece al confirmar. ``action_confirm`` la
    #: reescribe con el instante de la confirmación; hasta entonces vale el
    #: instante de creación.
    #:
    #: ``copy=False`` no tiene receptor aquí: este ORM no tiene ``copy()`` de
    #: registro. Se declara en la prosa para que quien lo construya sepa que
    #: esta columna **no** se duplica.
    date_order = fields.Datetime(
        default=timezone.now,
        help_text='Fecha de la orden (Odoo date_order): fecha de creación en '
                  'borrador o enviada, fecha de confirmación una vez '
                  'confirmada.',
    )
    locked     = fields.Boolean(
        default=False, help_text='Orden bloqueada, no modificable (Odoo locked).',
    )
    # Odoo sale.order.team_id (Many2one crm.team) — atribución de la orden a un
    # equipo de venta. El addon ``sale`` declara ``sales_team`` como dependencia
    # justamente para añadir este campo.
    team       = fields.Many2one(
        'sales_team.CrmTeam', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='sale_orders',
        help_text='Equipo de venta atribuido (Odoo sale.order.team_id).',
    )
    # V1 unificación orders→sale (DEC-FW-02): lo que el flujo vivo del
    # strangler ``orders.Order`` necesita y el canónico aún no tenía.
    # guest_email = checkout anónimo (BR-011); en Odoo el guest es un
    # partner efímero de website_sale — aquí se conserva el email snapshot.
    guest_email = fields.Char(
        max_length=254, blank=True, default='',
        help_text='Email del comprador anónimo (BR-011). Vacío si hay partner.',
    )
    notes       = fields.Text(
        blank=True, default='',
        help_text='Notas del comprador al confirmar (paridad orders.Order.notes).',
    )
    # Empresa dueña de la orden (Odoo sale.order.company_id). L3 rollout
    # SOL-085 S3: nullable durante el backfill (la migración asigna las filas
    # heredadas a la founder company). Espeja el patrón de company.CompanySetting.
    company     = fields.Many2one(
        'base.ResCompany', null=True, blank=True,
        on_delete=models.CASCADE, related_name='sale_orders',
        help_text='Empresa dueña de la orden (Odoo company_id). NULL pre-backfill.',
    )
    # Vigencia de la cotización (Odoo sale.order.validity_date, tarea #256).
    # ``store=True, compute='_compute_validity_date'`` en la referencia; aquí
    # se calcula en ``save()`` (ver el override abajo, junto a
    # ``_compute_validity_date``) porque el insumo es ``company`` — un campo
    # del propio ``SaleOrder``, no de ``order_line`` como ``amount_*``.
    validity_date = fields.Date(
        null=True, blank=True,
        help_text='Vigencia de la cotización (Odoo validity_date, '
                  'sale/models/sale_order.py:135). NULL si la empresa '
                  'no define quotation_validity_days.',
        compute='_compute_validity_date', store=True,
        readonly=False, precompute=True,
    )

    # Método de envío elegido (Odoo sale.order.carrier_id, que el módulo
    # ``delivery`` añade a sale.order — delivery/models/sale_order.py:13).
    # E1 del retiro del espejo: el dato vivía sólo en orders.Order.
    # SET_NULL — el catálogo de envío es configuración; darlo de baja no
    # puede llevarse la venta por delante.
    carrier     = fields.Many2one(
        'delivery.ShippingMethod', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='sale_orders',
        help_text='Método de envío elegido (Odoo sale.order.carrier_id).',
    )

    # Trazabilidad de cancelación (UC-ORD-04, UC-ORD-08 / H-ORD-001,
    # H-ADM-003). NO tienen equivalente en Odoo core —allí la cancelación es
    # ``state='cancel'`` + el hilo de ``mail.thread``—; son extensión propia
    # del proyecto, que el espejo legacy sí modelaba y el canónico no.
    admin_cancelled_by  = fields.Many2one(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='admin_cancelled_sale_orders',
        help_text='Admin que canceló. NULL si la canceló el comprador.',
    )
    cancellation_reason = fields.Text(
        blank=True, default='',
        help_text='Motivo de la cancelación (comprador o admin).',
    )
    cancelled_at        = fields.Datetime(
        null=True, blank=True,
        help_text='Momento de la cancelación. NULL si la orden no se canceló.',
    )

    # Factura de la orden (Odoo sale.order.invoice_ids, aquí 1:1). FK
    # sale→account (dirección correcta: account es la capa contable base). El
    # enlace hace idempotente action_create_invoice: una orden ya facturada no
    # emite duplicado. related_name='+' — sin accesor inverso (account limpio).
    invoice     = fields.Many2one(
        'account.AccountMove', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
        help_text='Factura emitida de la orden (Odoo invoice_ids, 1:1).',
    )

    # amount_untaxed/tax/total (H-API-30) — Odoo sale/models/sale_order.py:
    # 232-234, ``store=True, compute='_compute_amounts'``. Antes eran métodos
    # Python (obligaba a un shim SQL para agregarlos); materializados como
    # columnas reales, un ``Sum('amount_total')`` agrega directo. Se
    # recalculan y persisten en ``_compute_amounts`` (más abajo), disparado
    # desde ``SaleOrderLine.save()``/``delete()`` — ver el docstring ahí. Los
    # ``tracking=5``/``=4`` de la referencia no se portan: sólo el estado
    # tiene bitácora (ver ``_track_state``).
    amount_untaxed = fields.Monetary(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text='Subtotal sin IVA, suma de líneas (Odoo amount_untaxed).',
        compute='_compute_amounts', store=True,
    )
    amount_tax     = fields.Monetary(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text='IVA de la orden, suma de líneas (Odoo amount_tax).',
        compute='_compute_amounts', store=True,
    )
    amount_total   = fields.Monetary(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text='Total de la orden, suma de líneas (Odoo amount_total).',
        compute='_compute_amounts', store=True,
    )
    # Si la cotización venció (Odoo is_expired, compute, store=False;
    # tarea #256). Sólo este símbolo del eje ``is_expired`` — sus dos
    # consumidores de portal, ``_has_to_be_signed``/``_has_to_be_paid``
    # (``odoo19c: sale_order.py:1894,1914``), quedan fuera: confirmado
    # ausentes en ``src/`` (0 hits de implementación), eje portal sin
    # superficie propia en este stack. Es DECISIÓN de alcance, no omisión.
    is_expired = fields.NonStored(
        default=_compute_is_expired_default,
        help_text='Si la cotización venció (Odoo is_expired, compute, '
                  'store=False): state en draft/sent y validity_date '
                  'anterior a hoy.',
    )

    # === Campos de la referencia que faltaban =============================
    # ≙ ``odoo19c: sale/models/sale_order.py:52-330``. Los nombres de FK pierden
    # el sufijo ``_id`` porque Django lo repone en la columna: ``partner =
    # fields.Many2one(...)`` escribe ``partner_id``, que es exactamente el
    # nombre de la fuente. Es la convención dominante del árbol — medido por
    # AST sobre ``addons/**/models/*.py``: 495 declaraciones relacionales sin
    # sufijo contra 98 con él.

    # -- referencias del cliente y del documento ---------------------------
    client_order_ref = fields.Char(
        max_length=64, blank=True, default='',
        verbose_name='Referencia del cliente',
        help_text='Odoo client_order_ref ("Customer Reference"). El número con '
                  'que el cliente identifica esta compra de su lado.',
    )
    commitment_date = fields.Datetime(
        null=True, blank=True, verbose_name='Fecha de entrega',
        help_text='Odoo commitment_date ("Delivery Date"). Fecha prometida al '
                  'cliente; si se fija, el albarán se programa contra ella y '
                  'no contra los plazos de cada producto.',
    )
    origin = fields.Char(
        max_length=64, blank=True, default='',
        verbose_name='Documento de origen',
        help_text='Odoo origin ("Source Document"). Referencia del documento '
                  'que originó esta solicitud de venta.',
    )
    reference = fields.Char(
        max_length=64, blank=True, default='',
        verbose_name='Referencia de pago',
        help_text='Odoo reference ("Payment Ref."). La comunicación de pago de '
                  'este pedido — lo que el cliente ve en su estado de cuenta.',
    )
    pending_email_template_id = fields.Many2one(
        'mail.MailTemplate', null=True, blank=True,
        db_column='pending_email_template_id',
        on_delete=models.SET_NULL, related_name='+',
        verbose_name='Plantilla del correo pendiente',
        help_text='Odoo pending_email_template_id ("Pending Email Template"). '
                  'La plantilla del correo que queda por enviar de forma '
                  'asíncrona.',
    )

    # -- confirmación por el portal: firma, pago y anticipo ----------------
    # Los tres son ``compute … store=True, readonly=False, precompute=True`` en
    # la fuente (``:109-123``): su valor inicial sale de la empresa y el usuario
    # puede sobreescribirlo. Aquí el ``default`` cubre el ``precompute`` del
    # alta y los tres ``_compute_*`` correspondientes llegan con el bloque de
    # cómputos; el usuario puede escribirlos porque son columnas normales.
    require_signature = fields.Boolean(
        default=True, verbose_name='Firma en línea',
        help_text='Odoo require_signature ("Online signature"). Pide firma del '
                  'cliente para confirmar el pedido. Su valor inicial sale de '
                  'company.portal_confirmation_sign.',
    )
    require_payment = fields.Boolean(
        default=False, verbose_name='Pago en línea',
        help_text='Odoo require_payment ("Online payment"). Pide pago del '
                  'cliente para confirmar el pedido. Su valor inicial sale de '
                  'company.portal_confirmation_pay.',
    )
    prepayment_percent = fields.Float(
        default=1.0, verbose_name='Porcentaje de anticipo',
        help_text='Odoo prepayment_percent ("Prepayment percentage"). Fracción '
                  'del importe que el cliente debe pagar para confirmar. Su '
                  'valor inicial sale de company.prepayment_percent.',
    )
    signature = fields.Image(
        upload_to='sale/signatures/', null=True, blank=True,
        verbose_name='Firma',
        help_text='Odoo signature ("Signature", attachment=True, máx. '
                  '1024×1024). Imagen de la firma con que el cliente aceptó.',
    )
    signed_by = fields.Char(
        max_length=128, blank=True, default='', verbose_name='Firmado por',
        help_text='Odoo signed_by ("Signed By"). Nombre de quien firmó.',
    )
    signed_on = fields.Datetime(
        null=True, blank=True, verbose_name='Firmado el',
        help_text='Odoo signed_on ("Signed On"). Momento de la firma.',
    )

    # -- contabilidad y condiciones ----------------------------------------
    journal_id = fields.Many2one(
        'account.AccountJournal', null=True, blank=True,
        db_column='journal_id',
        on_delete=models.SET_NULL, related_name='+', check_company=True,
        verbose_name='Diario de facturación',
        help_text='Odoo journal_id ("Invoicing Journal"). Si se fija, el pedido '
                  'factura en este diario; si no, se usa el diario de ventas de '
                  'menor secuencia. Acotado por SALE_JOURNAL_DOMAIN.',
    )
    note = fields.Html(
        blank=True, default='', verbose_name='Términos y condiciones',
        help_text='Odoo note ("Terms and conditions"). Su valor inicial sale de '
                  'los términos de la empresa.',
    )
    partner_invoice_id = fields.Many2one(
        'base.ResPartner', null=True, blank=True,
        db_column='partner_invoice_id',
        on_delete=models.SET_NULL, related_name='+', check_company=True,
        db_index=True, verbose_name='Dirección de facturación',
        help_text='Odoo partner_invoice_id ("Invoice Address"). '
                  'index="btree_not_null" en la fuente: aquí el índice lo pone '
                  'Django con la FK; el tramo parcial se declara en Meta.indexes '
                  'cuando el volumen lo justifique.',
    )
    partner_shipping_id = fields.Many2one(
        'base.ResPartner', null=True, blank=True,
        db_column='partner_shipping_id',
        on_delete=models.SET_NULL, related_name='+', check_company=True,
        db_index=True, verbose_name='Dirección de entrega',
        help_text='Odoo partner_shipping_id ("Delivery Address").',
    )
    fiscal_position_id = fields.Many2one(
        'account.AccountFiscalPosition', null=True, blank=True,
        db_column='fiscal_position_id',
        on_delete=models.SET_NULL, related_name='+', check_company=True,
        verbose_name='Posición fiscal',
        help_text='Odoo fiscal_position_id ("Fiscal Position"). Adapta impuestos '
                  'y cuentas para un cliente o pedido concreto; su valor por '
                  'omisión sale del cliente.',
    )
    payment_term_id = fields.Many2one(
        'account.AccountPaymentTerm', null=True, blank=True,
        db_column='payment_term_id',
        on_delete=models.SET_NULL, related_name='+', check_company=True,
        verbose_name='Condiciones de pago',
        help_text='Odoo payment_term_id ("Payment Terms"). Acotado por '
                  'PAYMENT_TERM_DOMAIN: los de la empresa del pedido o los '
                  'compartidos (company_id vacío).',
    )
    preferred_payment_method_line_id = fields.Many2one(
        'account.AccountPaymentMethodLine', null=True, blank=True,
        db_column='preferred_payment_method_line_id',
        on_delete=models.SET_NULL, related_name='+', check_company=True,
        verbose_name='Método de pago',
        help_text='Odoo preferred_payment_method_line_id ("Payment Method"). '
                  'Acotado por PREFERRED_PAYMENT_METHOD_DOMAIN: entrante y de '
                  'la empresa del pedido.',
    )
    pricelist_id = fields.Many2one(
        'product.ProductPricelist', null=True, blank=True,
        db_column='pricelist_id',
        on_delete=models.SET_NULL, related_name='+', check_company=True,
        verbose_name='Tarifa',
        help_text='Odoo pricelist_id ("Pricelist"). Cambiarla sólo afecta a las '
                  'líneas que se añadan después. Acotada por PRICELIST_DOMAIN.',
    )
    currency_id = fields.Many2one(
        'base.ResCurrency', null=True, blank=True,
        db_column='currency_id',
        on_delete=models.PROTECT, related_name='+',
        verbose_name='Divisa',
        help_text='Odoo currency_id (compute, store=True, precompute, '
                  "ondelete='restrict'). Sale de la tarifa, o de la empresa si "
                  'el pedido no tiene tarifa. PROTECT ≙ restrict.',
    )
    currency_rate = fields.Float(
        default=1.0, verbose_name='Tipo de cambio',
        help_text='Odoo currency_rate ("Currency Rate", digits=0 — sin redondeo '
                  'declarado). Tasa aplicada al confirmar, congelada en el '
                  'pedido para que un cambio posterior no reescriba el importe.',
    )
    user_id = fields.Many2one(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        db_column='user_id',
        on_delete=models.SET_NULL, related_name='sale_orders_as_salesperson',
        db_index=True, verbose_name='Vendedor',
        help_text='Odoo user_id ("Salesperson"). NO es el cliente —ese es '
                  '``partner``—: es quien atiende la venta. Acotado por '
                  'SALESPERSON_GROUP: usuario interno del grupo de ventas de la '
                  'empresa del pedido.',
    )

    # -- estado de facturación ---------------------------------------------
    invoice_status = fields.Selection(
        max_length=16, choices=INVOICE_STATUS, null=True, blank=True,
        verbose_name='Estado de facturación',
        help_text='Odoo invoice_status (compute, store=True). Deriva del estado '
                  'de facturación de las líneas: por facturar, facturado por '
                  'completo, oportunidad de venta adicional, o nada que '
                  'facturar.',
    )

    # -- seguimiento comercial ---------------------------------------------
    tags = fields.Many2many(
        'sales_team.CrmTag', blank=True, related_name='sale_orders',
        db_table='sale_order_tag_rel', verbose_name='Etiquetas',
        help_text='Odoo tag_ids ("Tags", relation="sale_order_tag_rel"). El '
                  'nombre de la tabla intermedia se conserva verbatim. Su '
                  "groups='sales_team.group_sale_salesman' se aplica por "
                  'capacidad en la vista DRF (DEC-11), no en el campo.',
    )

    # -- los campos NO almacenados de la referencia ------------------------
    # ≙ ``odoo19c: sale/models/sale_order.py:235-327``. Ninguno tiene columna:
    # ``fields.NonStored`` es el equivalente construido de su ``store=False``,
    # y por eso no generan migración ni se pueden filtrar. La referencia declara
    # 19 en este tramo; aquí van los 11 cuyo insumo ya existe en el árbol, y los
    # 8 restantes se declaran abajo con su bloqueo medido y su sucesor.

    # Los cuatro ``related=`` — la cadena se recorre en el invocable porque un
    # ``NonStored`` no la resuelve por sí solo. Su destino son los cuatro campos
    # que ``account`` acaba de colgarle a ``res.company``
    # (``addons/account/models/res_company.py``): sin ellos el ``related`` no
    # tendría a qué apuntar.
    country_code = fields.NonStored(
        default=lambda order: (
            order.company.account_fiscal_country.code
            if order.company_id and order.company.account_fiscal_country_id
            else None),
        help_text='Odoo country_code '
                  '(related="company_id.account_fiscal_country_id.code"). '
                  'Código del país fiscal de la empresa del pedido.',
    )
    company_price_include = fields.NonStored(
        default=lambda order: (order.company.account_price_include
                               if order.company_id else None),
        help_text='Odoo company_price_include '
                  '(related="company_id.account_price_include"). Si el precio '
                  'de venta de la empresa incluye impuestos.',
    )
    tax_calculation_rounding_method = fields.NonStored(
        default=lambda order: (order.company.tax_calculation_rounding_method
                               if order.company_id else None),
        help_text='Odoo tax_calculation_rounding_method '
                  '(related="company_id.tax_calculation_rounding_method", '
                  'depends=["company_id"]). Redondeo por impuesto o por línea.',
    )
    terms_type = fields.NonStored(
        default=lambda order: (order.company.terms_type
                               if order.company_id else None),
        help_text='Odoo terms_type (related="company_id.terms_type"). Si los '
                  'términos y condiciones van como nota o como enlace.',
    )

    # Los dos de interfaz que la fuente agrupa bajo *«Remaining ux fields (not
    # computed, not stored)»* (``:321-327``). No tienen ``compute``: son
    # banderas que la vista pone y lee dentro de la misma edición, y por eso
    # nacen en ``False``.
    show_update_fpos = fields.NonStored(
        default=False,
        help_text='Odoo show_update_fpos ("Has Fiscal Position Changed", '
                  'store=False). Verdadero si la posición fiscal cambió y la '
                  'vista debe ofrecer recalcular los impuestos.',
    )
    show_update_pricelist = fields.NonStored(
        default=False,
        help_text='Odoo show_update_pricelist ("Has Pricelist Changed", '
                  'store=False). Verdadero si la tarifa cambió y la vista debe '
                  'ofrecer recalcular los precios.',
    )

    # Los cinco ``compute`` cuyo cuerpo se porta entero — cada invocable vive a
    # nivel de módulo, arriba, con la cita de su línea en la fuente.
    has_archived_products = fields.NonStored(
        default=_compute_has_archived_products,
        help_text='Odoo has_archived_products (compute, store=False). Si '
                  'alguna línea apunta a un producto archivado.',
    )
    has_active_pricelist = fields.NonStored(
        default=_compute_has_active_pricelist,
        help_text='Odoo has_active_pricelist (compute, store=False). Si existe '
                  'alguna tarifa activa para la empresa del pedido.',
    )
    tax_country = fields.NonStored(
        default=_compute_tax_country,
        help_text='Odoo tax_country_id (compute, store=False, '
                  'compute_sudo=True). País cuyo régimen fiscal acota los '
                  'impuestos disponibles: el de la posición fiscal si declara '
                  'RFC propio, si no el de la empresa.',
    )
    type_name = fields.NonStored(
        default=_compute_type_name,
        help_text='Odoo type_name ("Type Name", compute, store=False). '
                  '"Cotización" mientras no se confirma; "Orden de venta" '
                  'después.',
    )
    duplicated_orders = fields.NonStored(
        default=_compute_duplicated_orders,
        help_text='Odoo duplicated_order_ids (Many2many sale.order, compute, '
                  'store=False). Pedidos del mismo cliente y empresa cuyo '
                  'origen o referencia coincide con los de éste.',
    )

    # -- los 8 no almacenados que este árbol todavía no puede calcular ------
    # Los ocho leen símbolos que aún no existen. Ninguno se omite: cada uno
    # declara aquí su bloqueo con la forma fija y su sucesor, que es el bloque
    # siguiente de esta misma tarea #976 — no una iniciativa futura.
    #
    # BLOQUEADO por ``sale.order.line`` — ``addons/sale/models/sale_order_line.py``
    # tiene 164 líneas contra las 2036 de su contraparte, y ninguno de los
    # campos que estos cómputos leen (``amount_to_invoice``, ``amount_invoiced``,
    # ``invoice_lines``, ``customer_lead``, ``display_type``,
    # ``sale_line_warn_msg``) está declarado. Sucesor: #976, bloque 3.
    #
    #   amount_to_invoice   (``:235``)  suma de ``order_line.amount_to_invoice``
    #   amount_invoiced     (``:236``)  suma de ``order_line.amount_invoiced``
    #   invoice_count       (``:238``)  ``_get_invoiced``, sobre ``invoice_lines``
    #   expected_date       (``:301``)  ``_expected_date()`` de cada línea
    #   sale_warning_text   (``:253``)  ``sale_line_warn_msg`` de cada línea
    #
    # BLOQUEADO por ``account.tax`` — su fachada de tubería de impuestos no
    # está portada: ``_add_tax_details_in_base_line``,
    # ``_add_tax_details_in_base_lines``, ``_round_base_lines_tax_details`` y
    # ``_get_tax_totals_summary`` dan 0 declaraciones en
    # ``addons/account/models/account_tax.py``. Sucesor: #143.
    #
    #   amount_undiscounted (``:295``)  base sin descuento, línea por línea
    #   tax_totals          (``:316``)  resumen de impuestos para la vista
    #
    # BLOQUEADO por ``account.move`` — ``_build_credit_warning_message`` no
    # existe en ``addons/account/models/account_move.py``. Su interruptor
    # ``company.account_use_credit_limit`` sí quedó portado en este mismo pase.
    # Sucesor: #116.
    #
    #   partner_credit_warning (``:306``)  aviso de límite de crédito

    # -- eje de pago: los cuatro campos que cuelgan de la pasarela ---------
    # Los cuatro campos de pago de la fuente (``:257-281``) cuelgan de
    # ``payment.transaction``, y el resto del archivo los consume desde
    # ``_compute_authorized_transaction_ids`` y ``_compute_amount_paid``.
    #
    # BLOQUEADO por ``payment.transaction`` — el modelo no existe en este árbol;
    # ``addons/payment/models/`` declara Chargeback, PaymentGatewayEvent,
    # Payment, PaymentGateway, Refund, SavedCard y WebhookEvent, y el análogo
    # más cercano, ``payment.py::Payment``, modela el cobro efectuado y no la
    # transacción de pasarela con sus estados ni su enlace al pedido.
    # Sucesor: #983.
    #
    #   transaction_ids            (``:257``)  Many2many payment.transaction
    #   authorized_transaction_ids (``:263``)  compute sobre las anteriores
    #   has_authorized_transaction_ids (``:270``)
    #   amount_paid                (``:274``)  suma de las hechas y autorizadas

    #: Empresa con la que se cargó la fila — lo puebla ``from_db``. Es el
    #: sustituto del grafo de dependencias que la referencia sí tiene: sin él,
    #: ``save()`` no puede saber si ``company`` cambió.
    _loaded_company_id = _EMPRESA_NO_CARGADA

    objects = models.AccessManager()         # cross-company (L0 admin)
    scoped = RuleScopedManager()             # L3: record rules (ir_rule)

    class Meta:
        db_table     = 'sale_order'
        # Derivado de ``_order`` de la cabecera, término a término. Antes era
        # ``['-created_at']``, que coincide con éste en todo pedido que no se
        # haya confirmado —``date_order`` nace igual a la creación— y difiere
        # sólo en los confirmados, donde ``action_confirm`` reescribe la fecha
        # con el instante de la confirmación. Eso es exactamente lo que la
        # fuente ordena.
        ordering     = ['-date_order', '-id']
        verbose_name = 'Orden de venta'
        verbose_name_plural = 'Órdenes de venta'
        indexes      = [
            # ≙ ``_date_order_id_idx = models.Index("(date_order desc, id desc)")``
            # (``odoo19c: sale/models/sale_order.py:329``). Sostiene el ``_order``
            # de la cabecera, que ``Meta.ordering`` ya deriva término a término
            # desde la tarea #984; el índice sirve además a toda consulta que
            # ordene por fecha, no sólo al orden por omisión.
            # ``fields=`` y no posicional: un ``Index`` con cadenas sueltas las
            # trata como **expresiones**, y ahí el prefijo ``-`` no es
            # descendente sino un nombre de columna que el resolutor no
            # encuentra. Medido: 1061 errores de colección con
            # ``FieldError: Cannot resolve keyword '-date_order'``.
            models.Index(fields=['-date_order', '-id'],
                         name='sale_order_date_order_id_idx'),
        ]
        constraints  = [
            # Un solo draft por partner, garantizado por la BASE y no por
            # convención de código. El rodeo anterior lo sostenía en
            # services.get_or_create_draft_order() "porque MariaDB no soporta
            # UNIQUE parcial" — cierto entonces, falso desde ADR-028: el índice
            # único parcial es exactamente esta construcción.
            #
            # Un invariante en Python se cumple mientras todos pasen por esa
            # función; una migración de datos, un script de mantenimiento o dos
            # peticiones concurrentes lo saltan. La base no.
            #
            # partner__isnull=False acota el índice a las filas que le importan:
            # el carrito anónimo (partner NULL, unicidad por cart_token) queda
            # fuera. Ver H-API-309.
            models.UniqueConstraint(
                fields=['partner'],
                condition=models.Q(state='draft', partner__isnull=False),
                name='sale_order_un_draft_por_partner',
            ),
            # ≙ ``_date_order_conditional_required`` (``odoo19c: :40-43``):
            # ``CHECK((state = 'sale' AND date_order IS NOT NULL)
            #         OR state != 'sale')``.
            # Un pedido confirmado exige fecha de confirmación. Con el
            # ``default=`` portado la columna es NOT NULL y la restricción
            # queda tautológica — igual que en la fuente, que declara
            # ``required=True`` **y** este CHECK. Se porta porque la fuente lo
            # declara: es la red que sobrevive a que alguien afloje el campo.
            models.CheckConstraint(
                condition=(models.Q(state='sale', date_order__isnull=False)
                           | ~models.Q(state='sale')),
                name='sale_order_date_order_conditional_required',
                violation_error_message=_(
                    'Una orden de venta confirmada requiere fecha de '
                    'confirmación.'),
            ),
        ]

    @classmethod
    def fetch_duplicate_orders(cls, orders):
        """≙ ``_fetch_duplicate_orders`` (``odoo19c: sale_order.py:700-733``).

        Devuelve, por cada pedido con referencia de cliente, el conjunto de
        pedidos que lo duplican: misma empresa, mismo cliente, no cancelados, y
        cuyo ``origin`` coincide con el ``name`` del otro **o** cuya referencia
        de cliente es la misma.

        El SQL se porta **verbatim** — mismo ``JOIN`` reflexivo, mismas cuatro
        condiciones, mismo ``array_agg`` y mismo ``GROUP BY``. Es la conducta
        que ``porte-completo-no-parcial.md`` prescribe para el SQL nativo: la
        referencia lo escribió así porque el ORM no expresa un auto-join con
        agregación de identificadores en una sola consulta, y aquí tampoco.

        Lo que **no** se porta es su ``flush_model(...)``: allá el ORM difiere
        las escrituras a un buffer y hay que vaciarlo antes de consultar por
        SQL crudo. Django escribe en el ``save()``, así que la fila ya está en
        la transacción cuando esta consulta corre — no hay buffer que vaciar.

        **Divergencia de mecanismo declarada, en una línea:** la fuente escribe
        ``id IN %(orders)s`` con una tupla, que es la forma de psycopg2. Con
        psycopg3 una tupla en esa posición se adapta como literal de registro y
        PostgreSQL la rechaza — medido:
        ``syntax error at or near "'(100)'"`` sobre
        ``WHERE sale_order.id IN '(100)'``. La forma nativa del driver que
        corremos es ``= ANY(%s)`` con una **lista**, que se adapta a un arreglo
        de PostgreSQL. Es el mismo predicado con la sintaxis del motor, no un
        recorte: el resto del SQL va verbatim.

        :param orders: iterable de :class:`SaleOrder` ya persistidos.
        :return: ``{id_del_pedido: {ids_duplicados}}``; los pedidos sin
                 referencia de cliente no aparecen, igual que en la fuente.
        """
        ids = [
            order.pk for order in orders
            if order.pk and order.client_order_ref
        ]
        if not ids:
            return {}

        consulta = SQL("""
            SELECT
                sale_order.id AS order_id,
                array_agg(duplicate_order.id) AS duplicate_ids
              FROM sale_order
              JOIN sale_order AS duplicate_order
                ON sale_order.company_id = duplicate_order.company_id
                 AND sale_order.id != duplicate_order.id
                 AND duplicate_order.state != 'cancel'
                 AND sale_order.partner_id = duplicate_order.partner_id
                 AND (
                    sale_order.origin = duplicate_order.name
                    OR sale_order.client_order_ref = duplicate_order.client_order_ref
                )
             WHERE sale_order.id = ANY(%(orders)s)
             GROUP BY sale_order.id
            """, orders=ids)

        with connection.cursor() as cursor:
            cursor.execute(consulta.code, consulta.params)
            return {
                order_id: set(duplicate_ids)
                for order_id, duplicate_ids in cursor.fetchall()
            }

    def __str__(self):
        return self.name or f'draft:{self.cart_token or self.pk}'

    @classmethod
    def from_db(cls, db, field_names, values):
        """Recuerda la empresa con la que se cargó la fila.

        Es lo que permite a ``save()`` distinguir "cambió ``company``" de
        "se guardó cualquier otra cosa", que es la diferencia entre reproducir
        ``@api.depends('company_id')`` y recalcular a ciegas. Sin este dato el
        único disparo posible sería "en cada save", que **no** es lo que hace
        la referencia.
        """
        order = super().from_db(db, field_names, values)
        if 'company_id' in field_names:
            order._loaded_company_id = order.company_id
        return order

    def save(self, *args, **kwargs):
        """Calcula ``validity_date`` antes de persistir (tarea #256).

        Mismo patrón de disparo que ``res_country.save()`` (precedente tras
        ``__str__``): en la referencia ``@api.depends('company_id')`` dispara
        ``_compute_validity_date`` automáticamente; aquí ``@api.depends`` es
        **inerte** (``orm/decorators.py:23-27`` sólo anota ``_depends``, no hay
        motor de recompute — tarea #191), así que el único disparo real es este
        ``save()``.

        Reproduce **los dos** disparos de la referencia, que no son uno:

        1. ``precompute=True`` — al **crear**, y sólo si quien llama no dio
           valor. Medido en ``odoo19c: odoo/orm/models.py:4841``
           (``_add_precomputed_values``): ``if fname not in vals:`` — un
           ``validity_date`` explícito en ``create()`` **sobrevive**, no lo
           pisa el cómputo.
        2. ``@api.depends('company_id')`` — al **cambiar la empresa**, no en
           cada escritura. Recalcular siempre convertiría un campo editable
           (``readonly=False``) en uno que el usuario no puede fijar.

        Fuera de esos dos casos no toca el valor. ``update_fields`` se respeta:
        si el cómputo corre en un ``save`` parcial, ``validity_date`` se añade
        a la lista para que llegue a la base — calcularlo sin persistirlo
        dejaría la instancia divergiendo de la fila en silencio.
        """
        update_fields = kwargs.get('update_fields')
        cambio_empresa = (
            self._loaded_company_id is not _EMPRESA_NO_CARGADA
            and self._loaded_company_id != self.company_id
        )
        if self._state.adding:
            if self.validity_date is None:
                self._compute_validity_date()
        elif cambio_empresa:
            self._compute_validity_date()
            if update_fields is not None and 'validity_date' not in update_fields:
                kwargs['update_fields'] = [*update_fields, 'validity_date']
        super().save(*args, **kwargs)
        self._loaded_company_id = self.company_id

    # amount_untaxed/tax/total — de sale.order._compute_amounts
    # (sale/models/sale_order.py:513): suma del desglose por línea ya redondeado.
    #
    # Los tres atributos son **columnas** de la línea desde que
    # ``SaleOrderLine._compute_amount`` las puebla en su ``save()``; antes eran
    # métodos y este ``getattr`` los invocaba. Hoy se leen, no se llaman — y
    # por eso un ``Sum('price_total')`` puede agregar en el motor cuando haga
    # falta, sin recorrer las líneas en Python.
    def _sum_lines(self, attr: str) -> Decimal:
        return sum(
            (getattr(line, attr) for line in self.order_line.all()),
            Decimal('0.00'),
        )

    @api.depends('order_line.price_subtotal', 'order_line.price_tax',
                 'order_line.price_total')
    def _compute_amounts(self):
        """Recalcula y persiste ``amount_untaxed``/``amount_tax``/``amount_total``.

        Espeja ``sale.order._compute_amounts`` (Odoo sale/models/sale_order.py:
        513): suma el desglose ya redondeado **por línea** — ``SaleOrderLine``
        cuantiza a centavos antes de sumar (``sale_order_line.py:85-88``), no
        al final; sumar exacto y redondear al final divergiría un centavo en
        casos adversos (ver ``TestRedondeoPorLinea`` del test de paridad).

        En la referencia, ``@api.depends`` dispara este cómputo automáticamente
        cuando cambia algo de lo que depende. Django no tiene ese motor: el
        decorador de arriba es sólo documental (``orm/decorators.py``) — quien
        dispara el recálculo real es ``SaleOrderLine.save()``/``delete()``
        (mismo patrón de adaptación que ``_track`` ya documenta para el rastro
        de estado).
        """
        self.amount_untaxed = self._sum_lines('price_subtotal')
        self.amount_tax = self._sum_lines('price_tax')
        self.amount_total = self._sum_lines('price_total')
        self.save(update_fields=[
            'amount_untaxed', 'amount_tax', 'amount_total', 'updated_at'])

    @api.depends('company')
    def _compute_validity_date(self):
        """Vigencia de la cotización — ≙ ``_compute_validity_date``
        (``odoo19c: sale/models/sale_order.py:367-374``).

        Cuerpo fiel a la referencia, **sin guard de early-return**: recalcula
        siempre, y cuando ``quotation_validity_days`` es 0 o la orden no tiene
        empresa, **limpia** la fecha (``else: order.validity_date = False`` de
        la referencia). Que la empresa baje el plazo a 0 tiene que borrar las
        vigencias, no dejarlas rancias — una fecha rancia dispararía
        ``is_expired`` sobre cotizaciones que la empresa ya no quiere vencer.

        Sin empresa equivale a la referencia con recordset vacío:
        ``order.company_id.quotation_validity_days`` sobre vacío da 0, así que
        cae en la rama que limpia.

        **Huso — divergencia declarada.** La referencia usa
        ``fields.Date.context_today(self)`` (fecha de HOY en la zona del
        *usuario*) aquí, y ``fields.Date.today()`` (fecha del servidor) en
        ``_compute_is_expired``. Esa asimetría es deliberada y se conserva:
        este stack no tiene contexto de zona por usuario, así que el análogo
        más cercano a "hoy donde opera la empresa" es ``timezone.localdate()``
        (``settings.TIME_ZONE``), no UTC. ``is_expired`` sí usa la fecha del
        servidor, como la referencia.
        """
        days = self.company.quotation_validity_days if self.company else 0
        self.validity_date = (
            timezone.localdate() + timedelta(days=days) if days > 0 else None
        )

    # ------------------------------------------------------------------
    # Máquina de estados de venta — de sale.order (sale/models/sale_order.py):
    # action_confirm (1166), action_draft (1058), action_lock (1318),
    # action_cancel (1324). Es la transición que el checkout dispara al unificar
    # cart→order (draft → sale). Adaptación single-record de los métodos Odoo.
    # ------------------------------------------------------------------
    def _track(self, field, field_desc, field_type, old, new):
        """Deja el cambio de ``field`` en el chatter (Odoo ``tracking=True``).

        En Odoo el rastro lo dispara el ``write()`` del ORM al ver un campo con
        ``tracking=``; Django no tiene ese enganche, así que lo invoca quien
        hace la transición — mismo resultado, mecanismo adaptado (ver
        ``MailThread._message_track``). No registra nada si el valor no cambió.
        """
        if old == new:
            return None
        return self._message_track([{
            'field': field, 'field_desc': field_desc,
            'field_type': field_type, 'old': old, 'new': new,
        }])

    def _track_state(self, old):
        # tracking=5 en amount_untaxed y =4 en amount_total de la referencia
        # son prioridades de despliegue, no aplican aquí: sólo se porta el
        # rastro del estado, que es el que la bitácora del espejo cubría.
        return self._track('state', 'Estado', 'char', old, self.state)

    def action_confirm(self):
        """Confirma la cotización/carrito (draft/sent → sale)."""
        if self.state == self.STATE_CANCEL:
            raise ValidationError('No se puede confirmar una orden cancelada.')
        if not self.order_line.exists():
            raise ValidationError('No se puede confirmar una orden sin líneas.')
        previo = self.state
        if not self.name:
            self.name = _next_sale_name()
        self.state = self.STATE_SALE
        self.date_order = timezone.now()
        self.save(update_fields=['name', 'state', 'date_order', 'updated_at'])
        self._track_state(previo)
        return True

    def action_draft(self):
        """Reabre a borrador (cancel/sent → draft)."""
        if self.state in (self.STATE_CANCEL, self.STATE_SENT):
            previo = self.state
            self.state = self.STATE_DRAFT
            self.save(update_fields=['state', 'updated_at'])
            self._track_state(previo)
        return True

    def action_cancel(self):
        """Cancela la orden (Odoo action_cancel; bloqueada → error)."""
        if self.locked:
            raise ValidationError('No se puede cancelar una orden bloqueada.')
        previo = self.state
        self.state = self.STATE_CANCEL
        self.save(update_fields=['state', 'updated_at'])
        self._track_state(previo)
        return True

    def action_lock(self):
        previo = self.locked
        self.locked = True
        self.save(update_fields=['locked', 'updated_at'])
        self._track('locked', 'Bloqueada', 'boolean', previo, self.locked)
        return True

    def action_unlock(self):
        previo = self.locked
        self.locked = False
        self.save(update_fields=['locked', 'updated_at'])
        self._track('locked', 'Bloqueada', 'boolean', previo, self.locked)
        return True

    # ------------------------------------------------------------------
    # Puente O2C → factura (H-API-08 (a)). sale es dueño del enganche a
    # account (dirección de dependencia correcta: account es la capa base y no
    # importa sale). Espeja Odoo sale.order._create_invoices como acción
    # EXPLÍCITA — NO un efecto de action_confirm (auto-facturar al confirmar es
    # política config-gated tipo website_sale.automatic_invoice; se difiere).
    # ------------------------------------------------------------------
    def action_create_invoice(self):
        """Emite y postea la factura de esta orden, o devuelve la existente.

        Idempotente: si la orden ya tiene ``invoice``, la devuelve sin emitir
        un duplicado (Odoo salta órdenes ya facturadas). Requiere que la orden
        esté confirmada (``state='sale'``) y tenga empresa emisora.

        :raises UserError: si la orden no tiene empresa, no está confirmada o
            sin líneas, o a la empresa le faltan el diario/cuentas (delegado a
            ``account.services.create_invoice_from_sale_order``).
        """
        if self.invoice_id is not None:
            return self.invoice
        if self.company_id is None:
            raise UserError(_('La orden no tiene empresa asignada para facturar.'))
        move = create_invoice_from_sale_order(self, self.company)
        move.post()
        self.invoice = move
        self.save(update_fields=['invoice', 'updated_at'])
        return move
