"""Contador de carritos abandonados del equipo de venta — tarea **#568**.

Adaptación de ``odoo19c: addons/website_sale/models/crm_team.py``
(``odoo-tools@622ddc2a``, LGPL-3). Los cuatro símbolos portados de los cinco,
ejercitados contra PostgreSQL real.

Por qué el caso central es un **par**, y no un caso feliz
==========================================================

``_compute_abandoned_carts`` abre con un guard (``odoo19c: :23``)::

    website_teams = self.filtered(lambda team: team.website_ids)

Ese guard decide la población: un equipo que **no** sea salesteam de ningún
sitio recibe ``0`` aunque tenga carritos abandonados a su nombre
(``:31-33``, ``counts.get(team.id, 0)``).

Este archivo existe porque ese guard estuvo a punto de perderse. El campo del
que cuelga —``website.salesteam_id``— no existía en el árbol, y las dos formas
de portar el cómputo sin él eran silenciosamente falsas: sin guard, un equipo
sin sitio reportaría ``> 0``; con guard vacío, todos reportarían ``0``. Ni una
ni otra rompe ningún test que sólo mire el caso feliz.

De ahí el par ``test_team_that_is_website_salesteam_counts_its_carts`` /
``test_team_with_carts_but_no_website_reports_zero``: los dos comparten
montaje y difieren **sólo** en si el equipo es salesteam de un sitio. Juntos
son la prueba de que el guard sigue vivo; por separado, ninguno lo es.

Los casos cubren, en este orden:

1. **La cabecera del porte** — que los símbolos aterrizaron sobre ``crm.team``
   y que los dos campos **no** crearon columna (son ``store=False`` en la
   fuente). Un porte parcial pasa la suite igual que uno completo si nadie
   cuenta los símbolos.
2. **El par del guard** — descrito arriba.
3. **El dominio del cómputo** — que el correo ya enviado excluye, y que el
   importe suma de verdad sobre varios carritos.
4. **D-3** — un cómputo, dos campos, una consulta.
5. **El campo ``salesteam``** — sus cinco atributos portados, incluido el
   índice parcial y el ``default`` que hoy devuelve ``None`` por diseño.
6. **La arista declarada** — que ``get_abandoned_carts`` NO está portado.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.db.models import Q
from django.utils import timezone

from addons.base.models import ResCompany, ResUsers
from addons.sale.models import SaleOrder
from addons.sales_team.models import CrmTeam
from addons.website.models.website import Website
from addons.website_sale.models import website as website_module
from addons.website_sale.models.website import (
    WEBSITE_SALESTEAM_XMLID,
    WebsiteSaleSettings,
    _default_salesteam_id,
)
from orm.environments import company_scope
from tests.factories.product_factory import make_product
# Los dos ayudantes se **importan**, no se reescriben: ``make_buyer`` existe
# porque ``sale_order_un_draft_por_partner`` es un índice único parcial (un
# solo borrador por cliente), y ``make_cart`` alinea ``created_at`` con
# ``date_order`` para poder fabricar un pedido viejo. Duplicarlos aquí sería
# fabricar una segunda fuente de verdad que nadie sincroniza.
from tests.unit.website_sale.test_abandoned_cart import make_buyer, make_cart

pytestmark = [pytest.mark.django_db]


#: Los símbolos que ``apply_website_sale_crm_team_extensions()`` cuelga sobre
#: ``crm.team``. ``website_ids`` no está aquí: es el ``related_name`` de la FK
#: (D-1), y se comprueba aparte.
PORTED_ON_CRM_TEAM = [
    'abandoned_carts_count',
    'abandoned_carts_amount',
    '_compute_abandoned_carts',
]


# ── fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def public_user(db):
    """El usuario público del sitio — ≙ ``website.user_id``."""
    return ResUsers.objects.create_user(login='public-team@kaupamex.test')


@pytest.fixture
def company(db):
    return ResCompany.objects.create(name='Kaupamex Equipos QA')


@pytest.fixture
def website(company, public_user):
    with company_scope(company.pk):
        yield Website.objects.create(name='Tienda equipos', sequence=1,
                                     user=public_user)


@pytest.fixture
def product(db):
    return make_product(name='Otí', price=Decimal('250.00'))


@pytest.fixture
def team(company):
    """El equipo que **sí** es salesteam de un sitio."""
    return CrmTeam.objects.create(name='Ventas web', company=company)


@pytest.fixture
def other_team(company):
    """El equipo de control: existe, tiene carritos, y no es salesteam."""
    return CrmTeam.objects.create(name='Ventas mostrador', company=company)


@pytest.fixture
def settings_row(website, team):
    """La política del sitio, con ``team`` como su equipo de venta.

    Es la fila que crea el vínculo equipo ↔ sitio: ``team.websites`` la
    encuentra por el ``related_name`` de ``salesteam``.
    """
    return WebsiteSaleSettings.objects.create(
        website=website, cart_abandoned_delay=10.0,
        send_abandoned_cart_email=True, salesteam=team)


def assign(order, team):
    """Atribuye un pedido a un equipo — ≙ ``sale.order.team_id``."""
    SaleOrder.objects.filter(pk=order.pk).update(team=team)
    order.refresh_from_db()
    return order


# ── 1. la cabecera del porte ────────────────────────────────────────────────

@pytest.mark.parametrize('symbol', PORTED_ON_CRM_TEAM)
def test_ported_symbol_is_installed_on_crm_team(symbol):
    """Los tres símbolos que se cuelgan de ``crm.team`` están ahí.

    El conteo es el gate: sin él, quitar uno del ``extend_model`` no rompe
    ningún test que no lo use.
    """
    assert hasattr(CrmTeam, symbol)


@pytest.mark.parametrize('field', ['abandoned_carts_count',
                                   'abandoned_carts_amount'])
def test_abandoned_carts_fields_have_no_column(field):
    """``compute`` sin ``store`` en la fuente (``odoo19c: :12-17``).

    Si generaran columna, la adaptación habría cambiado la naturaleza de los
    campos sin decirlo — y habría además una migración que este pase no
    escribe.
    """
    assert field not in {f.name for f in CrmTeam._meta.get_fields()}


def test_website_ids_is_the_related_name(team, settings_row):
    """≙ ``website_ids`` (``:9-11``) — D-1: no es un campo, es el inverso.

    Y alcanza la fila de política, no el sitio (D-7 de ``models/website.py``);
    el sitio está un salto más allá. La cardinalidad es la misma porque la
    relación es 1-1, que es lo único que el guard pregunta.
    """
    assert list(team.websites.all()) == [settings_row]
    # El salto que D-7 declara: de la política al sitio.
    assert [row.website for row in team.websites.all()] == [settings_row.website]
    # Y no hay campo ``website_ids`` inventado sobre el equipo.
    assert 'website_ids' not in {f.name for f in CrmTeam._meta.get_fields()}


# ── 2. el par del guard ─────────────────────────────────────────────────────

def test_team_that_is_website_salesteam_counts_its_carts(
        settings_row, website, team, product):
    """Un equipo que **es** salesteam de un sitio cuenta sus carritos.

    Mitad feliz del par. Por sí sola no prueba nada sobre el guard: un cómputo
    que ignorara el guard daría exactamente este mismo resultado.
    """
    cart = make_cart(website, make_buyer('team-a'), product, hours_ago=24.0)
    assign(cart, team)

    assert cart.is_abandoned_cart is True
    assert team.abandoned_carts_count == 1
    assert team.abandoned_carts_amount == Decimal('250.00')


def test_team_with_carts_but_no_website_reports_zero(
        settings_row, website, other_team, product):
    """Un equipo con carritos abandonados que **no** es salesteam da ``0``.

    Ésta es la mitad que prueba el guard, y la que fallaría si alguien lo
    quitara «porque el dominio ya filtra». El montaje es idéntico al del caso
    anterior salvo en una cosa: ``other_team`` no aparece en ninguna
    ``WebsiteSaleSettings.salesteam``.

    El carrito **sí** es abandonado —se afirma explícitamente— para que un
    fallo aquí no se pueda confundir con un montaje que no produjo carrito.
    """
    cart = make_cart(website, make_buyer('team-b'), product, hours_ago=24.0)
    assign(cart, other_team)

    assert cart.is_abandoned_cart is True
    assert other_team.websites.exists() is False
    assert other_team.abandoned_carts_count == 0
    assert other_team.abandoned_carts_amount == 0


# ── 3. el dominio del cómputo ───────────────────────────────────────────────

def test_cart_already_mailed_is_not_counted(settings_row, website, team,
                                            product):
    """≙ ``('cart_recovery_email_sent', '=', False)`` (``odoo19c: :26``).

    Un carrito ya recuperado no vuelve a contarse: el contador mide lo que
    queda por hacer, no el histórico.
    """
    cart = make_cart(website, make_buyer('team-c'), product, hours_ago=24.0)
    assign(cart, team)
    info = cart.website_sale_info
    info.cart_recovery_email_sent = True
    info.save(update_fields=['cart_recovery_email_sent'])

    assert team.abandoned_carts_count == 0
    assert team.abandoned_carts_amount == 0


def test_amount_sums_across_carts(settings_row, website, team, product):
    """≙ ``amount_total:sum`` (``:28``) — y D-4: sin truncar a entero.

    Dos carritos exigen dos compradores: ``sale_order_un_draft_por_partner``
    admite un solo borrador por cliente (ver ``make_buyer``).
    """
    for tag in ('team-d', 'team-e'):
        assign(make_cart(website, make_buyer(tag), product, hours_ago=24.0),
               team)

    assert team.abandoned_carts_count == 2
    assert team.abandoned_carts_amount == Decimal('500.00')


def test_young_cart_is_not_counted(settings_row, website, team, product):
    """El retraso del sitio son 10 h; a las 2 h todavía está comprando.

    El contador hereda el predicado de ``_search_abandoned_cart``, así que la
    fecha de corte es la del **sitio**, no una constante de este archivo.
    """
    assign(make_cart(website, make_buyer('team-f'), product, hours_ago=2.0),
           team)

    assert team.abandoned_carts_count == 0


# ── 4. D-3: un cómputo, dos campos, una consulta ────────────────────────────

def test_reading_one_field_fills_the_other(settings_row, website, team,
                                           product,
                                           django_assert_num_queries):
    """≙ ``:32-33``: la fuente asigna los dos campos en el mismo ``compute``.

    Aquí cada ``NonStored`` tiene su propio ``default``, así que la garantía
    hay que comprobarla: leer el primero deja el segundo puesto en la
    instancia, y leerlo no vuelve a consultar.
    """
    assign(make_cart(website, make_buyer('team-g'), product, hours_ago=24.0),
           team)

    team.abandoned_carts_count            # dispara el cómputo
    assert 'abandoned_carts_amount' in team.__dict__

    with django_assert_num_queries(0):
        assert team.abandoned_carts_amount == Decimal('250.00')


# ── 5. el campo ``salesteam`` y sus atributos ───────────────────────────────

def test_salesteam_field_attributes():
    """Los atributos de ``salesteam_id`` (``odoo19c: website.py:63-69``).

    ``porte-completo-no-parcial.md``: portar el nombre y perder los atributos
    es un porte parcial que ningún gate de campos mira.
    """
    field = WebsiteSaleSettings._meta.get_field('salesteam')

    assert field.related_model is CrmTeam            # comodel_name='crm.team'
    assert field.remote_field.on_delete.__name__ == 'SET_NULL'   # ondelete
    assert field.remote_field.related_name == 'websites'         # website_ids
    assert field.null is True
    assert field.default is _default_salesteam_id


def test_salesteam_index_is_partial():
    """≙ ``index='btree_not_null'`` (``:66``).

    Un ``db_index=True`` daría un btree **entero** — otro índice, no éste. La
    condición es lo que distingue los dos, y es lo que se comprueba.
    """
    index = next(i for i in WebsiteSaleSettings._meta.indexes
                 if i.name == 'website_sale_salesteam_nn')

    assert index.fields == ['salesteam']
    assert index.condition == Q(salesteam__isnull=False)


def test_salesteam_default_is_none_while_xmlid_is_unseeded():
    """≙ ``_default_salesteam_id`` (``:35-39``) con el equipo ausente.

    El identificador externo ``sales_team.salesteam_website_sales`` no está
    sembrado en este árbol (``addons/sales_team/`` no tiene ``data/``), así
    que el default devuelve ``None`` — **el mismo desenlace** que la fuente da
    cuando el equipo no existe o está archivado.

    El día que se siembre, este test falla y señala exactamente dónde mirar:
    es el aviso de que la arista de la tarea #568 se cerró.
    """
    assert _default_salesteam_id() is None
    assert WEBSITE_SALESTEAM_XMLID == 'sales_team.salesteam_website_sales'


def test_archived_team_is_not_defaulted(company, monkeypatch):
    """≙ ``if team and team.active`` (``:37``) — un equipo archivado no se asigna.

    La condición se ejercita inyectando el equipo que el identificador externo
    devolvería, porque la siembra no existe todavía. Sin este caso, el
    ``and team.active`` podría perderse sin que nada lo notara.
    """
    archived = CrmTeam.objects.create(name='Web (archivado)', company=company,
                                      active=False)
    monkeypatch.setattr(website_module.IrModelData, 'ref',
                        classmethod(lambda cls, xmlid, **kw: archived))
    assert website_module._default_salesteam_id() is None

    archived.active = True
    archived.save(update_fields=['active'])
    assert website_module._default_salesteam_id() == archived.pk


# ── 6. la arista declarada ──────────────────────────────────────────────────

def test_get_abandoned_carts_is_not_ported():
    """``get_abandoned_carts`` (``odoo19c: :35-54``) NO está portado.

    Devuelve un ``ir.actions.act_window`` y resuelve un identificador de vista
    XML; este árbol no tiene ninguna vista XML (medido: 0 archivos) y sirve su
    superficie por DRF. Sucesor: tarea **#570**.

    El test fija la arista: si alguien lo porta sin decidir antes la forma de
    las acciones de navegación, esto falla y le señala la tarea.
    """
    assert not hasattr(CrmTeam, 'get_abandoned_carts')
