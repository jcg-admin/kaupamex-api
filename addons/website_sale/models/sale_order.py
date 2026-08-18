"""``sale.order`` — el carrito abandonado y su recuperación (≙ ``_inherit``).

Adaptación de ``odoo19c: addons/website_sale/models/sale_order.py``
(``odoo-tools@622ddc2a``, LGPL-3) — atribución y aviso de licencia preservados
(DEC-KX-03). El archivo de la referencia tiene **938 líneas** y reabre
``sale.order`` entero: precios, entrega, pasos del checkout, accesorios. Este
pase porta **una rebanada nombrada**, la recuperación de carrito abandonado
(tarea **#258**); el resto llega con su superficie.

Universo medido de la rebanada — 12 símbolos
==============================================

Los once primeros salen por AST: entradas del cuerpo de ``class SaleOrder``
cuyo nombre o cuerpo menciona ``abandoned`` / ``cart_recovery`` / ``recovery``.

.. list-table::
   :header-rows: 1
   :widths: 42 14 44

   * - Símbolo de la referencia (línea)
     - Estado
     - Forma aquí
   * - ``website_id`` (``:24-28``)
     - portado
     - ``WebsiteSaleOrderInfo.website`` — ver la nota de la métrica
   * - ``cart_recovery_email_sent`` (``:30``)
     - portado
     - ``WebsiteSaleOrderInfo.cart_recovery_email_sent``
   * - ``is_abandoned_cart`` (``:46-48``)
     - portado
     - ``fields.NonStored`` sobre ``SaleOrder`` — es ``store=False`` allá
   * - ``_compute_abandoned_cart`` (``:78-89``)
     - portado
     - función de módulo instalada como método; D-3
   * - ``_search_abandoned_cart`` (``:128-143``)
     - portado
     - ``classmethod`` que devuelve un ``QuerySet``; D-4
   * - ``action_recovery_email_send`` (``:196-217``)
     - **no portado**
     - arista abajo
   * - ``_get_cart_recovery_template`` (``:219-228``)
     - portado
     - método; ``IrModelData.ref`` es el ``env.ref`` del árbol
   * - ``_cart_recovery_email_send`` (``:722-734``)
     - portado
     - método; D-6 en el envío
   * - ``_message_mail_after_hook`` (``:736-743``)
     - **no portado**
     - arista abajo
   * - ``_message_post_after_hook`` (``:745-749``)
     - **no portado**
     - arista abajo
   * - ``_notify_get_recipients_groups`` (``:751-768``)
     - **no portado**
     - arista abajo
   * - ``_filter_can_send_abandoned_cart_mail`` (``:775-815``)
     - portado
     - ``classmethod`` sobre un ``QuerySet``; D-5

*Métrica:* entradas del cuerpo de ``class SaleOrder`` que nombran o mencionan
la recuperación, contadas por AST — **11**. Se añade a mano el duodécimo,
``website_id``: no menciona ninguna de las tres cadenas y sin él la rebanada no
existe, porque ``_compute_abandoned_cart``, ``_search_abandoned_cart`` y
``website._send_abandoned_cart_email`` lo leen los tres. La métrica de cadenas
es **ciega al ancla del mecanismo**, y ésta es la corrección declarada.
*Ciega a:* lo que otros addons cuelgan del mismo modelo —
``website_sale_stock`` y ``website_event_sale`` extienden
``_filter_can_send_abandoned_cart_mail`` con un ``super()`` cada uno
(``odoo19c: website_sale_stock/models/sale_order.py:134``,
``website_event_sale/models/sale_order.py:124``). Este conteo sólo ve el
archivo de ``website_sale``; cuando esos addons lleguen, su encadenado es el de
``orm.method_chain``, no un ``if not hasattr`` (:ref:`h-api-364`).

Divergencias declaradas
========================

**D-1 — el estado con columna vive en un modelo propio de ``website_sale``.**
Misma razón, mismo precedente y misma restricción de plataforma que en
``models/website.py`` (su D-1) y en ``models/product_template.py``: el
autodetector atribuye la migración al ``app_label`` del **modelo**, así que
añadir columnas a ``sale_order`` obligaría a escribir en
``addons/sale/migrations/``. La tabla lateral 1-1 propiedad del addon que
extiende es la forma que el árbol ya usa —
``account_check_printing.CheckPrintingJournalSettings`` sobre
``account.journal``, ``delivery.ShipmentGuide`` sobre ``sale.SaleOrder``.

**D-2 — ``is_abandoned_cart`` es un ``NonStored``, no una ``property``.** La
fuente lo declara ``compute`` **sin** ``store=True``, es decir ``store=False``,
y ése es exactamente el campo que ``orm/fields_nonstored.py`` construye. Se usa
él y no una ``property`` porque la fuente admite asignarlo en memoria y una
``property`` de sólo lectura no.

**D-3 — el ``compute`` devuelve en vez de asignar.** ``_compute_abandoned_cart``
allá recorre ``self`` y escribe ``order.is_abandoned_cart``; aquí recibe un
pedido y devuelve el booleano, que es lo que el ``default`` del ``NonStored``
consume. El cuerpo de la decisión —sitio, borrador, fecha, comprador distinto
del público, con líneas— se conserva entero.

**D-4 — ``_search_abandoned_cart`` devuelve un ``QuerySet``, no un
``Domain``.** Este árbol no tiene el ``Domain`` de la referencia; el precedente
de búsqueda sobre campo no almacenado es
``mail_activity_mixin._search_activity_state``, que devuelve
``cls.objects.filter(...)``. Se conservan verbatim el nombre, la firma
``(operator, value)`` y el ``return NotImplemented`` cuando el operador no es
``'in'``. Se conserva también que la fuente **ignora** ``value``: su dominio
describe el carrito abandonado y no el valor buscado.

**D-5 — ``_filter_can_send_abandoned_cart_mail`` es ``classmethod`` sobre un
``QuerySet`` y devuelve una lista.** No hay recordset en este ORM; los tres
predicados del filtro (correo del comprador, ningún pago fallido, alguna línea
con precio) son de nivel Python y no se pueden empujar a SQL sin cambiar su
significado. Dentro, dos adaptaciones más:

- ``transaction_ids`` con ``state == 'error'`` → ``sale_order.payments`` con
  ``status == 'FAILED'``. ``payment.Payment`` cuelga de ``sale.SaleOrder`` por
  FK directa aquí, divergencia ya declarada en ``addons/payment/models/
  payment.py:57-60``.
- ``partner_id.email`` → el correo del comprador, que aquí puede venir del
  ``login`` del usuario o del ``guest_email`` del checkout anónimo.

**D-6 — el envío es ``MailTemplate.render`` + ``dispatch_email``.** Igual que en
``models/website.py`` (su D-5): ``MailTemplate`` de este árbol declara
``render()`` y deja el despacho a ``email_executor``.

Aristas de porte
=================

Porte BLOQUEADO — 8 de 12 símbolos

- ``action_recovery_email_send`` (``:196-217``) —
  BLOQUEADO por ``mail.compose.message`` — devuelve un
  ``ir.actions.act_window`` que abre el asistente de composición, y ni el
  asistente ni el cliente web que lo abriría existen en este árbol
  (``grep -rn "mail.compose.message" addons/ src/`` → 0 hits). Mismo criterio
  que ``account_check_printing``/``action_checks_to_print`` (su D-3): navegación
  pura sin vista DRF en este pase. Lo que el botón dispara **sí** está portado:
  es ``_cart_recovery_email_send``. Sucesor: tarea **#570**.
- ``_message_mail_after_hook`` (``:736-743``) —
  BLOQUEADO por ``mail.thread._message_mail_after_hook`` — el gancho no existe:
  ``addons/mail/models/mail_thread.py`` declara ``message_post`` y
  ``message_post_with_template``, ningún ``_message_*_after_hook``. Sucesor:
  tarea **#571**.
- ``_message_post_after_hook`` (``:745-749``) —
  BLOQUEADO por ``mail.thread._message_post_after_hook`` — misma medición y
  mismo sucesor que el anterior.
- ``_notify_get_recipients_groups`` (``:751-768``) —
  BLOQUEADO por ``mail.thread._notify_get_recipients_groups`` — además de
  faltar el gancho, su cuerpo reescribe el botón del portal con
  ``self.access_token``, y ``sale.SaleOrder`` no declara ``access_token`` ni
  ``_portal_ensure_token`` (medido: 0 hits en
  ``addons/sale/models/sale_order.py``). Sucesor: tarea **#572**.

Ese último dato afecta también a un símbolo **sí** portado:
``_cart_recovery_email_send`` llama a ``order._portal_ensure_token()`` antes de
enviar, *"para evitar enlaces rotos"*. Aquí esa línea no tiene a qué llamar y se
omite con la razón escrita en el propio método, no en silencio.
"""
import logging
from datetime import timedelta

from django.utils import timezone

import fields
import models
from addons.base.models import TimeStampedModel
from addons.base.models.ir_model import IrModelData
from addons.mail.models.email_executor import dispatch_email
from addons.payment.models.payment import Payment
from addons.website.models.website import Website
from addons.website_sale.models.website import (
    CART_RECOVERY_TEMPLATE_XMLID,
    WebsiteSaleSettings,
    _buyer_email,
)
from exceptions import UserError
from orm.model_classes import extend_model
from tools.float_utils import float_is_zero
from tools.translate import _

logger = logging.getLogger(__name__)

#: Precisión con la que se juzga si una línea es gratuita. La fuente usa
#: ``precision_rounding=line.currency_id.rounding`` (``:813``);
#: ``sale.SaleOrderLine.price_unit`` es un ``Monetary`` de dos decimales y este
#: árbol no cuelga la moneda de la línea, así que se fija la precisión de la
#: columna. Divergencia menor, declarada aquí para que no se lea como descuido.
PRICE_PRECISION_DIGITS = 2


class WebsiteSaleOrderInfo(TimeStampedModel):
    """Lo que ``website_sale`` añade a ``sale.order`` y **sí** tiene columna.

    Uno a uno con el pedido: en la fuente son columnas de ``sale_order``, así
    que no puede haber dos juegos para el mismo pedido. Ver D-1 del docstring
    del módulo para por qué es una tabla aparte.

    Su ausencia significa *"este pedido no nació en la tienda"* — que es
    exactamente lo que ``website_id`` vacío significa en la referencia.
    """

    sale_order = models.OneToOneField(
        'sale.SaleOrder', on_delete=models.CASCADE,
        related_name='website_sale_info',
        help_text='Pedido al que pertenece esta información (Odoo _inherit '
                  'sale.order).',
    )
    website = fields.Many2one(
        Website, on_delete=models.CASCADE, related_name='sale_orders',
        help_text='Sitio por el que se hizo el pedido (Odoo website_id, '
                  'readonly).',
    )
    cart_recovery_email_sent = fields.Boolean(
        default=False,
        verbose_name='Correo de recuperación ya enviado',
        help_text='Odoo cart_recovery_email_sent.',
    )

    class Meta:
        db_table = 'website_sale_order_info'
        ordering = ['sale_order_id']
        verbose_name = 'Datos de tienda del pedido'
        verbose_name_plural = 'Datos de tienda de los pedidos'

    def __str__(self):
        return 'Tienda — pedido %s' % self.sale_order_id


def _info_of(sale_order):
    """La fila lateral del pedido, o ``None`` si no nació en la tienda.

    Símbolo **nuestro**: la fuente lee ``order.website_id`` directamente porque
    allá la columna es del pedido. Existe por D-1, y se centraliza porque el
    acceso inverso de un ``OneToOneField`` ausente levanta en vez de devolver
    ``None``.
    """
    return WebsiteSaleOrderInfo.objects.filter(sale_order=sale_order).first()


def _settings_of(website_id):
    """La política de recuperación de un sitio, o ``None`` si no la tiene."""
    return WebsiteSaleSettings.objects.filter(website_id=website_id).first()


def _abandoned_delay_of(website_id):
    """Las horas de abandono efectivas de un sitio — ≙ el ``or 1.0`` de la fuente.

    La referencia lo escribe inline dos veces (``:84`` y ``:137``) con el mismo
    respaldo de 1 hora cuando el sitio no lo configura. Aquí, además, el sitio
    puede no tener fila de política: sin ella rige el mismo respaldo.
    """
    settings = _settings_of(website_id)
    return settings._get_cart_abandoned_delay() if settings else 1.0


def _compute_abandoned_cart(self):
    """≙ ``_compute_abandoned_cart`` (``odoo19c: :78-89``).

    Una cotización cuenta como carrito abandonado si nació en un sitio, sigue
    en borrador, tiene fecha, esa fecha es anterior al retraso configurado, su
    comprador no es el usuario público del sitio y tiene líneas.

    D-3: devuelve el booleano en vez de asignarlo; lo consume el ``default``
    del ``NonStored`` ``is_abandoned_cart``.
    """
    info = _info_of(self)
    if not (info and info.website_id and self.state == 'draft' and self.date_order):
        return False
    abandoned_datetime = timezone.now() - timedelta(
        hours=_abandoned_delay_of(info.website_id))
    # ``partner_id != public_partner_id`` de la fuente. Allá el público es un
    # ``res.partner``; aquí el comprador del pedido es un ``res.users``, así
    # que la comparación se hace contra ``website.user`` —el mismo registro,
    # un salto más arriba— en vez de contra su partner.
    return bool(
        self.date_order <= abandoned_datetime
        and self.partner_id != info.website.user_id
        and self.order_line.exists()
    )


def _search_abandoned_cart(cls, operator, value):
    """≙ ``_search_abandoned_cart`` (``odoo19c: :128-143``).

    D-4: devuelve un ``QuerySet``, no un ``Domain``. La fuente ignora ``value``
    —su dominio describe el carrito abandonado, no el valor buscado— y aquí
    también; el parámetro se conserva porque conserva la firma.
    """
    if operator != 'in':
        return NotImplemented
    # Se recorren los **sitios**, no las políticas — verbatim de la fuente,
    # que itera ``self.env['website'].search_read(...)``. Un sitio sin fila de
    # política cuenta igual, con el respaldo de 1 hora; recorrer las políticas
    # dejaría a esos sitios fuera del search y **dentro** del compute, que es
    # la desincronización que este par existe para no tener.
    delays = {row.website_id: row._get_cart_abandoned_delay()
              for row in WebsiteSaleSettings.objects.all()}
    condition = models.Q()
    matched_any_website = False
    for website in Website.objects.all():
        matched_any_website = True
        deadline = timezone.now() - timedelta(
            hours=delays.get(website.pk, 1.0))
        condition |= (
            models.Q(website_sale_info__website=website.pk)
            & models.Q(date_order__lte=deadline)
            # ``~Q(partner_id=X)`` descartaría también las filas con
            # ``partner_id`` NULL, que son los carritos anónimos y sí cuentan
            # (su correo lo aporta ``guest_email``). La disyunción explícita lo
            # evita.
            & (models.Q(partner_id__isnull=True)
               | ~models.Q(partner_id=website.user_id))
        )
    if not matched_any_website:
        return cls.objects.none()
    return (cls.objects
            .filter(state='draft')
            .exclude(order_line=None)
            .filter(condition)
            .distinct())


def _get_cart_recovery_template(self):
    """≙ ``_get_cart_recovery_template`` (``odoo19c: :219-228``).

    La plantilla específica del sitio si la hay; si no, la del addon. ``None``
    si tampoco esa está sembrada — la fuente devuelve ahí el recordset vacío
    ``self.env['mail.template']``, que es su forma de decir lo mismo.

    Divergencia: la fuente opera sobre un recordset y sólo usa la plantilla del
    sitio ``if len(websites) == 1``. Aquí ``self`` es siempre un pedido, así que
    la condición es trivialmente cierta y se omite en vez de simularla.
    """
    info = _info_of(self)
    settings = _settings_of(info.website_id) if info and info.website_id else None
    template = settings.cart_recovery_mail_template if settings else None
    return template or IrModelData.ref(CART_RECOVERY_TEMPLATE_XMLID,
                                       raise_if_not_found=False)


def _cart_recovery_email_send(self):
    """≙ ``_cart_recovery_email_send`` (``odoo19c: :722-734``).

    Envía el correo de recuperación de **este** pedido y lo marca como enviado.
    Hermano de ``action_recovery_email_send``, pensado para llamarse desde una
    automatización; a diferencia de aquél usa la plantilla propia del sitio.

    La fuente llama antes a ``order._portal_ensure_token()`` *"para evitar
    enlaces rotos"*. Aquí esa línea se **omite**, y no en silencio:
    ``sale.SaleOrder`` no declara ``access_token`` ni ``_portal_ensure_token``
    (medido: 0 hits). Es la misma pieza que deja fuera a
    ``_notify_get_recipients_groups``; ver las aristas del módulo.

    :return: ``True`` si el correo salió.
    """
    template = self._get_cart_recovery_template()
    if template is None:
        logger.warning(
            'Recuperación de carrito: no hay plantilla para el pedido %s.',
            self.pk)
        return False
    rendered = template.render(self)
    recipient = rendered.get('email_to') or ''
    if not (template.email_to or template.partner_to or template.use_default_to):
        recipient = _buyer_email(self)
    if not recipient:
        logger.warning(
            'Recuperación de carrito: el pedido %s no tiene destinatario.',
            self.pk)
        return False
    dispatch_email(
        rendered['subject'], rendered['body_html'],
        rendered['email_from'] or None, [recipient],
    )
    info = _info_of(self)
    if info is not None:
        info.cart_recovery_email_sent = True
        info.save(update_fields=['cart_recovery_email_sent'])
    return True


def _filter_can_send_abandoned_cart_mail(cls, orders):
    """≙ ``_filter_can_send_abandoned_cart_mail`` (``odoo19c: :775-815``).

    De los carritos abandonados de **un solo sitio**, los que de verdad merecen
    correo. Los cuatro criterios de la fuente, con sus tres comentarios
    conservados porque son la especificación:

    - hay que conocer el correo del comprador;
    - si hubo un error al procesar el pago, el correo no sale;
    - si todas las líneas son gratuitas, el correo no sale;
    - si esa persona ya completó una compra después del abandono, tampoco.

    D-5: ``classmethod`` sobre un ``QuerySet``, devuelve una lista.
    """
    orders = list(orders)
    if not orders:
        return []
    # ≙ ``self.website_id.ensure_one()`` (``:776``): el retraso de abandono es
    # del sitio, así que mezclar sitios daría una fecha de corte falsa.
    infos = {order.pk: _info_of(order) for order in orders}
    website_ids = {info.website_id for info in infos.values() if info}
    if len(website_ids) != 1:
        raise UserError(_(
            'El filtro de recuperación de carrito exige un solo sitio; '
            'se recibieron %(count)s.', count=len(website_ids)))
    website_id = website_ids.pop()
    abandoned_datetime = timezone.now() - timedelta(
        hours=_abandoned_delay_of(website_id))

    buyers = [order.partner_id for order in orders if order.partner_id]
    sales_after_abandoned_date = cls.objects.filter(
        state='sale',
        partner_id__in=buyers,
        created_at__gte=abandoned_datetime,
        website_sale_info__website=website_id,
    )
    latest_create_date_per_buyer = {}
    for sale in orders:
        previous = latest_create_date_per_buyer.get(sale.partner_id)
        latest_create_date_per_buyer[sale.partner_id] = (
            sale.created_at if previous is None
            else max(previous, sale.created_at))
    has_later_sale_order = {}
    for sale in sales_after_abandoned_date:
        if has_later_sale_order.get(sale.partner_id, False):
            continue
        latest = latest_create_date_per_buyer.get(sale.partner_id)
        has_later_sale_order[sale.partner_id] = (
            latest is not None and sale.date_order is not None
            and latest <= sale.date_order)

    return [
        order for order in orders
        if _buyer_email(order)
        and not order.payments.filter(status=Payment.STATUS_FAILED).exists()
        and any(not float_is_zero(float(line.price_unit),
                                  precision_digits=PRICE_PRECISION_DIGITS)
                for line in order.order_line.all())
        and not has_later_sale_order.get(order.partner_id, False)
    ]


def apply_website_sale_order_extensions():
    """Cuelga sobre ``sale.order`` lo que la tienda le añade — ≙ ``_inherit``.

    Se invoca desde ``WebsiteSaleConfig.ready()``: en tiempo de import el
    registro de modelos aún no está poblado.

    El destino se nombra con el par de Django y no con ``'sale.order'`` porque
    ``sale.SaleOrder`` no declara ``_name`` — la misma medición y el mismo
    motivo que ``addons/stock/models/res_users.py`` deja escritos (:ref:
    `h-api-618`). Completar su cabecera toca ``addons/sale``, transversal, y no
    entra en este pase.
    """
    extend_model('sale', 'SaleOrder', campos={
        # ``store=False`` en la fuente (``:46-48``): no genera columna. D-2.
        'is_abandoned_cart': fields.NonStored(
            default=_compute_abandoned_cart,
            help_text='El carrito lleva más del retraso configurado sin '
                      'confirmarse (Odoo is_abandoned_cart, store=False).',
        ),
    }, metodos={
        '_compute_abandoned_cart': _compute_abandoned_cart,
        '_search_abandoned_cart': classmethod(_search_abandoned_cart),
        '_get_cart_recovery_template': _get_cart_recovery_template,
        '_cart_recovery_email_send': _cart_recovery_email_send,
        '_filter_can_send_abandoned_cart_mail': classmethod(
            _filter_can_send_abandoned_cart_mail),
    })
