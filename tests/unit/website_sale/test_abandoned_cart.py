"""Recuperación de carrito abandonado — tarea **#258**.

Adaptación de ``odoo19c: addons/website_sale/models/{sale_order,website}.py``
(``odoo-tools@622ddc2a``, LGPL-3). Los ocho símbolos portados de la rebanada,
ejercitados contra PostgreSQL real.

Los casos cubren, en este orden:

1. **La cabecera de la rebanada** — que los ocho símbolos aterrizaron sobre
   ``sale.order`` y que ``is_abandoned_cart`` **no** creó columna. Un porte
   parcial pasa la suite igual que uno completo si nadie cuenta los símbolos;
   el conteo contra la fuente es lo único que los distingue
   (``porte-completo-no-parcial.md``).
2. **Los cuatro predicados de ``_compute_abandoned_cart``** — sitio, borrador,
   fecha vencida y líneas. Cada uno por separado, porque un ``and`` de cuatro
   términos se satisface por accidente si sólo se prueba el caso feliz.
3. **``_search_abandoned_cart``** — que el conjunto que devuelve coincide con
   lo que el ``compute`` dice de cada pedido. Compute y search son dos
   implementaciones del mismo predicado en la fuente, y ésa es exactamente la
   clase de par que se desincroniza en silencio.
4. **``_filter_can_send_abandoned_cart_mail``** — los cuatro criterios, más el
   ``ensure_one`` del sitio.
5. **La política del sitio** — el sellado de la hora de activación (el
   ``compute`` almacenado que vive en ``save()``) y el retraso por defecto.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from addons.base.models import ResCompany, ResUsers
from addons.payment.models import Payment
from addons.sale.models import SaleOrder, SaleOrderLine
from addons.website.models.website import Website
from addons.website_sale.models.sale_order import WebsiteSaleOrderInfo
from addons.website_sale.models.website import WebsiteSaleSettings
from exceptions import UserError
from orm.environments import company_scope
from tests.factories.product_factory import make_product

pytestmark = [pytest.mark.django_db]


#: Los ocho símbolos de la rebanada que se cuelgan de ``sale.order``.
#: ``website_id`` y ``cart_recovery_email_sent`` no están aquí: viven en
#: ``WebsiteSaleOrderInfo`` por la D-1 de ``models/sale_order.py``.
PORTED_ON_SALE_ORDER = [
    'is_abandoned_cart',
    '_compute_abandoned_cart',
    '_search_abandoned_cart',
    '_get_cart_recovery_template',
    '_cart_recovery_email_send',
    '_filter_can_send_abandoned_cart_mail',
]


# ── fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def public_user(db):
    """El usuario público del sitio — ≙ ``website.user_id``."""
    return ResUsers.objects.create_user(login='public-ws@kaupamex.test')


@pytest.fixture
def website(db, public_user):
    company = ResCompany.objects.create(name='Kaupamex Carrito QA')
    with company_scope(company.pk):
        yield Website.objects.create(name='Tienda', sequence=1,
                                     user=public_user)


@pytest.fixture
def settings_row(website):
    """La política del sitio con el envío activo y 10 h de retraso."""
    return WebsiteSaleSettings.objects.create(
        website=website, cart_abandoned_delay=10.0,
        send_abandoned_cart_email=True)


@pytest.fixture
def buyer(db):
    return ResUsers.objects.create_user(login='comprador@kaupamex.test')


def make_buyer(tag):
    """Un comprador propio por carrito en borrador.

    ``sale_order_un_draft_por_partner`` (``addons/sale/models/sale_order.py``)
    es un índice único parcial: **un solo** pedido en borrador por cliente. Es
    una invariante deliberada de este árbol (H-API-309) y la fuente no la
    tiene, así que un caso que necesite dos carritos abandonados a la vez
    necesita dos clientes — no es una limitación del montaje, es lo que la
    base admite.
    """
    return ResUsers.objects.create_user(login=f'comprador-{tag}@kaupamex.test')


@pytest.fixture
def product(db):
    return make_product(name='Adimú', price=Decimal('250.00'))


def make_cart(website, buyer, product, *, hours_ago=24.0,
              state=SaleOrder.STATE_DRAFT, with_line=True, price=None,
              attach_info=True):
    """Un carrito con la antigüedad y los rasgos que el caso necesite.

    ``created_at`` se alinea con ``date_order``: es ``auto_now_add``, así que
    hay que reescribirlo por ``update()`` para fabricar un pedido viejo. Sin
    esa alineación todo pedido nacería «ahora» y
    ``_filter_can_send_abandoned_cart_mail`` —que compara ``create_date``
    contra ``date_order``— mediría un mundo que no existe.
    """
    born = timezone.now() - timedelta(hours=hours_ago)
    order = SaleOrder.objects.create(state=state, partner=buyer,
                                     date_order=born)
    SaleOrder.objects.filter(pk=order.pk).update(created_at=born)
    order.refresh_from_db()
    if with_line:
        SaleOrderLine.objects.create(
            order=order, product=product, product_uom_qty=1,
            price_unit=Decimal('250.00') if price is None else price)
    if attach_info:
        WebsiteSaleOrderInfo.objects.create(sale_order=order, website_id=website)
    return order


# ── 1. la cabecera de la rebanada ───────────────────────────────────────────

@pytest.mark.parametrize('symbol', PORTED_ON_SALE_ORDER)
def test_ported_symbol_is_installed_on_sale_order(symbol):
    """Los seis símbolos que se cuelgan de ``sale.order`` están ahí.

    El conteo es el gate: sin él, quitar uno del ``extend_model`` no rompe
    ningún test que no lo use.
    """
    assert hasattr(SaleOrder, symbol)


def test_is_abandoned_cart_has_no_column():
    """``store=False`` en la fuente (``odoo19c: sale_order.py:46-48``): el
    campo existe para leerse, no para consultarse. Si generara columna, la
    adaptación habría cambiado la naturaleza del campo sin decirlo."""
    assert 'is_abandoned_cart' not in {f.name
                                       for f in SaleOrder._meta.get_fields()}


def test_stored_half_lives_in_the_side_table():
    """``website_id`` y ``cart_recovery_email_sent`` — D-1."""
    names = {f.name for f in WebsiteSaleOrderInfo._meta.get_fields()}
    assert {'website_id', 'cart_recovery_email_sent', 'sale_order'} <= names


# ── 2. los cuatro predicados del compute ────────────────────────────────────

def test_cart_older_than_delay_is_abandoned(settings_row, website, buyer,
                                            product):
    cart = make_cart(website, buyer, product, hours_ago=24.0)
    assert cart.is_abandoned_cart is True


def test_cart_younger_than_delay_is_not_abandoned(settings_row, website, buyer,
                                                  product):
    """El retraso configurado son 10 h; a las 2 h todavía está comprando."""
    cart = make_cart(website, buyer, product, hours_ago=2.0)
    assert cart.is_abandoned_cart is False


def test_order_without_website_is_not_abandoned(settings_row, website, buyer,
                                                product):
    """≙ ``if order.website_id and …``: un pedido que no nació en la tienda
    no es un carrito abandonado, por viejo que sea."""
    cart = make_cart(website, buyer, product, hours_ago=48.0,
                     attach_info=False)
    assert cart.is_abandoned_cart is False


def test_confirmed_order_is_not_abandoned(settings_row, website, buyer,
                                          product):
    """≙ ``order.state == 'draft'``."""
    cart = make_cart(website, buyer, product, hours_ago=48.0,
                     state=SaleOrder.STATE_SALE)
    assert cart.is_abandoned_cart is False


def test_empty_cart_is_not_abandoned(settings_row, website, buyer, product):
    """≙ ``and order.order_line``: no hay nada que recuperar."""
    cart = make_cart(website, buyer, product, hours_ago=48.0, with_line=False)
    assert cart.is_abandoned_cart is False


def test_public_user_cart_is_not_abandoned(settings_row, website, public_user,
                                           product):
    """≙ ``order.partner_id != public_partner_id``.

    Divergencia declarada: la comparación es contra ``website.user`` porque el
    comprador de un pedido es aquí un ``res.users``, no un ``res.partner``.
    """
    cart = make_cart(website, public_user, product, hours_ago=48.0)
    assert cart.is_abandoned_cart is False


def test_delay_falls_back_to_one_hour_without_settings(website, buyer,
                                                       product):
    """≙ el ``or 1.0`` de la fuente (``:84``), extendido al sitio sin fila de
    política: sin configuración rige una hora, no cero ni infinito."""
    cart = make_cart(website, buyer, product, hours_ago=2.0)
    assert cart.is_abandoned_cart is True


# ── 3. el search dice lo mismo que el compute ───────────────────────────────

def test_search_rejects_operators_other_than_in(settings_row):
    """≙ ``if operator != 'in': return NotImplemented`` (``:129-130``)."""
    assert SaleOrder._search_abandoned_cart('=', [True]) is NotImplemented


def test_search_agrees_with_compute(settings_row, website, buyer, product):
    """Compute y search son dos implementaciones del mismo predicado.

    Se construyen los cinco casos del bloque anterior a la vez y se exige que
    el conjunto del search coincida **exactamente** con los que el compute
    marca. Es el par que se desincroniza en silencio si sólo se prueba uno.
    """
    # Cuatro de los cinco quedan en borrador a la vez, así que cada uno lleva
    # su propio cliente (ver ``make_buyer``). El confirmado puede compartir
    # comprador: el índice único sólo cubre ``state='draft'``.
    abandoned = make_cart(website, buyer, product, hours_ago=24.0)
    recent = make_cart(website, make_buyer('reciente'), product, hours_ago=1.0)
    confirmed = make_cart(website, buyer, product, hours_ago=48.0,
                          state=SaleOrder.STATE_SALE)
    empty = make_cart(website, make_buyer('vacio'), product, hours_ago=48.0,
                      with_line=False)
    off_site = make_cart(website, make_buyer('fuera'), product, hours_ago=48.0,
                         attach_info=False)

    found = set(SaleOrder._search_abandoned_cart('in', [True])
                .values_list('pk', flat=True))
    expected = {order.pk
                for order in (abandoned, recent, confirmed, empty, off_site)
                if order.is_abandoned_cart}

    assert found == expected
    assert found == {abandoned.pk}


def test_search_covers_a_website_without_policy_row(website, buyer, product):
    """El search recorre **sitios**, no políticas — verbatim de la fuente, que
    itera ``self.env['website'].search_read(...)``.

    Un sitio sin fila de política sigue dentro, con el respaldo de 1 hora. Si
    el recorrido fuera sobre políticas, este carrito quedaría fuera del search
    y dentro del compute: la desincronización silenciosa que el par
    compute/search existe para no tener.
    """
    cart = make_cart(website, buyer, product, hours_ago=2.0)
    assert cart.is_abandoned_cart is True
    found = set(SaleOrder._search_abandoned_cart('in', [True])
                .values_list('pk', flat=True))
    assert found == {cart.pk}


# ── 4. el filtro de envío ───────────────────────────────────────────────────

def test_filter_keeps_the_recoverable_cart(settings_row, website, buyer,
                                           product):
    cart = make_cart(website, buyer, product, hours_ago=24.0)
    kept = SaleOrder._filter_can_send_abandoned_cart_mail(
        SaleOrder.objects.filter(pk=cart.pk))
    assert [order.pk for order in kept] == [cart.pk]


def test_filter_drops_cart_without_buyer_email(settings_row, website, product):
    """≙ ``abandoned_sale_order.partner_id.email`` (``:811``): sin dirección
    no hay a quién escribirle. Aquí el carrito anónimo sin ``guest_email`` es
    el caso equivalente."""
    cart = SaleOrder.objects.create(
        state=SaleOrder.STATE_DRAFT, partner=None,
        date_order=timezone.now() - timedelta(hours=24))
    SaleOrderLine.objects.create(order=cart, product=product,
                                 product_uom_qty=1,
                                 price_unit=Decimal('250.00'))
    WebsiteSaleOrderInfo.objects.create(sale_order=cart, website_id=website)
    kept = SaleOrder._filter_can_send_abandoned_cart_mail(
        SaleOrder.objects.filter(pk=cart.pk))
    assert kept == []


def test_filter_drops_cart_with_failed_payment(settings_row, website, buyer,
                                               product):
    """≙ ``not any(transaction.state == 'error' …)`` (``:812``).

    Divergencia declarada: el eje de pago aquí es ``payment.Payment`` colgado
    por FK del pedido, y su estado equivalente a ``error`` es ``FAILED``.
    """
    cart = make_cart(website, buyer, product, hours_ago=24.0)
    Payment.objects.create(sale_order=cart, gateway=Payment.GATEWAYS[0][0],
                           status=Payment.STATUS_FAILED,
                           amount=Decimal('250.00'))
    kept = SaleOrder._filter_can_send_abandoned_cart_mail(
        SaleOrder.objects.filter(pk=cart.pk))
    assert kept == []


def test_filter_drops_cart_whose_lines_are_all_free(settings_row, website,
                                                    buyer, product):
    """≙ ``any(not float_is_zero(line.price_unit …))`` (``:813``)."""
    cart = make_cart(website, buyer, product, hours_ago=24.0,
                     price=Decimal('0.00'))
    kept = SaleOrder._filter_can_send_abandoned_cart_mail(
        SaleOrder.objects.filter(pk=cart.pk))
    assert kept == []


def test_filter_drops_cart_when_the_buyer_already_bought(settings_row, website,
                                                         buyer, product):
    """≙ ``not has_later_sale_order.get(partner_id)`` (``:814``): quien ya
    completó una compra después del abandono no necesita que le insistan."""
    cart = make_cart(website, buyer, product, hours_ago=5.0)
    later = make_cart(website, buyer, product, hours_ago=1.0,
                      state=SaleOrder.STATE_SALE)
    assert later.state == SaleOrder.STATE_SALE
    kept = SaleOrder._filter_can_send_abandoned_cart_mail(
        SaleOrder.objects.filter(pk=cart.pk))
    assert kept == []


def test_filter_demands_a_single_website(settings_row, website, buyer,
                                         product, public_user):
    """≙ ``self.website_id.ensure_one()`` (``:776``): el retraso de abandono es
    del sitio, así que mezclar sitios daría una fecha de corte falsa."""
    other_company = ResCompany.objects.create(name='Kaupamex Otro Sitio QA')
    with company_scope(other_company.pk):
        other = Website.objects.create(name='Otra tienda', sequence=2,
                                       user=public_user)
    # Dos carritos vivos a la vez → dos clientes (ver ``make_buyer``).
    first = make_cart(website, buyer, product, hours_ago=24.0)
    second = make_cart(other, make_buyer('otro-sitio'), product, hours_ago=24.0)
    with pytest.raises(UserError):
        SaleOrder._filter_can_send_abandoned_cart_mail(
            SaleOrder.objects.filter(pk__in=[first.pk, second.pk]))


def test_filter_on_empty_input_returns_empty(settings_row):
    assert SaleOrder._filter_can_send_abandoned_cart_mail(
        SaleOrder.objects.none()) == []


# ── 5. la política del sitio ────────────────────────────────────────────────

def test_activation_time_is_sealed_when_the_flag_turns_on(website):
    """≙ ``_compute_send_abandoned_cart_email_activation_time`` (``:291-295``),
    que aquí vive en ``save()`` porque este ORM no tiene ``@api.depends``."""
    row = WebsiteSaleSettings.objects.create(website=website,
                                             send_abandoned_cart_email=False)
    assert row.send_abandoned_cart_email_activation_time is None

    row.send_abandoned_cart_email = True
    row.save()
    assert row.send_abandoned_cart_email_activation_time is not None


def test_activation_time_is_cleared_when_the_flag_turns_off(settings_row):
    """La otra mitad del ``depends``: sin envío activo no hay hora sellada, y
    los carritos anteriores a la próxima activación no se recuperan."""
    assert settings_row.send_abandoned_cart_email_activation_time is not None
    settings_row.send_abandoned_cart_email = False
    settings_row.save()
    assert settings_row.send_abandoned_cart_email_activation_time is None


def test_default_delay_matches_the_reference(website):
    """``default=10.0`` (``odoo19c: website.py:107``) — verbatim."""
    row = WebsiteSaleSettings.objects.create(website=website)
    assert row.cart_abandoned_delay == 10.0
    assert row._get_cart_abandoned_delay() == 10.0


def test_zero_delay_falls_back_to_one_hour(website):
    """≙ ``website.cart_abandoned_delay or 1.0``: un cero configurado no
    convierte todo carrito en abandonado al instante."""
    row = WebsiteSaleSettings.objects.create(website=website,
                                             cart_abandoned_delay=0.0)
    assert row._get_cart_abandoned_delay() == 1.0


# ── 6. la plantilla de recuperación ─────────────────────────────────────────

def test_template_is_none_when_nothing_is_seeded(settings_row, website, buyer,
                                                 product):
    """≙ el recordset vacío ``self.env['mail.template']`` de la fuente
    (``:228``): sin plantilla del sitio ni del addon no hay con qué escribir.

    ``_cart_recovery_email_send`` lo respeta y devuelve ``False`` en vez de
    marcar el carrito como recuperado, que es el defecto que dejaría un
    carrito sin correo y sin posibilidad de reintento.
    """
    cart = make_cart(website, buyer, product, hours_ago=24.0)
    assert cart._get_cart_recovery_template() is None
    assert cart._cart_recovery_email_send() is False
    info = WebsiteSaleOrderInfo.objects.get(sale_order=cart)
    assert info.cart_recovery_email_sent is False
